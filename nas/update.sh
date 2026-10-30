#!/bin/bash
# TotalMaint - aggiornamento sul NAS (Synology DS723+)
#
# Uso (via SSH, dalla cartella del progetto):
#     sudo bash nas/update.sh
#
# Cosa fa:
#   1. backup del database (cartella backup/, tiene gli ultimi 30)
#   2. scarica l'ultima versione da GitHub (git pull)
#   3. ricostruisce e riavvia i container (i dati restano)
#   4. controlla che l'app risponda
set -euo pipefail

cd "$(dirname "$0")/.."
DIR="$(pwd)"

if [ "$(id -u)" -ne 0 ]; then
    echo "Avvia con sudo:  sudo bash nas/update.sh"
    exit 1
fi

# docker compose (nuovo) o docker-compose (vecchio)
if docker compose version >/dev/null 2>&1; then
    DC="docker compose"
else
    DC="docker-compose"
fi

# Usa lo stesso nome di progetto che ha dato Container Manager,
# altrimenti verrebbe creato un secondo set di container.
PROJECT="$(docker ps -a --filter "label=com.docker.compose.project.working_dir=$DIR" \
           --format '{{.Label "com.docker.compose.project"}}' | head -n1)"
PROJECT="${PROJECT:-$(basename "$DIR")}"
DC="$DC -p $PROJECT"
echo "== Progetto: $PROJECT  ($DIR)"

# 1. Backup
mkdir -p backup
STAMP="$(date +%Y-%m-%d_%H%M)"
FILE="backup/db-$STAMP.sql.gz"
echo "== Backup del database -> $FILE"
if $DC exec -T db pg_dump -U totalmaint totalmaint | gzip > "$FILE"; then
    echo "   ok ($(du -h "$FILE" | cut -f1))"
else
    echo "!! Backup fallito: aggiornamento annullato, niente e' stato toccato."
    rm -f "$FILE"
    exit 1
fi
ls -1t backup/db-*.sql.gz | tail -n +31 | xargs -r rm -f

# 2. Codice nuovo
OLD="$(git rev-parse --short HEAD)"
echo "== Scarico da GitHub"
git pull --ff-only
NEW="$(git rev-parse --short HEAD)"
if [ "$OLD" = "$NEW" ]; then
    echo "   Nessuna novita' (versione $NEW). Ricostruisco comunque."
else
    echo "   Modifiche $OLD -> $NEW:"
    git log --oneline "$OLD..$NEW" | sed 's/^/     /'
fi

# 3. Ricostruisci e riavvia
echo "== Ricostruisco e riavvio i container"
$DC up -d --build
docker image prune -f >/dev/null || true

# 4. Controllo
echo "== Controllo che l'app risponda"
for i in $(seq 1 30); do
    if $DC exec -T app python -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/health')" >/dev/null 2>&1; then
        echo ""
        echo "OK - TotalMaint aggiornato alla versione $NEW"
        exit 0
    fi
    sleep 2
done
echo ""
echo "!! L'app non risponde dopo 60 secondi. Guarda i log con:"
echo "     sudo $DC logs --tail 50 app"
echo "   Per tornare alla versione precedente:"
echo "     sudo git reset --hard $OLD && sudo $DC up -d --build"
exit 1

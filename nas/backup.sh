#!/bin/bash
# TotalMaint - backup notturno del database (tiene gli ultimi 30).
# DSM > Pannello di controllo > Utilita' di pianificazione > Crea > Attivita' pianificata > Script definito dall'utente
#   Utente: root   Pianificazione: ogni giorno alle 03:00
#   Comando: bash /volume1/docker/totalmaint/nas/backup.sh
set -euo pipefail
cd "$(dirname "$0")/.."
DIR="$(pwd)"
if docker compose version >/dev/null 2>&1; then DC="docker compose"; else DC="docker-compose"; fi
PROJECT="$(docker ps -a --filter "label=com.docker.compose.project.working_dir=$DIR" \
           --format '{{.Label "com.docker.compose.project"}}' | head -n1)"
PROJECT="${PROJECT:-$(basename "$DIR")}"
mkdir -p backup
FILE="backup/db-$(date +%Y-%m-%d_%H%M).sql.gz"
$DC -p "$PROJECT" exec -T db pg_dump -U totalmaint totalmaint | gzip > "$FILE"
ls -1t backup/db-*.sql.gz | tail -n +31 | xargs -r rm -f
echo "Backup: $FILE"

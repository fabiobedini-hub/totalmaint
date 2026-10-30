# TotalMaint – come mantenere e aggiornare il codice

Il percorso di ogni modifica:

```
PC (OneDrive\TotalMant)  ──pubblica.bat──▶  GitHub (privato)  ──nas/update.sh──▶  NAS DS723+
   modifichi e provi                        copia centrale e storico           l'app usata davvero
```

* **Il codice** vive su GitHub, con lo storico di ogni modifica.
* **I dati** (database, allegati, `.env` con le password) restano solo sul NAS e **non** vanno mai su GitHub.
* Sul NAS non si modifica niente a mano: si scarica sempre da GitHub.

---

## A. Preparazione una tantum sul PC (circa 15 minuti)

1. **Installa Git per Windows** da <https://git-scm.com/download/win> (lascia tutte le opzioni predefinite).
2. **Crea un account GitHub** su <https://github.com/signup> (gratuito).
3. **Crea un repository privato:** su GitHub premi **+** (in alto a destra) e scegli **New repository**.
   * Nome: `totalmaint`
   * Seleziona **Private**
   * **Non** spuntare "Add a README" (il repository deve essere vuoto)
   * Premi **Create repository** e copia l'indirizzo `https://github.com/TUONOME/totalmaint.git`
4. Nella cartella TotalMant fai **doppio clic su `prima_configurazione_git.bat`**:
   * ti chiede nome ed e-mail (solo la prima volta);
   * mostra l'elenco dei file da caricare: controlla che **non** ci siano `.env`, `data\` o file `.db`, poi rispondi `s`;
   * incolla l'indirizzo del punto 3;
   * si apre il browser per accedere a GitHub: autorizza.

Su GitHub dovresti ora vedere i tuoi file.

> Le cartelle `_backup_2026-10-28` e `_archivio_flask` restano sul PC ma non vanno su GitHub: d'ora in poi è Git a fare da storico. Quando ti fidi, puoi cancellarle.

---

## B. Preparazione una tantum sul NAS (circa 20 minuti)

**1. Installa Git sul NAS:** apri **Centro pacchetti**, cerca **Git Server** e installalo (serve solo per avere il comando `git`).

**2. Attiva SSH:** vai in **Pannello di controllo → Terminale e SNMP → Attiva servizio SSH**, poi **Applica**.

**3. Collegati dal PC:** apri **PowerShell** e scrivi (con il tuo utente DSM e l'IP del NAS):
```
ssh fabio@192.168.1.XX
```
Poi diventa amministratore (ti chiede la password DSM):
```
sudo -i
```

**4. Crea una chiave per GitHub, valida solo in lettura:**
```
ssh-keygen -t ed25519 -N "" -f /root/.ssh/id_ed25519 -C "nas-totalmaint"
cat /root/.ssh/id_ed25519.pub
```
Copia la riga che compare (inizia con `ssh-ed25519`). Su GitHub apri il repository e vai in **Settings → Deploy keys → Add deploy key**. Dagli un titolo (`NAS`), incolla la riga, lascia **senza** spunta "Allow write access" e premi **Add key**.

Poi verifica (alla domanda rispondi `yes`):
```
ssh -T git@github.com
```
Deve rispondere *"Hi TUONOME/totalmaint! You've successfully authenticated"*.

**5. Fai un backup di sicurezza del database attuale:**
```
cd /volume1/docker/totalmaint
docker ps --format '{{.Names}}'
```
Cerca il nome del database (per esempio `totalmaint-db-1`) e usalo qui sotto:
```
mkdir -p backup
docker exec totalmaint-db-1 pg_dump -U totalmaint totalmaint | gzip > backup/db-prima-di-git.sql.gz
```
(Se la cartella sul NAS ha un altro percorso, usa quello al posto di `/volume1/docker/totalmaint` in tutta la guida.)

**6. Collega la cartella esistente a GitHub.** `.env`, `data/` e `backup/` non vengono toccati:
```
git config --global --add safe.directory /volume1/docker/totalmaint
git init -b main
git remote add origin git@github.com:TUONOME/totalmaint.git
git fetch origin
git reset --hard origin/main
git branch -u origin/main
```

**7. Prova l'aggiornamento:**
```
bash nas/update.sh
```
Deve terminare con **"OK - TotalMaint aggiornato…"**.

**8. Imposta il backup automatico notturno:** vai in **Pannello di controllo → Utilità di pianificazione → Crea → Attività pianificata → Script definito dall'utente**.
* Utente: `root`
* Pianificazione: ogni giorno alle 03:00
* Comando: `bash /volume1/docker/totalmaint/nas/backup.sh`

Vengono tenuti gli ultimi 30 backup, nella cartella `backup/`. Se vuoi una copia fuori dal NAS, includi la cartella in **Hyper Backup**.

---

## C. Ogni volta che fai una modifica (il ciclo normale)

| # | Dove | Cosa fai |
|---|---|---|
| 1 | PC | Modifichi il codice (anche insieme a Claude, nella cartella TotalMant) |
| 2 | PC | `run_local.bat` e provi su <http://localhost:8000> |
| 3 | PC | **`pubblica.bat`**: esegue i test e, se sono tutti verdi, chiede una riga di descrizione e invia a GitHub. Se un test fallisce, non pubblica niente |
| 4 | NAS | `ssh fabio@IP-NAS`, poi `cd /volume1/docker/totalmaint && sudo bash nas/update.sh` |

`update.sh` fa da solo: backup del database → scarica da GitHub → ricostruisce i container → controlla che l'app risponda. Se qualcosa va storto, ti stampa i comandi per tornare indietro.

Aggiorna anche `CHANGELOG.md` con una riga per ogni modifica: ti servirà per ricordare cosa è cambiato, e per Google Play.

---

## D. Regole d'oro

1. **Non modificare file direttamente sul NAS** (né con File Station, né con Container Manager): al prossimo aggiornamento `git pull` si bloccherebbe. Unica eccezione: il file `.env`.
2. **Le password stanno solo in `.env`**, mai nel codice.
3. **Modifiche al database.** Il programma aggiunge da solo le **nuove colonne** elencate in `backend/app/db.py` (`NEW_COLUMNS`) e crea le nuove tabelle. **Rinominare o cancellare** colonne o tabelle, invece, richiede una migrazione apposita: quando servirà, passeremo ad Alembic. In ogni caso `update.sh` fa sempre un backup prima.
4. **Testa sempre in locale prima** (`run_local.bat` + test verdi).

---

## E. Se qualcosa va storto

**Tornare alla versione precedente del codice** (sul NAS, da `sudo -i`):
```
cd /volume1/docker/totalmaint
git log --oneline -10
git reset --hard CODICE
docker compose up -d --build
```
`git log` mostra le ultime versioni; `CODICE` è quello della versione che vuoi, per esempio `a1b2c3d`.
Nota: se `git log` dice che il tuo ramo è "behind", al prossimo `update.sh` torneresti all'ultima versione. Per annullare davvero una modifica, è meglio annullarla sul PC e ripubblicarla.

**Ripristinare il database da un backup.** Attenzione: sostituisce tutti i dati attuali con quelli del backup.
```
cd /volume1/docker/totalmaint
ls backup/
docker compose stop app
docker compose exec -T db psql -U totalmaint -d totalmaint -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
gunzip -c backup/db-AAAA-MM-GG_HHMM.sql.gz | docker compose exec -T db psql -U totalmaint -d totalmaint
docker compose start app
```
(Se il progetto in Container Manager ha un nome diverso dalla cartella, aggiungi `-p NOME` dopo `docker compose`.)

**Vedere gli errori dell'app:**
```
docker compose logs --tail 100 app
```

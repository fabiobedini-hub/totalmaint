# Changelog – TotalMaint

Una riga per ogni modifica pubblicata. La più recente in alto.

## 0.4.1 – 2026-10-30
- **TotalMant Admin in tre lingue**: italiano, inglese e norvegese. Si sceglie con IT · EN · NO nella pagina di accesso e in fondo al menu; la scelta resta salvata nel browser. Al primo avvio segue la lingua del browser.
- Anche i messaggi di errore del server (password sbagliata, sessione scaduta …) vengono mostrati nella lingua scelta. Il testo degli eventi nel registro resta quello salvato dal server (inglese).

## 0.4.0 – 2026-10-30
- **TotalMant Admin**: console separata per chi gestisce il server, sulla porta 8081 (rete di casa e Tailscale), con password propria `ADMIN_PASSWORD`. Dashboard (oggi rispetto a ieri, il mese rispetto al mese scorso, ultime attività, azioni rapide), famiglie, utenti (link password, blocca/sblocca, elimina), inviti e registrazioni, registro e-mail ed e-mail di prova, registrazione aperta/con codice/chiusa senza riavviare, backup con un clic e download, tabelle del database, registro eventi.
- **Adminer** sulla porta 8082 per vedere le tabelle a mano.
- Nuova tabella `events`: registrazioni, accessi, inviti, e-mail, backup (solo chi/cosa/quando, mai il contenuto delle famiglie).
- Account **bloccabili**: niente accesso, sessioni chiuse subito, niente promemoria.
- Corretto: `SIGNUP`, `SIGNUP_CODE`, `INVITE_DAYS`, `RESET_HOURS` nel `.env` non arrivavano all'app sul NAS (mancavano nel `docker-compose.yml`).
- Immagine Docker su Debian 13 con `pg_dump`, necessario per "Backup ora".

## 0.3.2 – 2026-10-30
- **Registrer en ny familie** dalla pagina di login: nome della famiglia, nome, e-mail e password; chi registra diventa Eier. Aperto di default; `SIGNUP=closed` nel `.env` lo chiude, `SIGNUP_CODE` richiede un codice.
- Anche il primo utente sceglie il nome della famiglia (prima era sempre "Family").
- Innstillinger → **Ny familie**: chi ha già un account crea un'altra famiglia (hytta, båtforening …) e passa dall'una all'altra.

## 0.3.1 – 2026-10-30
- **Glemt passord?** sulla pagina di login: si inserisce l'e-mail e arriva un link monouso (valido `RESET_HOURS`, 2 ore) per scegliere una nuova password. La risposta è la stessa anche se l'e-mail non esiste; massimo 3 e-mail all'ora per persona.
- Dopo il reset tutti gli altri dispositivi vengono disconnessi.
- Senza SMTP: in Innstillinger → Medlemmer l'amministratore crea "Lenke for nytt passord" da mandare alla persona.

## 0.3.0 – 2026-10-30
- **Gruppi** (famiglia, club della barca …): ogni oggetto e fornitore appartiene a un gruppo; un gruppo non vede quelli degli altri. Una persona può stare in più gruppi.
- **Ruoli modificabili** per gruppo: Eier, Administrator, Bidragsyter, Leser già pronti; l'amministratore spunta i permessi (20, da "Opprette ting" a "Endre roller") e può creare ruoli nuovi. Eier è bloccato e ha sempre tutto.
- **Inviti via e-mail** con link monouso (14 giorni) e "Kopier lenke" se l'SMTP non è configurato. Registrazione libera solo con `SIGNUP_CODE` nel `.env` (vuoto = chiusa).
- Un unico controllo dei permessi nel server (`permissions.py`); l'app nasconde i pulsanti che il ruolo non può usare e mostra i moduli in sola lettura.
- **Aggiornamento automatico dei dati esistenti** al primo avvio: tutto diventa il gruppo "Familien", il primo amministratore è Eier, gli altri amministratori Administrator, gli altri utenti Bidragsyter.

## 0.2.2 – 2026-10-30
- Password fields (settings, users, login) have an eye button to show / hide the password.

## 0.2.1 – 2026-10-30
- Innstillinger: titolo cambiato in "Generelle innstillinger" (EN: "General settings").

## 0.2.0 – 2026-10-30
- Prima versione sotto Git e su GitHub.
- Installata sul Synology DS723+ (Container Manager, PostgreSQL).
- Funzioni: oggetti, componenti, attività ricorrenti, contatori (km / ore), fornitori, ricambi e lista della spesa, garanzie, allegati, calendario e iCal, più utenti, promemoria e-mail, norvegese/inglese.
- Aggiunti `pubblica.bat`, `nas/update.sh`, `nas/backup.sh` e `GUIDA_AGGIORNAMENTI.md`.

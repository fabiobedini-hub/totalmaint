# Changelog – TotalMaint

Una riga per ogni modifica pubblicata. La più recente in alto.

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

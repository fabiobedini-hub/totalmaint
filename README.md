# TotalMaint

Maintenance manager for home, car, boat and cabin. One Python server (FastAPI) with one
database, and one web app (PWA) that works in the browser, installs on the phone and
installs on the desktop.

```
┌──────────── phone / PC / browser ────────────┐
│   PWA (frontend/)  – same code everywhere     │
└──────────────────────┬────────────────────────┘
                       │ /api
┌──────────────────────┴────────────────────────┐
│ FastAPI (backend/app)  + daily reminder job    │
│ SQLite locally  ──or──  PostgreSQL on the NAS  │
│ uploads/ folder for receipts, manuals, photos  │
└───────────────────────────────────────────────┘
```

## 1. Run it locally (no Docker)

You need Python 3.11 or newer.

**Windows:** double-click `run_local.bat`.
**macOS / Linux:** `./run_local.sh`.

The first start creates `.venv` and installs the packages. Then open
<http://localhost:8000>. The first account you create becomes the administrator.

Everything is stored in the `data/` folder next to this file:

| File | What it is |
|---|---|
| `data/totalmaint.db` | SQLite database |
| `data/uploads/` | attached files |
| `data/secret.key` | key that signs log-ins (created automatically) |

Delete `data/` to start from scratch.

API documentation (try every call from the browser): <http://localhost:8000/docs>

### Testing on your phone at home
Your PC and phone must be on the same Wi-Fi. Open `http://<pc-name>:8000`; if the name
doesn't resolve, use the PC's IP address (`ipconfig`). Windows Firewall will ask to
allow Python the first time; allow it on private networks.

Note: "Add to Home Screen" works over plain http, but the offline mode and the
installed-app behaviour only fully work over **https** (or on `localhost`). That is
solved on the NAS with Tailscale or the reverse proxy (see below).

## 2. What's in it

* **Things** (assets): house, car, boat, cabin, other. Each with:
  * **Components** (heat pump, roof, tyres) with brand, model, serial number, install date
  * **Tasks**: repeat every N days / weeks / months / years, or one-off; next due date,
    reminder window, responsible person, estimated cost
  * **Spare parts** with stock and minimum stock; below minimum or flagged → shopping list
  * **Warranties** with end date (also in the calendar)
  * **Files** on things, tasks, history entries and warranties
* **Templates**: one click fills a new thing with typical components and tasks
  (house basics, heat pump, ventilation, garden, EV, petrol/diesel car, boat, cabin).
  Edit or add bundles in `backend/app/templates_data.py`.
* **Mark as done**: logs date, cost, notes and receipts; the next due date is counted
  from the day it was actually done.
* **Overview**: overdue, due soon, next 60 days, cost this year, recent work.
* **Calendar**: month view with future repeats, plus an **iCal link** to subscribe from
  Outlook / Google / iPhone.
* **Groups and roles**: everything belongs to a group (a family, a boat club …), and groups don't
  see each other. Each group has the roles Owner, Admin, Creator and Viewer; the admin ticks what
  each role may do under Settings → Roles and can add roles of their own. Owner always has
  everything. All checks are in `backend/app/permissions.py`.
* **Invitations** by e-mail: a one-time link valid for `INVITE_DAYS` (14). Without SMTP the app
  shows the link to copy.
* **Register a new family** from the log-in screen: the person names the family and becomes its
  owner. `SIGNUP=closed` in `.env` switches this off (invitations only); `SIGNUP_CODE` makes it
  need a code you hand out. Someone with an account adds another family under Settings → New family.
* **TotalMant Admin**, a separate console for whoever runs the server (port 8081 on the NAS,
  home network and Tailscale only, its own `ADMIN_PASSWORD`): dashboard, families, users
  (password link, block, delete), invitations, e-mail log, sign-up settings, backups, database.
  In English, Norwegian and Italian (`admin/i18n.js`).
  Locally: `run_admin.bat` → <http://localhost:8001>. Code: `backend/app/admin_main.py` + `admin/`.
* **Multiple users** with their own language (English / Norwegian) and "only my tasks".
* **E-mail reminders** once a day (configure SMTP in `.env`; without it they are only logged).

## 3. Moving it to the Synology DS723+

1. Install **Container Manager** from Package Center.
2. Copy this folder to the NAS, e.g. `/volume1/docker/totalmaint`.
3. Copy `.env.example` to `.env` and set `POSTGRES_PASSWORD`, `SECRET_KEY`, `PUBLIC_URL`.
4. Container Manager → **Project** → **Create** → path `/volume1/docker/totalmaint` →
   it finds `docker-compose.yml` → build and start.
5. Open `http://<nas-ip>:8080`.

The NAS uses PostgreSQL instead of SQLite; the code is the same. To bring your local
test data along, the simplest way is to start fresh on the NAS. (A small export/import
script can be added if you want to keep it.)

### Access from outside the house
* **Tailscale** (recommended to start): install the Tailscale package on the NAS and the
  Tailscale app on your phones. Set `PUBLIC_URL=http://<nas-tailscale-name>:8080`.
* **Public https**: DSM → Control Panel → External Access (DDNS `*.synology.me`) +
  Security → Certificate (Let's Encrypt) + Login Portal → Advanced → Reverse Proxy from
  `https://totalmaint.<you>.synology.me` to `localhost:8080`. Open port 443 on the router.

### Backups
* Nightly DB dump (DSM Task Scheduler, user root):
  `docker exec totalmaint-db-1 pg_dump -U totalmaint totalmaint > /volume1/docker/totalmaint/backup/db-$(date +\%F).sql`
* Hyper Backup the whole `/volume1/docker/totalmaint` folder (includes uploads) to C2,
  OneDrive or a USB disk.

## 4. Developing further

* Backend code: `backend/app/` (`models.py` = tables, `api.py` = endpoints).
* Frontend: `frontend/` (plain JavaScript, no build step; texts in `i18n.js`).
* Tables are created automatically on start. Once you have real data and start
  changing `models.py`, add **Alembic** for migrations so existing data is upgraded
  instead of needing a fresh database.

Ideas for next steps: push notifications to the installed app (Web Push), cost export
to Excel, photo of the receipt straight from the phone camera, QR stickers on
components that open the right page.

### Automatic tests

Double-click `run_tests.bat` (or run `./run_tests.sh`). The tests use a temporary database, never your real data.
They cover login and rights, task dates and status, completing tasks, counters (km / hours), vendors,
spare parts and the shopping list, templates for every type of thing, calendar, iCal and attachments.
Run them after every change: all green = nothing old was broken.
New tests go in `backend/tests/` (one file per area, functions named `test_...`).

## 5. Updating (Git → GitHub → NAS)

See **[GUIDA_AGGIORNAMENTI.md](GUIDA_AGGIORNAMENTI.md)** (Italian). In short:
change and test on the PC → `pubblica.bat` (runs the tests, commits, pushes to GitHub) →
on the NAS `sudo bash nas/update.sh` (DB backup, `git pull`, rebuild, health check).
Nightly DB backup: `nas/backup.sh` in the DSM Task Scheduler.

# Mama Vuna Fresh

**Community labour support and maternal protection for pregnant women in Tanzania.**
By Ngwala Inventions.

Pregnant women register on any phone by USSD. The platform works out the weeks when they
would normally do dangerous work: heavy lifting, long bending and pesticide spraying on the farm, or carrying
water, market loads and heavy chores at home. Before each of those periods it finds a helper from the
community (a cooperative, savings group, women's or youth group) and asks them by SMS. Community health
workers (CHWs) follow up, respond to danger signs and confirm the help, and every confirmed hour goes into a
tamper-evident time-credit ledger.

Smallholder farmers are the core group. Any pregnant woman can join, in rural, peri-urban or urban areas.

---

## Who uses what

| Person | Uses | Can do |
|---|---|---|
| Pregnant woman | USSD (`*149*77#` or your code) and SMS, in Kiswahili or English | Register, see her rest weeks, ask for help now, report danger signs, report the birth, correct her due date. Send `HATARI` (danger), `MSAADA` (help) or `STOP` by SMS |
| Helper | USSD and SMS | Register, answer requests (`1` accept, `2` decline), see verified hours, go on leave |
| Community health worker | Web dashboard (phone or computer) | See her own mothers, act on danger reports, record visits and birth outcomes, assign helpers, confirm hours |
| District officer | Web dashboard | Everything in the district, add CHW accounts and facilities, download reports |
| Administrator | Web dashboard | Everything, plus the crop calendar, staff accounts, phone simulator, system settings and audit log |

## What is included

- **USSD gateway** for Africa's Talking, plus a fallback format (`MSISDN`, `USSD_STRING`) for direct links with mobile operators. The menus cover registration for mothers and helpers, status, help on request, danger signs, birth reports, due-date changes and language switching.
- **SMS** in and out through Africa's Talking. Every message is logged, failed messages are retried, and delivery reports are recorded.
- **Risk-window engine.** Protection runs from week 28 to 6 weeks after birth. Farm windows come from the crop labour calendar for her region and crop. Daily-work windows (water, household, market stall, livestock) come from her livelihood, in 4-week blocks.
- **Crop labour calendar.** 150 rows covering 8 regions in detail, with national defaults for the rest. You can upload your own CSV.
- **Helper matching.** Helpers are matched within the district and scored on closeness, reliability and current load. Pesticide tasks go only to trained helpers. Each helper gets one question at a time, a request moves to the next helper after 24 hours without a reply, and the CHW gets an SMS if nobody is free.
- **Background scheduler** (every 15 minutes). It creates requests 21 days ahead, sends alerts, escalates, sends 7 pregnancy messages per pregnancy, closes finished records and retries failed SMS.
- **Danger-sign flow.** The mother is told to go to her nearest facility (with its phone number), the CHW gets an SMS at once, and the response time is tracked.
- **CHW follow-up visits.** CHWs record heavy work, pesticide handling, help received and antenatal care, which give *measured* protection indicators.
- **Birth outcomes.** Gestational age, birth weight, place, preterm and low birth weight are recorded.
- **Time-credit ledger.** Hash-chained with SHA-256 and storing codes only, with a one-click integrity check and a published head hash.
- **Reports.** Every indicator shows its denominator. Reports break down by district and can be downloaded as anonymised CSV, plus a monthly aggregate file in DHIS2 `dataValueSets` layout.
- **Roles and data scoping.** Sessions are signed, passwords are hashed with PBKDF2, all forms have CSRF protection, failed logins are rate-limited, and there is an audit log.
- **Phone simulator** for testing the real USSD and SMS logic without a telecom line, and **training data** that is flagged and kept out of every report.
- **Partner API** (read-only) with interactive docs at `/api/docs`.

---

## 1. Try it on your computer

You need Python 3.11 or newer.

```bash
cd mama-vuna-fresh
python3 -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and set at least `APP_ENV=development`, `SESSION_HTTPS_ONLY=false`,
`DATABASE_URL=sqlite:///data/mamavuna.db`, `ADMIN_EMAIL` and `ADMIN_PASSWORD`. Then load it and start:

```bash
set -a; source .env; set +a
uvicorn app.main:app --reload
```

1. Open http://localhost:8000 and sign in with the admin email and password.
2. Go to **System → Load training data**, then **Run now**.
3. Open **Phone simulator** and dial the USSD code, or try the numbers from the training data.

Run the tests with `pip install -r requirements-dev.txt && pytest -q`.

## 2. Put it on a server

Any Ubuntu 22.04/24.04 server with 1 GB RAM is enough for a district pilot. Point a domain or subdomain
(for example `mamavuna.yourdomain.co.tz`) at the server's IP address first.

### Option A: Docker (recommended)

```bash
sudo apt update && sudo apt install -y docker.io docker-compose-v2 nginx certbot python3-certbot-nginx
# copy the project folder to the server, e.g. with scp, then:
cd /opt/mama-vuna-fresh
cp .env.example .env && nano .env          # fill in SECRET_KEY, ADMIN_EMAIL, ADMIN_PASSWORD, WEBHOOK_TOKEN
mkdir -p data backups && sudo chown 1000:1000 data backups
sudo docker compose up -d --build
curl http://127.0.0.1:8000/health          # {"status":"ok"}
```

### Option B: without Docker

```bash
sudo apt install -y python3-venv sqlite3 nginx certbot python3-certbot-nginx
sudo useradd --system --create-home mvf
sudo mkdir -p /opt/mama-vuna-fresh && sudo cp -r . /opt/mama-vuna-fresh && cd /opt/mama-vuna-fresh
sudo python3 -m venv .venv && sudo .venv/bin/pip install -r requirements.txt
sudo cp .env.example .env && sudo nano .env      # set DATABASE_URL=sqlite:////opt/mama-vuna-fresh/data/mamavuna.db
sudo mkdir -p data backups && sudo chown -R mvf:mvf /opt/mama-vuna-fresh
sudo cp deploy/mamavuna.service /etc/systemd/system/ && sudo systemctl daemon-reload
sudo systemctl enable --now mamavuna
```

### HTTPS with nginx (both options)

```bash
sudo cp deploy/nginx.conf /etc/nginx/sites-available/mamavuna
sudo nano /etc/nginx/sites-available/mamavuna            # replace mamavuna.yourdomain.co.tz
sudo ln -s /etc/nginx/sites-available/mamavuna /etc/nginx/sites-enabled/
sudo certbot --nginx -d mamavuna.yourdomain.co.tz
sudo nginx -t && sudo systemctl reload nginx
```

Generate the secrets with `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`, once for
`SECRET_KEY` and again for `WEBHOOK_TOKEN`. The app refuses to start in production without a `SECRET_KEY`.

### Backups

```bash
crontab -e
15 2 * * * /opt/mama-vuna-fresh/scripts/backup.sh >> /var/log/mamavuna-backup.log 2>&1
```

Also copy `backups/` to a second place (another server or cloud storage). A backup kept on the same
machine does not protect against losing the server.

## 3. Connect the phone network (Africa's Talking)

1. Create an account at africastalking.com. Test everything in the **sandbox** first.
2. **USSD:** request a service code (a shared code like `*384*xxxx#` is quickest; a dedicated code needs
   TCRA approval). Set the callback URL to
   `https://mamavuna.yourdomain.co.tz/ussd?token=YOUR_WEBHOOK_TOKEN`, and put the code in `USSD_SERVICE_CODE`.
3. **SMS:** get a sender ID or short code. Set:
   - incoming messages callback: `https://…/sms/inbound?token=YOUR_WEBHOOK_TOKEN`
   - delivery reports callback: `https://…/sms/delivery?token=YOUR_WEBHOOK_TOKEN`
4. In `.env` set `SMS_PROVIDER=africastalking`, `AT_USERNAME`, `AT_API_KEY`, `AT_SENDER_ID` and, when you go
   live, `AT_SANDBOX=false`. Restart the app.
5. Check **System** in the dashboard. It shows the exact callback URLs, and the SMS log shows sent, failed
   and delivered messages.

Other gateways: `/ussd` also accepts `MSISDN` and `USSD_STRING` (form, query or JSON). Replies start
with `CON` (continue) or `END`. If an operator needs a different format, adapt `app/routers/telecom.py` only.

## 4. First week checklist

- [ ] Sign in, change the admin password (**My account**).
- [ ] **Staff accounts:** add district officers and CHWs with their phone numbers. CHWs without a phone get no danger alerts.
- [ ] **Health facilities:** add the facilities in each pilot ward with a phone number that is answered.
- [ ] **Crop labour calendar:** ask the district agricultural extension officer to check the months for your district. Download the CSV, correct it and upload it.
- [ ] **Community groups and helpers:** register groups and their members, and mark who is trained in safe pesticide handling.
- [ ] Test every USSD menu on a real phone in the sandbox before telling mothers the code.
- [ ] Do **not** load training data on the live server. Use a separate training server.

## Data protection

The platform holds health information about pregnant women. Before going live:

- Register as a data controller and processor with Tanzania's **Personal Data Protection Commission** and
  follow the Personal Data Protection Act, 2022. Get ethics approval (e.g. NIMR) before using outcome
  data for research.
- Consent is recorded at registration (USSD or web) and helpers agree to share their number. Anyone can
  send `STOP`.
- CHWs see only their own mothers. District officers see only their district. Exports use codes, not names
  or phone numbers, and every export is in the audit log.
- The ledger stores codes and hours only.
- Use HTTPS, a strong `SECRET_KEY`, `WEBHOOK_TOKEN` and daily off-server backups.

## Indicators: what they mean

All figures are counted from records in the platform. Demo records are excluded.

| Indicator | Source |
|---|---|
| Requests filled | Requests that got a helper ÷ requests that were decided |
| Helper found within 48 h | Requests whose first acceptance came within 48 h of the first alert |
| Verified support hours | Sum of hours confirmed by CHWs in the ledger |
| No pesticide handling / no heavy work | CHW visit answers (last 7 days), week 28 and later |
| Preterm, low birth weight | Birth outcomes recorded by CHWs or facilities |

The outcome figures describe enrolled women only. To claim an effect (for example fewer preterm births),
compare them with similar women who were not enrolled, using the same definitions, in a study with ethics
approval. The platform's CSV exports are ready for that analysis.

## Not built yet (next steps)

- Voice (IVR) menus for women who cannot read USSD text.
- Anchoring the ledger head hash on a public blockchain. Today the hash chain is checked inside the platform.
- Automatic push to DHIS2. Today the monthly file is downloaded, and the codes must be mapped with the HMIS team first.
- Mobile-money micro-premiums from cooperatives, and an offline app for CHWs.

## Project layout

```
app/
  main.py              app start-up, routes, first admin
  config.py            settings from .env
  models.py            database tables
  security.py          passwords, roles, CSRF, data scoping
  routers/             telecom (USSD/SMS webhooks), pages, admin, reports, api, auth
  services/            ussd, sms, sms_inbound, matching, pregnancy, scheduler, ledger,
                       mothers, indicators, reference, texts (Kiswahili/English), demo
  templates/           web pages        static/  style.css, app.js
  data/                locations.csv (31 regions, 172 districts), crop_calendar.csv
scripts/               create_admin.py, backup.sh, run_scheduler_once.py
deploy/                nginx.conf, mamavuna.service
tests/                 automated tests (pytest)
```

The district list and crop calendar are reference data compiled for this platform. Check them against the
latest NBS/PO-RALG list and district agricultural calendars, and correct them as CSV.

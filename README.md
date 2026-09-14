# Indore City Bus Ticket Booking — WhatsApp Bot

Book an Indore city bus ticket **entirely inside WhatsApp**, or on the web.
Django · Twilio · Ngrok · MySQL · REST API.

The bot is a real conversational state machine — source → destination → date →
bus → seats → confirm → PNR — not a link that bounces you to a website.

```
you › hi
bot › 🚌 Namaste! Welcome to Indore iBus
      1 Book  2 My tickets  3 Cancel  4 Fare  5 Stops
you › 1
bot › 📍 Where are you boarding?
you › palasia
bot › 🎯 Boarding at Palasia. Where are you going?
you › vijay ngr                     ← abbreviations resolve
bot › 📅 1 Today  2 Tomorrow
you › 1
bot › 1. 6:00 PM · BRTS-01-UP  ₹5 · 2.8 km · 40 seats left
you › 1
bot › 👥 How many tickets? (1–6)
you › 2
bot › 🧾 Palasia → Vijay Nagar · 2 × ₹5 · Total ₹10 — reply YES
you › yes
bot › ✅ Ticket confirmed!  PNR: IBVW672D
```

---

## Quick start

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # then edit: SECRET_KEY at minimum
python manage.py migrate
python manage.py seed_network         # 41 stops, 12 route directions, fares, buses
python manage.py generate_trips --days 7
python manage.py createsuperuser
python manage.py runserver
```

Open <http://127.0.0.1:8000/>.

**Try the bot with no Twilio account and no phone:**

```bash
python manage.py chat
python manage.py chat --script "hi|1|palasia|vijay ngr|1|1|2|Asha|yes"
```

---

## What's where

```
bot/
  models.py              Stop · Route · RouteStop · FareSlab · Bus · Schedule · Trip
                         PassengerProfile · Booking · Passenger · Payment
                         ConversationSession · MessageLog
  services/              domain logic — no HTTP, no Twilio
    fares.py             distance-slab fare lookup
    matching.py          fuzzy stop-name resolution
    network.py           route/trip search
    booking.py           seat allocation, PNR issue, cancellation
    pnr.py               collision-safe human-readable PNRs
  conversation/          the WhatsApp FSM
    states.py            states + allowed transitions
    machine.py           dispatch(session, text) -> Reply    ← pure, testable
    render.py            message templates, pagination, 1600-char splitting
  webhooks/twilio.py     the only Twilio-aware module
  api/                   DRF serializers + views
  views.py               website (thin — calls services/)
  data/indore_network.py the authored Indore network
  management/commands/   seed_network · generate_trips · chat · expire_bookings
  tests/                 98 tests
```

`services/booking.py` is called identically by the bot, the website and the API,
so fare and seat logic exists in exactly one place.

---

## The Indore network

The BRTS corridor is real: **11.57 km, 22 stations, Rajiv Gandhi Square ↔
Niranjanpur** along AB Road ([Indore BRTS][brts]).

> Rajiv Gandhi Square · Aditya Nagar · Indrapuri · Holkar College · Zoo ·
> Navlakha · GPO · MY Hospital · Geeta Bhawan · Palasia · Industry House ·
> LIG Square · Press Complex · Shalimar Residency · Vijay Nagar · Satya Sai
> Square · Orbit Mall · Scheme 74 · Shalimar Township · Scheme 78 ·
> Lasudiya Mori · Niranjanpur

Plus five city routes covering Rajwada, Sarwate, Indore Junction, Airport,
Bhawarkuan, Khajrana, Bengali Square, Rau and others — 41 stops in total.

**Fares are distance-slab**, like the real system. Slabs are database rows, not
hardcoded branches, so they can be changed in the admin without a deploy:

| Distance | Fare |
|---|---|
| 0–3 km | ₹5 |
| 3–6 km | ₹10 |
| 6–10 km | ₹15 |
| 10–15 km | ₹20 |
| 15 km+ | ₹25 |

`RouteStop` stores *cumulative* km from the route origin, so the fare between
any two stops is one subtraction rather than a SUM over a range.

[brts]: https://en.wikipedia.org/wiki/Indore_Bus_Rapid_Transit_System

---

## REST API

Browsable at <http://127.0.0.1:8000/api/>.

| Endpoint | Purpose |
|---|---|
| `GET /api/stops/?q=pal` | stop autocomplete |
| `GET /api/routes/` | routes with their ordered stops |
| `GET /api/fare/?origin=1&destination=5` | fare quote |
| `GET /api/trips/?origin=1&destination=5&date=YYYY-MM-DD&seats=2` | bookable departures |
| `POST /api/bookings/create/` | create a booking |
| `GET /api/bookings/<PNR>/?whatsapp_number=+91…` | ticket lookup |

```bash
curl "http://127.0.0.1:8000/api/fare/?origin=1&destination=15"
```

The website's live fare preview is driven by `/api/fare/`.

---

## Connecting WhatsApp (Twilio + ngrok)

1. **Expose the local server**

   ```bash
   ngrok http 8000
   ```

2. **Tell Django about the tunnel** — edit `.env`:

   ```ini
   PUBLIC_BASE_URL=https://<your-id>.ngrok-free.app
   ALLOWED_HOSTS=127.0.0.1,localhost,<your-id>.ngrok-free.app
   CSRF_TRUSTED_ORIGINS=https://<your-id>.ngrok-free.app
   TWILIO_ACCOUNT_SID=ACxxxxxxxx
   TWILIO_AUTH_TOKEN=xxxxxxxx
   TWILIO_VALIDATE_SIGNATURE=True
   ```

3. **Point the Twilio WhatsApp sandbox** (Console → Messaging → Try it out →
   WhatsApp sandbox) at:

   ```
   https://<your-id>.ngrok-free.app/webhook/whatsapp/      (POST)
   ```

4. **Join the sandbox** from your phone (`join <two-words>`), then send `hi`.

The webhook validates Twilio's `X-Twilio-Signature`, so a leaked ngrok URL
cannot be driven by anyone else. It also dedupes on `MessageSid` — Twilio
retries on timeout, and without that a retry would book twice.

---

## Switching to MySQL

SQLite is the default so the project runs anywhere. For MySQL:

```bash
sudo apt install pkg-config default-libmysqlclient-dev build-essential
pip install mysqlclient
```

```sql
CREATE DATABASE indore_ibus CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

```ini
# .env
DB_ENGINE=mysql
DB_NAME=indore_ibus
DB_USER=root
DB_PASSWORD=yourpassword
DB_HOST=127.0.0.1
DB_PORT=3306
```

```bash
python manage.py migrate
python manage.py loaddata fixtures/users.json    # keeps existing accounts
python manage.py seed_network
python manage.py generate_trips --days 7
```

**A note on seat safety.** Seats are claimed with a *conditional UPDATE*
(`WHERE seats_booked <= total_seats - n`), not `select_for_update()`. On
MySQL/InnoDB the default REPEATABLE READ isolation means a plain `SELECT`
returns a possibly-stale snapshot, so read-check-write is genuinely broken
there; and on SQLite `select_for_update()` is silently a no-op. One conditional
UPDATE is correct on both. A `CheckConstraint` backs it up at the database
level. Genuine write parallelism is a MySQL property — SQLite serializes
writers.

---

## Housekeeping commands

```bash
python manage.py generate_trips --days 14 --purge-past
python manage.py expire_bookings     # release seats held by stale PENDING bookings
```

Run `generate_trips` on a schedule (cron/systemd timer) so future departures
always exist.

---

## Tests

```bash
python manage.py test bot
```

98 tests covering fare-slab boundaries, directional route search, stop matching,
PNR uniqueness, **overselling under 30 concurrent bookings**, every FSM
transition and global command, session expiry, the website, the REST API and
the webhook (including retry deduping and signature rejection).

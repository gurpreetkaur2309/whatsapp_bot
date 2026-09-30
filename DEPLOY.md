# Deploying to Vercel

**Yes, this deploys to Vercel** — and it's a genuine upgrade, because the Vercel
URL replaces ngrok as your Twilio webhook. No more restarting a tunnel and
re-pasting a URL every session.

**One thing cannot come with you: SQLite.** Vercel's filesystem is read-only and
every request may hit a fresh container, so `db.sqlite3` would silently discard
writes. You must point the app at a hosted database. Everything else already
works — the code writes nothing to disk (the ticket QR is generated in memory).

What's already been prepared in the repo:

| File | Purpose |
|---|---|
| `api/index.py` | WSGI entrypoint Vercel calls |
| `vercel.json` | build, routing, and the nightly cron |
| `.vercelignore` | keeps the demo video and unused theme out of the bundle |
| `whatsapp_bot/__init__.py` | PyMySQL shim — `mysqlclient` can't compile on Vercel |
| `settings.py` | `DATABASE_URL`, WhiteNoise, auto-trust of the Vercel domain |
| `/tasks/rollover/` | cron endpoint — generates trips, releases stale seats |

---

## Step 1 — Create a free hosted MySQL

### Pick a provider

| Provider | Free? | Storage | Notes |
|---|---|---|---|
| **[Aiven for MySQL](https://aiven.io/free-mysql-database)** ⭐ | **Always free, no card** | 1 GB / 1 GB RAM | Real MySQL 8, managed backups. **Recommended.** |
| [TiDB Cloud Serverless](https://tidbcloud.com/) | Free tier | 5 GB | MySQL-*compatible*, not MySQL. Much bigger quota. |
| [Neon](https://neon.tech) | Free tier | 0.5 GB | **Postgres**, not MySQL. Best free tier overall. |
| ~~Railway~~ | ✗ | — | $5 one-time credit, then $1/mo — won't sustain a DB. |
| ~~PlanetScale~~ | ✗ | — | Free tier removed in 2024. |

**Go with Aiven** unless you have a reason not to: it's genuinely free with no
credit card, has no time limit, and it's *actual* MySQL — which matters because
your project description says MySQL.

> Aiven's one catch: they reserve the right to shut down a free service that
> sits **unused for an extended period**. For a portfolio project that's fine —
> and your Vercel cron pings the database daily anyway, which keeps it active.

---

### 1.1 Create the service

1. Sign up at <https://aiven.io/free-mysql-database> (no credit card)
2. **Create service** → **MySQL**
3. Cloud + region: pick whatever is nearest you — for India, `google-asia-south1`
   (Mumbai) or `aws-ap-south-1`
4. Plan: select the **Free** plan (labelled *Free-1-5gb* or similar)
5. Name it `indore-ibus` → **Create**

Provisioning takes 2–4 minutes. Wait for the status to go from *REBUILDING* to
**RUNNING**.

### 1.2 Copy the connection URL

On the service **Overview** page, find **Connection information** and copy the
**Service URI**:

```
mysql://avnadmin:AVNS_xxxxxxxxxxxx@indore-ibus-yourproj.h.aivencloud.com:23456/defaultdb?ssl-mode=REQUIRED
```

That whole string — query parameter included — is your `DATABASE_URL`. Nothing
needs stripping: settings.py translates Aiven's `?ssl-mode=REQUIRED` into the
SSL option the driver actually accepts.

Aiven requires TLS, so leave `DB_REQUIRE_SSL` unset (it defaults to on here).

### 1.3 Test the connection before going further

```bash
cd /home/lap-35/Downloads/gurpreet/whatsapp_bot
source venv/bin/activate

export DATABASE_URL="mysql://avnadmin:AVNS_xxx@indore-ibus-yourproj.h.aivencloud.com:23456/defaultdb?ssl-mode=REQUIRED"

python manage.py check --database default
```

`System check identified no issues` means you're connected.

> If the password contains `@ : / # ?`, URL-encode it (`@` → `%40`) or the URL
> parses wrong and you'll get a confusing "unknown host".

---

### Alternative: TiDB Cloud Serverless

Worth it if 1 GB feels tight — the free tier is 5 GB.

1. Sign up at <https://tidbcloud.com>
2. **Create Cluster** → **Serverless** → free tier
3. **Connect** → set a password → copy the connection details
4. Assemble the URL yourself; TiDB shows host/port/user separately:

   ```
   mysql://<user>:<password>@gateway01.<region>.prod.aws.tidbcloud.com:4000/test
   ```

5. TiDB requires TLS — leave `DB_REQUIRE_SSL` at its default.

TiDB is MySQL-compatible rather than MySQL. Everything this project uses works
(including foreign keys and the conditional-UPDATE seat lock), but if you're
listing "MySQL" on a CV, Aiven is the more literally accurate answer.

---

### Alternative: Neon (Postgres)

The best free tier of the three, if you're willing to drop MySQL:

```bash
pip install "psycopg[binary]"
```

Use Neon's `postgres://…` URL as `DATABASE_URL`. No other code changes — the
project is ORM-only, and the seat-locking `UPDATE` behaves identically. But your
project description says MySQL, so this contradicts it.

---

## Step 2 — Load the schema and data (from your laptop, once)

Vercel gives you no shell, so migrations and seeding run locally **against the
remote database**:

```bash
cd /home/lap-35/Downloads/gurpreet/whatsapp_bot
source venv/bin/activate

export DATABASE_URL="mysql://avnadmin:PASSWORD@host:port/dbname"

python manage.py migrate
python manage.py seed_network
python manage.py generate_trips --days 14
python manage.py createsuperuser
```

Sanity check it landed:

```bash
python manage.py shell -c "from bot.models import Stop,Trip; print(Stop.objects.count(),'stops', Trip.objects.count(),'trips')"
```

Expect `41 stops 4312 trips`.

---

## Step 3 — Push to GitHub

```bash
git add -A
git commit -m "Add Vercel deployment config"
git push
```

---

## Step 4 — Import into Vercel

1. <https://vercel.com/new> → **Import** your GitHub repo
2. Framework preset: leave as detected (Vercel finds Django from `requirements.txt`)
3. **Don't deploy yet** — add the environment variables first (next step)

---

## Step 5 — Environment variables

In **Project → Settings → Environment Variables**, add these for
*Production, Preview and Development*:

| Name | Value |
|---|---|
| `DATABASE_URL` | the URL from step 1 |
| `SECRET_KEY` | generate one (below) |
| `DEBUG` | `False` |
| `ALLOWED_HOSTS` | `127.0.0.1,localhost` |
| `ALLOW_ALL_VERCEL_SUBDOMAINS` | `True` |
| `CRON_SECRET` | generate one (below) |
| `TWILIO_ACCOUNT_SID` | from Twilio console |
| `TWILIO_AUTH_TOKEN` | from Twilio console |
| `TWILIO_WHATSAPP_NUMBER` | `whatsapp:+14155238886` |
| `TWILIO_VALIDATE_SIGNATURE` | `True` |
| `CONN_MAX_AGE` | `0` |
| `DB_REQUIRE_SSL` | leave unset — auto-detected from the URL |

Generate the two secrets:

```bash
python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

You don't need to set `ALLOWED_HOSTS` to your Vercel domain — settings.py reads
Vercel's injected `VERCEL_URL` and trusts it automatically.

Now hit **Deploy**.

---

## Step 6 — Point Twilio at Vercel (goodbye ngrok)

Once deployed you'll have `https://your-project.vercel.app`.

1. Add one more env var so Twilio signature validation matches the exact URL:

   | Name | Value |
   |---|---|
   | `PUBLIC_BASE_URL` | `https://your-project.vercel.app` |

   Redeploy after adding it (**Deployments → ⋯ → Redeploy**).

2. Twilio Console → **Messaging → Try it out → WhatsApp sandbox → Sandbox settings**

   *When a message comes in:*
   ```
   https://your-project.vercel.app/webhook/whatsapp/     (POST)
   ```

3. Send `hi` from your phone.

---

## Step 7 — Confirm it's alive

```bash
curl -s https://your-project.vercel.app/api/stops/?q=palasia | head -c 200
curl -s -o /dev/null -w "%{http_code}\n" https://your-project.vercel.app/
```

Then open the site, `/admin/`, and `/api/` in a browser.

---

## The nightly cron

`vercel.json` schedules `/tasks/rollover/` daily at **00:00 IST** (18:30 UTC).
It tops up trips for the next 7 days and releases seats held by abandoned
bookings. Vercel sends `Authorization: Bearer $CRON_SECRET`; the endpoint
rejects anything else with a constant-time comparison, and refuses to run at
all (503) if `CRON_SECRET` is unset — so it can never run unprotected.

Trigger it by hand to test:

```bash
curl -X POST https://your-project.vercel.app/tasks/rollover/ \
  -H "Authorization: Bearer $CRON_SECRET"
```

> Vercel's **Hobby plan runs cron jobs once per day** and is for non-commercial
> use. That's fine here — trips are generated 7–14 days ahead.

---

## Things that behave differently on Vercel

**`manage.py` commands don't run there.** `chat`, `seed_network`,
`generate_trips`, `createsuperuser` are all local-only, run with `DATABASE_URL`
exported as in step 2. That's why the cron endpoint exists.

**Cold starts.** An idle deployment takes ~1–3 s to wake. Twilio's webhook
timeout is 10 s, so a cold start is survivable, but the first WhatsApp message
after a quiet period will feel slow.

**Connection limits.** Serverless opens a new DB connection per container.
`CONN_MAX_AGE=0` is set deliberately — persistent connections exhaust a free
tier's connection cap fast. If you see "too many connections", that's the cause.

**Seat-locking still holds.** The conditional `UPDATE` is enforced by the
database, not the process, so concurrent serverless invocations cannot oversell.
This is the one place where moving off SQLite makes the app *more* correct —
real row locks instead of a serialized file.

---

## If the build fails

| Symptom | Cause |
|---|---|
| `No module named MySQLdb` | `PyMySQL` missing from `requirements.txt` |
| `DisallowedHost` | set `ALLOW_ALL_VERCEL_SUBDOMAINS=True` |
| `CSRF verification failed` | set `PUBLIC_BASE_URL` to the real domain, redeploy |
| `no such table: bot_stop` | step 2 wasn't run against `DATABASE_URL` |
| Unstyled admin | `collectstatic` failed — check the build log |
| `Invalid Twilio signature` | `PUBLIC_BASE_URL` must match the webhook URL exactly |
| Lambda too large | raise `maxLambdaSize` in `vercel.json` |
| `TypeError: unexpected keyword argument 'ssl-mode'` | old settings.py — the URL's query params leaked into OPTIONS (fixed; see `test_settings_db.py`) |
| `SSLError` / `Can't connect` | provider doesn't do TLS — set `DB_REQUIRE_SSL=False` |
| "unknown host" with a valid URL | special characters in the password need URL-encoding (`@` → `%40`) |
| `Too many connections` | free tiers cap connections — keep `CONN_MAX_AGE=0` |
| Connection times out from Vercel | using a *private* host (e.g. `*.railway.internal`) — you need the public one |
| Aiven service went away | free services are reclaimed after long inactivity; the daily cron prevents this |

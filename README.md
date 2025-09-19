# BillPay - Plaid-Powered Financial Dashboard

BillPay is a mobile-first Flask web application that automatically pulls all financial data from Plaid. The app aggregates bank accounts, credit cards, bills, and income streams directly from Plaid and provides budgeting, paycheck modeling, and historical insights.

## Features

- **Automatic Data Sync**: Uses Plaid as the single source of truth for linked accounts, balances, transactions, and recurring bills/income
- **Dashboard**: Visual overview of financial health including net worth, income vs. expenses, and upcoming bills
- **Accounts**: View all linked accounts and balances from multiple financial institutions
- **Transactions**: Browse, filter, and search transactions with automatic categorization
- **Bills**: Track recurring bills with due dates, status, and payment history
- **Income**: Monitor income sources with paycheck simulator for financial planning

## Technology Stack

- **Backend**: Flask + SQLAlchemy
- **Frontend**: Jinja2 + Bootstrap 5 + Chart.js
- **Database**: PostgreSQL (production) / SQLite (development)
- **Plaid SDK**: plaid-python for all data access

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/billpay.git
   cd billpay
   ```

2. Create and activate a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   Create a `.env` file in the project root with:
   ```
   FLASK_APP=run.py
   FLASK_ENV=development
   SECRET_KEY=your-secret-key
   PLAID_CLIENT_ID=your-plaid-client-id
   PLAID_SECRET=your-plaid-sandbox-secret
   PLAID_ENV=sandbox
   ```

5. Initialize the database:
   ```
   flask db init
   flask db migrate -m "Initial migration"
   flask db upgrade
   ```

6. Run the application:
   ```
   flask run
   ```

7. Access the application at: http://127.0.0.1:5000/

## Database Setup

BillPay uses SQLAlchemy with Flask-Migrate. By default (no `DATABASE_URL` provided) it falls back to a local SQLite file `billpay.db` in the project root:

```
SQLALCHEMY_DATABASE_URI = sqlite:///billpay.db
```

### Development (SQLite)
No extra service required. After creating your virtual environment:

```
flask db init        # only once – creates migrations folder (already present in repo if checked in)
flask db migrate -m "Initial tables"
flask db upgrade
```

If migrations already exist, you typically just run:

```
flask db upgrade
```

To reset the dev database completely:
1. Stop the app.
2. Delete `billpay.db` (and optionally the `migrations/` folder if you want a clean migration history).
3. Re-run the migration commands above.

### Production (PostgreSQL Example)
1. Provision a PostgreSQL database (e.g., on Render, Railway, AWS RDS, Neon, Supabase, Heroku, etc.).
2. Collect the connection URL. Format examples:
   - Standard: `postgresql://user:password@host:5432/dbname`
   - Heroku style (deprecated scheme support): `postgres://user:password@host:5432/dbname` (SQLAlchemy rewrites to `postgresql://`).
3. Set the environment variable:
   - Windows PowerShell:
     ```powershell
     $Env:DATABASE_URL = "postgresql://user:password@host:5432/dbname"
     ```
   - Unix/macOS:
     ```bash
     export DATABASE_URL=postgresql://user:password@host:5432/dbname
     ```
4. Ensure `FLASK_ENV` (or config selection) points to production or export `FLASK_APP=run.py` and use a production WSGI server (gunicorn / waitress / uwsgi). Example (Linux/macOS):
   ```bash
   pip install gunicorn
   gunicorn 'run:app'
   ```
5. Run migrations against the production DB:
   ```
   flask db upgrade
   ```

### Creating New Migrations After Model Changes
Any time you modify models in `app/models.py`:

```
flask db migrate -m "Describe change"
flask db upgrade
```

If you see "No changes detected", ensure the app context can import models (run from project root, and that `FLASK_APP=run.py` is set). In PowerShell:

```powershell
$Env:FLASK_APP = "run.py"
flask db migrate -m "Add new field"
```

### Inspecting the Current Database
SQLite quick check:
```
python -c "import sqlite3; import os; db='billpay.db'; print('Exists:', os.path.exists(db)); print(sqlite3.connect(db).execute('select name from sqlite_master where type=\'table\'').fetchall())"
```

PostgreSQL (psql):
```
psql $DATABASE_URL -c "\dt"
```

### Switching from SQLite to PostgreSQL
1. Set `DATABASE_URL` to your Postgres URI.
2. (Optional) Dump existing SQLite data if you want to migrate content manually.
3. Run `flask db upgrade` on the new target.
4. Relink Plaid accounts (access tokens are environment-specific and not portable unless you migrate encrypted tokens carefully and keep the same `ENCRYPTION_KEY`).

### Common DB Issues
| Symptom | Cause | Fix |
|---------|-------|-----|
| `sqlite3.OperationalError: no such table` | Forgot migrations / upgrade | Run `flask db upgrade` |
| `No changes detected` on migrate | Models not imported | Ensure `FLASK_APP` set and run from project root |
| `psycopg2` not installed | Using Postgres without driver | `pip install psycopg2-binary` |
| Data lost after restart (prod) | Using ephemeral SQLite on a dyno | Switch to persistent Postgres service |

### Minimum Steps (You Haven't Set Up a DB Yet)
You can rely on SQLite immediately—just run:
```
flask db upgrade
```

## Testing & Modes

The application supports two runtime modes controlled by the feature flag `USE_PLAID`:

| Mode | USE_PLAID value | Behavior |
|------|-----------------|----------|
| Manual Entry (default) | unset / `false` | All financial data entered via the UI forms. Plaid client not initialized. Plaid tests skipped. |
| Plaid Enabled | `true` | Plaid client attempts initialization (sandbox/production depending on env vars). Plaid tests run (unless filtered). |

### Running the Test Suite (Manual Mode)
```
pytest -q
```
You will see Plaid-specific tests reported as skipped (`s`).

### Running Only Plaid Tests
```
$Env:USE_PLAID = "true"   # PowerShell
pytest -m plaid -q
```

### Running Full Suite Including Plaid
```
$Env:USE_PLAID = "true"
pytest -q
```

### Excluding Plaid Tests Explicitly
If `USE_PLAID` is true but you want to ignore those tests:
```
pytest -m "not plaid" -q
```

### Plaid Test Marker
Plaid-dependent tests use the custom marker `@pytest.mark.plaid` (registered in `tests/conftest.py`). Collection logic automatically skips them when `USE_PLAID` is falsy, so you don't need individual `skipif` decorators in each test.

### Warning Filters
`pytest.ini` suppresses the `datetime.utcnow()` deprecation warning originating from `flask_login` to keep output clean.

### Local Toggle Script (Optional Future Enhancement)
A helper script (planned) can toggle the `USE_PLAID` flag in `.env` for convenience. For now, export the variable in your shell before running.

### Quick Diagnostic Command
Check which mode you're in from an interactive shell:
```python
from app import create_app
app = create_app('testing')
print('USE_PLAID =', app.config['USE_PLAID'])
```

This will create `billpay.db` automatically with all tables. No further action needed for local testing.

## Authentication & User Management

BillPay now includes a real authentication system (replacing prior development auto-login) with:

- User registration (`/register`)
- Login (`/login`)
- Logout (`/logout`)
- Password reset request (`/forgot-password`) and reset (`/reset-password/<token>`)
- Role support: `user` (default) and `admin`
- Admin panel placeholder (`/admin`)

### Registration Flow
1. Visit `/register`
2. Provide a unique email + password (min 8 chars)
3. After successful registration you're prompted to log in.

### Login Flow
1. Visit `/login`
2. Enter email + password
3. Optional Remember Me (session persistence)
4. Redirected to dashboard on success.

### Password Reset (Development Mode)
- Visit `/forgot-password` and enter your email.
- A signed token link is logged to the server console and also shown in the UI (development convenience).
- Navigate to the link to set a new password.
- Tokens expire after 1 hour (configurable via code change).

### Roles
- Users are created with role `user`.
- Admins have `role='admin'` and access the `/admin` route.
- A convenience property `User.is_admin` is available for checks and an `admin_required` decorator protects admin routes.

### Seeding an Admin User
Set environment variables before first run:
```
ADMIN_SEED_EMAIL=admin@example.com
ADMIN_SEED_PASSWORD=ChangeMe123!
```
On startup if that email does not exist it is created with `role='admin'`.

PowerShell example:
```powershell
$Env:ADMIN_SEED_EMAIL = "admin@example.com"
$Env:ADMIN_SEED_PASSWORD = "ChangeMe123!"
python run.py
```

### Database Schema Change (Role Column)
The `user` table now includes a `role` column. For SQLite dev environments the app performs a light auto-migration (adds the column if missing). For production (e.g., Postgres), run an Alembic migration:
```powershell
$Env:FLASK_APP = "run.py"
flask db migrate -m "Add user role"
flask db upgrade
```

### Security Notes / Hardening Roadmap
- Replace dev token display with real email delivery (Flask-Mail, SendGrid, etc.)
- Add rate limiting (Flask-Limiter) to login and password reset endpoints
- Add email confirmation step for new users (optional)
- Add multi-factor authentication for admin users
- Enforce stronger password complexity in production
- Track last login and failed attempts for auditing

### Testing the Auth Stack Quickly
```powershell
# (Optional) seed an admin
$Env:ADMIN_SEED_EMAIL = "admin@example.com"
$Env:ADMIN_SEED_PASSWORD = "ChangeMe123!"

# Run the app
python run.py

# Steps:
# 1. Register a normal user at http://127.0.0.1:5000/register
# 2. Log out, then log in at /login
# 3. Request password reset at /forgot-password and use displayed token
# 4. Log in as admin with seeded credentials and visit /admin
```


## Plaid Integration

BillPay uses the following Plaid products:
- Auth & Accounts: For account details and balances
- Transactions: For all bank and credit transactions
- Liabilities: For loans, credit card bills, and mortgage information
- Income (optional): For paycheck and deposit stream data

## Plaid Sandbox Setup & Workflow

This project is pre‑configured to work smoothly with the Plaid Sandbox. Follow the steps below to link test institutions, pull data, and refresh it during development.

### 1. Required Environment Variables
Create (or update) your `.env` file using the values from your Plaid Dashboard (Sandbox):

```
PLAID_CLIENT_ID=your-sandbox-client-id
PLAID_SECRET_SANDBOX=your-sandbox-secret   # Prefer explicit env-specific names now
PLAID_ENV=sandbox
PLAID_PRODUCTS=transactions,auth
PLAID_COUNTRY_CODES=US,CA
PLAID_REDIRECT_URI=   # (leave blank unless you have registered one in Plaid dashboard)

# App / Flask
FLASK_APP=run.py
FLASK_ENV=development
SECRET_KEY=replace-this-with-a-long-random-string

# Optional explicit encryption key (Fernet 32 url-safe base64 bytes). If omitted, an ephemeral key is generated each run.
ENCRYPTION_KEY=
```

See `.env.example` for a reference template. If `ENCRYPTION_KEY` is not set the app will warn you and generate a temporary one (linked Plaid access tokens will become unreadable on restart if you change keys).

### 2. Start the App
```
flask run
```
Visit `http://127.0.0.1:5000/` and log in / auto‑login (the development auth flow may auto‑authenticate a test user depending on current config).

### 3. Create / Refresh a Link Token
On the dashboard or accounts screen you should see a "Link Accounts" (or similar) button. This triggers a call to create a fresh Plaid link token with the sanitized product list (`transactions, auth`). If you add products in `.env` that are not enabled in your Sandbox account they will be automatically filtered out to avoid `INVALID_PRODUCT` errors.

### 4. Use Sandbox Test Credentials
When the Plaid Link modal opens choose a test institution (e.g., "First Platypus Bank"). Use any of the [Plaid Sandbox test credentials](https://plaid.com/docs/sandbox/test-credentials/), for example:

```
username: user_good
password: pass_good
```

### 5. Fetching & Refreshing Data
After linking, the app will automatically pull accounts and initial transactions. You can manually refresh via buttons (e.g., "Refresh Accounts", "Refresh Transactions") which call backend endpoints that re-hit Plaid and update stored data.

### 6. Common Sandbox Errors & Fixes
| Error Code | Cause | Resolution |
|------------|-------|------------|
| `INVALID_PRODUCT` | A product listed in `PLAID_PRODUCTS` not enabled for your key | Remove it from `.env` or rely on built-in filtering (it will retry without unauthorized products). |
| `INVALID_FIELD` with `redirect_uri` | `PLAID_REDIRECT_URI` provided but not registered | Clear the env var or register the URI in the Plaid dashboard. |
| `PRODUCT_NOT_ENABLED` later in sync | Product newly added to `.env` but not approved | Request enablement in Plaid dashboard or remove until approved. |
| Token decrypt error / missing data after restart | Changed or removed `ENCRYPTION_KEY` between runs | Set a persistent `ENCRYPTION_KEY` before first real link and keep it stable. |

### 7. Adjusting Products
Update `PLAID_PRODUCTS` in `.env` (comma separated). Supported examples: `transactions,auth,liabilities,income`. The app will sanitize & log the final list on startup. Only keep what you actively use to reduce latency and error surface.

In the Sandbox, you can optionally enable extra products for exploration by setting:

```
SANDBOX_ALLOW_ADVANCED_PRODUCTS=true
```

When this flag is true and `PLAID_ENV=sandbox`, the app will allow `liabilities` and `income` in the requested product list. We still filter highly gated products like `assets` and `investments` by default.

### 8. Security Notes (Development vs Production)
Development conveniences (e.g., auto-login shortcuts) should be disabled for production:
1. Ensure real authentication (remove any auto-login test user logic).
2. Set a strong, persistent `SECRET_KEY` and `ENCRYPTION_KEY`.
3. Use HTTPS in production and rotate Plaid secrets if exposed.

### 9. Migrating From Sandbox to Development/Production (Re‑Enable Plaid Securely)
The application now supports environment‑specific Plaid secrets. You can keep both sandbox and production values in your deployment environment (NOT committed) and switch using `PLAID_ENV`.

Supported secret variables (checked in this order):
| Active `PLAID_ENV` | Preferred Secret Var | Fallback |
|--------------------|----------------------|----------|
| `sandbox`          | `PLAID_SECRET_SANDBOX` | `PLAID_SECRET` |
| `production`       | `PLAID_SECRET_PRODUCTION` | `PLAID_SECRET` |

Steps:
1. Keep `USE_PLAID=false` while configuring production secrets.
2. Set:
   - `PLAID_CLIENT_ID=<your real client id>`
   - `PLAID_SECRET_PRODUCTION=<your production secret>`
   - Leave `PLAID_SECRET_SANDBOX` in place for rollback if desired.
3. Switch `PLAID_ENV=production`.
4. (Optional) Run a health check (planned script) or start the app locally with production keys only if on a secured machine / VPN.
5. Flip `USE_PLAID=true` and restart. Logs will show masked confirmation:
   `Plaid production mode enabled (secret length=XX, tail=***1234).`
6. Perform a fresh Plaid Link. Sandbox items cannot be promoted; users must relink.

Safety Guards Implemented:
* Secret never fully logged (only last 4 chars + length).
* If `PLAID_ENV=production` but the secret string contains `sandbox`, an error is logged and you should rotate / correct.
* Missing client id or secret halts Plaid client initialization gracefully (manual mode still works).

Rollback to Sandbox:
1. Set `USE_PLAID=false` (optional pause).
2. Switch `PLAID_ENV=sandbox`.
3. Ensure `PLAID_SECRET_SANDBOX` present.
4. Set `USE_PLAID=true` and restart.

Minimal Production Variable Set Example (PowerShell):
```powershell
$Env:USE_PLAID = "true"
$Env:PLAID_ENV = "production"
$Env:PLAID_CLIENT_ID = "prod_client_id_here"
$Env:PLAID_SECRET_PRODUCTION = "prod_secret_value_here"
python run.py
```

Do NOT commit these values to the repository. Use platform secret managers or deployment env var configuration (Heroku, Render, Railway, Docker secrets, etc.).

### 10. Regenerating a Fernet Encryption Key
If you need to set `ENCRYPTION_KEY` manually:
```python
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
```
Place that value in `.env`. Changing it after items are linked will make previously stored Plaid access tokens unreadable; you'd need users to relink.

### 11. Troubleshooting Quick Checklist
1. Link modal fails immediately: Check network console for 4xx; verify `PLAID_CLIENT_ID` / `PLAID_SECRET`.
2. Repeated `INVALID_PRODUCT`: Remove unsupported products; confirm Plaid dashboard enablement.
3. Blank charts: Check browser console for JSON parse errors; ensure script tag with chart data is present in dashboard HTML.
4. No refresh effect: Confirm the refresh endpoint returns 200 and inspect server logs for Plaid fetch errors.

### 12. Unlink / Reset Plaid (Sandbox Testing)

If you want to start over (avoid duplicated account balances in net worth):

1. Click the new `Unlink Plaid` button on the dashboard (only visible when already linked).
2. This calls `POST /api/plaid/unlink` with `{ "reset": true }` which:
   - Clears `plaid_access_token` and `item_id`.
   - Deletes all Accounts & Transactions for the user.
   - Deletes only Plaid-created Bills (those with `plaid_bill_id`) and Plaid-created Income (with `plaid_income_id`).
3. Re-link using the standard Plaid Link flow.

Safety: Manually added Bills and Income (without Plaid IDs) are preserved unless you delete them yourself—so you can keep custom budgeting data while swapping out bank data.

Sandbox Mode Banner: When running with `PLAID_ENV=sandbox` an informational banner appears indicating data is synthetic Plaid Sandbox test data.

---

If you encounter a new issue, search server logs first (they include sanitized Plaid product lists and any filtered retries) before filing an issue.

## Sandbox Checkouts (Branch: `sandbox-checkouts`)

This branch focuses on exploring Plaid Sandbox data and flows.

- Default local `.env` on this branch is set to Sandbox with expanded products:
   - `PLAID_ENV=sandbox`
   - `PLAID_PRODUCTS=transactions,auth,liabilities,income`
   - `SANDBOX_ALLOW_ADVANCED_PRODUCTS=true`

- Toggle Plaid and environment via the helper script:
   - Enable Plaid in sandbox: `python modectl.py plaid on sandbox`
   - Enable Plaid in production: `python modectl.py plaid on production`
   - Disable Plaid: `python modectl.py plaid off`

- Notes on Sandbox data:
   - Test institutions often return 2–3 depository accounts (e.g., checking/savings, sometimes credit).
   - The number of accounts shown is dictated by the institution’s sandbox profile, not limited by our code. We ingest all accounts returned by Plaid (`/accounts/get`).
   - To simulate bills and liabilities, include the `liabilities` product and use institutions that expose credit or loan accounts in Sandbox.
   - Income is synthesized by our app from deposits when using `fetch_income()`; setting `SANDBOX_ALLOW_ADVANCED_PRODUCTS=true` lets you also explore Plaid’s income products if your keys have access.

- Quick start on this branch:
   1. Ensure Sandbox keys in `.env` (`PLAID_CLIENT_ID`, `PLAID_SECRET_SANDBOX`).
   2. `PLAID_ENV=sandbox`, `USE_PLAID=true`.
   3. Run `python run.py` and link with a sandbox institution (e.g., First Platypus Bank, user_good/pass_good).
   4. Use Accounts/Transactions refresh to pull data; try enabling `liabilities` to generate Bill records from credit cards/loans.

## Development

### Project Structure

```
finance_app/
│
├── app/
│   ├── __init__.py
│   ├── models.py
│   ├── plaid_service.py
│   ├── forms.py
│   ├── routes/
│   │   ├── auth.py
│   │   ├── dashboard.py
│   │   ├── accounts.py
│   │   ├── transactions.py
│   │   ├── bills.py
│   │   ├── income.py
│   │   └── plaid_webhook.py
│   ├── templates/
│   │   ├── base.html
│   │   ├── landing.html
│   │   ├── auth/
│   │   ├── dashboard/
│   │   ├── accounts/
│   │   ├── transactions/
│   │   ├── bills/
│   │   ├── income/
│   │   └── partials/
│   └── static/
│       ├── css/
│       └── js/
│
├── migrations/
├── tests/
│   ├── test_plaid.py
│   ├── test_models.py
│   └── test_routes.py
├── config.py
├── run.py
└── requirements.txt
```

### Running Tests

```
pytest
```

## Deployment

BillPay can be deployed to platforms like Heroku, Fly.io, or any other platform that supports Python applications.

For production deployment:
1. Set environment variables for production
2. Configure a PostgreSQL database
3. Use gunicorn as the WSGI server

## License

[MIT License](LICENSE)

## Acknowledgements

- [Plaid API](https://plaid.com/docs/) - Financial data connectivity
- [Flask](https://flask.palletsprojects.com/) - Web framework
- [Bootstrap](https://getbootstrap.com/) - Frontend components
- [Chart.js](https://www.chartjs.org/) - Interactive charts

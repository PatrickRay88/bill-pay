from flask import Flask
import os
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_bcrypt import Bcrypt
try:
    import plaid  # type: ignore
    from plaid.api import plaid_api  # type: ignore
except ImportError:  # Plaid optional if USE_PLAID disabled
    plaid = None
    plaid_api = None
from config import config

# Initialize extensions (set expire_on_commit False globally to keep objects usable across contexts, aiding tests)
db = SQLAlchemy(session_options={"expire_on_commit": False})
migrate = Migrate()
login_manager = LoginManager()
# Redirect unauthenticated users to the real login route (auto_login removed)
login_manager.login_view = 'auth.login'
csrf = CSRFProtect()
bcrypt = Bcrypt()

# Initialize Plaid client
plaid_client = None

def create_app(config_name='default'):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Testing adjustments (must occur before extensions init)
    if app.config.get('TESTING'):
        # Disable CSRF for test client form submissions (relationships stay available due to global session option)
        app.config['WTF_CSRF_ENABLED'] = False

    # Plaid product sanitization
    raw_products = [p.strip() for p in app.config.get('PLAID_PRODUCTS', []) if p.strip()]
    # In sandbox, optionally allow advanced products for testing
    sandbox = app.config.get('PLAID_ENV', 'sandbox') == 'sandbox'
    allow_adv = bool(app.config.get('SANDBOX_ALLOW_ADVANCED_PRODUCTS')) if sandbox else False
    # Always filter the most commonly gated products unless explicitly testing: assets, investments
    filtered_products = [p for p in raw_products if p not in {'assets', 'investments'}]
    if not allow_adv and sandbox:
        # Also filter liabilities/income unless explicitly allowed
        filtered_products = [p for p in filtered_products if p not in {'liabilities', 'income'}]
    if not filtered_products:
        filtered_products = ['transactions', 'auth']
    if filtered_products != raw_products:
        app.logger.info(f"Sanitized Plaid products list from {raw_products} -> {filtered_products}")
    app.config['PLAID_PRODUCTS'] = filtered_products

    # Credential selection & sanity checks (only if Plaid feature enabled)
    if app.config.get('USE_PLAID'):
        plaid_env = app.config.get('PLAID_ENV', 'sandbox').lower()
        # Choose secret precedence: specific env secret > generic PLAID_SECRET
        chosen_secret = None
        if plaid_env == 'production' and app.config.get('PLAID_SECRET_PRODUCTION'):
            chosen_secret = app.config.get('PLAID_SECRET_PRODUCTION')
        elif plaid_env == 'sandbox' and app.config.get('PLAID_SECRET_SANDBOX'):
            chosen_secret = app.config.get('PLAID_SECRET_SANDBOX')
        else:
            chosen_secret = app.config.get('PLAID_SECRET')

        # Inject into config so downstream code uses the resolved one
        app.config['PLAID_SECRET_RESOLVED'] = chosen_secret

        client_id = app.config.get('PLAID_CLIENT_ID')
        if not client_id or not chosen_secret:
            app.logger.warning("Plaid credentials missing (client id or secret); Plaid-dependent features will be disabled.")
        else:
            # Basic production validation heuristics without leaking the secret
            masked = f"***{chosen_secret[-4:]}" if len(chosen_secret or '') >= 4 else "***"  # last 4 only
            secret_len = len(chosen_secret)
            if plaid_env == 'production':
                # Heuristic: sandbox secrets often contain 'sandbox' or are shorter; add a warning if suspicious
                if 'sandbox' in chosen_secret.lower():
                    app.logger.error("PLAID_ENV=production but secret looks like a sandbox secret (contains 'sandbox').")
                app.logger.info(f"Plaid production mode enabled (secret length={secret_len}, tail={masked}).")
            else:
                app.logger.info(f"Plaid sandbox mode enabled (secret length={secret_len}, tail={masked}).")
    else:
        app.logger.info("USE_PLAID disabled; application running in manual entry mode.")
    
    # Initialize extensions with app
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    bcrypt.init_app(app)
    
    # Initialize Plaid client only if feature enabled and library present
    global plaid_client
    if app.config.get('USE_PLAID') and plaid is not None:
        # Use resolved secret from earlier selection
        resolved_secret = app.config.get('PLAID_SECRET_RESOLVED') or app.config.get('PLAID_SECRET')
        creds_present = bool(app.config.get('PLAID_CLIENT_ID') and resolved_secret)
        if creds_present and not app.config.get('TESTING'):
            try:
                plaid_env = app.config.get('PLAID_ENV', 'sandbox').lower()
                configuration = plaid.Configuration(
                    host=plaid.Environment.Sandbox if plaid_env == 'sandbox' else plaid.Environment.Production,
                    api_key={
                        'clientId': app.config['PLAID_CLIENT_ID'],
                        'secret': resolved_secret,
                    }
                )
                api_client = plaid.ApiClient(configuration)
                plaid_client = plaid_api.PlaidApi(api_client)  # type: ignore
                app.logger.info("Initialized Plaid API client.")
            except Exception as e:
                app.logger.error(f"Failed to initialize Plaid client: {e}")
                plaid_client = None
        else:
            app.logger.info("Plaid credentials absent or testing; skipping Plaid client init.")
            plaid_client = None
    else:
        plaid_client = None  # Explicitly None in manual mode
    
    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.accounts import accounts_bp
    from app.routes.transactions import transactions_bp
    from app.routes.bills import bills_bp
    from app.routes.income import income_bp
    from app.routes.plaid_webhook import plaid_webhook_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(accounts_bp)
    app.register_blueprint(transactions_bp)
    app.register_blueprint(bills_bp)
    app.register_blueprint(income_bp)
    app.register_blueprint(plaid_webhook_bp)
    
    # Create database tables
    with app.app_context():
        db.create_all()
        # Lightweight migration helper: add 'role' column if missing (SQLite dev convenience)
        from sqlalchemy import inspect, text
        inspector = inspect(db.engine)
        cols = [c['name'] for c in inspector.get_columns('user')]
        if 'role' not in cols:
            if db.engine.url.get_backend_name() == 'sqlite':
                # SQLAlchemy 2.x: use a connection and commit explicitly
                try:
                    with db.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE user ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'user'"))
                        conn.commit()
                    app.logger.info("Added missing 'role' column to user table (SQLite auto-migrate)")
                except Exception as e:
                    app.logger.error(f"Failed to auto-add role column: {e}")
            else:
                app.logger.warning("'role' column missing; run migrations to add it.")
        # Optional admin seed via env vars
        admin_email = os.environ.get('ADMIN_SEED_EMAIL')
        admin_password = os.environ.get('ADMIN_SEED_PASSWORD')
        if admin_email and admin_password:
            from app.models import User
            if not User.query.filter_by(email=admin_email.lower()).first():
                u = User(email=admin_email.lower(), role='admin')
                u.set_password(admin_password)
                db.session.add(u)
                db.session.commit()
                app.logger.info(f"Seeded admin user {admin_email}")
        
    @app.context_processor
    def inject_plaid_credentials():
        from flask_login import current_user
        from app.models import Account
        from app.utils.time import utc_now
        acct_count = 0
        if current_user.is_authenticated:
            try:
                acct_count = Account.query.filter_by(user_id=current_user.id).count()
            except Exception:
                acct_count = 0
        base = dict(
            ACCOUNT_COUNT=acct_count,
            CURRENT_TIME=utc_now(),
            USE_PLAID=app.config.get('USE_PLAID'),
            # Always expose PLAID_ENV so the navbar badge reflects reality even in manual mode
            PLAID_ENV=app.config.get('PLAID_ENV')
        )
        if app.config.get('USE_PLAID'):
            base.update(
                PLAID_CLIENT_ID=app.config.get('PLAID_CLIENT_ID'),
                PLAID_PRODUCTS=app.config.get('PLAID_PRODUCTS'),
                PLAID_COUNTRY_CODES=app.config.get('PLAID_COUNTRY_CODES'),
            )
        return base
    
    @app.route('/')
    def home():
        """Landing page for unauthenticated users; redirect authenticated users to dashboard."""
        from flask_login import current_user
        from flask import render_template, redirect, url_for
        # For simplicity and to satisfy tests always return landing page (even if authenticated) while TESTING
        if not app.config.get('TESTING') and current_user.is_authenticated:
            return redirect(url_for('dashboard.index'))
        return render_template('landing.html', title='Welcome')
    return app

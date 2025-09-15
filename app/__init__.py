from flask import Flask
import os
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_bcrypt import Bcrypt
import plaid
from plaid.api import plaid_api
from config import config

# Initialize extensions
db = SQLAlchemy()
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

    # Plaid product sanitization: remove products that commonly trigger INVALID_PRODUCT in sandbox
    raw_products = [p.strip() for p in app.config.get('PLAID_PRODUCTS', []) if p.strip()]
    unauthorized_prone = {'income', 'liabilities', 'assets', 'investments'}
    filtered_products = [p for p in raw_products if p not in unauthorized_prone]
    if not filtered_products:
        filtered_products = ['transactions', 'auth']
    if filtered_products != raw_products:
        app.logger.info(f"Sanitized Plaid products list from {raw_products} -> {filtered_products}")
    app.config['PLAID_PRODUCTS'] = filtered_products

    # Credential sanity checks
    if not app.config.get('PLAID_CLIENT_ID') or not app.config.get('PLAID_SECRET'):
        app.logger.warning("Plaid credentials missing; Plaid-dependent features will be disabled.")
    elif app.config.get('PLAID_ENV', 'sandbox').lower() == 'sandbox':
        app.logger.info(f"Running in Plaid sandbox with products: {app.config['PLAID_PRODUCTS']}")
    
    # Initialize extensions with app
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    bcrypt.init_app(app)
    
    # Initialize Plaid client
    global plaid_client
    
    # Set Plaid environment based on configuration
    plaid_env = app.config['PLAID_ENV'].lower()
    
    configuration = plaid.Configuration(
        host=plaid.Environment.Sandbox if plaid_env == 'sandbox' else plaid.Environment.Production,
        api_key={
            'clientId': app.config['PLAID_CLIENT_ID'],
            'secret': app.config['PLAID_SECRET'],
        }
    )
    
    api_client = plaid.ApiClient(configuration)
    plaid_client = plaid_api.PlaidApi(api_client)
    
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
        acct_count = 0
        if current_user.is_authenticated:
            try:
                acct_count = Account.query.filter_by(user_id=current_user.id).count()
            except Exception:
                acct_count = 0
        return dict(
            PLAID_CLIENT_ID=app.config['PLAID_CLIENT_ID'],
            PLAID_ENV=app.config['PLAID_ENV'],
            PLAID_PRODUCTS=app.config['PLAID_PRODUCTS'],
            PLAID_COUNTRY_CODES=app.config['PLAID_COUNTRY_CODES'],
            ACCOUNT_COUNT=acct_count
        )
    
    return app

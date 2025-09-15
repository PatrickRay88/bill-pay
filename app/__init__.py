from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_bcrypt import Bcrypt
import plaid
from config import config

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
csrf = CSRFProtect()
bcrypt = Bcrypt()

# Initialize Plaid client
plaid_client = None

def create_app(config_name='default'):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Initialize extensions with app
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    bcrypt.init_app(app)
    
    # Initialize Plaid client
    global plaid_client
    plaid_client = plaid.Client(
        client_id=app.config['PLAID_CLIENT_ID'],
        secret=app.config['PLAID_SECRET'],
        environment=app.config['PLAID_ENV'],
        api_version='2020-09-14'
    )
    
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
        
    @app.context_processor
    def inject_plaid_credentials():
        return dict(
            PLAID_CLIENT_ID=app.config['PLAID_CLIENT_ID'],
            PLAID_ENV=app.config['PLAID_ENV'],
            PLAID_PRODUCTS=app.config['PLAID_PRODUCTS'],
            PLAID_COUNTRY_CODES=app.config['PLAID_COUNTRY_CODES']
        )
    
    return app

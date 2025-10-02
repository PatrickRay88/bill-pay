import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Base configuration.

    NOTE: Do not hard-code Plaid secrets here. Provide them via environment variables.
    Supports optional environment-specific secrets:
        PLAID_SECRET_SANDBOX
        PLAID_SECRET_PRODUCTION
    Fallback precedence for the active secret (in create_app):
        1. Specific env secret (e.g. PLAID_SECRET_PRODUCTION when PLAID_ENV=production)
        2. Generic PLAID_SECRET
        3. None (feature disabled / warning logged)
    """
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')
    FLASK_APP = os.environ.get('FLASK_APP', 'run.py')
    FLASK_ENV = os.environ.get('FLASK_ENV', 'development')
    # Feature flags
    USE_PLAID = os.environ.get('USE_PLAID', 'false').lower() in ('1', 'true', 'yes', 'on')

    # Database settings
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///billpay.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Plaid API base settings
    PLAID_CLIENT_ID = os.environ.get('PLAID_CLIENT_ID')
    PLAID_SECRET = os.environ.get('PLAID_SECRET')  # generic secret (backwards compatibility)
    PLAID_SECRET_SANDBOX = os.environ.get('PLAID_SECRET_SANDBOX')
    PLAID_SECRET_PRODUCTION = os.environ.get('PLAID_SECRET_PRODUCTION')
    # Normalize environment to only 'sandbox' or 'production' (Plaid modes)
    _raw_env = os.environ.get('PLAID_ENV', 'sandbox').strip().lower()
    PLAID_ENV = 'sandbox' if _raw_env == 'sandbox' else 'production'
    PLAID_REDIRECT_URI = os.environ.get('PLAID_REDIRECT_URI', 'http://localhost:5000/plaid/oauth-response')
    # Limit default products to core ones; include liabilities for converting minimum payments into Bills
    PLAID_PRODUCTS = os.environ.get('PLAID_PRODUCTS', 'transactions,auth,liabilities').split(',')
    PLAID_COUNTRY_CODES = os.environ.get('PLAID_COUNTRY_CODES', 'US').split(',')

    # Sandbox tuning: optionally allow advanced products in sandbox
    # When true and PLAID_ENV=sandbox, we won't filter out 'liabilities' or 'income' during startup.
    SANDBOX_ALLOW_ADVANCED_PRODUCTS = os.environ.get('SANDBOX_ALLOW_ADVANCED_PRODUCTS', 'false').lower() in ('1','true','yes','on')

class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    

class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    USE_PLAID = False  # Force disable Plaid in tests to simplify manual-entry mode
    

class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    TESTING = False
    # Force production environment selection for Plaid
    PLAID_ENV = 'production'
    # If USE_PLAID not explicitly set, default to true in production
    USE_PLAID = os.environ.get('USE_PLAID', 'true').lower() in ('1','true','yes','on')
    # Allow a production‑specific product list override (PLAID_PRODUCTS_PRODUCTION)
    _prod_products = os.environ.get('PLAID_PRODUCTS_PRODUCTION')
    if _prod_products:
        PLAID_PRODUCTS = [p.strip() for p in _prod_products.split(',') if p.strip()]
    # Prefer an external database; fall back to sqlite with a warning marker
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///site.db'
    

config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

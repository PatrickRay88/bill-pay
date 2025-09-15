import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')
    FLASK_APP = os.environ.get('FLASK_APP', 'run.py')
    FLASK_ENV = os.environ.get('FLASK_ENV', 'development')
    
    # Database settings
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///billpay.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Plaid API settings
    PLAID_CLIENT_ID = os.environ.get('PLAID_CLIENT_ID')
    PLAID_SECRET = os.environ.get('PLAID_SECRET')
    PLAID_ENV = os.environ.get('PLAID_ENV', 'sandbox')  # sandbox, development, or production
    PLAID_REDIRECT_URI = os.environ.get('PLAID_REDIRECT_URI', 'http://localhost:5000/plaid/oauth-response')
    PLAID_PRODUCTS = os.environ.get('PLAID_PRODUCTS', 'transactions,auth,income,liabilities').split(',')
    PLAID_COUNTRY_CODES = os.environ.get('PLAID_COUNTRY_CODES', 'US').split(',')

class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    

class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    

class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    TESTING = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    

config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

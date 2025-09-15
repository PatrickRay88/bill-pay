import pytest
from flask import url_for
from app import create_app, db
from app.models import User

@pytest.fixture
def app():
    app = create_app('testing')
    
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def runner(app):
    return app.test_cli_runner()

def test_landing_page(client):
    response = client.get('/')
    assert response.status_code == 200
    assert b'Welcome to BillPay' in response.data

def test_login_page(client):
    response = client.get('/login')
    assert response.status_code == 200
    assert b'Sign in to your account' in response.data

def test_register_page(client):
    response = client.get('/register')
    assert response.status_code == 200
    assert b'Create a new account' in response.data

def test_user_registration(client, app):
    response = client.post('/register', data={
        'email': 'test@example.com',
        'password': 'password123',
        'confirm_password': 'password123'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    
    # Check that the user was created
    with app.app_context():
        user = User.query.filter_by(email='test@example.com').first()
        assert user is not None

def test_user_login(client, app):
    # Create a test user
    with app.app_context():
        user = User(email='test@example.com')
        user.set_password('password123')
        db.session.add(user)
        db.session.commit()
    
    # Try to login
    response = client.post('/login', data={
        'email': 'test@example.com',
        'password': 'password123',
        'remember': False
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b'Dashboard' in response.data

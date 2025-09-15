from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, current_user
from werkzeug.security import generate_password_hash
from app import db
from app.models import User

auth_bp = Blueprint('auth', __name__)

# Create a test user for development
TEST_USER_EMAIL = "test@example.com"
TEST_USER_PASSWORD = "password123"

def create_test_user():
    """Create a test user if it doesn't exist."""
    user = User.query.filter_by(email=TEST_USER_EMAIL).first()
    if not user:
        user = User(email=TEST_USER_EMAIL)
        user.set_password(TEST_USER_PASSWORD)
        db.session.add(user)
        db.session.commit()
    return user

@auth_bp.route('/auto_login')
def auto_login():
    """Automatically log in as the test user."""
    user = create_test_user()
    login_user(user)
    flash('Auto-logged in as test user', 'info')
    return redirect(url_for('dashboard.index'))

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Redirect to auto login during development."""
    return redirect(url_for('auth.auto_login'))

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Redirect to auto login during development."""
    return redirect(url_for('auth.auto_login'))
    
    return render_template('auth/register.html', form=form, title='Register')

@auth_bp.route('/logout')
def logout():
    """User logout."""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.auto_login'))

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, current_user, login_required
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from app import db
from app.models import User
from app.forms import LoginForm, RegisterForm
from werkzeug.security import generate_password_hash

auth_bp = Blueprint('auth', __name__)
############################################
# Utility
############################################

def _serializer():
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'], salt='password-reset')

def generate_reset_token(user_id):
    return _serializer().dumps({'user_id': user_id})

def verify_reset_token(token, max_age=3600):
    try:
        data = _serializer().loads(token, max_age=max_age)
        return data.get('user_id')
    except (BadSignature, SignatureExpired):
        return None

############################################
# Authentication Routes
############################################

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            flash('Logged in successfully.', 'success')
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('dashboard.index'))
        else:
            flash('Invalid email or password.', 'danger')
    return render_template('auth/login.html', form=form, title='Login')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    form = RegisterForm()
    if form.validate_on_submit():
        email = form.email.data.lower()
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'warning')
        else:
            user = User(email=email)
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            flash('Account created. Please log in.', 'success')
            return redirect(url_for('auth.login'))
    return render_template('auth/register.html', form=form, title='Register')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))

############################################
# Password Reset
############################################
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, PasswordField
from wtforms.validators import DataRequired, Email, Length, EqualTo

class RequestPasswordResetForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Send Reset Link')

class ResetPasswordForm(FlaskForm):
    password = PasswordField('New Password', validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Reset Password')

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    form = RequestPasswordResetForm()
    token = None
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()
        if user:
            token = generate_reset_token(user.id)
            current_app.logger.info(f"Password reset token for {user.email}: {token}")
            flash('Password reset link generated (logged to server).', 'info')
        else:
            flash('If that email exists, a reset link was generated (dev mode).', 'info')
    return render_template('auth/forgot_password.html', form=form, title='Forgot Password', token=token)

@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    user_id = verify_reset_token(token)
    if not user_id:
        flash('Invalid or expired token.', 'danger')
        return redirect(url_for('auth.forgot_password'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user = User.query.get(user_id)
        if not user:
            flash('User no longer exists.', 'danger')
            return redirect(url_for('auth.register'))
        user.set_password(form.password.data)
        db.session.commit()
        flash('Password updated. Please log in.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('auth/reset_password.html', form=form, title='Reset Password')

############################################
# Admin Example Route (placeholder)
############################################
from functools import wraps

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Admin access required.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return wrapper

@auth_bp.route('/admin')
@admin_required
def admin_panel():
    return render_template('auth/admin.html', title='Admin Panel')

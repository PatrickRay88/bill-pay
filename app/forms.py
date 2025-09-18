from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField, SubmitField, BooleanField, DecimalField, DateField,
    TextAreaField, SelectField, IntegerField
)
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional, NumberRange

class LoginForm(FlaskForm):
    """Login form."""
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')
    submit = SubmitField('Login')

class RegisterForm(FlaskForm):
    """Registration form."""
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[
        DataRequired(), 
        Length(min=8, message='Password must be at least 8 characters long.')
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(), 
        EqualTo('password', message='Passwords must match.')
    ])
    submit = SubmitField('Register')

class BillForm(FlaskForm):
    """Form for adding or editing a bill."""
    name = StringField('Bill Name', validators=[DataRequired()])
    amount = DecimalField('Amount', validators=[DataRequired()])
    due_date = DateField('Due Date', validators=[DataRequired()], format='%Y-%m-%d')
    frequency = SelectField('Frequency', choices=[
        ('one-time', 'One-time'),
        ('weekly', 'Weekly'),
        ('bi-weekly', 'Bi-Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('annually', 'Annually')
    ])
    category = StringField('Category', validators=[Optional()])
    status = SelectField('Status', choices=[
        ('unpaid', 'Unpaid'),
        ('paid', 'Paid'),
        ('pending', 'Pending')
    ])
    autopay = BooleanField('Autopay Enabled')
    notes = TextAreaField('Notes', validators=[Optional()])
    submit = SubmitField('Save')

class IncomeForm(FlaskForm):
    """Form for adding or editing an income source."""
    source = StringField('Source', validators=[DataRequired()])
    gross_amount = DecimalField('Gross Amount', validators=[DataRequired()])
    net_amount = DecimalField('Net Amount', validators=[Optional()])
    frequency = SelectField('Frequency', choices=[
        ('weekly', 'Weekly'),
        ('bi-weekly', 'Bi-Weekly'),
        ('semi-monthly', 'Semi-Monthly'),
        ('monthly', 'Monthly')
    ])
    date = DateField('Date', validators=[DataRequired()], format='%Y-%m-%d')
    notes = TextAreaField('Notes', validators=[Optional()])
    submit = SubmitField('Save')

class ProfileForm(FlaskForm):
    """Form for editing user profile."""
    email = StringField('Email', validators=[DataRequired(), Email()])
    current_password = PasswordField('Current Password', validators=[Optional()])
    new_password = PasswordField('New Password', validators=[Optional(), Length(min=8)])
    confirm_password = PasswordField('Confirm New Password', validators=[
        EqualTo('new_password', message='Passwords must match.')
    ])
    submit = SubmitField('Update Profile')


class AccountForm(FlaskForm):
    """Form for manual creation/editing of an account."""
    name = StringField('Account Name', validators=[DataRequired()])
    type = SelectField(
        'Type',
        choices=[
            ('depository', 'Depository'),
            ('credit', 'Credit'),
            ('loan', 'Loan'),
            ('investment', 'Investment'),
            ('other', 'Other')
        ],
        validators=[DataRequired()]
    )
    subtype = StringField('Subtype', validators=[Optional()])
    current_balance = DecimalField('Current Balance', validators=[Optional()])
    available_balance = DecimalField('Available Balance', validators=[Optional()])
    iso_currency_code = StringField('Currency', default='USD', validators=[Length(max=3), Optional()])
    submit = SubmitField('Save Account')


class TransactionForm(FlaskForm):
    """Form for manual creation/editing of a transaction."""
    account_id = SelectField('Account', coerce=int, validators=[DataRequired()])
    name = StringField('Description', validators=[DataRequired(), Length(max=255)])
    amount = DecimalField('Amount', validators=[DataRequired()])
    date = DateField('Date', validators=[DataRequired()], format='%Y-%m-%d')
    category = StringField('Category', validators=[Optional(), Length(max=100)])
    merchant_name = StringField('Merchant', validators=[Optional(), Length(max=150)])
    pending = BooleanField('Pending')
    notes = TextAreaField('Notes', validators=[Optional()])
    submit = SubmitField('Save Transaction')

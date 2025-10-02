from flask import Blueprint, render_template, jsonify, flash, redirect, url_for, request, current_app
from flask_login import current_user
from app import db
from app.models import Account, Transaction, PlaidItem
from app.plaid_service import fetch_accounts, create_link_token
from app.forms import AccountForm
import uuid

accounts_bp = Blueprint('accounts', __name__, url_prefix='/accounts')

@accounts_bp.route('/')
def index(*args, **kwargs):
    """Accounts overview page with optional Plaid connect button if not linked."""
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))

    # Generate a link token if user not yet linked to Plaid
    # Always allow linking another institution; generate a link token
    link_token = create_link_token(current_user.id) if current_app.config.get('USE_PLAID') else None

    accounts = Account.query.filter_by(user_id=current_user.id).all()
    plaid_items = PlaidItem.query.filter_by(user_id=current_user.id).all()

    # Group accounts by type
    account_groups = {}
    for account in accounts:
        account_groups.setdefault(account.type, []).append(account)

    return render_template(
        'accounts/index.html',
        title='Accounts',
        account_groups=account_groups,
    link_token=link_token,
    plaid_items=plaid_items
    )

@accounts_bp.route('/new', methods=['GET', 'POST'])
def create(*args, **kwargs):
    """Manual account creation (manual mode or supplemental)."""
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))

    form = AccountForm()
    if form.validate_on_submit():
        # Generate placeholder Plaid account id for uniqueness
        placeholder_plaid_id = f"MANUAL-{uuid.uuid4()}"
        account = Account(
            user_id=current_user.id,
            plaid_account_id=placeholder_plaid_id,
            name=form.name.data.strip(),
            type=form.type.data,
            subtype=form.subtype.data.strip() if form.subtype.data else None,
            current_balance=float(form.current_balance.data) if form.current_balance.data is not None else None,
            available_balance=float(form.available_balance.data) if form.available_balance.data is not None else None,
            iso_currency_code=form.iso_currency_code.data.strip().upper() if form.iso_currency_code.data else 'USD'
        )
        db.session.add(account)
        db.session.commit()
        flash('Account created successfully.', 'success')
        return redirect(url_for('accounts.detail', account_id=account.id))

    return render_template(
        'accounts/form.html',
        title='New Account',
        form=form
    )

@accounts_bp.route('/<int:account_id>')
def detail(account_id, *args, **kwargs):
    """Account detail page with recent transactions."""
    # Ensure user is authenticated
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    account = Account.query.filter_by(id=account_id, user_id=current_user.id).first_or_404()
    
    # Get recent transactions for this account
    transactions = Transaction.query.filter_by(account_id=account_id)\
        .order_by(Transaction.date.desc())\
        .limit(50).all()
    
    return render_template(
        'accounts/detail.html',
        title=f'Account: {account.name}',
        account=account,
        transactions=transactions
    )

@accounts_bp.route('/refresh')
def refresh(*args, **kwargs):
    """Refresh account data from Plaid."""
    # Ensure user is authenticated
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    if not current_user.plaid_access_token:
        flash("No Plaid connection found. Please connect your bank first.", "warning")
        return jsonify({"success": False, "message": "No Plaid connection found"})
    
    success, message = fetch_accounts(current_user)
    if success:
        flash("Accounts refreshed successfully!", "success")
        return jsonify({"success": True, "message": message})
    else:
        flash(f"Error refreshing accounts: {message}", "danger")
        return jsonify({"success": False, "message": message})

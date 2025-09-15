from flask import Blueprint, render_template, jsonify, flash
from flask_login import login_required, current_user
from app import db
from app.models import Account, Transaction
from app.plaid_service import fetch_accounts

accounts_bp = Blueprint('accounts', __name__, url_prefix='/accounts')

@accounts_bp.route('/')
@login_required
def index():
    """Accounts overview page."""
    # Get all accounts for the current user
    accounts = Account.query.filter_by(user_id=current_user.id).all()
    
    # Group accounts by type for better organization
    account_groups = {}
    for account in accounts:
        if account.type not in account_groups:
            account_groups[account.type] = []
        account_groups[account.type].append(account)
    
    return render_template(
        'accounts/index.html',
        title='Accounts',
        account_groups=account_groups
    )

@accounts_bp.route('/<int:account_id>')
@login_required
def detail(account_id):
    """Account detail page with recent transactions."""
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
@login_required
def refresh():
    """Refresh account data from Plaid."""
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

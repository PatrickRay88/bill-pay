from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import current_user
from datetime import datetime, timedelta
from app import db
from app.models import Transaction, Account
from app.plaid_service import fetch_transactions

transactions_bp = Blueprint('transactions', __name__, url_prefix='/transactions')

@transactions_bp.route('/')
def index(*args, **kwargs):
    """Transactions listing page with filters."""
    # Ensure user is authenticated (redirect to real login)
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    # Get filter parameters
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    category = request.args.get('category')
    account_id = request.args.get('account_id')
    search = request.args.get('search')
    
    # Default to last 30 days if no dates provided
    if not start_date:
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    if not end_date:
        end_date = datetime.now().strftime('%Y-%m-%d')
        
    # Convert string dates to date objects
    start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
    end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    # Build the query
    query = Transaction.query.filter_by(user_id=current_user.id)
    query = query.filter(Transaction.date.between(start_date_obj, end_date_obj))
    
    if category:
        query = query.filter(Transaction.category == category)
    if account_id:
        query = query.filter(Transaction.account_id == account_id)
    if search:
        query = query.filter(Transaction.name.ilike(f'%{search}%'))
    
    # Order by date descending
    transactions = query.order_by(Transaction.date.desc()).all()
    
    # Get all accounts for filter dropdown
    accounts = Account.query.filter_by(user_id=current_user.id).all()
    
    # Get all unique categories for filter dropdown
    categories = db.session.query(Transaction.category)\
        .filter(Transaction.user_id == current_user.id, Transaction.category != None)\
        .distinct().all()
    categories = [c[0] for c in categories if c[0]]
    categories.sort()
    
    return render_template(
        'transactions/index.html',
        title='Transactions',
        transactions=transactions,
        accounts=accounts,
        categories=categories,
        start_date=start_date,
        end_date=end_date,
        selected_category=category,
        selected_account_id=account_id,
        search=search
    )

@transactions_bp.route('/refresh')
def refresh(*args, **kwargs):
    """Refresh transaction data from Plaid."""
    # API style endpoint: return JSON 401 instead of redirect when unauthenticated
    if not current_user.is_authenticated:
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    if not current_user.plaid_access_token:
        flash("No Plaid connection found. Please connect your bank first.", "warning")
        return jsonify({"success": False, "message": "No Plaid connection found"})
    
    # Get optional date parameters
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    success, message = fetch_transactions(current_user, start_date, end_date)
    if success:
        flash("Transactions refreshed successfully!", "success")
        return jsonify({"success": True, "message": message})
    else:
        flash(f"Error refreshing transactions: {message}", "danger")
        return jsonify({"success": False, "message": message})

@transactions_bp.route('/<int:transaction_id>')
def detail(transaction_id, *args, **kwargs):
    """Transaction detail page."""
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    transaction = Transaction.query.filter_by(id=transaction_id, user_id=current_user.id).first_or_404()
    account = Account.query.get(transaction.account_id)
    
    return render_template(
        'transactions/detail.html',
        title=f'Transaction: {transaction.name}',
        transaction=transaction,
        account=account
    )

@transactions_bp.route('/<int:transaction_id>/edit-note', methods=['POST'])
def edit_note(transaction_id, *args, **kwargs):
    """Update the note for a transaction."""
    if not current_user.is_authenticated:
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    transaction = Transaction.query.filter_by(id=transaction_id, user_id=current_user.id).first_or_404()
    
    notes = request.json.get('notes', '')
    transaction.notes = notes
    db.session.commit()
    
    return jsonify({"success": True})

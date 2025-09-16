from flask import Blueprint, render_template, redirect, url_for, flash, session, request, jsonify
from flask_login import current_user
from datetime import datetime, date, timedelta
from sqlalchemy import func
from app import db
from app.models import Account, Transaction, Bill, Income
from app.utils.time import fridays_in_month, utc_now
from app.plaid_service import create_link_token

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/dashboard')
def index():
    """Dashboard with financial overview."""
    # Redirect to login if not authenticated
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    
    # Initialize Plaid link token if needed
    link_token = None
    if not current_user.plaid_access_token:
        link_token = create_link_token(current_user.id)
    
    # Calculate net worth (sum of all account balances)
    net_worth = db.session.query(func.sum(Account.current_balance)).\
        filter(Account.user_id == current_user.id).scalar() or 0
    
    # Income mode: 'estimated' (current behavior) or 'calculated'
    mode = session.get('income_mode', 'estimated')
    # Base incomes
    incomes = Income.query.filter_by(user_id=current_user.id).all()
    total_net = sum(i.net_amount or 0 for i in incomes)
    monthly_income = 0
    if mode == 'estimated':
        monthly_income = total_net  # existing interpretation: already monthly net amounts
    else:
        # Calculated: derive per-pay amount (average net entry) * number of Fridays this month
        now_dt = utc_now()
        year, month = now_dt.year, now_dt.month
        friday_count = fridays_in_month(year, month)
        if incomes:
            avg_pay = total_net / len([i for i in incomes if (i.net_amount or 0) > 0]) if total_net else 0
            monthly_income = avg_pay * friday_count
        else:
            monthly_income = 0
    
    # Get monthly bills (sum of all bills)
    monthly_bills = db.session.query(func.sum(Bill.amount)).\
        filter(Bill.user_id == current_user.id).scalar() or 0
    
    # Get upcoming bills (due in next 30 days)
    today = date.today()
    thirty_days = today + timedelta(days=30)
    upcoming_bills = Bill.query.filter(
        Bill.user_id == current_user.id,
        Bill.due_date.between(today, thirty_days),
        Bill.status != 'paid'
    ).order_by(Bill.due_date).all()
    
    # Get recent transactions
    recent_transactions = Transaction.query.filter_by(user_id=current_user.id)\
        .order_by(Transaction.date.desc())\
        .limit(5).all()

    # Count linked accounts for conditional UI (avoid showing unlink if no data yet)
    account_count = Account.query.filter_by(user_id=current_user.id).count()
    
    # Get transaction data for charts
    # For income vs. expenses chart
    now = datetime.now()
    start_date = date(now.year, now.month, 1)
    end_date = date(now.year, now.month + 1, 1) if now.month < 12 else date(now.year + 1, 1, 1)
    
    # Get income and expense transactions
    transactions = Transaction.query.filter(
        Transaction.user_id == current_user.id,
        Transaction.date.between(start_date, end_date)
    ).all()
    
    # Categorize transactions
    income_total = sum(t.amount for t in transactions if t.amount < 0)
    expense_total = sum(t.amount for t in transactions if t.amount > 0)
    
    # Category breakdown
    categories = {}
    for transaction in transactions:
        if transaction.amount > 0 and transaction.category:  # Expense with category
            if transaction.category not in categories:
                categories[transaction.category] = 0
            categories[transaction.category] += transaction.amount
    
    # Sort categories by amount
    sorted_categories = sorted(categories.items(), key=lambda x: x[1], reverse=True)
    
    # Prepare chart data
    # NOTE: Use key name 'data' instead of 'values' so Jinja attribute lookup
    # does not resolve the dict.values method, which caused JSON serialization errors.
    chart_data = {
        'income_vs_expenses': {
            'labels': ['Income', 'Expenses'],
            'data': [abs(income_total), expense_total]
        },
        'categories': {
            'labels': [c[0] for c in sorted_categories[:5]],  # Top 5 categories
            'data': [c[1] for c in sorted_categories[:5]]
        }
    }
    
    return render_template(
        'dashboard/index.html',
        title='Dashboard',
        link_token=link_token,
        net_worth=net_worth,
        monthly_income=monthly_income,
        monthly_bills=monthly_bills,
        upcoming_bills=upcoming_bills,
        recent_transactions=recent_transactions,
        chart_data=chart_data,
        account_count=account_count,
        income_mode=mode
    )

@dashboard_bp.route('/dashboard/income-mode', methods=['POST'])
def set_income_mode():
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json(silent=True) or {}
    mode = data.get('mode')
    if mode not in ('estimated','calculated'):
        return jsonify({'error': 'Invalid mode'}), 400
    session['income_mode'] = mode
    return jsonify({'success': True, 'mode': mode})

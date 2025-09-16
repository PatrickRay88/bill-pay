from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import current_user
from datetime import date
from app import db
from app.models import Income
from app.forms import IncomeForm
from app.plaid_service import fetch_income
from app.utils.time import fridays_in_month, utc_now

income_bp = Blueprint('income', __name__, url_prefix='/income')

@income_bp.route('/')
def index(*args, **kwargs):
    """Income overview page with projected vs actual monthly total logic.

    Rules:
    - While the month is in progress and not all expected weekly/bi-weekly paychecks
      have been recorded, show a projection: (average per-pay net) * (Fridays in month)
      plus any monthly-frequency incomes (treated as already monthly).
    - Once the number of recorded weekly/bi-weekly pay entries for the current month
      is >= the total Fridays in the month, switch to the ACTUAL sum of that month's
      income entries (net where available, fallback gross).
    - If there are zero weekly/bi-weekly entries yet, projection = 0 (or just monthly incomes).
    Assumptions:
      * Weekly cadence is the baseline for projection (using Fridays as pay anchors).
      * Bi-weekly entries are treated the same for averaging; (a refinement could
        weight them differently, deferred for simplicity per current requirement).
    """
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))

    # All incomes (for table display)
    incomes = Income.query.filter_by(user_id=current_user.id).order_by(Income.date.desc()).all()

    # Current month context
    now_dt = utc_now()
    year, month = now_dt.year, now_dt.month
    fridays_total = fridays_in_month(year, month)

    current_month_incomes = [i for i in incomes if i.date.year == year and i.date.month == month]

    # Separate weekly-like and monthly incomes for current month
    weeklike = [i for i in current_month_incomes if i.frequency in ('weekly', 'bi-weekly')]
    monthly_entries = [i for i in current_month_incomes if i.frequency == 'monthly']

    # Net amounts (fallback to gross if net missing)
    def net_or_gross(entry: Income) -> float:
        return entry.net_amount if entry.net_amount is not None else entry.gross_amount

    weeklike_total_net = sum(net_or_gross(i) for i in weeklike)
    monthly_total_net = sum(net_or_gross(i) for i in monthly_entries)

    # Actual month sum (all entries)
    actual_month_total = sum(net_or_gross(i) for i in current_month_incomes)

    paychecks_recorded = len(weeklike)
    avg_pay = (weeklike_total_net / paychecks_recorded) if paychecks_recorded else 0

    # Determine if full month realized (all expected weekly pay events captured)
    full_month_realized = paychecks_recorded >= fridays_total and paychecks_recorded > 0

    if full_month_realized:
        estimated_monthly = actual_month_total
        is_projection = False
    else:
        projected_weeklike = avg_pay * fridays_total if paychecks_recorded else 0
        estimated_monthly = projected_weeklike + monthly_total_net
        is_projection = True

    return render_template(
        'income/index.html',
        title='Income',
        incomes=incomes,
        estimated_monthly=estimated_monthly,
        is_projection=is_projection,
        actual_month_total=actual_month_total,
        avg_pay=avg_pay,
        fridays_total=fridays_total,
        paychecks_recorded=paychecks_recorded,
        month_year=date(year, month, 1)
    )

@income_bp.route('/add', methods=['GET', 'POST'])
def add(*args, **kwargs):
    """Add a new income source."""
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    form = IncomeForm()
    if form.validate_on_submit():
        income = Income(
            user_id=current_user.id,
            source=form.source.data,
            gross_amount=form.gross_amount.data,
            net_amount=form.net_amount.data or form.gross_amount.data,
            frequency=form.frequency.data,
            date=form.date.data,
            notes=form.notes.data
        )
        db.session.add(income)
        db.session.commit()
        flash('Income source added successfully!', 'success')
        return redirect(url_for('income.index'))
        
    return render_template('income/form.html', title='Add Income Source', form=form)

@income_bp.route('/<int:income_id>/edit', methods=['GET', 'POST'])
def edit(income_id, *args, **kwargs):
    """Edit an existing income source."""
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    income = Income.query.filter_by(id=income_id, user_id=current_user.id).first_or_404()
    
    # Check if it's a Plaid-detected income
    is_plaid_income = bool(income.plaid_income_id)
    
    form = IncomeForm(obj=income)
    if form.validate_on_submit():
        form.populate_obj(income)
        db.session.commit()
        flash('Income source updated successfully!', 'success')
        return redirect(url_for('income.index'))
        
    return render_template('income/form.html', title='Edit Income Source', form=form, is_plaid_income=is_plaid_income)

@income_bp.route('/<int:income_id>/delete', methods=['POST'])
def delete(income_id, *args, **kwargs):
    """Delete an income source."""
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    income = Income.query.filter_by(id=income_id, user_id=current_user.id).first_or_404()
    
    # Check if it's a Plaid-detected income
    is_plaid_income = bool(income.plaid_income_id)
    if is_plaid_income:
        flash("Cannot delete an income source imported from Plaid. It will be re-created on the next sync.", "warning")
        return redirect(url_for('income.index'))
    
    db.session.delete(income)
    db.session.commit()
    flash('Income source deleted successfully!', 'success')
    return redirect(url_for('income.index'))

@income_bp.route('/simulator')
def simulator(*args, **kwargs):
    """Paycheck simulator tool."""
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    # Get all income sources for the current user
    incomes = Income.query.filter_by(user_id=current_user.id).all()
    
    return render_template('income/simulator.html', title='Income Simulator', incomes=incomes)

@income_bp.route('/refresh')
def refresh(*args, **kwargs):
    """Refresh income data from Plaid."""
    if not current_user.is_authenticated:
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    if not current_user.plaid_access_token:
        flash("No Plaid connection found. Please connect your bank first.", "warning")
        return jsonify({"success": False, "message": "No Plaid connection found"})
    
    success, message = fetch_income(current_user)
    if success:
        flash("Income data refreshed successfully!", "success")
        return jsonify({"success": True, "message": message})
    else:
        flash(f"Error refreshing income data: {message}", "danger")
        return jsonify({"success": False, "message": message})

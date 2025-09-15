from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Income
from app.forms import IncomeForm
from app.plaid_service import fetch_income

income_bp = Blueprint('income', __name__, url_prefix='/income')

@income_bp.route('/')
@login_required
def index():
    """Income overview page."""
    # Get all income sources for the current user
    incomes = Income.query.filter_by(user_id=current_user.id).order_by(Income.date.desc()).all()
    
    # Calculate totals
    weekly_total = sum(i.gross_amount for i in incomes if i.frequency == 'weekly')
    biweekly_total = sum(i.gross_amount for i in incomes if i.frequency == 'bi-weekly')
    monthly_total = sum(i.gross_amount for i in incomes if i.frequency == 'monthly')
    
    # Estimate monthly income
    estimated_monthly = (
        (weekly_total * 4.33) +  # Weekly → Monthly
        (biweekly_total * 2.17) +  # Bi-weekly → Monthly
        monthly_total  # Already monthly
    )
    
    return render_template(
        'income/index.html',
        title='Income',
        incomes=incomes,
        estimated_monthly=estimated_monthly
    )

@income_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    """Add a new income source."""
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
@login_required
def edit(income_id):
    """Edit an existing income source."""
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
@login_required
def delete(income_id):
    """Delete an income source."""
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
@login_required
def simulator():
    """Paycheck simulator tool."""
    # Get all income sources for the current user
    incomes = Income.query.filter_by(user_id=current_user.id).all()
    
    return render_template('income/simulator.html', title='Income Simulator', incomes=incomes)

@income_bp.route('/refresh')
@login_required
def refresh():
    """Refresh income data from Plaid."""
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

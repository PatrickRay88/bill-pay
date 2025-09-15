from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import current_user
from datetime import datetime
from app import db
from app.models import Bill
from app.forms import BillForm
from app.plaid_service import fetch_liabilities

bills_bp = Blueprint('bills', __name__, url_prefix='/bills')

@bills_bp.route('/')
def index(*args, **kwargs):
    """Bills overview page."""
    # Ensure user is authenticated
    if not current_user.is_authenticated:
        return redirect(url_for('auth.auto_login'))
    # Get all bills for the current user
    bills = Bill.query.filter_by(user_id=current_user.id).order_by(Bill.due_date).all()
    
    # Separate bills into upcoming, past due, and paid
    today = datetime.now().date()
    upcoming_bills = [b for b in bills if b.due_date >= today and b.status != 'paid']
    past_due_bills = [b for b in bills if b.due_date < today and b.status != 'paid']
    paid_bills = [b for b in bills if b.status == 'paid']
    
    return render_template(
        'bills/index.html',
        title='Bills',
        upcoming_bills=upcoming_bills,
        past_due_bills=past_due_bills,
        paid_bills=paid_bills
    )

@bills_bp.route('/add', methods=['GET', 'POST'])
def add(*args, **kwargs):
    """Add a new bill."""
    # Ensure user is authenticated
    if not current_user.is_authenticated:
        return redirect(url_for('auth.auto_login'))
    form = BillForm()
    if form.validate_on_submit():
        bill = Bill(
            user_id=current_user.id,
            name=form.name.data,
            amount=form.amount.data,
            due_date=form.due_date.data,
            frequency=form.frequency.data,
            category=form.category.data,
            status=form.status.data,
            autopay=form.autopay.data,
            notes=form.notes.data
        )
        db.session.add(bill)
        db.session.commit()
        flash('Bill added successfully!', 'success')
        return redirect(url_for('bills.index'))
        
    return render_template('bills/form.html', title='Add Bill', form=form)

@bills_bp.route('/<int:bill_id>/edit', methods=['GET', 'POST'])
def edit(bill_id, *args, **kwargs):
    """Edit an existing bill."""
    # Ensure user is authenticated
    if not current_user.is_authenticated:
        return redirect(url_for('auth.auto_login'))
    bill = Bill.query.filter_by(id=bill_id, user_id=current_user.id).first_or_404()
    
    # Check if it's a Plaid-detected bill
    is_plaid_bill = bool(bill.plaid_bill_id)
    
    form = BillForm(obj=bill)
    if form.validate_on_submit():
        form.populate_obj(bill)
        db.session.commit()
        flash('Bill updated successfully!', 'success')
        return redirect(url_for('bills.index'))
        
    return render_template('bills/form.html', title='Edit Bill', form=form, is_plaid_bill=is_plaid_bill)

@bills_bp.route('/<int:bill_id>/delete', methods=['POST'])
def delete(bill_id, *args, **kwargs):
    """Delete a bill."""
    # Ensure user is authenticated
    if not current_user.is_authenticated:
        return redirect(url_for('auth.auto_login'))
    bill = Bill.query.filter_by(id=bill_id, user_id=current_user.id).first_or_404()
    
    # Check if it's a Plaid-detected bill
    is_plaid_bill = bool(bill.plaid_bill_id)
    if is_plaid_bill:
        flash("Cannot delete a bill imported from Plaid. It will be re-created on the next sync.", "warning")
        return redirect(url_for('bills.index'))
    
    db.session.delete(bill)
    db.session.commit()
    flash('Bill deleted successfully!', 'success')
    return redirect(url_for('bills.index'))

@bills_bp.route('/<int:bill_id>/toggle-status', methods=['POST'])
def toggle_status(bill_id, *args, **kwargs):
    """Toggle a bill's status between paid and unpaid."""
    # Ensure user is authenticated
    if not current_user.is_authenticated:
        return redirect(url_for('auth.auto_login'))
    bill = Bill.query.filter_by(id=bill_id, user_id=current_user.id).first_or_404()
    
    if bill.status == 'paid':
        bill.status = 'unpaid'
    else:
        bill.status = 'paid'
    
    db.session.commit()
    return jsonify({"success": True, "status": bill.status})

@bills_bp.route('/refresh')
def refresh(*args, **kwargs):
    """Refresh bill data from Plaid."""
    # Ensure user is authenticated
    if not current_user.is_authenticated:
        return redirect(url_for('auth.auto_login'))
    if not current_user.plaid_access_token:
        flash("No Plaid connection found. Please connect your bank first.", "warning")
        return jsonify({"success": False, "message": "No Plaid connection found"})
    
    success, message = fetch_liabilities(current_user)
    if success:
        flash("Bills refreshed successfully!", "success")
        return jsonify({"success": True, "message": message})
    else:
        flash(f"Error refreshing bills: {message}", "danger")
        return jsonify({"success": False, "message": message})

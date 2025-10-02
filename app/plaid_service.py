import os
import datetime
from app.utils.time import utc_now
from plaid.api import plaid_api
from plaid.model.accounts_get_request import AccountsGetRequest
from plaid.model.transactions_get_request import TransactionsGetRequest
from plaid.model.transactions_get_request_options import TransactionsGetRequestOptions
from plaid.model.liabilities_get_request import LiabilitiesGetRequest
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products
from plaid.model.sandbox_public_token_create_request import SandboxPublicTokenCreateRequest
from plaid.model.country_code import CountryCode
from flask import current_app
from cryptography.fernet import Fernet
from app import db, plaid_client
from app.models import User, Account, Transaction, Bill, Income, PlaidItem

def unlink_plaid(user, reset_data=True):
    """Completely unlink Plaid for a user.

    Parameters:
        user: User instance
        reset_data (bool): If True, delete Plaid-derived records (accounts, transactions, bills with plaid_bill_id, incomes with plaid_income_id).

    Returns (success, message)
    """
    try:
        # Clear credentials
        user.plaid_access_token = None
        user.item_id = None

        if reset_data:
            # Delete dependent data in safe order (transactions -> accounts). Bills/income only those linked to Plaid IDs.
            Transaction.query.filter_by(user_id=user.id).delete()
            Account.query.filter_by(user_id=user.id).delete()
            Bill.query.filter(Bill.user_id==user.id, Bill.plaid_bill_id.isnot(None)).delete()
            Income.query.filter(Income.user_id==user.id, Income.plaid_income_id.isnot(None)).delete()

        db.session.commit()
        return True, 'Plaid connection removed.'
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to unlink Plaid: {e}")
        return False, f"Failed to unlink Plaid: {e}"

def unlink_plaid_item(user, plaid_item_id, reset_data=True):
    """Unlink a single PlaidItem and optionally its accounts/transactions."""
    try:
        item = PlaidItem.query.filter_by(id=plaid_item_id, user_id=user.id).first()
        if not item:
            return False, 'Plaid item not found.'
        if reset_data:
            # Delete transactions tied to accounts of this item
            acct_ids = [a.id for a in Account.query.filter_by(user_id=user.id, plaid_item_id=item.id).all()]
            if acct_ids:
                Transaction.query.filter(Transaction.account_id.in_(acct_ids)).delete(synchronize_session=False)
            Account.query.filter_by(user_id=user.id, plaid_item_id=item.id).delete()
        db.session.delete(item)
        db.session.commit()
        # If no more items remain, clear legacy fields
        remaining = PlaidItem.query.filter_by(user_id=user.id).count()
        if remaining == 0:
            user.plaid_access_token = None
            user.item_id = None
            db.session.commit()
        return True, 'Plaid institution disconnected.'
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to unlink Plaid item {plaid_item_id}: {e}")
        return False, f"Failed to unlink institution: {e}"

# For encrypting/decrypting the Plaid access token
def get_encryption_key():
    """Return a stable Fernet key.

    Order of preference:
    1. ENCRYPTION_KEY env var (assumed valid base64 fernet key)
    2. Generated and cached in app config for this process (warning logged)
    Never silently slice SECRET_KEY (risk of decryption mismatch on restart)."""
    env_key = os.environ.get('ENCRYPTION_KEY')
    if env_key:
        try:
            # Validate length by attempting to build Fernet
            Fernet(env_key)
            return env_key.encode()
        except Exception:
            current_app.logger.warning('Provided ENCRYPTION_KEY invalid; generating ephemeral key.')
    # Fallback: cache a generated key for runtime (NOT persistent)
    if not hasattr(current_app, '_ephemeral_fernet_key'):
        from cryptography.fernet import Fernet as _F
        current_app._ephemeral_fernet_key = _F.generate_key()
        current_app.logger.warning('Using ephemeral encryption key; set ENCRYPTION_KEY for persistence.')
    return current_app._ephemeral_fernet_key

def encrypt_token(token):
    """Encrypt the Plaid access token before storing it."""
    if not token:
        return None
    f = Fernet(get_encryption_key())
    return f.encrypt(token.encode()).decode()

def decrypt_token(encrypted_token):
    """Decrypt the stored Plaid access token."""
    if not encrypted_token:
        return None
    f = Fernet(get_encryption_key())
    return f.decrypt(encrypted_token.encode()).decode()

def create_link_token(user_id):
    """Create a Plaid Link token for initializing Link.

    Retries once if unauthorized products are requested (common in sandbox when
    income or liabilities not yet enabled)."""
    configured_products = list(current_app.config['PLAID_PRODUCTS'])
    # Normalize list (could be strings already)
    configured_products = [p if isinstance(p, str) else str(p) for p in configured_products]

    # Pre-log context so we can trace failures clearly
    current_app.logger.info(
        "Plaid link token request: env=%s products=%s redirect_uri=%s user_id=%s",
        current_app.config.get('PLAID_ENV'),
        configured_products,
        current_app.config.get('PLAID_REDIRECT_URI') or 'none',
        user_id
    )

    # Early validation for production secret format to avoid opaque INVALID_FIELD from Plaid
    if current_app.config.get('PLAID_ENV') == 'production':
        secret = current_app.config.get('PLAID_SECRET_RESOLVED') or ''
        if not secret:
            current_app.logger.error('Cannot create link token: production secret missing.')
            return None
        if 'production-' not in secret and len(secret) < 40:
            # Warn but DO NOT block; some older or internal style secrets may differ.
            current_app.logger.warning('PLAID_SECRET_PRODUCTION format heuristic not met (no production- prefix, len<40); proceeding anyway.')

    def _attempt(products):
        kwargs = dict(
            client_name="BillPay App",
            country_codes=[CountryCode(code) for code in current_app.config['PLAID_COUNTRY_CODES']],
            language="en",
            user=LinkTokenCreateRequestUser(client_user_id=str(user_id)),
            products=[Products(p) for p in products]
        )
        # Always include redirect_uri if configured; required for OAuth-based institutions.
        # Plaid supports localhost redirect URIs for development when registered in the dashboard.
        redirect_uri = current_app.config.get('PLAID_REDIRECT_URI')
        if redirect_uri:
            kwargs['redirect_uri'] = redirect_uri
        req = LinkTokenCreateRequest(**kwargs)
        return plaid_client.link_token_create(req)

    try:
        try:
            response = _attempt(configured_products)
            return response.link_token
        except Exception as first_error:
            msg = str(first_error)
            current_app.logger.warning(f"Initial link token attempt failed: {msg}")
            # Detect unauthorized products pattern
            if 'client is not authorized to access the following products' in msg:
                # Parse product names inside brackets, handling escaped quotes.
                import re
                unauthorized = []
                match = re.search(r'products: \[(.+?)\]', msg)
                if match:
                    raw = match.group(1)
                    # Unescape common patterns and split
                    raw_clean = raw.replace('\\"', '"').replace("'", "")
                    for part in raw_clean.split(','):
                        name = part.strip().strip('"').strip()
                        if name:
                            unauthorized.append(name)
                filtered = [p for p in configured_products if p not in set(unauthorized)]
                if not filtered:
                    current_app.logger.error("All requested Plaid products unauthorized; falling back to 'transactions'.")
                    filtered = ['transactions']
                else:
                    current_app.logger.info(
                        "Retrying link token creation with products filtered (%s -> %s) removed=%s",
                        configured_products,
                        filtered,
                        unauthorized
                    )
                try:
                    response = _attempt(filtered)
                    return response.link_token
                except Exception as retry_err:
                    current_app.logger.error(f"Retry after filtering unauthorized products failed: {retry_err}")
                    raise retry_err
            else:
                raise first_error
    except Exception as e:
        current_app.logger.error(f"Error creating link token after retry: {e}")
        return None


def exchange_public_token(public_token, user, institution_name=None):
    """Exchange the public token for an access token and persist as a PlaidItem (multi-item support).

    Legacy fallback: if PlaidItem creation fails, we still try to set user.plaid_access_token (should be removed after migration).
    """
    try:
        user = db.session.merge(user)
        exchange_request = ItemPublicTokenExchangeRequest(public_token=public_token)
        exchange_response = plaid_client.item_public_token_exchange(exchange_request)
        access_token = exchange_response.access_token
        item_id = exchange_response.item_id

        enc = encrypt_token(access_token)
        existing = PlaidItem.query.filter_by(item_id=item_id, user_id=user.id).first()
        if existing:
            existing.access_token = enc
            if institution_name and not existing.institution_name:
                existing.institution_name = institution_name
            existing.last_synced = utc_now()
        else:
            db.session.add(PlaidItem(user_id=user.id, item_id=item_id, access_token=enc, institution_name=institution_name))

        user.plaid_access_token = enc  # legacy
        user.item_id = item_id  # legacy
        db.session.commit()

        products_lower = {p.lower() for p in current_app.config.get('PLAID_PRODUCTS', [])}
        fetch_accounts_for_item(user, item_id)
        fetch_transactions_for_item(user, item_id)
        if current_app.config.get('TESTING') or 'liabilities' in products_lower:
            fetch_liabilities(user)
        if current_app.config.get('TESTING') or 'income' in products_lower:
            fetch_income(user)
        return True, "Successfully connected your institution!"
    except Exception as e:
        current_app.logger.error(f"Error exchanging public token: {e}")
        return False, f"Error connecting your account: {e}"

def fetch_accounts(user):
    """Fetch accounts for all PlaidItems for the user (multi-item)."""
    user = db.session.merge(user)
    items = PlaidItem.query.filter_by(user_id=user.id).all()
    ok = True
    for item in items:
        success, _ = fetch_accounts_for_item(user, item.item_id)
        ok = ok and success
    return ok, "Accounts refreshed"

def _decrypt_item_access(item: PlaidItem):
    try:
        return decrypt_token(item.access_token)
    except Exception:
        return None

def fetch_accounts_for_item(user, item_id):
    """Fetch accounts for a single PlaidItem (by item_id)."""
    try:
        item = PlaidItem.query.filter_by(item_id=item_id, user_id=user.id).first()
        if not item:
            return False, "Item not found"
        access_token = _decrypt_item_access(item)
        if not access_token:
            return False, "No access token for item"
        request = AccountsGetRequest(access_token=access_token)
        response = plaid_client.accounts_get(request)
        for plaid_account in response.accounts:
            account = Account.query.filter_by(user_id=user.id, plaid_account_id=plaid_account.account_id).first()
            if not account:
                acct_type = getattr(plaid_account, 'type', None)
                acct_subtype = getattr(plaid_account, 'subtype', None)
                account = Account(
                    user_id=user.id,
                    plaid_account_id=plaid_account.account_id,
                    name=plaid_account.name,
                    official_name=plaid_account.official_name,
                    type=str(acct_type) if acct_type is not None else 'unknown',
                    subtype=str(acct_subtype) if acct_subtype is not None else None,
                    mask=plaid_account.mask,
                    plaid_item_id=item.id
                )
                db.session.add(account)
            if plaid_account.balances:
                account.current_balance = plaid_account.balances.current
                account.available_balance = plaid_account.balances.available
                account.iso_currency_code = plaid_account.balances.iso_currency_code or 'USD'
            account.last_synced = utc_now()
        db.session.commit()
        return True, "Accounts updated"
    except Exception as e:
        current_app.logger.error(f"Error fetching accounts for item {item_id}: {e}")
        db.session.rollback()
        return False, f"Error fetching accounts for item: {e}"

def fetch_transactions(user, start_date=None, end_date=None):
    user = db.session.merge(user)
    items = PlaidItem.query.filter_by(user_id=user.id).all()
    ok = True
    for item in items:
        success, _ = fetch_transactions_for_item(user, item.item_id, start_date=start_date, end_date=end_date)
        ok = ok and success
    return ok, "Transactions refreshed"

def fetch_transactions_for_item(user, item_id, start_date=None, end_date=None):
    try:
        item = PlaidItem.query.filter_by(item_id=item_id, user_id=user.id).first()
        if not item:
            return False, "Item not found"
        access_token = _decrypt_item_access(item)
        if not access_token:
            return False, "No access token for item"
        if not start_date:
            start_date = (datetime.datetime.now() - datetime.timedelta(days=30)).date()
        if not end_date:
            end_date = datetime.datetime.now().date()
        options = TransactionsGetRequestOptions(count=500, include_personal_finance_category=True)
        request = TransactionsGetRequest(access_token=access_token, start_date=start_date, end_date=end_date, options=options)
        response = plaid_client.transactions_get(request)
        account_map = {a.plaid_account_id: a.id for a in Account.query.filter_by(user_id=user.id, plaid_item_id=item.id).all()}
        for plaid_transaction in response.transactions:
            transaction = Transaction.query.filter_by(plaid_transaction_id=plaid_transaction.transaction_id).first()
            if plaid_transaction.account_id not in account_map:
                continue
            account_id = account_map[plaid_transaction.account_id]
            if not transaction:
                transaction = Transaction(
                    user_id=user.id,
                    account_id=account_id,
                    plaid_transaction_id=plaid_transaction.transaction_id,
                    name=plaid_transaction.name,
                    amount=plaid_transaction.amount,
                    date=plaid_transaction.date,
                    pending=plaid_transaction.pending
                )
                db.session.add(transaction)
            transaction.category = plaid_transaction.personal_finance_category.primary if plaid_transaction.personal_finance_category else None
            transaction.category_id = plaid_transaction.category_id
            transaction.payment_channel = plaid_transaction.payment_channel
            transaction.merchant_name = plaid_transaction.merchant_name
            if hasattr(plaid_transaction, 'location'):
                parts = []
                loc = plaid_transaction.location
                if loc.city: parts.append(loc.city)
                if loc.region: parts.append(loc.region)
                if loc.postal_code: parts.append(loc.postal_code)
                if loc.country: parts.append(loc.country)
                transaction.location = ", ".join(parts)
        detect_recurring_transactions(user.id)
        db.session.commit()
        return True, "Transactions updated"
    except Exception as e:
        msg = str(e)
        if 'PRODUCT_NOT_READY' in msg:
            current_app.logger.warning(f'Transactions product not ready for item {item_id}; retry later.')
            return False, 'Transactions not ready yet'
        current_app.logger.error(f"Error fetching transactions for item {item_id}: {msg}")
        db.session.rollback()
        return False, f"Error fetching transactions for item: {msg}"

def detect_recurring_transactions(user_id):
    """Analyze transactions to detect recurring bills."""
    # This is a simplified implementation - in a real app, you'd use more sophisticated algorithms
    # or leverage Plaid's recurring transactions endpoints if available
    try:
        # Group transactions by name and approximate amount
        # Look for patterns in timing (monthly, weekly, etc.)
        # For this example, we'll just look for transactions with the same name and similar amounts
        
        # Get all transactions for this user
        transactions = Transaction.query.filter_by(user_id=user_id).all()
        
        # Group by name
        by_name = {}
        for transaction in transactions:
            if transaction.amount < 0:  # Only consider outgoing payments
                name = transaction.name.lower().strip()
                if name not in by_name:
                    by_name[name] = []
                by_name[name].append(transaction)
        
        # Look for recurring patterns
        for name, txns in by_name.items():
            if len(txns) >= 2:  # Need at least 2 occurrences
                # Sort by date
                txns.sort(key=lambda t: t.date)
                
                # Mark as potentially recurring
                for txn in txns:
                    txn.is_recurring = True
                
                # Check if we already have a bill for this
                bill = Bill.query.filter_by(
                    user_id=user_id,
                    name=name
                ).first()
                
                if not bill:
                    # Create a new bill
                    # Use the average amount and most recent date
                    avg_amount = abs(sum(t.amount for t in txns) / len(txns))
                    latest_date = txns[-1].date
                    
                    # Create a bill
                    bill = Bill(
                        user_id=user_id,
                        name=name.title(),  # Capitalize for display
                        amount=round(avg_amount, 2),
                        due_date=latest_date,
                        category=txns[0].category,
                        status="paid" if latest_date <= datetime.datetime.now().date() else "unpaid",
                        notes="Automatically detected from recurring transactions"
                    )
                    db.session.add(bill)
        
        db.session.commit()
        return True, "Recurring transactions detected"
    
    except Exception as e:
        current_app.logger.error(f"Error detecting recurring transactions: {str(e)}")
        db.session.rollback()
        return False, f"Error detecting recurring transactions: {str(e)}"

def sync_liability_bills(user, response):
    """Transform Plaid liabilities response into Bill records (credit, student, mortgage).

    Idempotent: identifies bills by (user_id, plaid_bill_id).
    Uses existing Bill.plaid_bill_id field to store the Plaid account_id for liability-derived bills.
    Updates amount & due_date if an entry already exists.
    """
    created = 0
    updated = 0
    try:
        # Defensive: response may lack liabilities sub-structure in some sandbox cases
        liabilities = getattr(response, 'liabilities', None)
        if not liabilities:
            return True, "No liabilities section present"

        accounts_by_id = {acct.account_id: acct for acct in getattr(response, 'accounts', [])}

        # Helper to upsert a bill
        def upsert(plaid_account_id, name, amount, due_date, category, note_suffix):
            nonlocal created, updated
            if not plaid_account_id or due_date is None:
                return
            bill = Bill.query.filter_by(user_id=user.id, plaid_bill_id=plaid_account_id).first()
            if not bill:
                bill = Bill(
                    user_id=user.id,
                    plaid_bill_id=plaid_account_id,
                    name=name,
                    amount=amount or 0,
                    due_date=due_date,
                    category=category,
                    status='unpaid',
                    notes=f"Automatically created from Plaid liabilities ({note_suffix})"
                )
                db.session.add(bill)
                created += 1
            else:
                # Update if changed
                changed = False
                if amount is not None and abs((bill.amount or 0) - amount) > 0.009:
                    bill.amount = amount
                    changed = True
                if due_date and bill.due_date != due_date:
                    bill.due_date = due_date
                    changed = True
                if changed:
                    updated += 1

        # Credit cards
        for credit in getattr(liabilities, 'credit', []) or []:
            acct = accounts_by_id.get(credit.account_id)
            name = f"{acct.name if acct else 'Credit Card'} Payment"
            amount = getattr(credit, 'minimum_payment_amount', None) or getattr(credit, 'last_statement_balance', None) or 0
            due = getattr(credit, 'next_payment_due_date', None)
            upsert(credit.account_id, name, amount, due, 'Credit Card', 'credit')

        # Student loans
        for loan in getattr(liabilities, 'student', []) or []:
            acct = accounts_by_id.get(loan.account_id)
            base_name = getattr(loan, 'loan_name', None) or (acct.name if acct else 'Student Loan')
            name = f"{base_name} Payment"
            amount = getattr(loan, 'minimum_payment_amount', None) or 0
            due = getattr(loan, 'next_payment_due_date', None)
            upsert(loan.account_id, name, amount, due, 'Student Loan', 'student')

        # Mortgages
        for mortgage in getattr(liabilities, 'mortgage', []) or []:
            acct = accounts_by_id.get(mortgage.account_id)
            name = f"{acct.name if acct else 'Mortgage'} Payment"
            amount = getattr(mortgage, 'next_monthly_payment', None) or 0
            due = getattr(mortgage, 'next_payment_due_date', None)
            upsert(mortgage.account_id, name, amount, due, 'Mortgage', 'mortgage')

        db.session.commit()
        return True, f"Liabilities updated (created {created}, updated {updated})"
    except Exception as e:
        current_app.logger.error(f"sync_liability_bills error: {e}")
        db.session.rollback()
        return False, f"Failed updating liability bills: {e}"

def fetch_liabilities(user):
    """Fetch liability data from Plaid and store it in the database."""
    try:
        user = db.session.merge(user)
        # Decrypt the access token
        access_token = decrypt_token(user.plaid_access_token)
        if not access_token:
            return False, "No access token available"
        
        # Request liabilities
        request = LiabilitiesGetRequest(access_token=access_token)
        response = plaid_client.liabilities_get(request)
        success, msg = sync_liability_bills(user, response)
        return success, msg if success else (False, msg)
    
    except Exception as e:
        current_app.logger.error(f"Error fetching liabilities: {str(e)}")
        db.session.rollback()
        return False, f"Error fetching liabilities: {str(e)}"

def fetch_income(user):
    """
    Analyze transactions to identify income sources.
    
    Note: This is a simplified approach. A production app would use Plaid's
    income verification endpoints or more sophisticated algorithms.
    """
    try:
        user = db.session.merge(user)
        # For this example, we'll identify income by looking for large deposits
        # A more complete implementation would use Plaid's income verification products
        
        # Get all deposits for this user
        deposits = Transaction.query.filter_by(user_id=user.id)\
            .filter(Transaction.amount < 0)\
            .order_by(Transaction.date.desc())\
            .limit(100).all()
        
        # Group by source/description
        income_sources = {}
        for deposit in deposits:
            if deposit.amount < -200:  # Only consider larger deposits as potential income
                name = deposit.name.lower().strip()
                if "salary" in name or "payroll" in name or "deposit" in name or "direct dep" in name:
                    if name not in income_sources:
                        income_sources[name] = []
                    income_sources[name].append(deposit)
        
        # Create/update income records
        for name, transactions in income_sources.items():
            if len(transactions) >= 1:  # Need at least one occurrence
                # Check if we already have this income source
                income = Income.query.filter_by(
                    user_id=user.id,
                    source=name
                ).first()
                
                # Average amount and latest date
                avg_amount = sum(abs(t.amount) for t in transactions) / len(transactions)
                latest_date = max(t.date for t in transactions)
                
                if not income:
                    # Create new income record
                    income = Income(
                        user_id=user.id,
                        source=name.title(),  # Capitalize for display
                        gross_amount=round(avg_amount, 2),
                        net_amount=round(avg_amount, 2),
                        frequency="bi-weekly",  # Default assumption
                        date=latest_date,
                        notes="Automatically detected from deposits"
                    )
                    db.session.add(income)
                else:
                    # Update existing income
                    income.gross_amount = round(avg_amount, 2)
                    income.net_amount = round(avg_amount, 2)
                    income.date = latest_date
        
        db.session.commit()
        return True, "Income sources detected successfully"
    
    except Exception as e:
        current_app.logger.error(f"Error analyzing income: {str(e)}")
        db.session.rollback()
        return False, f"Error analyzing income: {str(e)}"

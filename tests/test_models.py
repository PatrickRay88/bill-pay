import pytest
import datetime
from app import create_app, db
from app.models import User, Account, Transaction, Bill, Income

@pytest.fixture
def app():
    app = create_app('testing')
    
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()

@pytest.fixture
def test_user(app):
    with app.app_context():
        user = User(email='test@example.com')
        user.set_password('password123')
        db.session.add(user)
        db.session.commit()
        return user

def test_user_model(app, test_user):
    """Test the User model."""
    with app.app_context():
        # Test user creation
        user = User.query.filter_by(email='test@example.com').first()
        assert user is not None
        assert user.email == 'test@example.com'
        
        # Test password hashing
        assert user.check_password('password123')
        assert not user.check_password('wrongpassword')

def test_account_model(app, test_user):
    """Test the Account model."""
    with app.app_context():
        # Create a test account
        account = Account(
            user_id=test_user.id,
            plaid_account_id='test_account_id',
            name='Test Checking',
            type='depository',
            subtype='checking',
            current_balance=1000.00,
            available_balance=950.00
        )
        db.session.add(account)
        db.session.commit()
        
        # Test account retrieval
        saved_account = Account.query.filter_by(plaid_account_id='test_account_id').first()
        assert saved_account is not None
        assert saved_account.name == 'Test Checking'
        assert saved_account.current_balance == 1000.00
        
        # Test account-user relationship
        # Use SQLAlchemy 2.0 style session.get instead of deprecated Query.get
        user = db.session.get(User, test_user.id)
        assert len(user.accounts) == 1
        assert user.accounts[0].name == 'Test Checking'

def test_transaction_model(app, test_user):
    """Test the Transaction model."""
    with app.app_context():
        # Create a test account
        account = Account(
            user_id=test_user.id,
            plaid_account_id='test_account_id',
            name='Test Checking',
            type='depository'
        )
        db.session.add(account)
        db.session.commit()
        
        # Create a test transaction
        transaction = Transaction(
            user_id=test_user.id,
            account_id=account.id,
            plaid_transaction_id='test_transaction_id',
            name='Grocery Store',
            amount=45.67,
            date=datetime.date.today(),
            category='Food & Dining'
        )
        db.session.add(transaction)
        db.session.commit()
        
        # Test transaction retrieval
        saved_transaction = Transaction.query.filter_by(plaid_transaction_id='test_transaction_id').first()
        assert saved_transaction is not None
        assert saved_transaction.name == 'Grocery Store'
        assert saved_transaction.amount == 45.67
        assert saved_transaction.category == 'Food & Dining'
        
        # Test transaction-account relationship
        assert saved_transaction.account.name == 'Test Checking'
        
        # Test transaction-user relationship
        user = db.session.get(User, test_user.id)
        assert len(user.transactions) == 1
        assert user.transactions[0].name == 'Grocery Store'

def test_bill_model(app, test_user):
    """Test the Bill model."""
    with app.app_context():
        # Create a test bill
        bill = Bill(
            user_id=test_user.id,
            name='Rent',
            amount=1200.00,
            due_date=datetime.date.today(),
            frequency='monthly',
            category='Housing',
            status='unpaid'
        )
        db.session.add(bill)
        db.session.commit()
        
        # Test bill retrieval
        saved_bill = Bill.query.filter_by(name='Rent').first()
        assert saved_bill is not None
        assert saved_bill.amount == 1200.00
        assert saved_bill.status == 'unpaid'
        
        # Test bill-user relationship
        user = db.session.get(User, test_user.id)
        assert len(user.bills) == 1
        assert user.bills[0].name == 'Rent'

def test_income_model(app, test_user):
    """Test the Income model."""
    with app.app_context():
        # Create a test income source
        income = Income(
            user_id=test_user.id,
            source='Employer',
            gross_amount=3000.00,
            net_amount=2400.00,
            frequency='bi-weekly',
            date=datetime.date.today()
        )
        db.session.add(income)
        db.session.commit()
        
        # Test income retrieval
        saved_income = Income.query.filter_by(source='Employer').first()
        assert saved_income is not None
        assert saved_income.gross_amount == 3000.00
        assert saved_income.net_amount == 2400.00
        
        # Test income-user relationship
        user = db.session.get(User, test_user.id)
        assert len(user.incomes) == 1
        assert user.incomes[0].source == 'Employer'

import pytest
from unittest.mock import patch, MagicMock
from app import create_app, db
from app.models import User
from app.plaid_service import (
    encrypt_token, decrypt_token, create_link_token,
    exchange_public_token, fetch_accounts, fetch_transactions
)

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

def test_encrypt_decrypt_token(app):
    """Test the token encryption and decryption."""
    with app.app_context():
        token = "test-access-token"
        encrypted = encrypt_token(token)
        
        # Ensure encrypted token is different from original
        assert encrypted != token
        
        # Ensure we can decrypt back to the original
        decrypted = decrypt_token(encrypted)
        assert decrypted == token
        
        # Test with empty token
        assert encrypt_token(None) is None
        assert decrypt_token(None) is None

@patch('app.plaid_service.plaid_client')
def test_create_link_token(mock_plaid_client, app, test_user):
    """Test creating a Plaid Link token."""
    # Mock the Plaid client response
    mock_response = MagicMock()
    mock_response.link_token = "test-link-token"
    mock_plaid_client.link_token_create.return_value = mock_response
    
    with app.app_context():
        token = create_link_token(test_user.id)
        assert token == "test-link-token"
        mock_plaid_client.link_token_create.assert_called_once()

@patch('app.plaid_service.plaid_client')
@patch('app.plaid_service.fetch_accounts')
@patch('app.plaid_service.fetch_transactions')
@patch('app.plaid_service.fetch_liabilities')
@patch('app.plaid_service.fetch_income')
def test_exchange_public_token(
    mock_fetch_income, mock_fetch_liabilities, mock_fetch_transactions, 
    mock_fetch_accounts, mock_plaid_client, app, test_user
):
    """Test exchanging a public token."""
    # Mock the Plaid client response
    mock_exchange_response = MagicMock()
    mock_exchange_response.access_token = "test-access-token"
    mock_exchange_response.item_id = "test-item-id"
    mock_plaid_client.item_public_token_exchange.return_value = mock_exchange_response
    
    # Set up mocks for fetch methods
    mock_fetch_accounts.return_value = (True, "Success")
    mock_fetch_transactions.return_value = (True, "Success")
    mock_fetch_liabilities.return_value = (True, "Success")
    mock_fetch_income.return_value = (True, "Success")
    
    with app.app_context():
        success, message = exchange_public_token("test-public-token", test_user)
        
        # Check that token exchange was successful
        assert success is True
        assert "Successfully connected" in message
        
        # Check that user record was updated
        user = User.query.get(test_user.id)
        assert user.plaid_access_token is not None
        assert user.item_id == "test-item-id"
        
        # Check that fetch methods were called
        mock_fetch_accounts.assert_called_once_with(test_user)
        mock_fetch_transactions.assert_called_once_with(test_user)
        mock_fetch_liabilities.assert_called_once_with(test_user)
        mock_fetch_income.assert_called_once_with(test_user)

# Mock classes and helpers for Plaid responses
class MockAccount:
    def __init__(self, account_id, name, type_, balances=None):
        self.account_id = account_id
        self.name = name
        self.official_name = f"Official {name}"
        self.type = type_
        self.subtype = "checking" if type_ == "depository" else "credit card"
        self.mask = "1234"
        self.balances = balances or MockBalances()

class MockBalances:
    def __init__(self, current=1000.0, available=900.0, currency="USD"):
        self.current = current
        self.available = available
        self.iso_currency_code = currency

@patch('app.plaid_service.decrypt_token')
@patch('app.plaid_service.plaid_client')
def test_fetch_accounts(mock_plaid_client, mock_decrypt_token, app, test_user):
    """Test fetching accounts from Plaid."""
    # Set up mocks
    mock_decrypt_token.return_value = "decrypted-token"
    
    # Create mock accounts response
    mock_account1 = MockAccount("acc1", "Checking", "depository")
    mock_account2 = MockAccount("acc2", "Credit Card", "credit")
    mock_response = MagicMock()
    mock_response.accounts = [mock_account1, mock_account2]
    mock_plaid_client.accounts_get.return_value = mock_response
    
    with app.app_context():
        # Set up test user with access token
        test_user.plaid_access_token = "encrypted-token"
        db.session.commit()
        
        # Fetch accounts
        success, message = fetch_accounts(test_user)
        
        # Check that fetch was successful
        assert success is True
        assert "successfully" in message
        
        # Check that accounts were created
        accounts = test_user.accounts
        assert len(accounts) == 2
        account_ids = [acc.plaid_account_id for acc in accounts]
        assert "acc1" in account_ids
        assert "acc2" in account_ids

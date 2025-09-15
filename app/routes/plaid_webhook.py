from flask import Blueprint, request, jsonify
from app import db
from app.models import User
from app.plaid_service import fetch_accounts, fetch_transactions, decrypt_token

plaid_webhook_bp = Blueprint('plaid_webhook', __name__, url_prefix='/api/plaid')

@plaid_webhook_bp.route('/link-token', methods=['POST'])
def get_link_token():
    """Create a link token for the current user."""
    from app.plaid_service import create_link_token
    from flask_login import current_user, login_required
    
    @login_required
    def get_token():
        link_token = create_link_token(current_user.id)
        if link_token:
            return jsonify({"link_token": link_token})
        else:
            return jsonify({"error": "Failed to create link token"}), 400
    
    return get_token()

@plaid_webhook_bp.route('/exchange-token', methods=['POST'])
def exchange_token():
    """Exchange a public token for an access token."""
    from app.plaid_service import exchange_public_token
    from flask_login import current_user, login_required
    
    @login_required
    def exchange():
        public_token = request.json.get('public_token')
        if not public_token:
            return jsonify({"error": "No public token provided"}), 400
            
        success, message = exchange_public_token(public_token, current_user)
        if success:
            return jsonify({"message": message})
        else:
            return jsonify({"error": message}), 400
    
    return exchange()

@plaid_webhook_bp.route('/webhook', methods=['POST'])
def webhook():
    """Handle Plaid webhooks."""
    webhook_data = request.json
    webhook_type = webhook_data.get('webhook_type')
    webhook_code = webhook_data.get('webhook_code')
    
    # Log the webhook
    from app import create_app
    app = create_app()
    with app.app_context():
        app.logger.info(f"Received Plaid webhook - Type: {webhook_type}, Code: {webhook_code}")
    
    # Handle different webhook types
    if webhook_type == 'TRANSACTIONS':
        item_id = webhook_data.get('item_id')
        
        with app.app_context():
            # Find the user with this item_id
            user = User.query.filter_by(item_id=item_id).first()
            if not user:
                app.logger.error(f"No user found for item_id: {item_id}")
                return jsonify({"status": "error", "message": "User not found"}), 400
            
            if webhook_code == 'INITIAL_UPDATE' or webhook_code == 'HISTORICAL_UPDATE':
                # Initial or historical transactions update
                app.logger.info(f"Fetching initial/historical transactions for user {user.id}")
                fetch_transactions(user)
            elif webhook_code == 'DEFAULT_UPDATE':
                # Regular update with new transactions
                app.logger.info(f"Fetching new transactions for user {user.id}")
                fetch_transactions(user)
            elif webhook_code == 'TRANSACTIONS_REMOVED':
                # Transactions were removed - would need to sync removals
                app.logger.info(f"Processing removed transactions for user {user.id}")
                # Implement removal logic if needed
                pass
    
    elif webhook_type == 'ITEM':
        item_id = webhook_data.get('item_id')
        
        with app.app_context():
            user = User.query.filter_by(item_id=item_id).first()
            if not user:
                app.logger.error(f"No user found for item_id: {item_id}")
                return jsonify({"status": "error", "message": "User not found"}), 400
            
            if webhook_code == 'ERROR':
                # Handle item error
                app.logger.error(f"Item error for user {user.id}: {webhook_data.get('error')}")
            elif webhook_code == 'PENDING_EXPIRATION':
                # Access token is expiring soon
                app.logger.info(f"Access token expiring soon for user {user.id}")
                # Implement token update logic if needed
                pass
            elif webhook_code == 'USER_PERMISSION_REVOKED':
                # User revoked permissions - clear Plaid credentials
                app.logger.info(f"Permissions revoked for user {user.id}")
                user.plaid_access_token = None
                user.item_id = None
                db.session.commit()
    
    return jsonify({"status": "success"})

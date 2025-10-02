from flask import Blueprint, request, jsonify, session, current_app, redirect, url_for
from app import db
from app.models import User
from app.plaid_service import fetch_accounts, fetch_transactions, decrypt_token, unlink_plaid, unlink_plaid_item

plaid_webhook_bp = Blueprint('plaid_webhook', __name__, url_prefix='/api/plaid')

@plaid_webhook_bp.route('/diagnostics', methods=['GET'])
def diagnostics():
    """Return safe Plaid configuration diagnostics (no secrets)."""
    from flask_login import current_user
    cfg = current_app.config
    data = {
        'env': cfg.get('PLAID_ENV'),
        'use_plaid': bool(cfg.get('USE_PLAID')),
        'products': cfg.get('PLAID_PRODUCTS'),
        'redirect_uri_set': bool(cfg.get('PLAID_REDIRECT_URI')),
        'client_id_present': bool(cfg.get('PLAID_CLIENT_ID')),
        'secret_selected': bool(cfg.get('PLAID_SECRET_RESOLVED')),
        'user_authenticated': current_user.is_authenticated,
        'link_token_in_session': bool(session.get('plaid_link_token'))
    }
    return jsonify(data)

@plaid_webhook_bp.route('/link-token', methods=['POST'])
def get_link_token():
    """Create a link token for the current user."""
    from app.plaid_service import create_link_token
    from flask_login import current_user, login_required
    
    @login_required
    def get_token():
        link_token = create_link_token(current_user.id)
        if link_token:
            # Persist most recent link token so we can reuse after OAuth redirect
            session['plaid_link_token'] = link_token
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
            
        institution_name = request.json.get('institution_name')
        success, message = exchange_public_token(public_token, current_user, institution_name=institution_name)
        if success:
            return jsonify({"message": message})
        else:
            return jsonify({"error": message}), 400
    
    return exchange()

@plaid_webhook_bp.route('/oauth-response')
def oauth_response():
    """Handle the browser redirect back from an OAuth-based institution flow.

    Plaid requires re-initializing Link with the same link_token after redirect.
    We simply render a minimal page that triggers JS to resume Link (handled by main.js).
    """
    # Token should be in session; if missing, guide user back to dashboard to start over.
    link_token = session.get('plaid_link_token')
    if not link_token:
        current_app.logger.warning('OAuth redirect without stored link_token; redirecting to dashboard.')
        return redirect(url_for('dashboard.index'))
    # Render a lightweight inline HTML (avoid new template overhead) referencing existing JS which will detect token.
    html = (
        "<html><head><title>Plaid OAuth Redirect</title>"
        "<script src='https://cdn.plaid.com/link/v2/stable/link-initialize.js'></script>"
        "<script>window.addEventListener('load',function(){"
        "var handler=Plaid.create({token:'" + link_token + "',receivedRedirectUri:window.location.href,onSuccess:function(public_token){"
        "fetch('/api/plaid/exchange-token',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({public_token:public_token})})"
        ".then(r=>r.json()).then(d=>{if(d.error){alert('Error: '+d.error);}else{window.location='/dashboard';}});},"
        "onExit:function(err){console.log('Plaid exit after OAuth',err);window.location='/dashboard';}});handler.open();});</script></head>"
        "<body><p style='font-family:sans-serif;padding:1rem;'>Resuming Plaid connection…</p></body></html>"
    )
    return html


@plaid_webhook_bp.route('/unlink', methods=['POST'])
def unlink():
    """Unlink (disconnect) Plaid for the current user, optionally clearing imported data."""
    from flask_login import current_user, login_required

    @login_required
    def do_unlink():
        reset = True
        if request.is_json:
            reset = bool(request.json.get('reset', True))
        success, message = unlink_plaid(current_user, reset_data=reset)
        if success:
            return jsonify({"message": message})
        return jsonify({"error": message}), 400

    return do_unlink()

@plaid_webhook_bp.route('/unlink-item/<int:item_id>', methods=['POST'])
def unlink_item(item_id):
    """Unlink a single Plaid item (institution)."""
    from flask_login import current_user, login_required

    @login_required
    def do_unlink_item():
        reset = True
        if request.is_json:
            reset = bool(request.json.get('reset', True))
        success, message = unlink_plaid_item(current_user, item_id, reset_data=reset)
        if success:
            return jsonify({"message": message})
        return jsonify({"error": message}), 400

    return do_unlink_item()

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

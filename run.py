import os
from app import create_app

# Create app instance with configuration from environment
app = create_app(os.getenv('FLASK_CONFIG', 'default'))

if __name__ == '__main__':
    app.run(debug=app.config['DEBUG'])

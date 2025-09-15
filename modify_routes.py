import os
import re

# Define route files to modify
route_files = [
    'accounts.py',
    'bills.py',
    'income.py',
    'transactions.py'
]

# Path to the routes directory
routes_dir = 'app/routes'

# Loop through each file and replace login_required decorators
for file_name in route_files:
    file_path = os.path.join(routes_dir, file_name)
    
    with open(file_path, 'r') as file:
        content = file.read()
    
    # Replace imports
    new_content = re.sub(
        r'from flask_login import (.*?)login_required(.*?)current_user',
        r'from flask_login import \1\2current_user',
        content
    )
    
    # Remove @login_required decorators
    new_content = re.sub(r'@login_required\n', '', new_content)
    
    # Add check for current_user authentication
    new_content = re.sub(
        r'def (\w+)\(.*?\):\n    """(.*?)"""',
        r'def \1(*args, **kwargs):\n    """\2"""\n    # Ensure user is authenticated\n    if not current_user.is_authenticated:\n        return redirect(url_for(\'auth.auto_login\'))',
        new_content
    )
    
    # Add import for redirect and url_for if not present
    if 'from flask import ' in new_content and 'redirect' not in new_content:
        new_content = new_content.replace(
            'from flask import ',
            'from flask import redirect, url_for, '
        )
    
    with open(file_path, 'w') as file:
        file.write(new_content)
    
    print(f'Modified {file_path}')

# BillPay - Plaid-Powered Financial Dashboard

BillPay is a mobile-first Flask web application that automatically pulls all financial data from Plaid. The app aggregates bank accounts, credit cards, bills, and income streams directly from Plaid and provides budgeting, paycheck modeling, and historical insights.

## Features

- **Automatic Data Sync**: Uses Plaid as the single source of truth for linked accounts, balances, transactions, and recurring bills/income
- **Dashboard**: Visual overview of financial health including net worth, income vs. expenses, and upcoming bills
- **Accounts**: View all linked accounts and balances from multiple financial institutions
- **Transactions**: Browse, filter, and search transactions with automatic categorization
- **Bills**: Track recurring bills with due dates, status, and payment history
- **Income**: Monitor income sources with paycheck simulator for financial planning

## Technology Stack

- **Backend**: Flask + SQLAlchemy
- **Frontend**: Jinja2 + Bootstrap 5 + Chart.js
- **Database**: PostgreSQL (production) / SQLite (development)
- **Plaid SDK**: plaid-python for all data access

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/billpay.git
   cd billpay
   ```

2. Create and activate a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   Create a `.env` file in the project root with:
   ```
   FLASK_APP=run.py
   FLASK_ENV=development
   SECRET_KEY=your-secret-key
   PLAID_CLIENT_ID=your-plaid-client-id
   PLAID_SECRET=your-plaid-sandbox-secret
   PLAID_ENV=sandbox
   ```

5. Initialize the database:
   ```
   flask db init
   flask db migrate -m "Initial migration"
   flask db upgrade
   ```

6. Run the application:
   ```
   flask run
   ```

7. Access the application at: http://127.0.0.1:5000/

## Plaid Integration

BillPay uses the following Plaid products:
- Auth & Accounts: For account details and balances
- Transactions: For all bank and credit transactions
- Liabilities: For loans, credit card bills, and mortgage information
- Income (optional): For paycheck and deposit stream data

## Development

### Project Structure

```
finance_app/
│
├── app/
│   ├── __init__.py
│   ├── models.py
│   ├── plaid_service.py
│   ├── forms.py
│   ├── routes/
│   │   ├── auth.py
│   │   ├── dashboard.py
│   │   ├── accounts.py
│   │   ├── transactions.py
│   │   ├── bills.py
│   │   ├── income.py
│   │   └── plaid_webhook.py
│   ├── templates/
│   │   ├── base.html
│   │   ├── landing.html
│   │   ├── auth/
│   │   ├── dashboard/
│   │   ├── accounts/
│   │   ├── transactions/
│   │   ├── bills/
│   │   ├── income/
│   │   └── partials/
│   └── static/
│       ├── css/
│       └── js/
│
├── migrations/
├── tests/
│   ├── test_plaid.py
│   ├── test_models.py
│   └── test_routes.py
├── config.py
├── run.py
└── requirements.txt
```

### Running Tests

```
pytest
```

## Deployment

BillPay can be deployed to platforms like Heroku, Fly.io, or any other platform that supports Python applications.

For production deployment:
1. Set environment variables for production
2. Configure a PostgreSQL database
3. Use gunicorn as the WSGI server

## License

[MIT License](LICENSE)

## Acknowledgements

- [Plaid API](https://plaid.com/docs/) - Financial data connectivity
- [Flask](https://flask.palletsprojects.com/) - Web framework
- [Bootstrap](https://getbootstrap.com/) - Frontend components
- [Chart.js](https://www.chartjs.org/) - Interactive charts

// Main JavaScript for BillPay

document.addEventListener('DOMContentLoaded', function() {
    // Initialize Plaid Link if token is available
    initPlaidLink();
    initRefreshButtons();
    initUnlinkPlaid();
    
    // Initialize tooltips
    var tooltips = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    tooltips.forEach(function(tooltip) {
        new bootstrap.Tooltip(tooltip);
    });
    
    // Bill status toggle
    setupBillStatusToggle();
    
    // Format currency displays
    formatCurrencyDisplays();
});

// Initialize Plaid Link
function initPlaidLink() {
    const linkTokenElement = document.getElementById('plaid-link-token');
    if (!linkTokenElement) return;
    const linkButtons = document.querySelectorAll('.plaid-link-button');
    if (!linkButtons.length) return;

    const linkToken = linkTokenElement.dataset.token;

    // Initialize Plaid Link once
    const handler = Plaid.create({
        token: linkToken,
        onSuccess: (public_token, metadata) => {
            exchangePublicToken(public_token);
        },
        onExit: (err, metadata) => {
            if (err) {
                console.error('Plaid Link Error:', err);
                showAlert('danger', 'There was an error connecting your bank. Please try again.');
            }
        },
        onEvent: (event, metadata) => {
            console.log('Plaid Link Event:', event, metadata);
        }
    });

    linkButtons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            handler.open();
        });
    });
}

function initUnlinkPlaid() {
    const unlinkBtn = document.getElementById('plaid-unlink-button');
    if (!unlinkBtn) return;
    unlinkBtn.addEventListener('click', () => {
        if(!confirm('Unlink Plaid and remove imported data?')) return;
        showLoadingOverlay();
        fetch('/api/plaid/unlink', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCSRFToken() },
            body: JSON.stringify({ reset: true })
        })
        .then(r=>r.json())
        .then(d=>{ hideLoadingOverlay(); if(d.error){ showAlert('danger', d.error);} else { showAlert('success','Unlinked. Reloading…'); setTimeout(()=>window.location.reload(),1000);} })
        .catch(e=>{ hideLoadingOverlay(); console.error(e); showAlert('danger','Unlink failed'); });
    });
}

function initRefreshButtons() {
    const accountsBtn = document.getElementById('refresh-accounts-btn');
    const transactionsBtn = document.getElementById('refresh-transactions-btn');
    if (accountsBtn) {
        accountsBtn.addEventListener('click', () => {
            showLoadingOverlay();
            fetch('/accounts/refresh', { headers: { 'X-CSRFToken': getCSRFToken() }} )
                .then(r => r.json())
                .then(d => { hideLoadingOverlay(); if(d.success){ showAlert('success','Accounts refreshed'); setTimeout(()=>window.location.reload(),900);} else { showAlert('warning', d.message||'Accounts refresh failed'); }})
                .catch(e => { hideLoadingOverlay(); console.error(e); showAlert('danger','Accounts refresh error'); });
        });
    }
    if (transactionsBtn) {
        transactionsBtn.addEventListener('click', () => {
            showLoadingOverlay();
            fetch('/transactions/refresh', { headers: { 'X-CSRFToken': getCSRFToken() }} )
                .then(r => r.json())
                .then(d => { hideLoadingOverlay(); if(d.success){ showAlert('success','Transactions refreshed'); setTimeout(()=>window.location.reload(),900);} else { showAlert('warning', d.message||'Transactions refresh failed'); }})
                .catch(e => { hideLoadingOverlay(); console.error(e); showAlert('danger','Transactions refresh error'); });
        });
    }
}


// Exchange public token for access token
function exchangePublicToken(public_token) {
    showLoadingOverlay();
    
    fetch('/api/plaid/exchange-token', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify({ public_token: public_token })
    })
    .then(response => response.json())
    .then(data => {
        hideLoadingOverlay();
        if (data.error) {
            showAlert('danger', data.error);
        } else {
            showAlert('success', 'Bank account connected successfully!');
            setTimeout(() => {
                window.location.reload();
            }, 1500);
        }
    })
    .catch(error => {
        hideLoadingOverlay();
        console.error('Error:', error);
        showAlert('danger', 'Failed to connect bank account. Please try again.');
    });
}

// Get CSRF token from meta tag
function getCSRFToken() {
    return document.querySelector('meta[name="csrf-token"]').getAttribute('content');
}

// Setup bill status toggle functionality
function setupBillStatusToggle() {
    const statusToggles = document.querySelectorAll('.bill-status-toggle');
    
    statusToggles.forEach(toggle => {
        toggle.addEventListener('change', function() {
            const billId = this.dataset.billId;
            const checked = this.checked;
            
            fetch(`/bills/${billId}/toggle-status`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCSRFToken()
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Update UI if needed
                    const billItem = this.closest('.bill-item');
                    if (billItem) {
                        if (data.status === 'paid') {
                            billItem.classList.add('paid');
                            billItem.classList.remove('past-due');
                        } else {
                            billItem.classList.remove('paid');
                            // Check if past due
                            const dueDate = new Date(billItem.dataset.dueDate);
                            if (dueDate < new Date()) {
                                billItem.classList.add('past-due');
                            }
                        }
                    }
                    
                    showAlert('success', `Bill marked as ${data.status}`);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showAlert('danger', 'Failed to update bill status');
                // Revert toggle state
                this.checked = !checked;
            });
        });
    });
}

// Format all currency displays
function formatCurrencyDisplays() {
    const elements = document.querySelectorAll('.format-currency');
    
    elements.forEach(element => {
        const value = parseFloat(element.textContent);
        if (!isNaN(value)) {
            element.textContent = formatCurrency(value);
        }
    });
}

// Format a number as currency
function formatCurrency(value) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD'
    }).format(value);
}

// Show an alert message
function showAlert(type, message) {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.role = 'alert';
    
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    const container = document.querySelector('.container');
    container.insertBefore(alertDiv, container.firstChild);
    
    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        const bsAlert = new bootstrap.Alert(alertDiv);
        bsAlert.close();
    }, 5000);
}

// Show loading overlay
function showLoadingOverlay() {
    const overlay = document.createElement('div');
    overlay.className = 'loading-overlay';
    overlay.innerHTML = `
        <div class="spinner-border text-primary" role="status">
            <span class="visually-hidden">Loading...</span>
        </div>
    `;
    document.body.appendChild(overlay);
}

// Hide loading overlay
function hideLoadingOverlay() {
    const overlay = document.querySelector('.loading-overlay');
    if (overlay) {
        overlay.remove();
    }
}

import os, sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Default manual mode unless explicitly enabled externally
os.environ.setdefault('USE_PLAID', 'false')

PLAID_ENABLED = os.environ.get('USE_PLAID', 'false').lower() in ('1','true','yes','on')

def pytest_configure(config):
    config.addinivalue_line("markers", "plaid: marks tests that require Plaid feature flag (deselect with -m 'not plaid')")

def pytest_collection_modifyitems(config, items):
    if PLAID_ENABLED:
        return
    skip_plaid = pytest.mark.skip(reason="Plaid disabled (USE_PLAID env var false)")
    for item in items:
        if 'plaid' in item.keywords:
            item.add_marker(skip_plaid)
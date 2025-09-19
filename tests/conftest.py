import os, sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Keep default manual mode for runtime, but do NOT use it to skip mocked tests
os.environ.setdefault('USE_PLAID', 'false')

# Only true integration tests should be gated by this toggle
RUN_PLAID_INTEGRATION = os.environ.get('RUN_PLAID_INTEGRATION', 'false').lower() in ('1','true','yes','on')

def pytest_configure(config):
    config.addinivalue_line("markers", "plaid: mocked Plaid unit tests (no real API)")
    config.addinivalue_line("markers", "plaid_integration: tests that hit real Plaid; enable with RUN_PLAID_INTEGRATION=true")

def pytest_collection_modifyitems(config, items):
    # By default, run all tests including those marked 'plaid' (mocked).
    # Only skip real integration tests unless explicitly enabled.
    if RUN_PLAID_INTEGRATION:
        return
    skip_integration = pytest.mark.skip(reason="plaid_integration disabled (set RUN_PLAID_INTEGRATION=true to enable)")
    for item in items:
        if 'plaid_integration' in item.keywords:
            item.add_marker(skip_integration)

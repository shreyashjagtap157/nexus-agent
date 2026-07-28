import sys
from unittest.mock import MagicMock

# ⚡ Mock optional blessed dependency for tests
sys.modules['blessed'] = MagicMock()

import sys
from unittest.mock import MagicMock

# Mock blessed globally to prevent missing dependency errors in tests
sys.modules['blessed'] = MagicMock()

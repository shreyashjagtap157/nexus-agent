

import sys
from unittest.mock import MagicMock
if 'blessed' not in sys.modules:
    sys.modules['blessed'] = MagicMock()

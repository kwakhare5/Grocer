import traceback
try:
    import prophet.models
    print("prophet.models imported.")
except Exception as e:
    traceback.print_exc()

import sys
from prophet.models import CmdStanPyBackend

try:
    backend = CmdStanPyBackend()
    print("Backend instantiated successfully!")
except Exception as e:
    traceback.print_exc()

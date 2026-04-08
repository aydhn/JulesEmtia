import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("Testing core engine imports...")
try:
    import main
    from src import strategy
    from src import ml_validator
    from src import features
    from src import portfolio_manager
    from src import broker
    from src import monte_carlo
    from src import reporter
    from src import sentiment_filter
    from src import data_engine
    print("SUCCESS: All modules imported without errors.")
except Exception as e:
    import traceback
    print(f"FAILED: Import error detected -> {e}")
    traceback.print_exc()

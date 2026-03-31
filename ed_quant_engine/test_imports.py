import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

print("Testing imports again...")
try:
    import main
    import strategy
    import ml_validator
    import features
    import portfolio_manager
    import execution_model
    import paper_db
    import paper_broker
    import walk_forward
    import monte_carlo
    print("SUCCESS: All modules including new ones imported without errors.")
except Exception as e:
    print(f"FAILED: Import error detected -> {e}")

import sys
import os
sys.path.insert(0, os.path.abspath('ed_quant_engine'))

# Import all modules to ensure there are no syntax errors or unresolved imports
try:
    import config
    from core_engine import PaperDB, TelegramManager, logger
    from data_intelligence import DataEngine
    from risk_portfolio import RiskManager
    from trading_logic import PaperBroker, TradingSystem
    from reporter import ReportEngine
    from backtester import Backtester
    from walk_forward import WalkForwardOptimization
    from main import QuantOrchestrator

    print("Core Modules Loaded Successfully!")
except Exception as e:
    print(f"Error loading modules: {e}")
    sys.exit(1)

print("All tests passed.")

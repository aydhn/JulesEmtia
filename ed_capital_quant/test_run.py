import sys
import os

# Add the project root to sys.path so that absolute imports work
sys.path.append(os.path.abspath("ed_capital_quant"))

# Import main file to test if syntax and imports are correct
import main
print("Imports and syntax look good!")

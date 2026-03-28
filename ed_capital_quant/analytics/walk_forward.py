import pandas as pd

def walk_forward_optimization(data: pd.DataFrame, train_size=252, test_size=63):
    results = []
    for start in range(0, len(data) - train_size - test_size, test_size):
        train = data.iloc[start:start+train_size]
        test = data.iloc[start+train_size:start+train_size+test_size]
        # In real WFO:
        # best_params = optimize(train)
        # oos_performance = test_strategy(test, best_params)
        # results.append(oos_performance)
    return results

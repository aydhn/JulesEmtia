import pandas as pd
from utils.logger import log

def walk_forward_optimization(data: pd.DataFrame, train_size=252, test_size=63) -> pd.DataFrame:
    log.info("Walk-Forward Optimization Başlatılıyor...")
    results = []

    # Simple IS/OOS rolling window simulation
    for start in range(0, len(data) - train_size - test_size, test_size):
        train = data.iloc[start:start+train_size]
        test = data.iloc[start+train_size:start+train_size+test_size]

        # Here we mock the IS/OOS calculation.
        # In a real WFO, we would iterate params over `train` to maximize return,
        # then apply those exact params to `test` to get `oos_performance`.
        is_return = train['Close'].pct_change().sum() * 100
        oos_return = test['Close'].pct_change().sum() * 100

        wfe = (oos_return / is_return) if is_return != 0 else 0

        results.append({
            'Start_Date': train.index[0],
            'OOS_Start': test.index[0],
            'IS_Return': is_return,
            'OOS_Return': oos_return,
            'WFE': wfe
        })

        if wfe < 0.5:
            log.warning(f"OOS Return zayıf. WFE: {wfe:.2f}. Aşırı öğrenme (Overfitting) tespiti!")

    return pd.DataFrame(results)

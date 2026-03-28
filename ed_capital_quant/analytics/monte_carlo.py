import numpy as np

def run_monte_carlo(trades: list, simulations=10000) -> dict:
    if not trades: return {"Risk_of_Ruin": 0, "Expected_MDD_99": 0}

    results = []
    for _ in range(simulations):
        sampled = np.random.choice(trades, size=len(trades), replace=True)
        cumulative = np.cumprod(1 + sampled)
        mdd = (np.maximum.accumulate(cumulative) - cumulative) / np.maximum.accumulate(cumulative)
        results.append(mdd.max())

    return {
        "Risk_of_Ruin": np.mean(np.array(results) > 0.50),
        "Expected_MDD_99": np.percentile(results, 99)
    }

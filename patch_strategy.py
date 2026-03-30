import re

with open("ed_quant_engine/src/strategy.py", "r") as f:
    content = f.read()

# Add import for paper_db at the top
content = content.replace("from .logger", "from .paper_db import get_closed_trades\nfrom .logger")

# Replace fallback kelly logic with dynamic logic
new_kelly_logic = """
        # Kelly Büyüklük Hesaplaması (Daha önce SQLite'dan çekilmiş performans metriklerine göre)
        closed_trades = get_closed_trades()
        recent_trades = closed_trades[:50] if len(closed_trades) >= 10 else []

        if len(recent_trades) >= 10:
            wins = [t for t in recent_trades if t['pnl'] > 0]
            losses = [t for t in recent_trades if t['pnl'] <= 0]
            win_rate = len(wins) / len(recent_trades)
            avg_win = sum([t['pnl'] for t in wins]) / len(wins) if wins else 0
            avg_loss = abs(sum([t['pnl'] for t in losses]) / len(losses)) if losses else 1
            reward_risk = avg_win / avg_loss if avg_loss > 0 else 1.5
        else:
            win_rate = 0.60
            reward_risk = 1.5

        position_size = calculate_kelly_position(current_balance, win_rate, reward_risk, atr_stop_dist)
"""

# Find the block to replace
old_kelly_logic_regex = r"# Kelly Büyüklük Hesaplaması.*?(?=        # Kelly Koruması Vetosu)"

content = re.sub(old_kelly_logic_regex, new_kelly_logic, content, flags=re.DOTALL)

with open("ed_quant_engine/src/strategy.py", "w") as f:
    f.write(content)

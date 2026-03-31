# ED Capital Quant Engine Trading Universe

# Major Commodities
PRECIOUS_METALS = ["GC=F", "SI=F", "HG=F", "PA=F", "PL=F"]
ENERGY = ["CL=F", "BZ=F", "NG=F", "HO=F", "RB=F"]
AGRICULTURE = ["ZW=F", "ZC=F", "ZS=F", "KC=F", "CC=F", "SB=F", "CT=F", "LE=F"]

# TRY-based Forex
FOREX_TRY = ["USDTRY=X", "EURTRY=X", "GBPTRY=X", "JPYTRY=X", "CNHY=X", "CHFTRY=X", "AUDTRY=X"]

# Full Universe
UNIVERSE = PRECIOUS_METALS + ENERGY + AGRICULTURE + FOREX_TRY

# Spread Definitions (Base spread percentage per category)
SPREADS = {}
for ticker in PRECIOUS_METALS:
    SPREADS[ticker] = 0.0002  # 0.02%
for ticker in ENERGY:
    SPREADS[ticker] = 0.0003  # 0.03%
for ticker in AGRICULTURE:
    SPREADS[ticker] = 0.0005  # 0.05%
for ticker in FOREX_TRY:
    SPREADS[ticker] = 0.0010  # 0.10%

def get_base_spread(ticker: str) -> float:
    """Returns the base spread for a ticker."""
    return SPREADS.get(ticker, 0.0005)

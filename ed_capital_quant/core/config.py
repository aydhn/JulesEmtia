# ED Capital - Universe & Risk Configurations
TICKERS = {
    "METALS": ["GC=F", "SI=F", "HG=F", "PA=F", "PL=F"],
    "ENERGY": ["CL=F", "BZ=F", "NG=F", "HO=F", "RB=F"],
    "AGRI":   ["ZW=F", "ZC=F", "ZS=F", "KC=F", "CC=F", "SB=F", "CT=F"],
    "FX_TRY": ["USDTRY=X", "EURTRY=X", "GBPTRY=X", "JPYTRY=X", "CNHY=X", "CHFTRY=X"]
}

# Risk Limits (Phase 11 & 15)
MAX_OPEN_POSITIONS = 4
MAX_TOTAL_RISK_PCT = 0.06
FRACTIONAL_KELLY = 0.5
HARD_CAP_PCT = 0.04
CORRELATION_THRESHOLD = 0.75

# Spreads (Phase 21)
BASE_SPREADS = {"METALS": 0.0002, "ENERGY": 0.0003, "AGRI": 0.0005, "FX_TRY": 0.0010}

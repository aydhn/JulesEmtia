# ed_quant_engine

Canonical JulesEmtia application package.

Run from the repository root:

```powershell
.\start_windows.bat
```

Direct development commands:

```powershell
$env:PYTHONPATH="$PWD\ed_quant_engine"
.\.venv\Scripts\python.exe ed_quant_engine\main.py
.\.venv\Scripts\python.exe scripts\runtime_diagnostics.py
```

Runtime artifacts are intentionally ignored by Git:

- `ed_quant_engine/data`
- `ed_quant_engine/logs`
- `ed_quant_engine/models`
- `ed_quant_engine/reports`

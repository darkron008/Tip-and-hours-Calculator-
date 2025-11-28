# Tip-and-hours-Calculator-

Minimal Python scaffold for tip and hours calculations.

Run locally (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate
pip install -r requirements.txt
python -m pytest -q
```

Examples:

```powershell
python app.py tip --amount 100 --percent 15
python app.py pay --hours 40 --rate 15.50
```

Web UI:

Run the Flask web UI locally and open http://127.0.0.1:5000 in your browser:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
python web_app.py
```

Upload your report, adjust column headers if needed, and download the generated Excel summary.

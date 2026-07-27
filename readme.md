# CFS Stock — Quick Start 
This is a small local web app to track stock across Workshop and Paddock. These instructions assume you use Windows and have no prior experience. Follow each step exactly.

---

## What this does
- View, add, remove and move stock between locations  
- Admin panel for creating/deleting items, importing Excel, exporting XLSX and viewing logs  
- Local database file: `Webapp/Backend/stock.db`

---

## 1 — Install required software
1. Install Python 3.10+ from https://www.python.org/downloads/  
   - During install, check "Add Python to PATH".  
2. (Optional) Install Git: https://git-scm.com/downloads

---

## 2 — Prepare the project (one-time)
Open PowerShell and run the commands below (paste line-by-line). Adjust paths if your project is elsewhere.

```powershell
cd "D:\CFS_WEBAPP\CFS_Stock_site\Webapp\Backend"
python -m venv venv
.\venv\Scripts\Activate.ps1     # if using PowerShell
# OR for Command Prompt:
# .\venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r "..\..\requirements.txt"
```

If PowerShell blocks running scripts, run once (as admin if required):
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

---

## 3 — Start the app (local + LAN access)
While the virtual environment is active:

```powershell
cd "D:\CFS_WEBAPP\CFS_Stock_site\Webapp\Backend"
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

- Open on the PC: http://localhost:8000  
- From another device on the same Wi‑Fi: find your PC IP (run `ipconfig`) then open `http://<YOUR_PC_IP>:8000`  
- Allow port 8000 through Windows Firewall if prompted

---

## 4 — Admin user
- Visit the Admin page in the app to create an admin user if none exists.  
- Admins can import Excel files, export data, manage users and view logs.

---

## 5 — Import stock from Excel (.xlsx)
The importer expects columns:
- Column A = Category (empty cells will inherit the previous non-empty category)
- Column B = Product code (item code)
- Column C = Product name

If your import script is in a folder with spaces (e.g. `stock import`) either:
- Run with quotes:
```powershell
python "D:\CFS_WEBAPP\CFS_Stock_site\Webapp\Backend\stock import\import_stock_xlsx.py"
```
- Or rename the folder to avoid spaces:
```powershell
Rename-Item "D:\CFS_WEBAPP\CFS_Stock_site\Webapp\Backend\stock import" stock_import
python .\stock_import\import_stock_xlsx.py
```

The script will create or update items at the default location (Workshop) unless modified.

---

## 6 — Common workflows
- Overview: search by product name, category or item code; see per-location counts.  
- Home (Quick edit): select category → product → location, choose Add or Remove, enter quantity and order code, then Confirm.  
- Move stock: choose product, From, To and quantity.  
- Export (Admin): downloads an XLSX with sheets for Stock, Logs and Users. The filename is timestamped.

---

## 7 — Backups
Recommended: copy the `stock.db` file regularly to an external folder.

Simple Python helper (place in backend and run/schedule it):
```python
from pathlib import Path
from datetime import datetime
import shutil

src = Path(__file__).resolve().parent / "stock.db"
dest_dir = Path("D:/CFS_WEBAPP/CFS_Stock_site/backups")
dest_dir.mkdir(parents=True, exist_ok=True)
t = datetime.now().strftime("%Y%m%d-%H%M%S")
shutil.copy2(src, dest_dir / f"stock-{t}.db")
```

Or schedule a PowerShell Task to run a single-line copy:
```powershell
Copy-Item "D:\CFS_WEBAPP\CFS_Stock_site\Webapp\Backend\stock.db" "D:\CFS_WEBAPP\CFS_Stock_site\backups\stock-$(Get-Date -Format yyyyMMdd-HHmmss).db"
```

Keep backups off the same drive if possible and prune old backups regularly.

---

## 8 — Troubleshooting (common issues)
- ModuleNotFoundError (e.g. openpyxl): ensure venv is activated and run:
  ```powershell
  .\venv\Scripts\Activate.ps1
  python -m pip install openpyxl
  ```
- CSS not updating: hard refresh the browser (Ctrl+F5) or clear cache.  
- Server error (500): check the terminal running `uvicorn` — copy the full traceback when asking for help.  
- Paths with spaces: wrap them in quotes when running scripts.

---

## 9 — Safety notes
- This app uses a local SQLite file. Back up frequently.  
- If accessible on LAN, ensure firewall settings are secure.  
- Do not expose the app to the public internet without adding proper authentication and HTTPS.

---

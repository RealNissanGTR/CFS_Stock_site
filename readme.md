# CFS Stock — Complete Documentation

A local web application for tracking inventory across Workshop and Paddock locations with automatic backups, admin panel, user management, and detailed activity logs.

---

## Table of Contents
1. [What this does](#what-this-does)
2. [Required software](#required-software)
3. [Download and prepare all project files](#download-and-prepare-all-project-files)
4. [Setup (one-time)](#setup-one-time)
5. [Starting the app](#starting-the-app)
6. [Features & how to use](#features--how-to-use)
7. [Backups & restoration](#backups--restoration)
8. [Troubleshooting](#troubleshooting)
9. [Tips & best practices](#tips--best-practices)

---

## What this does

This webapp is a simple, local-network inventory management system. It lets you:

- **View stock** across locations (Workshop, Paddock, or custom)
- **Add stock** with work order codes and comments
- **Remove stock** with sales/purchase order codes
- **Move stock** between locations
- **Search** by product name, category, or item code
- **Import** items from Excel (.xlsx) files
- **Export** current stock, logs, and users to timestamped XLSX
- **Manage users** and admin roles
- **Track activity** with detailed logs showing who, what, when, and where
- **Auto-backup** after every edit (quick backup) + monthly snapshots
- **Run indefinitely** on a local machine with PowerShell wrapper

---

## Required software

Install these before proceeding:

1. **Python 3.10 or higher**
   - Download from https://www.python.org/downloads/
   - During install: check "Add Python to PATH"
   - Verify: open PowerShell and run `python --version`

2. **Git** (optional but recommended)
   - Download from https://git-scm.com/downloads
   - Useful for version control and sharing project files

3. **Windows** (or Linux/Mac with appropriate path adjustments)

---

## Download and prepare all project files

Choose one of these methods.

### Option A: Download from Git (recommended)

1. Open PowerShell.
2. Move to the folder where you want to store the project:

```powershell
cd D:\
mkdir CFS_WEBAPP -ErrorAction SilentlyContinue
cd .\CFS_WEBAPP
```

3. Clone the repository:

```powershell
git clone <https://github.com/RealNissanGTR/CFS_Stock_site> CFS_Stock_site
cd .\CFS_Stock_site
```

Replace `<https://github.com/RealNissanGTR/CFS_Stock_site>` with your actual Git URL.

### Option B: Download ZIP (no Git required)

1. Download the project ZIP from your repository host (GitHub, OneDrive, SharePoint, etc.).
2. Extract it to:

```text
D:\CFS_WEBAPP\CFS_Stock_site
```

3. Make sure the extracted folder is named exactly `CFS_Stock_site`.

### Verify file structure before setup

From `D:\CFS_WEBAPP\CFS_Stock_site`, confirm you have:

- `requirements.txt`
- `readme.md`
- `Webapp\Backend\main.py`
- `Webapp\Backend\db\db_init.py`
- `Webapp\Backend\start_uvicorn.ps1`
- `Webapp\FrontEnd\login.html`
- `Webapp\FrontEnd\home.html`
- `Webapp\FrontEnd\overview.html`
- `Webapp\FrontEnd\admin.html`
- `Webapp\FrontEnd\styles.css`

If any are missing, re-download and extract again before continuing.

---

## Setup (one-time)

### Step 1: Prepare folders
Ensure this folder structure exists:
```
D:\CFS_WEBAPP\CFS_Stock_site\
├── Webapp\
│   ├── Backend\
│   │   ├── main.py
│   │   ├── db\
│   │   │   └── db_init.py
│   │   ├── backup\
│   │   │   ├── backup_db.py
│   │   │   ├── __init__.py
│   │   │   └── db_backups\
│   │   │       └── monthly\
│   │   ├── logs\
│   │   ├── stock_import\
│   │   │   └── import_stock_xlsx.py
│   │   └── venv\
│   └── FrontEnd\
│       ├── home.html
│       ├── admin.html
│       ├── overview.html
│       ├── login.html
│       ├── styles.css
│       └── static\
├── requirements.txt
└── readme.md
```

### Step 2: Create Python virtual environment
Open PowerShell and run (adjust path if needed):

```powershell
cd "D:\CFS_WEBAPP\CFS_Stock_site\Webapp\Backend"
python -m venv venv
```

This creates an isolated Python environment for the project.

### Step 3: Activate venv and install dependencies
```powershell
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r "..\..\requirements.txt"
```

If PowerShell blocks script execution, run once (as admin):
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

### Step 4: Initialize the database
The database is created automatically on first run. No manual steps needed.

---

## Starting the app

### Option A: Quick test (for development)
Use this if you're testing or making changes.

```powershell
cd "D:\CFS_WEBAPP\CFS_Stock_site\Webapp\Backend"
.\venv\Scripts\Activate.ps1
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

- Open on this PC: http://localhost:8000
- From another device on your Wi‑Fi: http://<YOUR_PC_IP>:8000
  - Find your IP by running `ipconfig` in PowerShell (look for "IPv4 Address")

Press `Ctrl+C` to stop.

### Option B: PowerShell wrapper (recommended for 24/7 use)
This runs the app in the background and logs output.

1. Ensure `start_uvicorn.ps1` is in `D:\CFS_WEBAPP\CFS_Stock_site\Webapp\Backend\`:

```powershell
param(
    [string]$BindHost = "0.0.0.0",
    [int]$Port = 8000
)

$backendDir = "D:\CFS_WEBAPP\CFS_Stock_site\Webapp\Backend"
$venvPython = Join-Path $backendDir "venv\Scripts\python.exe"
$logDir = Join-Path $backendDir "logs"

New-Item -ItemType Directory -Path $logDir -Force | Out-Null

$pythonCmd = $null
$pythonArgs = @()

if (Test-Path $venvPython) {
    $pythonCmd = $venvPython
    $pythonArgs = @("-m", "uvicorn", "main:app", "--host", $BindHost, "--port", $Port.ToString())
}
else {
    $pythonResult = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonResult) {
        throw "Python was not found. Install Python and try again."
    }
    $pythonCmd = $pythonResult.Source
    $pythonArgs = @("-m", "uvicorn", "main:app", "--host", $BindHost, "--port", $Port.ToString())
}

while ($true) {
    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $logFile = Join-Path $logDir "uvicorn-$timestamp.log"

    Write-Host ("Starting uvicorn on {0}:{1}" -f $BindHost, $Port)
    Write-Host ("Log file: {0}" -f $logFile)

    Push-Location $backendDir
    try {
        & $pythonCmd @pythonArgs 2>&1 | Tee-Object -FilePath $logFile
    }
    finally {
        Pop-Location
    }

    Write-Host "uvicorn stopped. Restarting in 3 seconds..."
    Start-Sleep -Seconds 3
}
```

2. Run it:

```powershell
powershell -ExecutionPolicy Bypass -File "D:\CFS_WEBAPP\CFS_Stock_site\Webapp\Backend\start_uvicorn.ps1"
```

3. Leave the PowerShell window open. Logs are saved in `Webapp/Backend/logs/`

### Option C: Windows Task Scheduler (runs at startup)
For true 24/7 operation:

1. Open Task Scheduler (search "Task Scheduler" in Windows)
2. Create Basic Task → Name it "CFS Stock"
3. Trigger: "At startup"
4. Action:
   - Program/script: `powershell.exe`
   - Arguments:
   ```powershell
   -NoProfile -ExecutionPolicy Bypass -File "D:\CFS_WEBAPP\CFS_Stock_site\Webapp\Backend\start_uvicorn.ps1"
   ```
   - Start in: `D:\CFS_WEBAPP\CFS_Stock_site\Webapp\Backend`
5. Settings: check "Run whether user is logged in or not"
6. Click OK and test by restarting your PC

---

## Features & how to use

### 1. Login
- Enter username and password
- Users can be created by admins only
- Passwords are hashed and never stored as plain text

### 2. Home (Quick Edit)
**For regular users and admins to quickly add/remove stock**

1. **Select category** from the dropdown
2. **Select product** (filtered by category)
3. **Select location** where the stock is (Workshop, Paddock, etc.)
4. **Choose Add or Remove** radio button
5. **Enter quantity** using the number input or +/− buttons
6. **Enter order code** (work order for adds, sales/purchase order for removes)
7. (Optional) Add comments
8. Click **Confirm add** or **Confirm remove**

The item counter shows how many are in stock per location in real time.

### 3. Overview
**Read-only view of all stock**

- Search by product name, category, or item code
- See per-location counts (Workshop, Paddock, Other)
- See totals
- Click product name or item code to go to Home with that item pre-selected

### 4. Admin Panel
**For administrators only**

#### Create Stock Item
- Item code, product name, category, quantity, location
- Creates a new item in the database

#### Delete Stock Item
- Select item code and location
- Removes the item entirely (logged as admin action)

#### Add/Remove User
- Username, password, admin checkbox
- Users default to non-admin (regular staff)
- Only one user is protected from deletion (the one logged in)

#### Toggle Admin
- Click button next to a username to make them admin or remove admin

#### Activity Logs
- Shows timestamp, action (Add/Remove/Move), who did it, order codes, comments
- Newest logs first
- Collapsible section (click Hide/Show logs)
- Max 200 logs shown in UI

#### Export Data
- Downloads a timestamped XLSX file with three sheets:
  - **Stock**: current database snapshot
  - **Logs**: activity log
  - **Users**: all users and their roles
- Filename: `data-export-YYYYMMDD-HHMMSS.xlsx`

#### Move Stock
- Select category → product
- Choose from-location and to-location
- Enter quantity
- Logged in activity

### 5. Import from Excel
**For bulk item creation**

Place your `.xlsx` file in `Webapp/Backend/stock_import/` with columns:
- Column A: Category
- Column B: Product code (item code)
- Column C: Product name

Run (from PowerShell in Backend folder):
```powershell
python .\stock_import\import_stock_xlsx.py
```

Items will be added at default location (Workshop) with zero stock count.

---

## Backups & restoration

### How backups work

Two types of backups are automatically managed:

1. **Quick backup** (`stock.quick.db`)
   - Created after every add/remove/move operation
   - Overwrites the previous quick backup
   - Use if something went wrong in the last edit

2. **Monthly backup** (`db_backups/monthly/stock-monthly-YYYYMMDD-HHMMSS.db`)
   - Created once every 30 days on a schedule
   - Timestamped so multiple copies are kept
   - Keeps only logs from the last 30 days in the backup copy
   - Use to restore from roughly a month ago if major data loss occurs

### Quick backup (automatic on every edit)

The code in `main.py` calls `quick_backup()` after every successful database commit:

```python
with SessionLocal() as db:
    db.commit()
    quick_backup()
```

This happens in these routes:
- `/inventory/change` (add or remove)
- (You can add more as needed)

### Monthly backup (manual or scheduled)

#### Manual monthly backup
```powershell
cd "D:\CFS_WEBAPP\CFS_Stock_site\Webapp\Backend"
.\venv\Scripts\Activate.ps1
python backup_db.py monthly
```

#### Scheduled monthly backup with Task Scheduler
1. Open Task Scheduler
2. Create Basic Task → Name: "CFS Monthly Backup"
3. Trigger: "Monthly" (choose a day/time that fits your backup cycle)
4. Action:
   - Program/script: `powershell.exe`
   - Arguments:
   ```powershell
   -NoProfile -ExecutionPolicy Bypass -Command "cd 'D:\CFS_WEBAPP\CFS_Stock_site\Webapp\Backend'; .\venv\Scripts\Activate.ps1; python backup_db.py monthly"
   ```
5. Click OK

### How to restore

**IMPORTANT**: Restoring replaces `stock.db` with the backup. Make a copy of the current database first if you want to keep it.

#### Restore the quick backup (last edit)
```powershell
cd "D:\CFS_WEBAPP\CFS_Stock_site\Webapp\Backend"
.\venv\Scripts\Activate.ps1
python backup_db.py restore-quick
```

#### Restore the latest monthly backup
```powershell
cd "D:\CFS_WEBAPP\CFS_Stock_site\Webapp\Backend"
.\venv\Scripts\Activate.ps1
python backup_db.py restore-latest-monthly
```

#### Restore a specific backup file
```powershell
cd "D:\CFS_WEBAPP\CFS_Stock_site\Webapp\Backend"
.\venv\Scripts\Activate.ps1
python backup_db.py restore-file "D:\CFS_WEBAPP\CFS_Stock_site\Webapp\Backend\backup\db_backups\monthly\stock-monthly-20260729-230000.db"
```

#### Manual restore (without Python)
1. Stop the app (close PowerShell window)
2. Navigate to `Webapp/Backend/backup/`
3. Right-click `stock.quick.db` → Copy
4. Go back to `Webapp/Backend/`
5. Right-click `stock.db` → Rename to `stock.db.old` (backup, just in case)
6. Paste the quick backup: Right-click in space → Paste
7. Rename the pasted file to `stock.db`
8. Start the app again

---

## Troubleshooting

### Python not found
**Error:** `python: command not found` or `Python was not found`

**Fix:**
1. Verify Python is installed: https://www.python.org/downloads/
2. During install, check "Add Python to PATH"
3. Restart PowerShell
4. Run `python --version` to confirm

### Virtual environment not activating
**Error:** `.\venv\Scripts\Activate.ps1` doesn't work

**Fix:**
1. Ensure you're in the correct folder: `D:\CFS_WEBAPP\CFS_Stock_site\Webapp\Backend`
2. If using Command Prompt instead of PowerShell, use: `.\venv\Scripts\activate.bat`
3. Verify venv exists: check if folder `Backend\venv` is present

### Port 8000 already in use
**Error:** `Address already in use`

**Fix:**
- Another app or instance is using port 8000
- Close other instances or use a different port:
  ```powershell
  uvicorn main:app --host 0.0.0.0 --port 8001
  ```

### ModuleNotFoundError (openpyxl, pandas, etc.)
**Error:** `ModuleNotFoundError: No module named 'openpyxl'`

**Fix:**
1. Activate venv: `.\venv\Scripts\Activate.ps1`
2. Reinstall requirements:
   ```powershell
   python -m pip install -r "..\..\requirements.txt"
   ```
3. Or install individual package:
   ```powershell
   python -m pip install openpyxl
   ```

### Can't access from another device
**Symptom:** Can open on this PC but not from another device

**Fix:**
1. Find your PC IP: run `ipconfig` and find "IPv4 Address" (e.g., 192.168.1.45)
2. Try: http://192.168.1.45:8000
3. Check Windows Firewall:
   - Go to Settings → Firewall & Network Protection
   - Click "Allow an app through firewall"
   - Find Python or uvicorn in the list
   - Check both Private and Public
4. If still blocked, add port 8000:
   ```powershell
   # run as admin
   New-NetFirewallRule -DisplayName "CFS Stock Uvicorn" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8000
   ```

### Database locked error
**Error:** `database is locked`

**Fix:**
- Another process is using the database
- Stop the app and any backup scripts
- Wait 30 seconds
- Restart the app

### Backup file too large
**Symptom:** Monthly backups are consuming lots of disk space

**Fix:**
- Delete old monthly backups manually:
   ```powershell
   cd "D:\CFS_WEBAPP\CFS_Stock_site\Webapp\Backend\backup\db_backups\monthly"
  # Delete files older than 30 days manually or use:
  Get-ChildItem | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } | Remove-Item
  ```

### Logs folder growing too large
**Error:** Disk space running low

**Fix:**
- Clear old log files:
  ```powershell
  cd "D:\CFS_WEBAPP\CFS_Stock_site\Webapp\Backend\logs"
  Get-ChildItem | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-7) } | Remove-Item
  ```

### CSS not updating in browser
**Symptom:** Style changes don't appear

**Fix:**
- Hard refresh: `Ctrl+F5` (or `Cmd+Shift+R` on Mac)
- Clear browser cache
- Close and reopen browser
- Try a different browser

### Login keeps failing
**Error:** "Invalid username or password"

**Fix:**
1. Verify username is correct (case-sensitive)
2. Verify password is correct
3. If you forgot the password, you need to:
   - Stop the app
   - Delete `stock.db` (or restore from backup)
   - Start the app (new empty database)
   - Create a new admin user

### Task Scheduler won't run the app
**Symptom:** Task says it ran but app isn't accessible

**Fix:**
1. Open Task Scheduler → find your task
2. Right-click → Properties → General tab
3. Check "Run whether user is logged in or not"
4. Check "Run with highest privileges"
5. Right-click task → Run (test it)
6. Check if it appears in `netstat -an | findstr 8000` output

---

## Tips & best practices

### User management
- Create a main admin account first
- Use strong passwords (8+ chars, mix of upper/lower/numbers)
- Only grant admin to trusted staff
- Delete unused accounts regularly

### Backup strategy
- Quick backups happen automatically; don't rely on them alone
- Set up monthly backups and verify they're being created
- Keep at least 4 monthly backups
- Copy backups to an external drive monthly

### Performance
- If the app gets slow, check if `stock.db` is very large
- Archive old logs (export to XLSX and delete rows in database)
- Clear old backups monthly

### Security (for local network)
- Change the `SECRET_KEY` in `main.py` to a random string:
  ```python
  SECRET_KEY = os.getenv("SECRET_KEY", "your-random-secret-here")
  ```
- Do NOT expose this app to the public internet
- Use a firewall to restrict access to your local network

### Data entry
- Use consistent product codes (e.g., all uppercase)
- Use consistent location names (exact spelling matters)
- Add comments for unusual stock changes
- Check the Activity Logs regularly to catch errors

### Maintenance schedule
- **Daily**: check the app is running (visit the URL)
- **Monthly**: verify monthly backups are being created
- **Monthly**: delete old log files and backups
- **Quarterly**: test a restore from a monthly backup

---

## Uninstalling / moving the project

To move the project to a different folder:
1. Copy the entire `CFS_Stock_site` folder
2. Update paths in:
   - `start_uvicorn.ps1`
   - Task Scheduler tasks (if any)
   - This readme
3. Run setup steps again to create a new venv

To uninstall:
1. Stop the app and any Task Scheduler tasks
2. Delete the entire `CFS_Stock_site` folder
3. Delete any Task Scheduler tasks you created
4. (optional) Remove Python if you don't need it for other projects

---

## Support & questions

If something isn't working:
1. Check the Troubleshooting section above
2. Look at log files in `Webapp/Backend/logs/`
3. Check the terminal output when running the app
4. Verify all required software is installed
5. Contact your system admin or the developer

---

**Version:** 1.0  
**Last updated:** July 2026

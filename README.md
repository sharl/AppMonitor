# AppMonitor

Application Memory Monitor

## Run

```powershell
git clone https://github.com/sharl/AppMonitor.git
cd AppMonitor
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
pythonw AppMonitor.py -n chrome.exe
```

### Re-run

```powershell
cd AppMonitor
.\.venv\Scripts\activate
pythonw AppMonitor.py -n chrome.exe
```

## Build

```powershell
pip install pyinstaller
pyinstaller "AppMonitor.py" "--onefile" "--noconsole" "--icon=Assets/sample.ico" "--exclude-module=PIL._avif" "--exclude-module=PIL._webp" "--exclude-module=PIL._imagingcms"
```

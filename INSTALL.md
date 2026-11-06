# Installation (Windows, step by step)

## 1. Requirements
* Python 3.10 or newer (https://www.python.org/downloads/ – tick **Add python.exe to PATH**).
* Internet access (public websites only). No accounts, no API keys.

## 2. Unzip
Unzip `ubuy-opportunity-engine.zip` anywhere, e.g. `C:\Users\U138\Desktop\ubuy-opportunity-engine`.
(Use a *new* folder – it does not overwrite your existing `ubuy-engine`.)

## 3. Install
Double-click **install.bat** (or run in a terminal inside the folder):
```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 4. Check it works (optional, offline)
```
.venv\Scripts\activate
python -m unittest discover -s tests -v
```
Expected: `Ran 17 tests ... OK`.

**Updating from an earlier version:** double-click **update.bat** once (installs the headless browser used for the exact Ubuy product-card check).

## 5. Launch
Double-click **run.bat**, or:
```
.venv\Scripts\activate

python app.py
```
Open **http://127.0.0.1:5000/opportunity/**

## 6. First India run
1. Country: **India** · Period: **30 days** (start small) · Category: **ALL** (or one category for a faster first test) · Max: 100.
2. Click **Start research**. Watch progress and the agent log. First run can take tens of minutes.
3. When completed: open **Qualified / Watchlist / Rejected** tabs, expand a product to see evidence URLs, download **Excel** or **CSV**.
4. If marketplaces show UNVERIFIED, check *Source health* – blocked or JavaScript sites are expected. See README for Playwright.
5. To enable profit maths, edit `country_configs/india.json → economics` (FX rate, shipping, duty %, tax %, expenses). Restart the app.

## 7. Configuration (all optional)
Create `opportunity_settings.json` next to `app.py`, e.g.:
```json
{"max_requests_per_run": 800, "min_delay_per_domain": 2.5, "workers": 3, "use_playwright": false, "strict_qualification": true}
```
Keys and defaults: `opportunity_research/settings.py`.

## 8. Add it to your existing Flask app instead
Copy folders `opportunity_research`, `country_configs`, `templates/opportunity` into the project, then:
```python
from opportunity_research.blueprint import opportunity_bp
app.register_blueprint(opportunity_bp)
```
`pip install -r requirements.txt`, restart, open `/opportunity/`.

## Linux / macOS
`bash install.sh` then `bash run.sh`.

## Troubleshooting
* *Everything UNVERIFIED / 0 candidates* – network blocks search engines; check *Source health* in the run page.
* *Run stopped after restart* – open the run and press **Resume** (checkpoints are kept).
* *Port in use* – change the port at the bottom of `app.py`.

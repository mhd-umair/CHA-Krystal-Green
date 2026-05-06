# Running the Customer Analytics Dashboard

Python + Streamlit. No build step, no compile step, no deploy step.

## Prerequisites

- Python 3.10+ (you have 3.14 installed)
- The SQLite database `perseus_equipment_database.db` in the repo root

## First-time setup

```powershell
# from the repo root
python -m pip install -r requirements.txt
```

That installs:
- `streamlit` - the dashboard framework
- `plotly` - charts
- `pandas` - data wrangling

## Run the app

```powershell
python -m streamlit run streamlit_app/Home.py
```

Streamlit prints something like:

```
  Local URL: http://localhost:8501
  Network URL: http://192.168.x.x:8501
```

Open the Local URL in your browser.

The Network URL works for any device on your LAN (other laptops, your phone, etc.) without any extra setup.

## Pages

| Page | Path in nav | What it shows |
|---|---|---|
| Overview | (default) | KPI tiles, monthly revenue chart, top-10 leaderboard, customer health segment chips |
| Leaderboard | sidebar | Sortable table with TTM/Lifetime toggle, search, click-through to profile |
| At Risk | sidebar | RFM segment chips + filterable customer table |
| Open A/R | sidebar | Aging buckets and per-customer outstanding |
| Customer Profile | follows from a row click | Lifetime/TTM KPIs, monthly revenue, type mix, invoices, contacts, open A/R |

You can also navigate directly to a customer profile via URL: `http://localhost:8501/Customer_Profile?customer=1761`.

## Tips

- Streamlit hot-reloads on file save. Edit any `.py` and the page refreshes automatically.
- Caching: queries are wrapped in `@st.cache_data(ttl=600)` so repeat page visits are instant. Restart the app or change the cache key to invalidate.
- The DB is opened **read-only** (`mode=ro`); the app physically cannot modify the database.
- Override the DB path with `PERSEUS_DB_PATH`:
  ```powershell
  $env:PERSEUS_DB_PATH = "C:\path\to\perseus_equipment_database.db"
  python -m streamlit run streamlit_app/Home.py
  ```

## Folder layout

```
.streamlit/
  config.toml                # theme + server settings (read from CWD on startup)
streamlit_app/
  Home.py                    # landing dashboard
  data.py                    # SQLite repo + cached queries
  pages/
    1_Leaderboard.py
    2_At_Risk.py
    3_Open_AR.py
    4_Customer_Profile.py    # /Customer_Profile?customer=<id>
requirements.txt
```

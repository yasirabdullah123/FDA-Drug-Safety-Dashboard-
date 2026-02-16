# 💊 FDA Drug Safety Dashboard

A real-time pharmacovigilance dashboard that queries the FDA's public adverse event database (FAERS) and visualises drug safety data through interactive charts.

**[Live Demo →](https://yourusername.streamlit.app)** &nbsp;|&nbsp; Built with Python, Streamlit, and Plotly

---

![Dashboard Preview](screenshot.png)

---

## What It Does

Select a drug from the sidebar and the app instantly pulls live adverse event reports from the FDA's FAERS database, surfacing three key views:

- **Trend line** — how report volume has changed year over year
- **Clinical side effect profile** — top reported adverse reactions (administrative filing codes filtered out so only real symptoms appear)
- **Global heatmap** — which countries are generating the most reports, scaled by volume

## Why It's Interesting

The FDA FAERS API is messy. Building this required solving several real data engineering problems:

- **Wrong query field** — `openfda.brand_name` misses thousands of reports because it only matches harmonised entries. Switched to `medicinalproduct` (the raw field) for maximum recall.
- **Broken server-side aggregation** — counting by `receivedate` while also filtering by `receivedate` returns nothing. The fix is to fetch 1,000 full records and aggregate the years client-side in Python.
- **Polluted side effect data** — the API returns "Drug Ineffective" and "Off Label Use" as top reactions because they are FAERS filing categories, not clinical symptoms. A blocklist of ~20 administrative terms filters these out before display.
- **API instability** — the FDA server returns 500 errors under load. Implemented exponential backoff retry (1s → 2s → 4s → 8s) via `urllib3.Retry` baked into the session adapter.

## Tech Stack

| Tool | Purpose |
|------|---------|
| Python 3.10+ | Core language |
| Streamlit | Web app framework |
| Plotly / Graph Objects | Interactive charts |
| PyDeck | Global scatter map |
| Requests + urllib3 | HTTP client with retry logic |
| Pandas | Data processing |

## Data Source

All data comes from **[OpenFDA FAERS](https://open.fda.gov/apis/drug/event/)** — the FDA's public Adverse Event Reporting System. Reports are submitted voluntarily by patients, healthcare providers, and manufacturers. No API key required.

## Running Locally

```bash
# 1. Clone the repo
git clone https://github.com/yourusername/fda-safety-dashboard
cd fda-safety-dashboard

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run
streamlit run fda_dashboard.py
```

App opens at `http://localhost:8501`

## Requirements

```
streamlit
pandas
requests
plotly
pydeck
```

## Drugs Included

| Display Name | Active Ingredient | Therapeutic Area |
|---|---|---|
| Ozempic | Semaglutide | Type 2 Diabetes / Weight Loss |
| Humira | Adalimumab | Autoimmune |
| Keytruda | Pembrolizumab | Oncology |
| Eliquis | Apixaban | Anticoagulation |
| Jardiance | Empagliflozin | Type 2 Diabetes |

Selected because they all have a substantial number of FAERS reports — enough to generate meaningful charts without overwhelming the API.

## Project Structure

```
fda-safety-dashboard/
├── fda_dashboard.py   # Main app — all logic and UI
├── requirements.txt   # Dependencies
└── README.md
```

## Disclaimer

This dashboard is for informational and educational purposes only. It is not a substitute for clinical judgement or professional medical advice. Report counts reflect submissions to FAERS and do not imply causation.

---

*Data refreshes every 10 minutes via Streamlit's cache. Built as a personal project to explore public health data engineering.*

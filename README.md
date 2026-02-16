# 💊 FDA Drug Safety Dashboard

A real-time pharmacovigilance dashboard that queries the FDA's public adverse event database (FAERS) and visualises drug safety data through interactive charts.

---

## What It Does

Every time a patient, doctor, or drug manufacturer reports a side effect to the FDA, that report enters a public database called FAERS — the FDA Adverse Event Reporting System. By 2024 it contains over 20 million reports spanning decades of drug use worldwide.

This dashboard makes that data accessible. Select a drug and within seconds you see:

- **How reporting has trended year over year** — is concern about this drug rising or falling? A spike in 2023 might mean a new market launch, a safety label update, or a high-profile news story.
- **What the actual clinical side effects are** — the top reported adverse reactions, filtered to show only real symptoms. Nausea, vomiting, fatigue — not the administrative filing codes the raw API buries them under.
- **Which countries are reporting the most** — a global map scaled by volume, showing where in the world this drug's safety profile is being tracked most closely.

The result is a live, interactive safety snapshot of any drug — the kind of view that would otherwise require a data team, an FDA data subscription, and hours of processing.

## Why It's Useful

Drug safety data is public but it's not accessible. The raw FAERS database is a 20+ million row JSON nightmare that requires significant technical knowledge to query, clean, and interpret. Pharmaceutical companies pay for proprietary tools to do exactly this. This dashboard replicates the core of that workflow for free, in real time, in a browser.

**Practical use cases:**
- A patient researching a new prescription wanting to understand reported side effects beyond the package insert
- A healthcare student learning what post-market drug surveillance actually looks like in practice
- A journalist or researcher tracking whether adverse event reports for a drug are rising after a news event
- Anyone curious about why the FDA continues monitoring drugs long after they're approved

**The data engineering problems it solves:**

The FDA FAERS API looks simple but has several non-obvious failure modes that make the data misleading if you don't know about them:

- **Wrong query field** — `openfda.brand_name` silently misses thousands of reports because it only matches entries that were successfully harmonised during indexing. Switched to `medicinalproduct` (the raw field) to capture everything.
- **Broken server-side aggregation** — asking the API to count records by date while also filtering by date returns nothing. The fix is fetching 1,000 full records and aggregating years client-side in Python.
- **Polluted side effect data** — without filtering, "Drug Ineffective" and "Off Label Use" appear as the top reactions because they are FAERS administrative categories, not clinical symptoms. A blocklist strips these so only real adverse events surface.
- **API instability** — the FDA server returns 500 errors under load. Implemented exponential backoff retry (1s → 2s → 4s → 8s) via `urllib3.Retry` so transient failures are invisible to the user.

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

This dashboard is for informational purposes only. It is not a substitute for clinical judgement or professional medical advice. Report counts reflect submissions to FAERS and do not imply causation.

---

*Data refreshes every 10 minutes via Streamlit's cache. Built as a personal project to explore public health data engineering.*

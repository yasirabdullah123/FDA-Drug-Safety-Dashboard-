import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import plotly.graph_objects as go
import pydeck as pdk
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from datetime import datetime

# ── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="FDA Drug Safety Dashboard", layout="wide")

st.markdown("""
<style>
    /* Global */
    .main { background-color: #f5f7fa; }
    .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }

    /* KPI Cards */
    .kpi-card {
        background: #ffffff;
        border-radius: 16px;
        padding: 1.4rem 1.6rem;
        box-shadow: 0 2px 12px rgba(0,0,0,0.07);
        border-top: 4px solid #2563eb;
        height: 100%;
    }
    .kpi-label {
        font-size: 0.72rem; color: #6b7280;
        text-transform: uppercase; letter-spacing: 0.08em;
        font-weight: 600; margin-bottom: 0.4rem;
    }
    .kpi-value {
        font-size: 2.2rem; font-weight: 800;
        color: #1e293b; line-height: 1.1;
    }
    .kpi-sub { font-size: 0.75rem; color: #9ca3af; margin-top: 0.3rem; }

    /* Insight boxes */
    .insight {
        background: #eff6ff;
        border-left: 4px solid #3b82f6;
        border-radius: 0 8px 8px 0;
        padding: 0.65rem 1rem;
        font-size: 0.83rem;
        color: #374151;
        margin-top: 0.6rem;
        line-height: 1.5;
    }

    /* Section headers */
    .section-title {
        font-size: 1.05rem; font-weight: 700;
        color: #1e293b; margin-bottom: 0.1rem;
    }
    .section-sub {
        font-size: 0.78rem; color: #6b7280; margin-bottom: 0.8rem;
    }

    /* Chart containers */
    .chart-card {
        background: #ffffff;
        border-radius: 16px;
        padding: 1.2rem 1.2rem 0.5rem;
        box-shadow: 0 2px 12px rgba(0,0,0,0.06);
        margin-bottom: 1rem;
    }

    /* Divider */
    hr { border: none; border-top: 1px solid #e5e7eb; margin: 1.5rem 0; }
</style>
""", unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────────────────────
DRUGS = {
    "Ozempic (semaglutide)":     "semaglutide",
    "Humira (adalimumab)":       "adalimumab",
    "Keytruda (pembrolizumab)":  "pembrolizumab",
    "Eliquis (apixaban)":        "apixaban",
    "Jardiance (empagliflozin)": "empagliflozin",
}

# These are administrative/process terms in FAERS — NOT clinical side effects.
# We fetch 30 reactions and strip these so the chart only shows real symptoms.
NON_SIDE_EFFECTS = {
    "drug ineffective", "off label use", "product use in unapproved indication",
    "inappropriate schedule of product administration",
    "wrong technique in product usage process",
    "drug administered to patient of inappropriate age",
    "drug dose omission", "expired product administered",
    "product quality issue", "intentional product misuse",
    "drug dispensing error", "drug interaction", "no adverse event",
    "product substitution issue", "drug administration error",
    "incorrect dose administered", "patient did not respond to treatment",
    "condition aggravated", "therapeutic response unexpected",
    "drug use for unknown indication",
}

ISO2_COORDS = {
    "US":(37.09,-95.71),"GB":(55.37,-3.43),"CA":(56.13,-106.34),"FR":(46.22,2.21),
    "DE":(51.16,10.45),"IT":(41.87,12.56),"ES":(40.46,-3.74),"JP":(36.20,138.25),
    "CN":(35.86,104.19),"IN":(20.59,78.96),"BR":(-14.23,-51.92),"AU":(-25.27,133.77),
    "RU":(61.52,105.31),"ZA":(-30.55,22.93),"MX":(23.63,-102.55),"KR":(35.90,127.76),
    "NL":(52.13,5.29),"SE":(60.12,18.64),"CH":(46.81,8.22),"TR":(38.96,35.24),
    "BE":(50.50,4.46),"AR":(-38.41,-63.61),"PL":(51.91,19.14),"TH":(15.87,100.99),
    "PT":(39.39,-8.22),"AT":(47.51,14.55),"DK":(56.26,9.50),"NO":(60.47,8.46),
    "FI":(61.92,25.74),"NZ":(-40.90,174.88),"IL":(31.04,34.85),"SG":(1.35,103.81),
    "IE":(53.41,-8.24),"GR":(39.07,21.82),"HU":(47.16,19.50),"CZ":(49.81,15.47),
    "RO":(45.94,24.96),"SA":(23.88,45.07),"MY":(4.21,101.97),
    "PH":(12.87,121.77),"NG":(9.08,8.67),"EG":(26.82,30.80),"UA":(48.37,31.16),
}

ISO2_TO_NAME = {
    'US':'United States','GB':'United Kingdom','CA':'Canada','FR':'France',
    'DE':'Germany','JP':'Japan','AU':'Australia','IT':'Italy','ES':'Spain',
    'NL':'Netherlands','SE':'Sweden','CH':'Switzerland','BE':'Belgium',
    'CN':'China','IN':'India','BR':'Brazil','RU':'Russia','MX':'Mexico',
    'KR':'South Korea','TR':'Turkey','AR':'Argentina','PL':'Poland',
    'SG':'Singapore','IE':'Ireland','GR':'Greece','HU':'Hungary',
}

BASE = "https://api.fda.gov/drug/event.json"

# Consistent, professional colour palette
BLUE       = "#2563eb"
BLUE_LIGHT = "#dbeafe"
RED        = "#dc2626"
GREY_GRID  = "#f1f5f9"
FONT_DARK  = "#1e293b"

# ── Resilient Session ─────────────────────────────────────────────────────────
def _session() -> requests.Session:
    s = requests.Session()
    retry = Retry(total=4, backoff_factor=1,
                  status_forcelist=[500,502,503,504],
                  allowed_methods=["GET"], raise_on_status=False)
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("https://", adapter)
    return s

SESSION = _session()

def _call(params: dict) -> tuple[list, str | None]:
    try:
        r = SESSION.get(BASE, params=params, timeout=20)
        if r.status_code == 200:
            return r.json().get("results", []), None
        elif r.status_code == 404:
            return [], "no_data"
        else:
            return [], f"server_error_{r.status_code}"
    except requests.RequestException as e:
        return [], f"network_error: {e}"

def _q(term: str) -> str:
    return f'patient.drug.medicinalproduct:"{term.upper()}"'

# ── Data Fetchers ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=600, show_spinner=False)
def get_reactions(term: str) -> tuple[pd.DataFrame, str | None]:
    # Fetch 30 so we still have 5 real ones after stripping admin/process terms
    data, err = _call({
        "search": _q(term),
        "count": "patient.reaction.reactionmeddrapt.exact",
        "limit": 30
    })
    if err or not data:
        return pd.DataFrame(columns=["Reaction", "Reports"]), err
    df = pd.DataFrame(data).rename(columns={"term": "Reaction", "count": "Reports"})
    df["Reaction"] = df["Reaction"].str.title()
    # Filter out non-clinical terms
    mask = ~df["Reaction"].str.lower().isin(NON_SIDE_EFFECTS)
    df = df[mask].head(8).reset_index(drop=True)
    return df, None

@st.cache_data(ttl=600, show_spinner=False)
def get_timeline(term: str) -> tuple[pd.DataFrame, str | None]:
    data, err = _call({"search": _q(term), "limit": 1000})
    if err or not data:
        return pd.DataFrame(columns=["Year", "Reports"]), err
    rows = []
    for record in data:
        try:
            raw_date = record.get("receivedate", "")
            if len(raw_date) == 8:
                year = int(raw_date[:4])
                if 2000 <= year <= datetime.now().year:
                    rows.append(year)
        except (ValueError, TypeError):
            continue
    if not rows:
        return pd.DataFrame(columns=["Year", "Reports"]), "no_data"
    df = pd.Series(rows).value_counts().sort_index().reset_index()
    df.columns = ["Year", "Reports"]
    return df, None

@st.cache_data(ttl=600, show_spinner=False)
def get_geo(term: str) -> tuple[pd.DataFrame, str | None]:
    data, err = _call({"search": _q(term), "count": "occurcountry.exact", "limit": 50})
    if err or not data:
        return pd.DataFrame(columns=["country","name","Reports","lat","lon"]), err
    rows = []
    for item in data:
        iso2   = item.get("term", "").upper()
        count  = item.get("count", 0)
        coords = ISO2_COORDS.get(iso2)
        if coords:
            rows.append({
                "country": iso2,
                "name": ISO2_TO_NAME.get(iso2, iso2),
                "Reports": count,
                "lat": coords[0],
                "lon": coords[1],
            })
    if not rows:
        return pd.DataFrame(columns=["country","name","Reports","lat","lon"]), "no_data"
    return pd.DataFrame(rows), None

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 💊 Drug Safety")
    drug_label = st.selectbox("Select Drug", list(DRUGS.keys()))
    st.markdown("---")
    st.markdown("**About this dashboard**")
    st.caption(
        "Real-time data from **OpenFDA FAERS** — the FDA's Adverse Event "
        "Reporting System. Includes voluntary reports from patients, "
        "healthcare providers, and manufacturers."
    )
    st.markdown("---")
    st.caption("🔄 Cached 10 min · Auto-retry on server errors")

drug_term = DRUGS[drug_label]

# ── Fetch ─────────────────────────────────────────────────────────────────────
with st.spinner(f"Loading FDA data for {drug_label}..."):
    df_react, err_react = get_reactions(drug_term)
    df_time,  err_time  = get_timeline(drug_term)
    df_geo,   err_geo   = get_geo(drug_term)

def _show_err(err, label):
    if err == "no_data":
        st.info(f"No {label} data found.")
    elif err:
        st.warning(f"{label} error: {err}")

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(f"# 💊 FDA Drug Safety Dashboard")
st.markdown(
    f"<span style='color:#6b7280;font-size:0.9rem'>Adverse event surveillance for "
    f"<b style='color:{BLUE}'>{drug_label}</b> · OpenFDA FAERS database</span>",
    unsafe_allow_html=True
)
st.markdown("<hr>", unsafe_allow_html=True)

# ── KPI Cards ─────────────────────────────────────────────────────────────────
total_reports = f"{int(df_time['Reports'].sum()):,}" if not df_time.empty else "—"
top_reaction  = str(df_react.iloc[0]["Reaction"]) if not df_react.empty else "—"
top_country   = df_geo.sort_values("Reports", ascending=False).iloc[0]["name"] if not df_geo.empty else "—"

# Peak year for trend arrow
if not df_time.empty and len(df_time) >= 2:
    last_two = df_time.sort_values("Year").tail(2)["Reports"].values
    trend_arrow = "↑" if last_two[-1] > last_two[-2] else "↓"
    trend_color = "#16a34a" if last_two[-1] > last_two[-2] else "#dc2626"
    trend_html  = f'<span style="color:{trend_color};font-size:0.8rem">{trend_arrow} vs prior year</span>'
else:
    trend_html = ""

k1, k2, k3 = st.columns(3)
with k1:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">Total Reports (sample)</div>
        <div class="kpi-value">{total_reports}</div>
        <div class="kpi-sub">Most recent 1,000 records · {trend_html}</div>
    </div>""", unsafe_allow_html=True)
with k2:
    st.markdown(f"""
    <div class="kpi-card" style="border-top-color:#dc2626">
        <div class="kpi-label">Most Common Side Effect</div>
        <div class="kpi-value" style="font-size:1.4rem;color:#dc2626">{top_reaction}</div>
        <div class="kpi-sub">Clinical adverse reactions only</div>
    </div>""", unsafe_allow_html=True)
with k3:
    st.markdown(f"""
    <div class="kpi-card" style="border-top-color:#0891b2">
        <div class="kpi-label">Primary Reporting Country</div>
        <div class="kpi-value" style="font-size:1.4rem;color:#0891b2">{top_country}</div>
        <div class="kpi-sub">Highest submission volume</div>
    </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Chart 1: Timeline ─────────────────────────────────────────────────────────
st.markdown('<div class="section-title">📅 Adverse Event Reports Over Time</div>', unsafe_allow_html=True)
st.markdown('<div class="section-sub">Yearly count from the most recent 1,000 FAERS submissions</div>', unsafe_allow_html=True)
_show_err(err_time, "Timeline")

if not df_time.empty:
    # Add a trend line via scatter on top of bars
    fig_time = go.Figure()

    # Bars
    fig_time.add_trace(go.Bar(
        x=df_time["Year"].astype(str),
        y=df_time["Reports"],
        marker_color=BLUE,
        marker_opacity=0.85,
        name="Reports",
        text=df_time["Reports"].apply(lambda x: f"{x:,}"),
        textposition="outside",
        textfont=dict(size=11, color=FONT_DARK),
        hovertemplate="<b>%{x}</b><br>Reports: %{y:,}<extra></extra>",
    ))

    # Trend line
    fig_time.add_trace(go.Scatter(
        x=df_time["Year"].astype(str),
        y=df_time["Reports"],
        mode="lines+markers",
        line=dict(color="#f59e0b", width=2.5, dash="dot"),
        marker=dict(size=7, color="#f59e0b"),
        name="Trend",
        hoverinfo="skip",
    ))

    fig_time.update_layout(
        paper_bgcolor="white", plot_bgcolor="white",
        height=340,
        margin=dict(l=20, r=20, t=30, b=20),
        xaxis=dict(
            showgrid=False, zeroline=False,
            tickfont=dict(size=12, color="#374151"),
            title=None,
        ),
        yaxis=dict(
            showgrid=True, gridcolor=GREY_GRID, zeroline=False,
            tickfont=dict(size=11, color="#6b7280"),
            title=dict(text="Reports", font=dict(size=12, color="#6b7280")),
        ),
        legend=dict(
            orientation="h", y=1.05, x=1, xanchor="right",
            font=dict(size=11),
        ),
        bargap=0.35,
        hovermode="x unified",
    )
    st.plotly_chart(fig_time, use_container_width=True)

    if len(df_time) >= 2:
        peak_yr  = int(df_time.loc[df_time["Reports"].idxmax(), "Year"])
        peak_val = int(df_time["Reports"].max())
        direction = "rising 📈" if last_two[-1] > last_two[-2] else "declining 📉"
        st.markdown(
            f'<div class="insight">💡 <b>Insight:</b> Reports peaked in <b>{peak_yr}</b> '
            f'({peak_val:,} submissions). Volume is currently <b>{direction}</b>. '
            f'Spikes often correspond to new market launches, media coverage, or safety label updates.</div>',
            unsafe_allow_html=True
        )

st.markdown("<hr>", unsafe_allow_html=True)

# ── Charts 2 & 3 ─────────────────────────────────────────────────────────────
col1, col2 = st.columns([1, 1], gap="large")

with col1:
    st.markdown('<div class="section-title">⚠️ Clinical Side Effect Profile</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Top reported adverse reactions (admin/process terms excluded)</div>', unsafe_allow_html=True)
    _show_err(err_react, "Reactions")

    if not df_react.empty:
        df_sorted = df_react.sort_values("Reports", ascending=True)
        # Colour gradient: darkest = most reports
        max_r = df_sorted["Reports"].max()
        colours = [
            f"rgba(220,38,38,{0.4 + 0.6*(v/max_r):.2f})"
            for v in df_sorted["Reports"]
        ]

        fig_bar = go.Figure(go.Bar(
            x=df_sorted["Reports"],
            y=df_sorted["Reaction"],
            orientation="h",
            marker_color=colours,
            text=df_sorted["Reports"].apply(lambda x: f"{x:,}"),
            textposition="outside",
            textfont=dict(size=11, color=FONT_DARK),
            hovertemplate="<b>%{y}</b><br>Reports: %{x:,}<extra></extra>",
        ))
        fig_bar.update_layout(
            paper_bgcolor="white", plot_bgcolor="white",
            height=360,
            margin=dict(l=10, r=70, t=10, b=10),
            xaxis=dict(
                showgrid=True, gridcolor=GREY_GRID, zeroline=False,
                tickfont=dict(size=11, color="#6b7280"), title="Reports",
            ),
            yaxis=dict(
                showgrid=False, zeroline=False,
                tickfont=dict(size=12, color=FONT_DARK), title=None,
            ),
            hovermode="y unified",
        )
        st.plotly_chart(fig_bar, use_container_width=True)
        top5 = df_react.iloc[0]["Reaction"]
        st.markdown(
            f'<div class="insight">💡 <b>Insight:</b> <b>{top5}</b> is the most reported '
            f'clinical reaction. Look for cardiac, hepatic, or haematological entries — '
            f'these carry the highest regulatory risk.</div>',
            unsafe_allow_html=True
        )

with col2:
    st.markdown('<div class="section-title">🌍 Global Report Distribution</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Report volume by country · hover for details</div>', unsafe_allow_html=True)
    _show_err(err_geo, "Geography")

    if not df_geo.empty:
        max_r = df_geo["Reports"].max()
        df_geo["radius"] = (df_geo["Reports"] / max_r * 700_000).clip(lower=60_000)
        df_geo["alpha"]  = ((df_geo["Reports"] / max_r) * 200 + 55).astype(int)

        layer = pdk.Layer(
            "ScatterplotLayer",
            data=df_geo,
            get_position=["lon", "lat"],
            get_radius="radius",
            get_fill_color=["alpha", 80, 200, "alpha"],
            pickable=True,
            stroked=True,
            get_line_color=[37, 99, 235],
            line_width_min_pixels=1,
        )
        view = pdk.ViewState(latitude=25, longitude=10, zoom=1.2, pitch=0)
        tooltip = {
            "html": "<b style='color:#fff'>{name}</b><br/>"
                    "<span style='color:#93c5fd'>Reports: {Reports}</span>",
            "style": {"background":"#1e293b","padding":"8px","border-radius":"6px"}
        }
        st.pydeck_chart(pdk.Deck(
            layers=[layer],
            initial_view_state=view,
            tooltip=tooltip,
            map_style="light",
        ), height=340)

        top_row = df_geo.sort_values("Reports", ascending=False).iloc[0]
        pct = top_row["Reports"] / df_geo["Reports"].sum() * 100
        st.markdown(
            f'<div class="insight">💡 <b>Insight:</b> <b>{top_row["name"]}</b> accounts for '
            f'~<b>{pct:.0f}%</b> of all mapped reports. US dominance is expected — '
            f'FAERS imposes mandatory reporting on manufacturers; most countries do not.</div>',
            unsafe_allow_html=True
        )

# ── Raw Data ──────────────────────────────────────────────────────────────────
st.markdown("<hr>", unsafe_allow_html=True)
with st.expander("🔍 View Raw Data Tables"):
    t1, t2, t3 = st.tabs(["Timeline", "Geography", "Reactions"])
    with t1:
        st.dataframe(df_time, use_container_width=True)
    with t2:
        st.dataframe(
            df_geo[["name","country","Reports"]].rename(columns={"name":"Country","country":"ISO2"}),
            use_container_width=True
        )
    with t3:
        st.dataframe(df_react, use_container_width=True)

st.markdown(
    "<div style='text-align:center;color:#9ca3af;font-size:0.75rem;padding:1rem 0'>"
    "Data: OpenFDA FAERS · fda.gov · For informational purposes only. "
    "Not a substitute for clinical judgement.</div>",
    unsafe_allow_html=True
)

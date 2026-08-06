import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date

st.set_page_config(page_title="LOYAGO · Sales Cockpit", page_icon="📊", layout="wide", initial_sidebar_state="expanded")

LOST_KEYWORDS = ["kein interesse", "verloren", "abgeschlossen", "closed lost", "closed won", "gewonnen", "won", "lost", "provisionskontrolle"]
PHASE_ORDER_SALES = [
    "Termin vereinbart", "Beratung läuft", "Angebot raus",
    "Antrag raus", "Nachbearbeitung",
]
PHASE_ORDER_AFTER = [
    "Policiert", "After Sales",
]
PHASE_ORDER = PHASE_ORDER_SALES + PHASE_ORDER_AFTER

# ── Farben (helles LOYAGO-Theme) ─────────────────────────────────────────────
BG      = "#cbdafb"
CARD    = "#ffffff"
CARD2   = "#eef3fd"
BDR     = "rgba(37,99,235,0.18)"
BLUE    = "#2563eb"
LBLUE   = "#c8d8f8"
TEXT    = "#1e293b"
MUTED   = "#64748b"
GREEN   = "#16a34a"
YEL     = "#d97706"
RED     = "#dc2626"
ORA     = "#ea580c"

st.markdown(f"""<style>
[data-testid="stAppViewContainer"]{{background:{BG};}}
[data-testid="stHeader"]{{background:transparent;}}
[data-testid="block-container"]{{padding-top:1.2rem!important;padding-bottom:1rem!important;}}
section[data-testid="stSidebar"]{{background:{CARD};border-right:1px solid {BDR};box-shadow:2px 0 12px rgba(37,99,235,.08);}}
[data-testid="metric-container"]{{background:{CARD};border:1px solid {BDR};border-radius:12px;padding:.75rem 1rem;box-shadow:0 2px 8px rgba(37,99,235,.07);}}
[data-testid="metric-container"] label{{color:{MUTED}!important;font-size:.68rem!important;text-transform:uppercase;letter-spacing:.08em;}}
[data-testid="metric-container"] [data-testid="stMetricValue"]{{color:{TEXT}!important;font-size:1.7rem!important;font-weight:800;}}
[data-testid="metric-container"] [data-testid="stMetricDelta"]{{display:none;}}
div[data-testid="stVerticalBlock"]>div{{gap:.5rem!important;}}
.stExpander{{background:{CARD}!important;border:1px solid {BDR}!important;border-radius:12px!important;box-shadow:0 2px 6px rgba(37,99,235,.06)!important;}}
.stExpander summary{{color:{TEXT}!important;font-weight:600;}}
hr{{border-color:{BDR}!important;}}
p,span,div,label{{color:{TEXT};}}
[data-testid="stDataFrame"]{{border-radius:10px;}}
@page{{margin:3mm 4mm;}}
@media print{{
  section[data-testid="stSidebar"],
  [data-testid="stHeader"],
  [data-testid="stToolbar"],
  [data-testid="stDecoration"],
  [data-testid="stStatusWidget"],
  iframe{{display:none!important;}}
  [data-testid="block-container"]{{padding:0!important;margin:0!important;max-width:100%!important;}}
  [data-testid="stVerticalBlock"]>div{{gap:0!important;margin-bottom:0!important;padding-bottom:0!important;}}
  [data-testid="stHorizontalBlock"]{{gap:2px!important;}}
  [data-testid="metric-container"]{{padding:.25rem .4rem!important;border-radius:6px!important;margin:0!important;}}
  [data-testid="metric-container"] [data-testid="stMetricValue"]{{font-size:1.1rem!important;}}
  [data-testid="metric-container"] label{{font-size:.55rem!important;}}
  div[data-testid="stVerticalBlockBorderWrapper"]{{padding:0!important;}}
  .element-container,.stMarkdown{{margin:0!important;padding:0!important;}}
}}
</style>""", unsafe_allow_html=True)

# ── helpers ───────────────────────────────────────────────────────────────────
def _phase_key(p):
    p_norm = str(p).strip().lower()
    for i, ref in enumerate(PHASE_ORDER):
        if ref.strip().lower() == p_norm:
            return i
    return len(PHASE_ORDER)

def _is_lost(phase):
    if pd.isna(phase): return False
    return any(kw in str(phase).lower() for kw in LOST_KEYWORDS)

def _parse_date_robust(series):
    """Parst Datumsspalten – deutsches Format zuerst, dann ISO/UTC."""
    for kw in [
        dict(errors="coerce", format="%d.%m.%Y"),
        dict(errors="coerce", format="%d.%m.%Y %H:%M"),
        dict(errors="coerce", format="%d.%m.%Y %H:%M:%S"),
        dict(utc=True, errors="coerce"),
        dict(errors="coerce", dayfirst=True),
    ]:
        parsed = pd.to_datetime(series, **kw)
        if parsed.notna().any():
            if parsed.dt.tz is not None:
                return parsed.dt.tz_convert(None)
            return parsed
    return pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns]")

def _parse_number(series):
    s = series.astype(str).str.strip()
    if s.str.contains(r"\d\.\d{3},", regex=True).any():
        s = s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    return pd.to_numeric(s, errors="coerce")

def fmt_eur(val):
    return f"€ {val:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")

def sep(title=""):
    if title:
        st.markdown(f'<div style="color:{MUTED};font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.14em;margin:.6rem 0 .35rem;padding-bottom:.3rem;border-bottom:1px solid {BDR};">{title}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div style="border-top:1px solid {BDR};margin:.5rem 0;"></div>', unsafe_allow_html=True)

def pc(h=400):
    return dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                height=h, font=dict(color=TEXT, size=12),
                margin=dict(l=10,r=10,t=45,b=10),
                xaxis=dict(gridcolor=BDR, linecolor=BDR, tickfont=dict(color=MUTED)),
                yaxis=dict(gridcolor=BDR, linecolor=BDR, tickfont=dict(color=MUTED)),
                legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=MUTED)))

def lead_table(df_in, sort_col="Alter_Tage"):
    COLS = ["Vorgang #","Titel","Typ","Phase","Zuständig","Kontakte","earliest_todo_due_at","Erstellt","Alter_Tage","Potenzieller Wert"]
    cols = [c for c in COLS if c in df_in.columns]
    out = df_in[cols].sort_values(sort_col, ascending=False) if sort_col in df_in.columns else df_in[cols]
    st.dataframe(out, use_container_width=True, hide_index=True)

# ── data ─────────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def load_csv(raw_bytes):
    import io
    df = None
    for enc in ("utf-8-sig","utf-8","latin-1","cp1252"):
        try:
            df = pd.read_csv(io.BytesIO(raw_bytes), encoding=enc, sep=None, engine="python")
            break
        except: continue
    if df is None:
        st.error("CSV konnte nicht gelesen werden."); st.stop()
    df.columns = df.columns.str.strip()
    # Phasennamen trimmen damit Leerzeichen in der CSV kein Problem machen
    if "Phase" in df.columns:
        df["Phase"] = df["Phase"].astype(str).str.strip()
    # Spaltennamen normalisieren für robuste Erkennung
    col_map = {c.lower().strip(): c for c in df.columns}
    for col in ("Erstellt","Wiedervorlage","earliest_todo_due_at","due_at","Frist"):
        real = col_map.get(col.lower(), col)
        if real in df.columns:
            df[real] = _parse_date_robust(df[real])
    # WV-Spalte: nimm die erste mit echten Werten
    _wv_set = False
    for wv_col in ("Wiedervorlage","due_at","Frist","earliest_todo_due_at"):
        real = col_map.get(wv_col.lower(), wv_col)
        if real in df.columns and df[real].notna().any():
            df["_wv"] = df[real]
            _wv_set = True
            break
    if not _wv_set:
        df["_wv"] = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
    for col in ("Potenzieller Wert","Provision","attr_case_potential_value"):
        if col in df.columns:
            df[col] = _parse_number(df[col])  # NaN bleibt NaN (= kein Eintrag), 0 bleibt 0
    if "Aufgaben" in df.columns:
        df["Aufgaben"] = pd.to_numeric(df["Aufgaben"], errors="coerce").fillna(0)
    today = pd.Timestamp(date.today())
    erstellt = df["Erstellt"] if "Erstellt" in df.columns else pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
    df["Alter_Tage"]   = (today - erstellt).dt.days
    df["Ist_Verloren"] = df["Phase"].apply(_is_lost)
    todo = df["_wv"]
    in3  = today + pd.Timedelta(days=3)
    in5  = today + pd.Timedelta(days=5)
    df["Flag_Keine_WV"]        = (~df["Ist_Verloren"]) & todo.isna()
    df["Flag_Kein_Wert"]       = (~df["Ist_Verloren"]) & (df["Potenzieller Wert"].isna() if "Potenzieller Wert" in df.columns else True)
    df["Flag_WV_Ueberfaellig"] = (~df["Ist_Verloren"]) & todo.notna() & (todo < today)
    df["Flag_WV_Heute"]        = (~df["Ist_Verloren"]) & todo.notna() & (todo.dt.date == date.today())
    df["WV_Bucket"] = "Später"
    df.loc[todo.isna() & ~df["Ist_Verloren"],                          "WV_Bucket"] = "Keine WV"
    df.loc[todo.notna() & (todo < today),                              "WV_Bucket"] = "Überfällig"
    df.loc[todo.notna() & (todo >= today) & (todo <= in3),             "WV_Bucket"] = "≤ 3 Tage"
    df.loc[todo.notna() & (todo > in3)   & (todo <= in5),             "WV_Bucket"] = "≤ 5 Tage"
    return df

# ── sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f'<p style="color:{MUTED};font-size:.7rem;text-transform:uppercase;letter-spacing:.1em;font-weight:600;">CSV Import</p>', unsafe_allow_html=True)
    uploaded  = st.file_uploader("Export", type=["csv"], label_visibility="collapsed")
    if st.button("🔄 Cache leeren", use_container_width=True):
        load_csv.clear()
        st.rerun()
    warn_days = 28

# ── header ────────────────────────────────────────────────────────────────────
hc1, hc2, hc3 = st.columns([2,5,2])
with hc1:
    st.markdown(f'<div style="margin-top:2px;"><span style="background:#1e293b;color:{LBLUE};font-weight:900;font-size:1.4rem;letter-spacing:-.02em;padding:5px 14px;border-radius:8px;font-family:Arial Black,sans-serif;">LOYAGO</span></div>', unsafe_allow_html=True)
with hc2:
    st.markdown(f'<div style="padding-top:10px;color:{MUTED};font-size:.7rem;text-transform:uppercase;letter-spacing:.18em;font-weight:600;">Sales Cockpit</div>', unsafe_allow_html=True)
with hc3:
    st.markdown(f'<div style="text-align:right;padding-top:8px;color:{BLUE};font-size:.82rem;font-weight:600;">{date.today().strftime("%d. %B %Y")}</div>', unsafe_allow_html=True)
sep()

if not uploaded:
    st.markdown(f'<div style="text-align:center;padding:6rem 2rem;color:{MUTED};font-size:.95rem;">📂 &nbsp; CSV-Export über die Seitenleiste hochladen</div>', unsafe_allow_html=True)
    st.stop()

df = load_csv(uploaded.read())

act = df[~df["Ist_Verloren"]].copy()
if act.empty:
    st.warning("Keine aktiven Leads."); st.stop()

# Sales vs. After Sales Split
act_sales = act[act["Phase"].isin(PHASE_ORDER_SALES)] if "Phase" in act.columns else act.iloc[0:0]
pip_val   = act_sales["Potenzieller Wert"].sum() if "Potenzieller Wert" in act_sales.columns else 0
n_overdue = int(act["Flag_WV_Ueberfaellig"].sum())
n_no_wv   = int(act["Flag_Keine_WV"].sum())
n_no_val  = int(act["Flag_Kein_Wert"].sum())
n_today   = int(act["Flag_WV_Heute"].sum())
count_col = "Vorgang #" if "Vorgang #" in act.columns else act.columns[0]
total     = len(act)

# ── KPIs ─────────────────────────────────────────────────────────────────────
k1,k2,k3,k4,k5 = st.columns(5)
k1.metric("Aktive Leads",       total)
k2.metric("Pipeline-Wert",      fmt_eur(pip_val))
k3.metric("Heute fällig",       n_today)
k4.metric("Überfällige WV",     n_overdue)
k5.metric("Ohne Wiedervorlage", n_no_wv)

# ── Helper: Phase Cards rendert ─────────────────────────────────────────────
def _render_phase_cards(data, phase_order, title_prefix=""):
    if data.empty or not phase_order:
        return False

    WV_ORDER  = ["Keine WV", "Überfällig", "≤ 3 Tage", "≤ 5 Tage", "Später"]
    WV_COLORS = {
        "Überfällig": "#dc2626",
        "Keine WV":   "#f97316",
        "≤ 3 Tage":  "#eab308",
        "≤ 5 Tage":  "#06b6d4",
        "Später":     "#64748b",
    }

    _PHASE_RANK = {ref.strip().lower(): i for i, ref in enumerate(phase_order)}
    _raw_phases = sorted(
        [p for p in data["Phase"].dropna().unique().tolist() if p in phase_order] if "Phase" in data.columns else [],
        key=lambda p: _PHASE_RANK.get(str(p).strip().lower(), 999)
    )

    if not _raw_phases:
        return False

    sep(title_prefix) if title_prefix else None
    pcols = st.columns(len(_raw_phases))

    for i, phase in enumerate(_raw_phases):
        ph    = data[data["Phase"] == phase] if "Phase" in data.columns else data.iloc[0:0]
        n     = len(ph)
        val   = ph["Potenzieller Wert"].sum() if "Potenzieller Wert" in ph.columns else 0
        pct   = round(n / len(data) * 100) if len(data) else 0

        n_no_val_ph = int(ph["Flag_Kein_Wert"].sum()) if "Flag_Kein_Wert" in ph.columns else 0
        wv_counts = ph["WV_Bucket"].value_counts() if "WV_Bucket" in ph.columns else pd.Series(dtype=int)
        wv_rows = ""
        for bucket in WV_ORDER:
            cnt     = int(wv_counts.get(bucket, 0))
            c       = WV_COLORS[bucket]
            bar_w   = round(cnt / n * 100) if n and cnt else 0
            cnt_col = c if cnt else "rgba(100,116,139,.28)"
            bar_col = c if cnt else "rgba(203,218,251,.35)"
            wv_rows += (
                f'<div style="display:flex;align-items:center;gap:5px;height:1.6rem;">'
                f'<span style="color:{MUTED};font-size:.72rem;width:58px;flex-shrink:0;white-space:nowrap;">{bucket}</span>'
                f'<div style="flex:1;background:{LBLUE};border-radius:3px;height:3px;">'
                f'<div style="background:{bar_col};width:{bar_w}%;height:3px;border-radius:3px;"></div></div>'
                f'<span style="color:{cnt_col};font-weight:700;font-size:.76rem;width:22px;text-align:right;">{cnt}</span>'
                f'</div>'
            )

        # Zuständige-Übersicht (kompakt, ohne Balken)
        owner_rows = ""
        if "Zuständig" in ph.columns:
            owner_counts = ph["Zuständig"].value_counts()
            for owner, cnt in owner_counts.head(5).items():
                safe_owner = str(owner).strip()[:12]  # Max 12 Zeichen
                owner_rows += (
                    f'<div style="font-size:.68rem;color:{MUTED};line-height:1.4;flex-shrink:0;">'
                    f'<span style="font-weight:600;color:{TEXT};">{safe_owner}</span>'
                    f' <span style="color:{BLUE};font-weight:700;">{cnt}</span>'
                    f'</div>'
                )

        no_val_hint = ""
        if n_no_val_ph:
            no_val_hint = (f'<div style="color:{MUTED};font-size:.68rem;margin-top:.15rem;'
                           f'flex-shrink:0;">{n_no_val_ph} ohne Wert</div>')

        with pcols[i]:
            st.markdown(
                f'<div style="background:{CARD};border:1px solid {BDR};border-radius:14px;'
                f'padding:1rem .85rem;box-shadow:0 2px 10px rgba(37,99,235,.08);'
                f'display:flex;flex-direction:column;min-height:380px;">'
                f'<div style="color:{BLUE};font-size:.68rem;font-weight:700;text-transform:uppercase;'
                f'letter-spacing:.08em;line-height:1.35;height:1.8rem;overflow:hidden;'
                f'margin-bottom:.4rem;flex-shrink:0;">{phase}</div>'
                f'<div style="display:flex;align-items:center;gap:.4rem;'
                f'margin-bottom:.1rem;flex-shrink:0;">'
                f'<span style="color:{TEXT};font-size:2rem;font-weight:800;line-height:1;">{n}</span>'
                f'<span style="background:{LBLUE};color:{BLUE};font-size:.66rem;font-weight:700;'
                f'padding:2px 8px;border-radius:20px;">{pct} %</span>'
                f'</div>'
                f'<div style="color:{MUTED};font-size:.72rem;margin-bottom:.25rem;flex-shrink:0;">Leads</div>'
                f'<div style="color:{BLUE};font-size:.88rem;font-weight:700;flex-shrink:0;">{fmt_eur(val)}</div>'
                f'{no_val_hint}'
                f'<div style="border-top:1px solid {BDR};margin-top:.5rem;padding-top:.35rem;'
                f'display:flex;flex-direction:column;">{wv_rows}</div>'
                f'<div style="border-top:1px solid {BDR};margin-top:.35rem;padding-top:.35rem;'
                f'display:flex;flex-direction:column;">{owner_rows}</div>'
                f'</div>',
                unsafe_allow_html=True
            )

    return True

# ── Sales Funnel ──────────────────────────────────────────────────────────────
st.markdown(f'<h2 style="color:{BLUE};font-size:1.3rem;font-weight:800;margin:.8rem 0 .5rem;border-bottom:2px solid {BDR};padding-bottom:.4rem;">I. Aktueller Sales-Funnel</h2>', unsafe_allow_html=True)
_render_phase_cards(act_sales, PHASE_ORDER_SALES, "")

# Top-Chancen unter Sales
if "Potenzieller Wert" in act_sales.columns:
    top = act_sales[act_sales["Potenzieller Wert"] > 0].sort_values("Potenzieller Wert", ascending=False).head(10)
    if not top.empty:
        st.markdown(f'<div style="color:{MUTED};font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.14em;margin:1rem 0 .4rem;padding-bottom:.3rem;border-bottom:1px solid {BDR};">Top-Chancen</div>', unsafe_allow_html=True)
        TCOLS = ["Vorgang #","Titel","Typ","Phase","Zuständig","Kontakte","Potenzieller Wert"]
        tcols = [c for c in TCOLS if c in top.columns]
        hdr = "".join(f'<th style="padding:5px 8px;text-align:left;font-size:.68rem;font-weight:700;color:{MUTED};text-transform:uppercase;letter-spacing:.06em;border-bottom:2px solid {BDR};white-space:nowrap;">{c}</th>' for c in tcols)
        rows_html = ""
        for _, r in top[tcols].iterrows():
            cells = ""
            for c in tcols:
                v = fmt_eur(r[c]) if c == "Potenzieller Wert" else str(r[c]) if not pd.isna(r[c]) else ""
                fw = "700" if c == "Potenzieller Wert" else "400"
                col = BLUE if c == "Potenzieller Wert" else TEXT
                cells += f'<td style="padding:4px 8px;font-size:.72rem;color:{col};font-weight:{fw};border-bottom:1px solid {BDR};white-space:nowrap;max-width:200px;overflow:hidden;text-overflow:ellipsis;">{v}</td>'
            rows_html += f"<tr>{cells}</tr>"
        st.markdown(
            f'<div style="background:{CARD};border:1px solid {BDR};border-radius:12px;overflow:hidden;">'
            f'<table style="width:100%;border-collapse:collapse;"><thead><tr>{hdr}</tr></thead>'
            f'<tbody>{rows_html}</tbody></table></div>',
            unsafe_allow_html=True)

# ── After Sales ───────────────────────────────────────────────────────────────
st.markdown(f'<h2 style="color:{BLUE};font-size:1.3rem;font-weight:800;margin:1.2rem 0 .5rem;border-bottom:2px solid {BDR};padding-bottom:.4rem;">II. After Sales</h2>', unsafe_allow_html=True)
_render_phase_cards(act[act["Phase"].isin(PHASE_ORDER_AFTER)] if "Phase" in act.columns else act.iloc[0:0], PHASE_ORDER_AFTER, "")

# One-Pager: alles nach hier verstecken
st.markdown(f'<div style="color:{MUTED};font-size:.6rem;text-align:center;margin:1.5rem 0;padding-top:1rem;border-top:2px solid {BDR};">SALES DASHBOARD | One-Pager für den Druck optimiert</div>', unsafe_allow_html=True)

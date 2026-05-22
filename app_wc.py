import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.express as px
from datetime import date

st.set_page_config(page_title="LOYAGO · Welcome Calls", page_icon="📞", layout="wide", initial_sidebar_state="expanded")

# Nur "kein Interesse" rausfiltern — alle anderen Phasen bleiben sichtbar
LOST_KEYWORDS = ["kein interesse"]

# ── Farben (identisches Theme) ────────────────────────────────────────────────
BG    = "#cbdafb"
CARD  = "#ffffff"
BDR   = "rgba(37,99,235,0.18)"
BLUE  = "#2563eb"
LBLUE = "#c8d8f8"
TEXT  = "#1e293b"
MUTED = "#64748b"
GREEN = "#16a34a"
RED   = "#dc2626"
ORA   = "#ea580c"

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
@page{{margin:5mm 6mm;}}
@media print{{
  section[data-testid="stSidebar"],
  [data-testid="stHeader"],
  [data-testid="stToolbar"],
  [data-testid="stDecoration"],
  [data-testid="stStatusWidget"],
  iframe{{display:none!important;}}
  [data-testid="block-container"]{{padding:0!important;margin:0!important;max-width:100%!important;}}
  [data-testid="stVerticalBlock"]>div{{gap:0!important;}}
  [data-testid="metric-container"]{{padding:.35rem .6rem!important;}}
  [data-testid="metric-container"] [data-testid="stMetricValue"]{{font-size:1.3rem!important;}}
}}
</style>""", unsafe_allow_html=True)

# ── Helpers ───────────────────────────────────────────────────────────────────
def _is_lost(phase):
    if pd.isna(phase): return False
    return any(kw in str(phase).lower() for kw in LOST_KEYWORDS)

def _parse_date_robust(series):
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

def lead_table(df_in, sort_col="Alter_Tage"):
    COLS = ["Vorgang #","Titel","Typ","Phase","Zuständig","Kontakte","Wiedervorlage","Erstellt","Alter_Tage"]
    cols = [c for c in COLS if c in df_in.columns]
    out = df_in[cols].sort_values(sort_col, ascending=False) if sort_col in df_in.columns else df_in[cols]
    st.dataframe(out, use_container_width=True, hide_index=True)

# ── Daten laden ───────────────────────────────────────────────────────────────
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
    if "Phase" in df.columns:
        df["Phase"] = df["Phase"].astype(str).str.strip()
    col_map = {c.lower().strip(): c for c in df.columns}
    # Datum-Spalten parsen
    for col in ("Erstellt","Wiedervorlage","Abgeschlossen"):
        real = col_map.get(col.lower(), col)
        if real in df.columns:
            df[real] = _parse_date_robust(df[real])
    # WV-Spalte
    wv_col = col_map.get("wiedervorlage", "Wiedervorlage")
    df["_wv"] = df[wv_col] if wv_col in df.columns else pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
    # Wert-Spalte
    val_col = col_map.get("attr_case_potential_value", None)
    if val_col and val_col in df.columns:
        df["_wert"] = _parse_number(df[val_col])
    else:
        df["_wert"] = pd.Series(dtype=float)
    today = pd.Timestamp(date.today())
    erstellt_col = col_map.get("erstellt", "Erstellt")
    erstellt = df[erstellt_col] if erstellt_col in df.columns else pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
    df["Alter_Tage"]   = (today - erstellt).dt.days
    df["Ist_Verloren"] = df["Phase"].apply(_is_lost)
    todo = df["_wv"]
    in3  = today + pd.Timedelta(days=3)
    in5  = today + pd.Timedelta(days=5)
    df["Flag_Keine_WV"]        = (~df["Ist_Verloren"]) & todo.isna()
    df["Flag_WV_Ueberfaellig"] = (~df["Ist_Verloren"]) & todo.notna() & (todo < today)
    df["Flag_WV_Heute"]        = (~df["Ist_Verloren"]) & todo.notna() & (todo.dt.date == date.today())
    df["WV_Bucket"] = "Später"
    df.loc[todo.isna() & ~df["Ist_Verloren"],                "WV_Bucket"] = "Keine WV"
    df.loc[todo.notna() & (todo < today),                   "WV_Bucket"] = "Überfällig"
    df.loc[todo.notna() & (todo >= today) & (todo <= in3),  "WV_Bucket"] = "≤ 3 Tage"
    df.loc[todo.notna() & (todo > in3)   & (todo <= in5),  "WV_Bucket"] = "≤ 5 Tage"
    return df

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f'<p style="color:{MUTED};font-size:.7rem;text-transform:uppercase;letter-spacing:.1em;font-weight:600;">CSV Import</p>', unsafe_allow_html=True)
    uploaded = st.file_uploader("Export", type=["csv"], label_visibility="collapsed")
    if st.button("🔄 Cache leeren", use_container_width=True):
        load_csv.clear()
        st.rerun()
    warn_days = 28

# ── Header ────────────────────────────────────────────────────────────────────
hc1, hc2, hc3 = st.columns([2,5,2])
with hc1:
    st.markdown(f'<div style="margin-top:2px;"><span style="background:#1e293b;color:{LBLUE};font-weight:900;font-size:1.4rem;letter-spacing:-.02em;padding:5px 14px;border-radius:8px;font-family:Arial Black,sans-serif;">LOYAGO</span></div>', unsafe_allow_html=True)
with hc2:
    st.markdown(f'<div style="padding-top:10px;color:{MUTED};font-size:.7rem;text-transform:uppercase;letter-spacing:.18em;font-weight:600;">Welcome Call Cockpit</div>', unsafe_allow_html=True)
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

count_col  = "Vorgang #" if "Vorgang #" in act.columns else act.columns[0]
total      = len(act)
n_no_wv    = int(act["Flag_Keine_WV"].sum())
n_overdue  = int(act["Flag_WV_Ueberfaellig"].sum())
n_today    = int(act["Flag_WV_Heute"].sum())
n_with_wv  = total - n_no_wv

# ── KPIs ─────────────────────────────────────────────────────────────────────
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Aktive Leads",        total)
k2.metric("Mit Wiedervorlage",   n_with_wv)
k3.metric("Ohne Wiedervorlage",  n_no_wv)
k4.metric("Überfällige WV",      n_overdue)
k5.metric("Heute fällig",        n_today)

# ── Phase-Cards ───────────────────────────────────────────────────────────────
sep("Welcome Calls nach Phase")

WV_ORDER  = ["Keine WV", "Überfällig", "≤ 3 Tage", "≤ 5 Tage", "Später"]
WV_COLORS = {
    "Überfällig": "#dc2626",
    "Keine WV":   "#f97316",
    "≤ 3 Tage":  "#eab308",
    "≤ 5 Tage":  "#06b6d4",
    "Später":     "#64748b",
}

_PHASE_RANK = {}  # keine feste Reihenfolge — Phasen aus den Daten
_raw_phases = sorted(
    act["Phase"].dropna().unique().tolist() if "Phase" in act.columns else [],
    key=lambda p: _PHASE_RANK.get(str(p).strip().lower(), 999)
)

if "phase_order_wc" not in st.session_state or set(st.session_state.phase_order_wc) != set(_raw_phases):
    st.session_state.phase_order_wc = _raw_phases

with st.sidebar:
    st.markdown(f'<p style="color:{MUTED};font-size:.7rem;text-transform:uppercase;letter-spacing:.1em;font-weight:600;margin-top:1rem;">Phasen-Reihenfolge</p>', unsafe_allow_html=True)
    order = st.session_state.phase_order_wc
    for idx, ph_name in enumerate(order):
        c1, c2, c3 = st.columns([4,1,1])
        c1.markdown(f'<div style="font-size:.75rem;padding-top:4px;color:{TEXT};">{ph_name}</div>', unsafe_allow_html=True)
        if idx > 0 and c2.button("↑", key=f"wc_up_{idx}"):
            order[idx], order[idx-1] = order[idx-1], order[idx]; st.rerun()
        if idx < len(order)-1 and c3.button("↓", key=f"wc_dn_{idx}"):
            order[idx], order[idx+1] = order[idx+1], order[idx]; st.rerun()

phases_in = st.session_state.phase_order_wc

if phases_in:
    pcols = st.columns(len(phases_in))
    for i, phase in enumerate(phases_in):
        ph  = act[act["Phase"] == phase] if "Phase" in act.columns else act.iloc[0:0]
        n   = len(ph)
        pct = round(n / total * 100) if total else 0
        n_no_wv_ph = int(ph["Flag_Keine_WV"].sum())

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

        no_wv_hint = ""
        if n_no_wv_ph:
            no_wv_hint = (f'<div style="color:{ORA};font-size:.68rem;font-weight:600;'
                          f'margin-top:.15rem;flex-shrink:0;">⚠ {n_no_wv_ph} ohne WV</div>')

        with pcols[i]:
            st.markdown(
                f'<div style="background:{CARD};border:1px solid {BDR};border-radius:14px;'
                f'padding:1rem .85rem;box-shadow:0 2px 10px rgba(37,99,235,.08);display:flex;flex-direction:column;">'
                f'<div style="color:{BLUE};font-size:.68rem;font-weight:700;text-transform:uppercase;'
                f'letter-spacing:.08em;line-height:1.35;height:1.8rem;overflow:hidden;margin-bottom:.4rem;flex-shrink:0;">{phase}</div>'
                f'<div style="display:flex;align-items:center;gap:.4rem;margin-bottom:.1rem;flex-shrink:0;">'
                f'<span style="color:{TEXT};font-size:2rem;font-weight:800;line-height:1;">{n}</span>'
                f'<span style="background:{LBLUE};color:{BLUE};font-size:.66rem;font-weight:700;padding:2px 8px;border-radius:20px;">{pct} %</span>'
                f'</div>'
                f'<div style="color:{MUTED};font-size:.72rem;margin-bottom:.25rem;flex-shrink:0;">Leads</div>'
                f'{no_wv_hint}'
                f'<div style="border-top:1px solid {BDR};margin-top:.5rem;padding-top:.35rem;display:flex;flex-direction:column;">{wv_rows}</div>'
                f'</div>',
                unsafe_allow_html=True
            )

# JS: Seite-2-Inhalte vor dem Drucken verstecken
st.markdown('<span id="page2-marker" style="display:none;"></span>', unsafe_allow_html=True)
components.html("""<script>
(function(){
  var w = window.parent, d = w.document;
  if (!w._loyPrintWC) {
    w._loyPrintWC = true;
    w.addEventListener('beforeprint', function(){
      var m = d.getElementById('page2-marker');
      if (!m) return;
      var vb = m.closest('[data-testid="stVerticalBlock"]');
      if (!vb) return;
      var row = m; while (row.parentElement !== vb) row = row.parentElement;
      w._p2wc = [];
      var el = row;
      while (el) { el.style.setProperty('display','none','important'); w._p2wc.push(el); el = el.nextElementSibling; }
    });
    w.addEventListener('afterprint', function(){
      if (w._p2wc) { w._p2wc.forEach(function(el){ el.style.removeProperty('display'); }); w._p2wc = null; }
    });
  }
})();
</script>""", height=1)

# ── WV-Analyse nach Phase ─────────────────────────────────────────────────────
sep("Wiedervorlage-Status je Phase")

if "Phase" in act.columns and "WV_Bucket" in act.columns:
    wv_data = act.groupby(["Phase","WV_Bucket"]).size().reset_index(name="Anzahl")
    fig_wv = px.bar(wv_data, x="Phase", y="Anzahl", color="WV_Bucket", barmode="stack",
                    color_discrete_map=WV_COLORS, category_orders={"WV_Bucket": WV_ORDER})
    fig_wv.update_layout(
        title=dict(text="Wiedervorlage-Fälligkeit je Phase", font=dict(size=13, color=MUTED)),
        bargap=0.3,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        height=320, font=dict(color=TEXT, size=12),
        margin=dict(l=10,r=10,t=40,b=10),
        xaxis=dict(gridcolor=BDR, linecolor=BDR, tickfont=dict(color=MUTED)),
        yaxis=dict(gridcolor=BDR, linecolor=BDR, tickfont=dict(color=MUTED)),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=MUTED))
    )
    st.plotly_chart(fig_wv, use_container_width=True)

# ── Nach Mitarbeiter ──────────────────────────────────────────────────────────
if "Zuständig" in act.columns:
    sep("Nach Mitarbeiter")
    op = act.groupby(["Zuständig","Phase"]).agg(Leads=(count_col,"count")).reset_index()
    fig = px.bar(op, x="Zuständig", y="Leads", color="Phase", barmode="stack",
                 color_discrete_sequence=["#1d4ed8","#2563eb","#3b82f6","#60a5fa","#93c5fd","#bfdbfe","#dbeafe","#eff6ff"])
    fig.update_layout(
        title=dict(text="Leads pro Mitarbeiter", font=dict(size=13, color=MUTED)),
        bargap=0.3,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        height=320, font=dict(color=TEXT, size=12),
        margin=dict(l=10,r=10,t=40,b=10),
        xaxis=dict(gridcolor=BDR, linecolor=BDR, tickfont=dict(color=MUTED)),
        yaxis=dict(gridcolor=BDR, linecolor=BDR, tickfont=dict(color=MUTED)),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=MUTED))
    )
    st.plotly_chart(fig, use_container_width=True)

# ── Tages-Fokus ───────────────────────────────────────────────────────────────
sep("Tages-Fokus")
ec1, ec2 = st.columns(2)
with ec1:
    ov = act[act["Flag_WV_Ueberfaellig"]]
    with st.expander(f"⏰  Überfällige Wiedervorlagen  ({len(ov)})", expanded=len(ov)>0):
        if not ov.empty: lead_table(ov, "Wiedervorlage")
        else: st.markdown(f'<p style="color:{GREEN};">✓ Keine überfälligen WV</p>', unsafe_allow_html=True)
    no_wv_leads = act[act["Flag_Keine_WV"]]
    with st.expander(f"○  Ohne Wiedervorlage  ({len(no_wv_leads)})", expanded=False):
        if not no_wv_leads.empty: lead_table(no_wv_leads)
        else: st.markdown(f'<p style="color:{GREEN};">✓ Alle Leads haben WV</p>', unsafe_allow_html=True)
with ec2:
    td = act[act["Flag_WV_Heute"]]
    with st.expander(f"📅  Heute fällig  ({len(td)})", expanded=len(td)>0):
        if not td.empty: lead_table(td, "Wiedervorlage")
        else: st.markdown(f'<p style="color:{MUTED};">Keine WV für heute</p>', unsafe_allow_html=True)

# ── Alle Leads ────────────────────────────────────────────────────────────────
sep("Alle aktiven Welcome Calls")
f1, f2, f3, f4 = st.columns(4)
sp  = f1.selectbox("Phase",     ["Alle"]+sorted(act["Phase"].dropna().unique().tolist()))     if "Phase"     in act.columns else f1.selectbox("Phase",    ["Alle"])
so  = f2.selectbox("Zuständig", ["Alle"]+sorted(act["Zuständig"].dropna().unique().tolist())) if "Zuständig" in act.columns else f2.selectbox("Zuständig",["Alle"])
sf  = f3.multiselect("Filter",  ["Ohne WV","WV überfällig",f"Alter ≥ {warn_days} T."])

filt = act.copy()
if sp  != "Alle": filt = filt[filt["Phase"]     == sp]
if so  != "Alle" and "Zuständig" in filt.columns: filt = filt[filt["Zuständig"] == so]
if "Ohne WV"       in sf: filt = filt[filt["Flag_Keine_WV"]]
if "WV überfällig" in sf: filt = filt[filt["Flag_WV_Ueberfaellig"]]
if f"Alter ≥ {warn_days} T." in sf and "Alter_Tage" in filt.columns:
    filt = filt[filt["Alter_Tage"] >= warn_days]

st.markdown(f'<p style="color:{MUTED};font-size:.75rem;">{len(filt)} von {len(act)} aktiven Leads</p>', unsafe_allow_html=True)
lead_table(filt)

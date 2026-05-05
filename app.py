import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date

st.set_page_config(page_title="LOYAGO · Sales Cockpit", page_icon="📊", layout="wide", initial_sidebar_state="collapsed")

LOST_KEYWORDS = ["kein interesse", "verloren", "abgeschlossen", "closed lost", "closed won", "gewonnen", "won", "lost"]
PHASE_ORDER = [
    "Termin offen", "Termin vereinbart", "Beratung läuft",
    "Angebot raus", "Antrag raus", "Nachbearbeitung", "Policiert", "After Sales",
]

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
section[data-testid="stSidebar"]{{background:{CARD};border-right:1px solid {BDR};box-shadow:2px 0 12px rgba(37,99,235,.08);}}
[data-testid="metric-container"]{{background:{CARD};border:1px solid {BDR};border-radius:14px;padding:1.25rem 1.5rem;box-shadow:0 2px 8px rgba(37,99,235,.07);}}
[data-testid="metric-container"] label{{color:{MUTED}!important;font-size:.7rem!important;text-transform:uppercase;letter-spacing:.08em;}}
[data-testid="metric-container"] [data-testid="stMetricValue"]{{color:{TEXT}!important;font-size:1.9rem!important;font-weight:800;}}
.stExpander{{background:{CARD}!important;border:1px solid {BDR}!important;border-radius:12px!important;box-shadow:0 2px 6px rgba(37,99,235,.06)!important;}}
.stExpander summary{{color:{TEXT}!important;font-weight:600;}}
hr{{border-color:{BDR}!important;}}
p,span,div,label{{color:{TEXT};}}
[data-testid="stDataFrame"]{{border-radius:10px;}}
</style>""", unsafe_allow_html=True)

# ── helpers ───────────────────────────────────────────────────────────────────
def _phase_key(p):
    try: return PHASE_ORDER.index(p)
    except: return len(PHASE_ORDER)

def _is_lost(phase):
    if pd.isna(phase): return False
    return any(kw in str(phase).lower() for kw in LOST_KEYWORDS)

def _parse_date_robust(series):
    """Parst Datumsspalten mit mehreren Formaten (ISO, deutsch, mit/ohne TZ)."""
    for kw in [
        dict(utc=True, errors="coerce"),
        dict(errors="coerce", dayfirst=True),
        dict(errors="coerce", format="%d.%m.%Y"),
        dict(errors="coerce", format="%d.%m.%Y %H:%M"),
        dict(errors="coerce", format="%d.%m.%Y %H:%M:%S"),
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
        st.markdown(f'<div style="color:{MUTED};font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.14em;margin:2rem 0 .75rem;padding-bottom:.5rem;border-bottom:1px solid {BDR};">{title}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div style="border-top:1px solid {BDR};margin:1.5rem 0;"></div>', unsafe_allow_html=True)

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
            df[col] = _parse_number(df[col]).fillna(0)
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
    df["Flag_Kein_Wert"]       = (~df["Ist_Verloren"]) & (df.get("Potenzieller Wert", 0) == 0)
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
    warn_days = 28

# ── header ────────────────────────────────────────────────────────────────────
hc1, hc2, hc3 = st.columns([2,5,2])
with hc1:
    st.markdown(f'<div style="margin-top:8px;"><span style="background:#1e293b;color:{LBLUE};font-weight:900;font-size:1.5rem;letter-spacing:-.02em;padding:7px 16px;border-radius:8px;font-family:Arial Black,sans-serif;">LOYAGO</span></div>', unsafe_allow_html=True)
with hc2:
    st.markdown(f'<div style="padding-top:14px;color:{MUTED};font-size:.7rem;text-transform:uppercase;letter-spacing:.18em;font-weight:600;">Sales Cockpit</div>', unsafe_allow_html=True)
with hc3:
    st.markdown(f'<div style="text-align:right;padding-top:12px;color:{BLUE};font-size:.85rem;font-weight:600;">{date.today().strftime("%d. %B %Y")}</div>', unsafe_allow_html=True)
sep()

if not uploaded:
    st.markdown(f'<div style="text-align:center;padding:6rem 2rem;color:{MUTED};font-size:.95rem;">📂 &nbsp; CSV-Export über die Seitenleiste hochladen</div>', unsafe_allow_html=True)
    st.stop()

df = load_csv(uploaded.read())

act = df[~df["Ist_Verloren"]].copy()
if act.empty:
    st.warning("Keine aktiven Leads."); st.stop()

pip_val   = act["Potenzieller Wert"].sum() if "Potenzieller Wert" in act.columns else 0
n_overdue = int(act["Flag_WV_Ueberfaellig"].sum())
n_no_wv   = int(act["Flag_Keine_WV"].sum())
n_no_val  = int(act["Flag_Kein_Wert"].sum())
n_today   = int(act["Flag_WV_Heute"].sum())
count_col = "Vorgang #" if "Vorgang #" in act.columns else act.columns[0]
total     = len(act)

# ── Alert ─────────────────────────────────────────────────────────────────────
alerts = []
if n_overdue: alerts.append(f"<b>{n_overdue} überfällige WV</b>")
if n_no_wv:   alerts.append(f"<b>{n_no_wv} ohne Wiedervorlage</b>")
if n_no_val:  alerts.append(f"<b>{n_no_val} ohne Wert</b>")
if alerts:
    st.markdown(f'<div style="background:rgba(220,38,38,.08);border:1.5px solid rgba(220,38,38,.3);border-radius:12px;padding:.9rem 1.25rem;color:{RED};font-size:.875rem;margin-bottom:1rem;">⚠️ &nbsp; Handlungsbedarf: {" &nbsp;·&nbsp; ".join(alerts)}</div>', unsafe_allow_html=True)
else:
    st.markdown(f'<div style="background:rgba(22,163,74,.08);border:1.5px solid rgba(22,163,74,.3);border-radius:12px;padding:.9rem 1.25rem;color:{GREEN};font-size:.875rem;margin-bottom:1rem;">✓ &nbsp; Pipeline vollständig</div>', unsafe_allow_html=True)

# ── KPIs ─────────────────────────────────────────────────────────────────────
k1,k2,k3,k4,k5 = st.columns(5)
k1.metric("Aktive Leads",       total)
k2.metric("Pipeline-Wert",      fmt_eur(pip_val))
k3.metric("Heute fällig",       n_today)
k4.metric("Überfällige WV",     n_overdue)
k5.metric("Ohne Wiedervorlage", n_no_wv)

# ── Phase Cards ───────────────────────────────────────────────────────────────
sep("Pipeline nach Phase")

WV_ORDER  = ["Überfällig","Keine WV","≤ 3 Tage","≤ 5 Tage","Später"]
WV_COLORS = {"Überfällig": RED, "Keine WV": ORA, "≤ 3 Tage": YEL, "≤ 5 Tage": BLUE, "Später": GREEN}

phases_in  = [p for p in PHASE_ORDER if "Phase" in act.columns and p in act["Phase"].values]
phases_in += [p for p in (act["Phase"].dropna().unique() if "Phase" in act.columns else []) if p not in PHASE_ORDER]

if phases_in:
    pcols = st.columns(len(phases_in))
    for i, phase in enumerate(phases_in):
        ph   = act[act["Phase"] == phase] if "Phase" in act.columns else act.iloc[0:0]
        n    = len(ph)
        val  = ph["Potenzieller Wert"].sum() if "Potenzieller Wert" in ph.columns else 0
        pct  = round(n / total * 100) if total else 0
        n_ov = int(ph["Flag_WV_Ueberfaellig"].sum())
        n_wv = int(ph["Flag_Keine_WV"].sum())
        n_vl = int(ph["Flag_Kein_Wert"].sum())
        top  = RED if n_ov else (ORA if n_wv else (YEL if n_vl else GREEN))

        wv_counts = ph["WV_Bucket"].value_counts() if "WV_Bucket" in ph.columns else pd.Series(dtype=int)
        wv_rows = ""
        for bucket in WV_ORDER:
            cnt = int(wv_counts.get(bucket, 0))
            if cnt == 0: continue
            c = WV_COLORS[bucket]
            bar_w = round(cnt / n * 100) if n else 0
            wv_rows += f'''<div style="margin-bottom:5px;">
  <div style="display:flex;justify-content:space-between;margin-bottom:2px;">
    <span style="color:{MUTED};font-size:.6rem;">{bucket}</span>
    <span style="color:{c};font-weight:700;font-size:.65rem;">{cnt}</span>
  </div>
  <div style="background:{BG};border-radius:4px;height:4px;overflow:hidden;">
    <div style="background:{c};width:{bar_w}%;height:4px;border-radius:4px;"></div>
  </div>
</div>'''

        with pcols[i]:
            st.markdown(f"""<div style="background:{CARD};border:1px solid {BDR};border-radius:14px;padding:1.2rem 1rem;border-top:4px solid {top};box-shadow:0 2px 10px rgba(37,99,235,.08);">
<div style="color:{MUTED};font-size:.58rem;text-transform:uppercase;letter-spacing:.08em;margin-bottom:.5rem;min-height:2.4rem;display:flex;align-items:flex-end;">{phase}</div>
<div style="color:{TEXT};font-size:2rem;font-weight:800;line-height:1;margin-bottom:.1rem;">{n}</div>
<div style="color:{MUTED};font-size:.6rem;margin-bottom:.4rem;">Leads</div>
<div style="color:{BLUE};font-size:.9rem;font-weight:700;margin-bottom:.9rem;">{fmt_eur(val)}</div>
<div style="border-top:1px solid {BDR};padding-top:.7rem;">{wv_rows if wv_rows else f'<span style="color:{GREEN};font-size:.6rem;">✓ Alle WV gesetzt</span>'}</div>
</div>""", unsafe_allow_html=True)

# ── Phasen-Verteilung (visuell) ───────────────────────────────────────────────
sep("Wo stecken die meisten Leads?")

if "Phase" in act.columns and len(phases_in):
    phase_stats = (act.groupby("Phase")
        .agg(Leads=(count_col,"count"), Wert=("Potenzieller Wert","sum"))
        .reset_index())
    phase_stats["_o"]  = phase_stats["Phase"].apply(_phase_key)
    phase_stats = phase_stats.sort_values("_o").drop("_o", axis=1)
    phase_stats["Pct"] = (phase_stats["Leads"] / total * 100).round(1)
    max_leads = phase_stats["Leads"].max()

    for _, row in phase_stats.iterrows():
        bar_w  = int(row["Leads"] / max_leads * 100)
        is_max = row["Leads"] == max_leads
        bar_col = BLUE if is_max else f"rgba(37,99,235,0.35)"
        pct_col = BLUE if is_max else MUTED
        st.markdown(f"""<div style="display:flex;align-items:center;gap:1rem;margin-bottom:.6rem;">
  <div style="width:130px;text-align:right;color:{TEXT};font-size:.8rem;font-weight:{'700' if is_max else '400'};white-space:nowrap;">{row['Phase']}</div>
  <div style="flex:1;background:{BG};border-radius:6px;height:28px;overflow:hidden;border:1px solid {BDR};">
    <div style="background:{bar_col};width:{bar_w}%;height:28px;border-radius:5px;display:flex;align-items:center;padding-left:.6rem;">
      <span style="color:{'white' if is_max else TEXT};font-size:.75rem;font-weight:700;">{int(row['Leads'])} Leads</span>
    </div>
  </div>
  <div style="width:55px;text-align:right;color:{pct_col};font-size:{'1.1rem' if is_max else '.85rem'};font-weight:{'800' if is_max else '500'};">{row['Pct']}%</div>
  <div style="width:80px;text-align:right;color:{MUTED};font-size:.75rem;">{fmt_eur(row['Wert'])}</div>
</div>""", unsafe_allow_html=True)

# ── WV-Analyse je Phase ───────────────────────────────────────────────────────
sep("Wiedervorlage-Status je Phase")

if "Phase" in act.columns and "WV_Bucket" in act.columns:
    wv_data = act.groupby(["Phase","WV_Bucket"]).size().reset_index(name="Anzahl")
    wv_data["_o"] = wv_data["Phase"].apply(_phase_key)
    wv_data = wv_data.sort_values("_o").drop("_o", axis=1)
    fig_wv = px.bar(wv_data, x="Phase", y="Anzahl", color="WV_Bucket", barmode="stack",
                    color_discrete_map=WV_COLORS, category_orders={"WV_Bucket": WV_ORDER})
    fig_wv.update_layout(title=dict(text="Wiedervorlage-Fälligkeit je Phase", font=dict(size=13,color=MUTED)),
                         bargap=0.3, **pc(360))
    st.plotly_chart(fig_wv, use_container_width=True)

# ── Nach Mitarbeiter ──────────────────────────────────────────────────────────
if "Zuständig" in act.columns:
    sep("Pipeline nach Mitarbeiter")
    op = act.groupby(["Zuständig","Phase"]).agg(Leads=(count_col,"count"), Wert=("Potenzieller Wert","sum")).reset_index()
    mc1, mc2 = st.columns(2)
    with mc1:
        f1 = px.bar(op, x="Zuständig", y="Leads", color="Phase", barmode="stack",
                    color_discrete_sequence=["#1d4ed8","#2563eb","#3b82f6","#60a5fa","#93c5fd","#bfdbfe","#dbeafe","#eff6ff"])
        f1.update_layout(title=dict(text="Leads pro Mitarbeiter", font=dict(size=13,color=MUTED)), bargap=0.3, **pc(360))
        st.plotly_chart(f1, use_container_width=True)
    with mc2:
        f2 = px.bar(op, x="Zuständig", y="Wert", color="Phase", barmode="stack",
                    color_discrete_sequence=["#1d4ed8","#2563eb","#3b82f6","#60a5fa","#93c5fd","#bfdbfe","#dbeafe","#eff6ff"])
        f2.update_layout(title=dict(text="Wert pro Mitarbeiter", font=dict(size=13,color=MUTED)), bargap=0.3, **pc(360))
        st.plotly_chart(f2, use_container_width=True)

# ── Tages-Fokus ───────────────────────────────────────────────────────────────
sep("Tages-Fokus")
ec1, ec2 = st.columns(2)
with ec1:
    ov = act[act["Flag_WV_Ueberfaellig"]]
    with st.expander(f"⏰  Überfällige Wiedervorlagen  ({len(ov)})", expanded=len(ov)>0):
        if not ov.empty: lead_table(ov, "earliest_todo_due_at")
        else: st.markdown(f'<p style="color:{GREEN};">✓ Keine überfälligen WV</p>', unsafe_allow_html=True)
    no_wv = act[act["Flag_Keine_WV"]]
    with st.expander(f"○  Ohne Wiedervorlage  ({len(no_wv)})", expanded=False):
        if not no_wv.empty: lead_table(no_wv)
        else: st.markdown(f'<p style="color:{GREEN};">✓ Alle Leads haben WV</p>', unsafe_allow_html=True)
with ec2:
    td = act[act["Flag_WV_Heute"]]
    with st.expander(f"📅  Heute fällig  ({len(td)})", expanded=len(td)>0):
        if not td.empty: lead_table(td, "Potenzieller Wert")
        else: st.markdown(f'<p style="color:{MUTED};">Keine WV für heute</p>', unsafe_allow_html=True)
    no_val = act[act["Flag_Kein_Wert"]]
    with st.expander(f"€  Ohne Wert  ({len(no_val)})", expanded=False):
        if not no_val.empty: lead_table(no_val)
        else: st.markdown(f'<p style="color:{GREEN};">✓ Alle Leads haben Wert</p>', unsafe_allow_html=True)

# ── Top-Chancen ───────────────────────────────────────────────────────────────
if "Potenzieller Wert" in act.columns:
    top = act[act["Potenzieller Wert"] > 0].sort_values("Potenzieller Wert", ascending=False).head(10)
    if not top.empty:
        sep("Top-Chancen")
        lead_table(top, "Potenzieller Wert")

# ── Alle Leads ────────────────────────────────────────────────────────────────
sep("Alle aktiven Leads")
f1,f2,f3,f4 = st.columns(4)
sp  = f1.selectbox("Phase",     ["Alle"]+sorted(act["Phase"].dropna().unique().tolist()))     if "Phase"     in act.columns else f1.selectbox("Phase",    ["Alle"])
st_ = f2.selectbox("Typ",       ["Alle"]+sorted(act["Typ"].dropna().unique().tolist()))       if "Typ"       in act.columns else f2.selectbox("Typ",      ["Alle"])
so  = f3.selectbox("Zuständig", ["Alle"]+sorted(act["Zuständig"].dropna().unique().tolist())) if "Zuständig" in act.columns else f3.selectbox("Zuständig",["Alle"])
sf  = f4.multiselect("Filter",  ["Ohne WV","Ohne Wert","WV überfällig",f"Alter ≥ {warn_days} T."])

filt = act.copy()
if sp  != "Alle": filt = filt[filt["Phase"]     == sp]
if st_ != "Alle" and "Typ"       in filt.columns: filt = filt[filt["Typ"]       == st_]
if so  != "Alle" and "Zuständig" in filt.columns: filt = filt[filt["Zuständig"] == so]
if "Ohne WV"       in sf: filt = filt[filt["Flag_Keine_WV"]]
if "Ohne Wert"     in sf: filt = filt[filt["Flag_Kein_Wert"]]
if "WV überfällig" in sf: filt = filt[filt["Flag_WV_Ueberfaellig"]]
if f"Alter ≥ {warn_days} T." in sf and "Alter_Tage" in filt.columns:
    filt = filt[filt["Alter_Tage"] >= warn_days]

st.markdown(f'<p style="color:{MUTED};font-size:.75rem;">{len(filt)} von {len(act)} aktiven Leads</p>', unsafe_allow_html=True)
lead_table(filt)

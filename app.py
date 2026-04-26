import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date

st.set_page_config(page_title="LOYAGO · Sales Cockpit", page_icon="📊", layout="wide", initial_sidebar_state="collapsed")

LOST_KEYWORDS = ["kein interesse", "verloren", "abgeschlossen", "closed lost", "closed won", "gewonnen", "won", "lost"]
PHASE_ORDER = ["Termin offen", "Termin vereinbart", "Angebot raus", "Angebot angenommen", "Vertrag in Prüfung", "Abschluss"]

C_BG    = "#0f172a"
C_CARD  = "#1e293b"
C_BDR   = "#334155"
C_BLUE  = "#60a5fa"
C_LBLUE = "#c8d8f8"
C_TEXT  = "#f1f5f9"
C_MUTED = "#94a3b8"
C_GREEN = "#22c55e"
C_YEL   = "#f59e0b"
C_RED   = "#ef4444"
C_ORA   = "#f97316"

st.markdown(f"""<style>
[data-testid="stAppViewContainer"]{{background:{C_BG};}}
[data-testid="stHeader"]{{background:transparent;}}
section[data-testid="stSidebar"]{{background:{C_CARD};border-right:1px solid {C_BDR};}}
[data-testid="metric-container"]{{background:{C_CARD};border:1px solid {C_BDR};border-radius:12px;padding:1.2rem 1.5rem;}}
[data-testid="metric-container"] label{{color:{C_MUTED}!important;font-size:.7rem!important;text-transform:uppercase;letter-spacing:.08em;}}
[data-testid="metric-container"] [data-testid="stMetricValue"]{{color:{C_TEXT}!important;font-size:1.8rem!important;font-weight:700;}}
.stExpander{{background:{C_CARD}!important;border:1px solid {C_BDR}!important;border-radius:12px!important;}}
hr{{border-color:{C_BDR}!important;}}
p,span,div,label{{color:{C_TEXT};}}
</style>""", unsafe_allow_html=True)

# ── helpers ───────────────────────────────────────────────────────────────────

def _phase_key(p):
    try: return PHASE_ORDER.index(p)
    except: return len(PHASE_ORDER)

def _is_lost(phase):
    if pd.isna(phase): return False
    return any(kw in str(phase).lower() for kw in LOST_KEYWORDS)

def _parse_number(series):
    s = series.astype(str).str.strip()
    if s.str.contains(r"\d\.\d{3},", regex=True).any():
        s = s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    return pd.to_numeric(s, errors="coerce")

def fmt_eur(val):
    return f"€ {val:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")

def pc():
    return dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color=C_TEXT, size=12), margin=dict(l=10,r=10,t=45,b=10),
                xaxis=dict(gridcolor=C_BDR, linecolor=C_BDR, tickfont=dict(color=C_MUTED)),
                yaxis=dict(gridcolor=C_BDR, linecolor=C_BDR, tickfont=dict(color=C_MUTED)),
                legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=C_MUTED)))

def sep(title=""):
    if title:
        st.markdown(f'<div style="color:{C_MUTED};font-size:.7rem;text-transform:uppercase;letter-spacing:.14em;margin:2rem 0 .75rem;padding-bottom:.5rem;border-bottom:1px solid {C_BDR};">{title}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div style="border-top:1px solid {C_BDR};margin:1.5rem 0;"></div>', unsafe_allow_html=True)

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
    for col in ("Erstellt","earliest_todo_due_at","Frist"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], dayfirst=True, errors="coerce")
    for col in ("Potenzieller Wert","Provision","attr_case_potential_value"):
        if col in df.columns:
            df[col] = _parse_number(df[col]).fillna(0)
    if "Aufgaben" in df.columns:
        df["Aufgaben"] = pd.to_numeric(df["Aufgaben"], errors="coerce").fillna(0)
    today = pd.Timestamp(date.today())
    erstellt = df["Erstellt"] if "Erstellt" in df.columns else pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
    df["Alter_Tage"]   = (today - erstellt).dt.days
    df["Ist_Verloren"] = df["Phase"].apply(_is_lost)
    todo = df.get("earliest_todo_due_at", pd.Series(pd.NaT, index=df.index))
    in3 = today + pd.Timedelta(days=3)
    in5 = today + pd.Timedelta(days=5)
    df["Flag_Keine_WV"]        = (~df["Ist_Verloren"]) & todo.isna()
    df["Flag_Kein_Wert"]       = (~df["Ist_Verloren"]) & (df.get("Potenzieller Wert", 0) == 0)
    df["Flag_WV_Ueberfaellig"] = (~df["Ist_Verloren"]) & todo.notna() & (todo < today)
    df["Flag_WV_Heute"]        = (~df["Ist_Verloren"]) & todo.notna() & (todo.dt.date == date.today())
    df["WV_Bucket"] = "Später"
    df.loc[todo.isna() & ~df["Ist_Verloren"], "WV_Bucket"]                          = "Keine WV"
    df.loc[todo.notna() & (todo < today),     "WV_Bucket"]                          = "Überfällig"
    df.loc[todo.notna() & (todo >= today) & (todo <= in3), "WV_Bucket"]             = "≤ 3 Tage"
    df.loc[todo.notna() & (todo > in3)   & (todo <= in5), "WV_Bucket"]              = "≤ 5 Tage"
    return df

# ── sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown(f'<p style="color:{C_MUTED};font-size:.7rem;text-transform:uppercase;letter-spacing:.1em;">CSV Import</p>', unsafe_allow_html=True)
    uploaded  = st.file_uploader("Export", type=["csv"], label_visibility="collapsed")
    st.markdown("---")
    warn_days = st.slider("Kritisches Alter (Tage)", 14, 60, 28)

# ── header ────────────────────────────────────────────────────────────────────

hc1, hc2, hc3 = st.columns([2,5,2])
with hc1:
    st.markdown(f'<div style="margin-top:8px;"><span style="background:{C_LBLUE};color:#1a1a1a;font-weight:900;font-size:1.5rem;letter-spacing:-.02em;padding:7px 16px;border-radius:8px;font-family:Arial Black,sans-serif;">LOYAGO</span></div>', unsafe_allow_html=True)
with hc2:
    st.markdown(f'<div style="padding-top:14px;color:{C_MUTED};font-size:.7rem;text-transform:uppercase;letter-spacing:.18em;">Sales Cockpit</div>', unsafe_allow_html=True)
with hc3:
    st.markdown(f'<div style="text-align:right;padding-top:12px;color:{C_BLUE};font-size:.85rem;">{date.today().strftime("%d. %B %Y")}</div>', unsafe_allow_html=True)

sep()

if not uploaded:
    st.markdown(f'<div style="text-align:center;padding:6rem 2rem;color:{C_MUTED};font-size:.95rem;">📂 &nbsp; CSV-Export über die Seitenleiste hochladen</div>', unsafe_allow_html=True)
    st.stop()

df  = load_csv(uploaded.read())
act = df[~df["Ist_Verloren"]].copy()
if act.empty:
    st.warning("Keine aktiven Leads."); st.stop()

today      = pd.Timestamp(date.today())
pip_val    = act["Potenzieller Wert"].sum() if "Potenzieller Wert" in act.columns else 0
n_overdue  = int(act["Flag_WV_Ueberfaellig"].sum())
n_no_wv    = int(act["Flag_Keine_WV"].sum())
n_no_val   = int(act["Flag_Kein_Wert"].sum())
n_today    = int(act["Flag_WV_Heute"].sum())
count_col  = "Vorgang #" if "Vorgang #" in act.columns else act.columns[0]

# ── Alert banner ──────────────────────────────────────────────────────────────

alerts = []
if n_overdue: alerts.append(f"<b>{n_overdue} überfällige WV</b>")
if n_no_wv:   alerts.append(f"<b>{n_no_wv} ohne Wiedervorlage</b>")
if n_no_val:  alerts.append(f"<b>{n_no_val} ohne Wert</b>")
if alerts:
    st.markdown(f'<div style="background:rgba(239,68,68,.12);border:1px solid rgba(239,68,68,.35);border-radius:10px;padding:.85rem 1.25rem;color:#fca5a5;font-size:.875rem;margin-bottom:1rem;">⚠️ &nbsp; Handlungsbedarf: {" &nbsp;·&nbsp; ".join(alerts)}</div>', unsafe_allow_html=True)
else:
    st.markdown(f'<div style="background:rgba(34,197,94,.1);border:1px solid rgba(34,197,94,.3);border-radius:10px;padding:.85rem 1.25rem;color:#86efac;font-size:.875rem;margin-bottom:1rem;">✓ &nbsp; Pipeline vollständig – alle Leads haben Wiedervorlage und Wert</div>', unsafe_allow_html=True)

# ── KPI strip ─────────────────────────────────────────────────────────────────

k1,k2,k3,k4,k5 = st.columns(5)
k1.metric("Aktive Leads",       len(act))
k2.metric("Pipeline-Wert",      fmt_eur(pip_val))
k3.metric("Heute fällig",       n_today)
k4.metric("Überfällige WV",     n_overdue)
k5.metric("Ohne Wiedervorlage", n_no_wv)

# ── Phase Cards ───────────────────────────────────────────────────────────────

sep("Pipeline nach Phase")

WV_ORDER  = ["Überfällig","Keine WV","≤ 3 Tage","≤ 5 Tage","Später"]
WV_COLORS = {"Überfällig": C_RED, "Keine WV": C_ORA, "≤ 3 Tage": C_YEL, "≤ 5 Tage": C_BLUE, "Später": C_GREEN}

phases_in = [p for p in PHASE_ORDER if "Phase" in act.columns and p in act["Phase"].values]
phases_in += [p for p in (act["Phase"].dropna().unique() if "Phase" in act.columns else []) if p not in PHASE_ORDER]

if phases_in:
    pcols = st.columns(len(phases_in))
    for i, phase in enumerate(phases_in):
        ph  = act[act["Phase"] == phase] if "Phase" in act.columns else act.iloc[0:0]
        n   = len(ph)
        val = ph["Potenzieller Wert"].sum() if "Potenzieller Wert" in ph.columns else 0
        n_ov = int(ph["Flag_WV_Ueberfaellig"].sum())
        n_wv = int(ph["Flag_Keine_WV"].sum())
        n_vl = int(ph["Flag_Kein_Wert"].sum())
        top  = C_RED if n_ov else (C_ORA if n_wv else (C_YEL if n_vl else C_GREEN))

        # WV breakdown pills
        wv_counts = ph["WV_Bucket"].value_counts() if "WV_Bucket" in ph.columns else pd.Series(dtype=int)
        wv_html = ""
        for bucket in WV_ORDER:
            cnt = int(wv_counts.get(bucket, 0))
            if cnt == 0: continue
            c = WV_COLORS[bucket]
            wv_html += f'<div style="display:flex;justify-content:space-between;align-items:center;padding:3px 0;border-bottom:1px solid {C_BDR}15;"><span style="color:{C_MUTED};font-size:.6rem;">{bucket}</span><span style="color:{c};font-weight:700;font-size:.75rem;">{cnt}</span></div>'

        with pcols[i]:
            st.markdown(f"""<div style="background:{C_CARD};border:1px solid {C_BDR};border-radius:12px;padding:1.25rem 1.1rem;border-top:3px solid {top};height:100%;">
<div style="color:{C_MUTED};font-size:.6rem;text-transform:uppercase;letter-spacing:.1em;margin-bottom:.6rem;">{phase}</div>
<div style="color:{C_TEXT};font-size:2.2rem;font-weight:800;line-height:1;margin-bottom:.15rem;">{n}</div>
<div style="color:{C_MUTED};font-size:.65rem;margin-bottom:.5rem;">Leads</div>
<div style="color:{C_BLUE};font-size:.95rem;font-weight:700;margin-bottom:1rem;">{fmt_eur(val)}</div>
<div style="border-top:1px solid {C_BDR};padding-top:.6rem;">{wv_html if wv_html else f'<span style="color:{C_GREEN};font-size:.65rem;">✓ Alle WV gesetzt</span>'}</div>
</div>""", unsafe_allow_html=True)

# ── Funnel + Wert ─────────────────────────────────────────────────────────────

sep("Funnel & Pipeline-Wert")

phase_stats = (act.groupby("Phase")
    .agg(Leads=(count_col,"count"), Wert=("Potenzieller Wert","sum"))
    .reset_index()) if "Phase" in act.columns else pd.DataFrame(columns=["Phase","Leads","Wert"])
phase_stats["_o"] = phase_stats["Phase"].apply(_phase_key)
phase_stats = phase_stats.sort_values("_o").drop("_o", axis=1)
if len(phase_stats):
    phase_stats["Ø Wert"] = (phase_stats["Wert"] / phase_stats["Leads"]).round(0)

fc1, fc2 = st.columns(2)
with fc1:
    fig_f = go.Figure(go.Funnel(
        y=phase_stats["Phase"], x=phase_stats["Leads"],
        textinfo="value+percent initial",
        textfont=dict(color=C_TEXT, size=13),
        marker=dict(color=[C_BLUE]*len(phase_stats), opacity=[max(0.4, 1-i*.12) for i in range(len(phase_stats))], line=dict(color=C_BDR, width=1)),
    ))
    fig_f.update_layout(title=dict(text="Leads je Phase", font=dict(size=13, color=C_MUTED)), height=480, **pc())
    st.plotly_chart(fig_f, use_container_width=True)

with fc2:
    fig_v = px.bar(phase_stats, x="Phase", y="Wert", text="Wert",
                   color_discrete_sequence=[C_BLUE], height=480)
    fig_v.update_traces(texttemplate="%{text:,.0f} €", textposition="outside",
                        textfont=dict(color=C_MUTED, size=11), marker_line_color=C_BDR)
    fig_v.update_layout(title=dict(text="Pipeline-Wert je Phase", font=dict(size=13, color=C_MUTED)), **pc())
    st.plotly_chart(fig_v, use_container_width=True)

# ── WV-Analyse je Phase (Heatmap) ─────────────────────────────────────────────

sep("Wiedervorlage-Analyse je Phase")

if "Phase" in act.columns and "WV_Bucket" in act.columns:
    wv_pivot = act.groupby(["Phase","WV_Bucket"]).size().reset_index(name="Anzahl")
    wv_pivot["_o"] = wv_pivot["Phase"].apply(_phase_key)
    wv_pivot = wv_pivot.sort_values("_o").drop("_o", axis=1)

    fig_wv = px.bar(wv_pivot, x="Phase", y="Anzahl", color="WV_Bucket", barmode="stack",
                    color_discrete_map=WV_COLORS,
                    category_orders={"WV_Bucket": WV_ORDER},
                    height=380)
    fig_wv.update_layout(title=dict(text="WV-Status je Phase", font=dict(size=13, color=C_MUTED)),
                         bargap=0.3, **pc())
    st.plotly_chart(fig_wv, use_container_width=True)

# ── Nach Mitarbeiter ──────────────────────────────────────────────────────────

if "Zuständig" in act.columns:
    sep("Pipeline nach Mitarbeiter")
    op = act.groupby(["Zuständig","Phase"]).agg(Leads=(count_col,"count"), Wert=("Potenzieller Wert","sum")).reset_index()
    oc1, oc2 = st.columns(2)
    with oc1:
        fo1 = px.bar(op, x="Zuständig", y="Leads", color="Phase", barmode="stack",
                     color_discrete_sequence=px.colors.sequential.Blues_r, height=360)
        fo1.update_layout(title=dict(text="Leads pro Mitarbeiter", font=dict(size=13,color=C_MUTED)), bargap=0.35, **pc())
        st.plotly_chart(fo1, use_container_width=True)
    with oc2:
        fo2 = px.bar(op, x="Zuständig", y="Wert", color="Phase", barmode="stack",
                     color_discrete_sequence=px.colors.sequential.Blues_r, height=360)
        fo2.update_layout(title=dict(text="Wert pro Mitarbeiter", font=dict(size=13,color=C_MUTED)), bargap=0.35, **pc())
        st.plotly_chart(fo2, use_container_width=True)

# ── Tages-Fokus (Expander) ────────────────────────────────────────────────────

sep("Tages-Fokus")

ec1, ec2 = st.columns(2)
with ec1:
    ov = act[act["Flag_WV_Ueberfaellig"]]
    with st.expander(f"⏰ Überfällige Wiedervorlagen ({len(ov)})", expanded=len(ov)>0):
        if not ov.empty: lead_table(ov, "earliest_todo_due_at")
        else: st.markdown(f'<p style="color:{C_GREEN};">✓ Keine überfälligen WV</p>', unsafe_allow_html=True)

    no_wv = act[act["Flag_Keine_WV"]]
    with st.expander(f"○ Ohne Wiedervorlage ({len(no_wv)})", expanded=False):
        if not no_wv.empty: lead_table(no_wv)
        else: st.markdown(f'<p style="color:{C_GREEN};">✓ Alle Leads haben WV</p>', unsafe_allow_html=True)

with ec2:
    td = act[act["Flag_WV_Heute"]]
    with st.expander(f"📅 Heute fällig ({len(td)})", expanded=len(td)>0):
        if not td.empty: lead_table(td, "Potenzieller Wert")
        else: st.markdown(f'<p style="color:{C_MUTED};">Keine WV für heute</p>', unsafe_allow_html=True)

    no_val = act[act["Flag_Kein_Wert"]]
    with st.expander(f"€ Ohne Wert ({len(no_val)})", expanded=False):
        if not no_val.empty: lead_table(no_val)
        else: st.markdown(f'<p style="color:{C_GREEN};">✓ Alle Leads haben Wert</p>', unsafe_allow_html=True)

# ── Top-Chancen ───────────────────────────────────────────────────────────────

if "Potenzieller Wert" in act.columns:
    sep("Top-Chancen")
    top = act[act["Potenzieller Wert"] > 0].sort_values("Potenzieller Wert", ascending=False).head(10)
    if not top.empty:
        lead_table(top, "Potenzieller Wert")

# ── Alle Leads ────────────────────────────────────────────────────────────────

sep("Alle aktiven Leads")

f1,f2,f3,f4 = st.columns(4)
sp = f1.selectbox("Phase",     ["Alle"]+sorted(act["Phase"].dropna().unique().tolist()))     if "Phase"     in act.columns else f1.selectbox("Phase",    ["Alle"])
st_ = f2.selectbox("Typ",      ["Alle"]+sorted(act["Typ"].dropna().unique().tolist()))       if "Typ"       in act.columns else f2.selectbox("Typ",      ["Alle"])
so = f3.selectbox("Zuständig", ["Alle"]+sorted(act["Zuständig"].dropna().unique().tolist())) if "Zuständig" in act.columns else f3.selectbox("Zuständig",["Alle"])
sf = f4.multiselect("Filter",  ["Ohne WV","Ohne Wert","WV überfällig",f"Alter ≥ {warn_days} T."])

filt = act.copy()
if sp  != "Alle": filt = filt[filt["Phase"]     == sp]
if st_ != "Alle" and "Typ"       in filt.columns: filt = filt[filt["Typ"]       == st_]
if so  != "Alle" and "Zuständig" in filt.columns: filt = filt[filt["Zuständig"] == so]
if "Ohne WV"       in sf: filt = filt[filt["Flag_Keine_WV"]]
if "Ohne Wert"     in sf: filt = filt[filt["Flag_Kein_Wert"]]
if "WV überfällig" in sf: filt = filt[filt["Flag_WV_Ueberfaellig"]]
if f"Alter ≥ {warn_days} T." in sf and "Alter_Tage" in filt.columns:
    filt = filt[filt["Alter_Tage"] >= warn_days]

st.markdown(f'<p style="color:{C_MUTED};font-size:.75rem;">{len(filt)} von {len(act)} aktiven Leads</p>', unsafe_allow_html=True)
lead_table(filt)

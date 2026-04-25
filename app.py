import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date

st.set_page_config(page_title="LOYAGO · Sales Cockpit", page_icon="📊", layout="wide", initial_sidebar_state="collapsed")

LOST_KEYWORDS = ["kein interesse", "verloren", "abgeschlossen", "closed lost", "closed won", "gewonnen", "won", "lost"]
PHASE_ORDER = ["Termin offen", "Termin vereinbart", "Angebot raus", "Angebot angenommen", "Vertrag in Prüfung", "Abschluss"]
TYP_ORDER = ["Welcome Call", "Beratung"]

C_BG     = "#0f172a"
C_CARD   = "#1e293b"
C_BORDER = "#334155"
C_BLUE   = "#60a5fa"
C_LBLUE  = "#c8d8f8"
C_TEXT   = "#f1f5f9"
C_MUTED  = "#94a3b8"
C_GREEN  = "#22c55e"
C_YELLOW = "#f59e0b"
C_RED    = "#ef4444"

st.markdown(f"""<style>
[data-testid="stAppViewContainer"]{{background:{C_BG};}}
[data-testid="stHeader"]{{background:transparent;}}
section[data-testid="stSidebar"]{{background:{C_CARD};border-right:1px solid {C_BORDER};}}
[data-testid="metric-container"]{{background:{C_CARD};border:1px solid {C_BORDER};border-radius:10px;padding:1rem 1.25rem;}}
[data-testid="metric-container"] label{{color:{C_MUTED}!important;font-size:0.7rem!important;text-transform:uppercase;letter-spacing:.08em;}}
[data-testid="metric-container"] [data-testid="stMetricValue"]{{color:{C_TEXT}!important;font-size:1.6rem!important;font-weight:700;}}
.stTabs [data-baseweb="tab-list"]{{background:transparent;border-bottom:1px solid {C_BORDER};gap:0;}}
.stTabs [data-baseweb="tab"]{{background:transparent;color:{C_MUTED};font-size:.75rem;font-weight:600;letter-spacing:.1em;text-transform:uppercase;padding:.75rem 1.5rem;}}
.stTabs [aria-selected="true"]{{color:{C_BLUE}!important;background:transparent!important;border-bottom:2px solid {C_BLUE};}}
hr{{border-color:{C_BORDER}!important;}}
p,span,div,label{{color:{C_TEXT};}}
</style>""", unsafe_allow_html=True)

def _phase_key(p):
    try: return PHASE_ORDER.index(p)
    except: return len(PHASE_ORDER)

def _is_lost(phase):
    if pd.isna(phase): return False
    return any(kw in str(phase).lower() for kw in LOST_KEYWORDS)

def _age_bucket(days):
    if pd.isna(days): return "> 6 Wo."
    if days < 14:  return "≤ 2 Wo."
    if days < 28:  return "2–4 Wo."
    if days < 42:  return "4–6 Wo."
    return "> 6 Wo."

def _parse_number(series):
    s = series.astype(str).str.strip()
    if s.str.contains(r"\d\.\d{3},", regex=True).any():
        s = s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    return pd.to_numeric(s, errors="coerce")

def fmt_eur(val):
    return f"€ {val:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")

def chart_layout():
    return dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color=C_TEXT), margin=dict(l=0,r=0,t=40,b=0),
                xaxis=dict(gridcolor=C_BORDER, linecolor=C_BORDER),
                yaxis=dict(gridcolor=C_BORDER, linecolor=C_BORDER))

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
        st.error("CSV konnte nicht gelesen werden.")
        st.stop()
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
    df["Alter_Bucket"] = df["Alter_Tage"].apply(_age_bucket)
    df["Ist_Verloren"] = df["Phase"].apply(_is_lost)
    todo = df.get("earliest_todo_due_at", pd.Series(pd.NaT, index=df.index))
    df["Flag_Keine_WV"]        = (~df["Ist_Verloren"]) & todo.isna()
    df["Flag_Kein_Wert"]       = (~df["Ist_Verloren"]) & (df.get("Potenzieller Wert", 0) == 0)
    df["Flag_WV_Ueberfaellig"] = (~df["Ist_Verloren"]) & todo.notna() & (todo < today)
    df["Flag_WV_Heute"]        = (~df["Ist_Verloren"]) & todo.notna() & (todo.dt.date == date.today())
    return df

def lead_table(df_show, sort_col="Alter_Tage"):
    COLS = ["Vorgang #","Titel","Typ","Phase","Zuständig","Kontakte","earliest_todo_due_at","Erstellt","Alter_Tage","Potenzieller Wert"]
    cols = [c for c in COLS if c in df_show.columns]
    st.dataframe(df_show[cols].sort_values(sort_col, ascending=False) if sort_col in df_show.columns else df_show[cols],
                 use_container_width=True, hide_index=True)

# ── Sidebar
with st.sidebar:
    st.markdown(f'<div style="color:{C_MUTED};font-size:.7rem;text-transform:uppercase;letter-spacing:.1em;margin-bottom:.75rem;">CSV Import</div>', unsafe_allow_html=True)
    uploaded = st.file_uploader("Export", type=["csv"], label_visibility="collapsed")
    st.markdown("---")
    warn_days = st.slider("Kritisches Alter (Tage)", 14, 60, 28)

# ── Header
c1, c2, c3 = st.columns([2, 5, 2])
with c1:
    st.markdown(f'<div style="margin-top:8px;"><span style="background:{C_LBLUE};color:#1a1a1a;font-weight:900;font-size:1.4rem;letter-spacing:-.02em;padding:6px 14px;border-radius:6px;font-family:Arial Black,sans-serif;">LOYAGO</span></div>', unsafe_allow_html=True)
with c2:
    st.markdown(f'<div style="padding-top:12px;color:{C_MUTED};font-size:.7rem;text-transform:uppercase;letter-spacing:.15em;">Sales Cockpit</div>', unsafe_allow_html=True)
with c3:
    st.markdown(f'<div style="text-align:right;padding-top:10px;color:{C_BLUE};font-size:.85rem;">{date.today().strftime("%d. %B %Y")}</div>', unsafe_allow_html=True)

st.markdown(f'<hr style="border:none;border-top:1px solid {C_BORDER};margin:.75rem 0 1.5rem;">', unsafe_allow_html=True)

if not uploaded:
    st.markdown(f'<div style="text-align:center;padding:5rem 2rem;color:{C_MUTED};font-size:.9rem;">📂 &nbsp; CSV-Export in der Seitenleiste hochladen</div>', unsafe_allow_html=True)
    st.stop()

df  = load_csv(uploaded.read())
act = df[~df["Ist_Verloren"]].copy()
if act.empty:
    st.warning("Keine aktiven Leads gefunden.")
    st.stop()

# ── KPIs
pipeline_val = act["Potenzieller Wert"].sum() if "Potenzieller Wert" in act.columns else 0
n_overdue = int(act["Flag_WV_Ueberfaellig"].sum())
n_no_wv   = int(act["Flag_Keine_WV"].sum())
n_no_val  = int(act["Flag_Kein_Wert"].sum())
n_today   = int(act["Flag_WV_Heute"].sum())

k1,k2,k3,k4,k5 = st.columns(5)
k1.metric("Aktive Leads",       len(act))
k2.metric("Pipeline-Wert",      fmt_eur(pipeline_val))
k3.metric("Heute fällig",       n_today)
k4.metric("Überfällige WV",     n_overdue)
k5.metric("Ohne Wiedervorlage", n_no_wv)

st.markdown("<div style='height:.75rem'></div>", unsafe_allow_html=True)

alerts = []
if n_overdue: alerts.append(f"<b>{n_overdue} überfällige WV</b>")
if n_no_wv:   alerts.append(f"<b>{n_no_wv} ohne Wiedervorlage</b>")
if n_no_val:  alerts.append(f"<b>{n_no_val} ohne Wert</b>")
if alerts:
    st.markdown(f'<div style="background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.3);border-radius:8px;padding:.75rem 1.25rem;color:#fca5a5;font-size:.85rem;">⚠️ &nbsp; {" &nbsp;·&nbsp; ".join(alerts)}</div>', unsafe_allow_html=True)
else:
    st.markdown(f'<div style="background:rgba(34,197,94,.1);border:1px solid rgba(34,197,94,.3);border-radius:8px;padding:.75rem 1.25rem;color:#86efac;font-size:.85rem;">✓ &nbsp; Pipeline vollständig</div>', unsafe_allow_html=True)

st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

# ── Phase Cards
st.markdown(f'<div style="color:{C_MUTED};font-size:.7rem;text-transform:uppercase;letter-spacing:.12em;margin-bottom:.75rem;">Pipeline nach Phase</div>', unsafe_allow_html=True)

phases_in_data = [p for p in PHASE_ORDER if p in act["Phase"].values] if "Phase" in act.columns else []
phases_in_data += [p for p in act["Phase"].dropna().unique() if p not in PHASE_ORDER] if "Phase" in act.columns else []

if phases_in_data:
    pcols = st.columns(len(phases_in_data))
    for i, phase in enumerate(phases_in_data):
        ph = act[act["Phase"] == phase]
        n    = len(ph)
        val  = ph["Potenzieller Wert"].sum() if "Potenzieller Wert" in ph.columns else 0
        n_ov = int(ph["Flag_WV_Ueberfaellig"].sum())
        n_wv = int(ph["Flag_Keine_WV"].sum())
        n_vl = int(ph["Flag_Kein_Wert"].sum())
        n_old= int((ph["Alter_Tage"] >= warn_days).sum()) if "Alter_Tage" in ph.columns else 0
        top  = C_RED if n_ov else (C_YELLOW if (n_wv or n_vl) else C_GREEN)
        pills = ""
        if n_ov:  pills += f'<span style="background:rgba(239,68,68,.15);color:#fca5a5;border:1px solid rgba(239,68,68,.3);font-size:.6rem;padding:2px 7px;border-radius:100px;font-weight:700;white-space:nowrap;">⏰ {n_ov} überfällig</span> '
        if n_wv:  pills += f'<span style="background:rgba(245,158,11,.15);color:#fcd34d;border:1px solid rgba(245,158,11,.3);font-size:.6rem;padding:2px 7px;border-radius:100px;font-weight:700;white-space:nowrap;">○ {n_wv} ohne WV</span> '
        if n_vl:  pills += f'<span style="background:rgba(245,158,11,.15);color:#fcd34d;border:1px solid rgba(245,158,11,.3);font-size:.6rem;padding:2px 7px;border-radius:100px;font-weight:700;white-space:nowrap;">€ {n_vl} kein Wert</span> '
        if n_old: pills += f'<span style="background:rgba(249,115,22,.15);color:#fdba74;border:1px solid rgba(249,115,22,.3);font-size:.6rem;padding:2px 7px;border-radius:100px;font-weight:700;white-space:nowrap;">🕐 {n_old} alt</span> '
        if not pills: pills = f'<span style="background:rgba(34,197,94,.15);color:#86efac;border:1px solid rgba(34,197,94,.3);font-size:.6rem;padding:2px 7px;border-radius:100px;font-weight:700;">✓ OK</span>'
        with pcols[i]:
            st.markdown(f"""<div style="background:{C_CARD};border:1px solid {C_BORDER};border-radius:10px;padding:1.2rem;border-top:3px solid {top};margin-bottom:.5rem;">
<div style="color:{C_MUTED};font-size:.6rem;text-transform:uppercase;letter-spacing:.1em;margin-bottom:.75rem;">{phase}</div>
<div style="color:{C_TEXT};font-size:2rem;font-weight:700;line-height:1;">{n}</div>
<div style="color:{C_MUTED};font-size:.65rem;margin-bottom:.4rem;">Leads</div>
<div style="color:{C_BLUE};font-size:.9rem;font-weight:600;margin-bottom:.75rem;">{fmt_eur(val)}</div>
<div style="display:flex;flex-wrap:wrap;gap:4px;">{pills}</div>
</div>""", unsafe_allow_html=True)

st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)

# ── Tabs
tab_focus, tab_funnel, tab_table = st.tabs(["TAGES-FOKUS", "FUNNEL & ANALYSE", "LEAD-ÜBERSICHT"])

with tab_focus:
    col_a, col_b = st.columns(2)
    with col_a:
        ov = act[act["Flag_WV_Ueberfaellig"]].sort_values("earliest_todo_due_at") if "earliest_todo_due_at" in act.columns else act[act["Flag_WV_Ueberfaellig"]]
        st.markdown(f'<div style="color:{C_RED};font-size:.75rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;margin-bottom:.75rem;">⏰ Überfällige Wiedervorlagen ({len(ov)})</div>', unsafe_allow_html=True)
        if not ov.empty: lead_table(ov, "earliest_todo_due_at")
        else: st.markdown(f'<div style="color:{C_GREEN};padding:1rem 0;font-size:.85rem;">✓ Keine überfälligen WV</div>', unsafe_allow_html=True)
    with col_b:
        td = act[act["Flag_WV_Heute"]].sort_values("Potenzieller Wert", ascending=False) if "Potenzieller Wert" in act.columns else act[act["Flag_WV_Heute"]]
        st.markdown(f'<div style="color:{C_YELLOW};font-size:.75rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;margin-bottom:.75rem;">📅 Heute fällig ({len(td)})</div>', unsafe_allow_html=True)
        if not td.empty: lead_table(td, "Potenzieller Wert")
        else: st.markdown(f'<div style="color:{C_MUTED};padding:1rem 0;font-size:.85rem;">Keine WV für heute</div>', unsafe_allow_html=True)

    st.markdown("---")
    col_c, col_d = st.columns(2)
    with col_c:
        no_wv = act[act["Flag_Keine_WV"]].sort_values("Alter_Tage", ascending=False) if "Alter_Tage" in act.columns else act[act["Flag_Keine_WV"]]
        st.markdown(f'<div style="color:{C_YELLOW};font-size:.75rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;margin-bottom:.75rem;">○ Ohne Wiedervorlage ({len(no_wv)})</div>', unsafe_allow_html=True)
        if not no_wv.empty: lead_table(no_wv)
        else: st.markdown(f'<div style="color:{C_GREEN};padding:1rem 0;font-size:.85rem;">✓ Alle Leads haben WV</div>', unsafe_allow_html=True)
    with col_d:
        no_val = act[act["Flag_Kein_Wert"]].sort_values("Alter_Tage", ascending=False) if "Alter_Tage" in act.columns else act[act["Flag_Kein_Wert"]]
        st.markdown(f'<div style="color:{C_YELLOW};font-size:.75rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;margin-bottom:.75rem;">€ Ohne Wert ({len(no_val)})</div>', unsafe_allow_html=True)
        if not no_val.empty: lead_table(no_val)
        else: st.markdown(f'<div style="color:{C_GREEN};padding:1rem 0;font-size:.85rem;">✓ Alle Leads haben Wert</div>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown(f'<div style="color:{C_MUTED};font-size:.7rem;text-transform:uppercase;letter-spacing:.12em;margin-bottom:.75rem;">🏆 Top-Chancen</div>', unsafe_allow_html=True)
    top = act[act["Potenzieller Wert"] > 0].sort_values("Potenzieller Wert", ascending=False).head(10) if "Potenzieller Wert" in act.columns else pd.DataFrame()
    if not top.empty: lead_table(top, "Potenzieller Wert")

with tab_funnel:
    count_col = "Vorgang #" if "Vorgang #" in act.columns else act.columns[0]
    phase_stats = act.groupby("Phase").agg(Leads=(count_col,"count"), Wert=("Potenzieller Wert","sum")).reset_index() if "Phase" in act.columns else pd.DataFrame(columns=["Phase","Leads","Wert"])
    phase_stats["_ord"] = phase_stats["Phase"].apply(_phase_key)
    phase_stats = phase_stats.sort_values("_ord").drop("_ord", axis=1)
    if len(phase_stats): phase_stats["Ø Wert"] = (phase_stats["Wert"] / phase_stats["Leads"]).round(0)

    col_f1, col_f2 = st.columns(2)
    with col_f1:
        fig = go.Figure(go.Funnel(
            y=phase_stats["Phase"], x=phase_stats["Leads"],
            textinfo="value+percent initial", textfont=dict(color=C_TEXT),
            marker=dict(color=[C_BLUE]*len(phase_stats), line=dict(color=C_BORDER, width=1)),
        ))
        fig.update_layout(title=dict(text="Leads-Funnel", font=dict(size=13, color=C_MUTED)), height=420, **chart_layout())
        st.plotly_chart(fig, use_container_width=True)
    with col_f2:
        fig2 = px.bar(phase_stats, x="Phase", y="Wert", text="Wert", color_discrete_sequence=[C_BLUE], height=420)
        fig2.update_traces(texttemplate="%{text:,.0f} €", textposition="outside", textfont=dict(color=C_MUTED,size=11), marker_line_color=C_BORDER)
        fig2.update_layout(title=dict(text="Pipeline-Wert je Phase", font=dict(size=13,color=C_MUTED)), **chart_layout())
        st.plotly_chart(fig2, use_container_width=True)

    disp = phase_stats.copy()
    if "Wert" in disp.columns:   disp["Wert"]   = disp["Wert"].map(fmt_eur)
    if "Ø Wert" in disp.columns: disp["Ø Wert"] = disp["Ø Wert"].map(fmt_eur)
    st.dataframe(disp, use_container_width=True, hide_index=True)

    if "Typ" in act.columns:
        st.markdown("---")
        tp = act.groupby(["Typ","Phase"]).agg(Leads=(count_col,"count"), Wert=("Potenzieller Wert","sum")).reset_index()
        tp["_o"] = tp["Phase"].apply(_phase_key)
        tp = tp.sort_values("_o").drop("_o", axis=1)
        fig3 = px.bar(tp, x="Phase", y="Leads", color="Typ", barmode="group",
                      color_discrete_sequence=[C_BLUE,"#9cb8f7"], height=320)
        fig3.update_layout(title=dict(text="Leads nach Typ & Phase", font=dict(size=13,color=C_MUTED)), **chart_layout())
        st.plotly_chart(fig3, use_container_width=True)

    if "Zuständig" in act.columns:
        op = act.groupby(["Zuständig","Phase"]).agg(Leads=(count_col,"count"), Wert=("Potenzieller Wert","sum")).reset_index()
        oc1, oc2 = st.columns(2)
        with oc1:
            fig4 = px.bar(op, x="Zuständig", y="Leads", color="Phase", barmode="stack",
                          color_discrete_sequence=px.colors.sequential.Blues_r, height=320)
            fig4.update_layout(title=dict(text="Leads pro Mitarbeiter", font=dict(size=13,color=C_MUTED)), **chart_layout())
            st.plotly_chart(fig4, use_container_width=True)
        with oc2:
            fig5 = px.bar(op, x="Zuständig", y="Wert", color="Phase", barmode="stack",
                          color_discrete_sequence=px.colors.sequential.Blues_r, height=320)
            fig5.update_layout(title=dict(text="Wert pro Mitarbeiter", font=dict(size=13,color=C_MUTED)), **chart_layout())
            st.plotly_chart(fig5, use_container_width=True)

with tab_table:
    f1,f2,f3,f4 = st.columns(4)
    sel_phase = f1.selectbox("Phase", ["Alle"]+sorted(act["Phase"].dropna().unique().tolist())) if "Phase" in act.columns else f1.selectbox("Phase",["Alle"])
    sel_typ   = f2.selectbox("Typ",   ["Alle"]+sorted(act["Typ"].dropna().unique().tolist()))   if "Typ"   in act.columns else f2.selectbox("Typ",  ["Alle"])
    sel_own   = f3.selectbox("Zuständig", ["Alle"]+sorted(act["Zuständig"].dropna().unique().tolist())) if "Zuständig" in act.columns else f3.selectbox("Zuständig",["Alle"])
    sel_flags = f4.multiselect("Filter", ["Ohne WV","Ohne Wert","WV überfällig",f"Alter ≥ {warn_days} T."])

    filt = act.copy()
    if sel_phase != "Alle": filt = filt[filt["Phase"] == sel_phase]
    if sel_typ   != "Alle" and "Typ"       in filt.columns: filt = filt[filt["Typ"]       == sel_typ]
    if sel_own   != "Alle" and "Zuständig" in filt.columns: filt = filt[filt["Zuständig"] == sel_own]
    if "Ohne WV"       in sel_flags: filt = filt[filt["Flag_Keine_WV"]]
    if "Ohne Wert"     in sel_flags: filt = filt[filt["Flag_Kein_Wert"]]
    if "WV überfällig" in sel_flags: filt = filt[filt["Flag_WV_Ueberfaellig"]]
    if f"Alter ≥ {warn_days} T." in sel_flags: filt = filt[filt["Alter_Tage"] >= warn_days]

    st.markdown(f'<div style="color:{C_MUTED};font-size:.75rem;margin-bottom:.5rem;">{len(filt)} von {len(act)} aktiven Leads</div>', unsafe_allow_html=True)
    lead_table(filt)

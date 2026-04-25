import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta

st.set_page_config(page_title="LOYAGO · Sales Cockpit", page_icon="📊", layout="wide", initial_sidebar_state="collapsed")

LOST_KEYWORDS = ["kein interesse", "verloren", "abgeschlossen", "closed lost", "closed won", "gewonnen", "won", "lost"]
PHASE_ORDER = ["Termin offen", "Termin vereinbart", "Angebot raus", "Angebot angenommen", "Vertrag in Prüfung", "Abschluss"]
TYP_ORDER = ["Welcome Call", "Beratung"]

C_BG    = "#0f172a"
C_CARD  = "#1e293b"
C_CARD2 = "#263548"
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
.stTabs [data-baseweb="tab-list"]{{background:transparent;border-bottom:1px solid {C_BDR};gap:0;}}
.stTabs [data-baseweb="tab"]{{background:transparent;color:{C_MUTED};font-size:.75rem;font-weight:600;letter-spacing:.1em;text-transform:uppercase;padding:.75rem 1.5rem;}}
.stTabs [aria-selected="true"]{{color:{C_BLUE}!important;background:transparent!important;border-bottom:2px solid {C_BLUE};}}
hr{{border-color:{C_BDR}!important;}}
p,span,div,label{{color:{C_TEXT};}}
.stDataFrame{{border-radius:10px;overflow:hidden;}}
</style>""", unsafe_allow_html=True)

# ── helpers ──────────────────────────────────────────────────────────────────

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

def card(label, value, color=None):
    col = color or C_BLUE
    return f"""<div style="background:{C_CARD};border:1px solid {C_BDR};border-radius:12px;padding:1.25rem 1.5rem;">
<div style="color:{C_MUTED};font-size:.65rem;text-transform:uppercase;letter-spacing:.1em;margin-bottom:.5rem;">{label}</div>
<div style="color:{col};font-size:1.9rem;font-weight:700;line-height:1;">{value}</div></div>"""

def section(title):
    st.markdown(f'<div style="color:{C_MUTED};font-size:.7rem;text-transform:uppercase;letter-spacing:.12em;margin:1.25rem 0 .75rem;">{title}</div>', unsafe_allow_html=True)

def cline():
    st.markdown(f'<hr style="border:none;border-top:1px solid {C_BDR};margin:1.5rem 0;">', unsafe_allow_html=True)

def plot_cfg():
    return dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color=C_TEXT, size=12), margin=dict(l=10,r=10,t=45,b=10),
                xaxis=dict(gridcolor=C_BDR, linecolor=C_BDR, tickfont=dict(color=C_MUTED)),
                yaxis=dict(gridcolor=C_BDR, linecolor=C_BDR, tickfont=dict(color=C_MUTED)),
                legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=C_MUTED)))

def lead_table(df_in, sort_col="Alter_Tage"):
    COLS = ["Vorgang #","Titel","Typ","Phase","Zuständig","Kontakte","earliest_todo_due_at","Erstellt","Alter_Tage","Potenzieller Wert"]
    cols = [c for c in COLS if c in df_in.columns]
    st.dataframe(df_in[cols].sort_values(sort_col, ascending=False) if sort_col in df_in.columns else df_in[cols],
                 use_container_width=True, hide_index=True)

# ── data loading ──────────────────────────────────────────────────────────────

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
    df["Ist_Verloren"] = df["Phase"].apply(_is_lost)
    todo = df.get("earliest_todo_due_at", pd.Series(pd.NaT, index=df.index))
    df["Flag_Keine_WV"]        = (~df["Ist_Verloren"]) & todo.isna()
    df["Flag_Kein_Wert"]       = (~df["Ist_Verloren"]) & (df.get("Potenzieller Wert", 0) == 0)
    df["Flag_WV_Ueberfaellig"] = (~df["Ist_Verloren"]) & todo.notna() & (todo < today)
    df["Flag_WV_Heute"]        = (~df["Ist_Verloren"]) & todo.notna() & (todo.dt.date == date.today())
    # WV buckets per lead
    in3 = today + pd.Timedelta(days=3)
    in5 = today + pd.Timedelta(days=5)
    df["WV_Bucket"] = "Später"
    df.loc[todo.isna() & ~df["Ist_Verloren"], "WV_Bucket"] = "Keine WV"
    df.loc[todo.notna() & (todo < today), "WV_Bucket"] = "Überfällig"
    df.loc[todo.notna() & (todo >= today) & (todo <= in3), "WV_Bucket"] = "≤ 3 Tage"
    df.loc[todo.notna() & (todo > in3) & (todo <= in5), "WV_Bucket"] = "≤ 5 Tage"
    return df

# ── sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown(f'<div style="color:{C_MUTED};font-size:.7rem;text-transform:uppercase;letter-spacing:.1em;margin-bottom:.75rem;">CSV Import</div>', unsafe_allow_html=True)
    uploaded = st.file_uploader("Export", type=["csv"], label_visibility="collapsed")
    st.markdown("---")
    warn_days = st.slider("Kritisches Alter (Tage)", 14, 60, 28)

# ── header ────────────────────────────────────────────────────────────────────

hc1, hc2, hc3 = st.columns([2,5,2])
with hc1:
    st.markdown(f'<div style="margin-top:8px;"><span style="background:{C_LBLUE};color:#1a1a1a;font-weight:900;font-size:1.5rem;letter-spacing:-.02em;padding:7px 16px;border-radius:8px;font-family:Arial Black,sans-serif;">LOYAGO</span></div>', unsafe_allow_html=True)
with hc2:
    st.markdown(f'<div style="padding-top:13px;color:{C_MUTED};font-size:.7rem;text-transform:uppercase;letter-spacing:.18em;">Sales Cockpit</div>', unsafe_allow_html=True)
with hc3:
    st.markdown(f'<div style="text-align:right;padding-top:11px;color:{C_BLUE};font-size:.85rem;font-weight:500;">{date.today().strftime("%d. %B %Y")}</div>', unsafe_allow_html=True)

st.markdown(f'<hr style="border:none;border-top:1px solid {C_BDR};margin:.75rem 0 1.5rem;">', unsafe_allow_html=True)

if not uploaded:
    st.markdown(f'<div style="text-align:center;padding:6rem 2rem;"><div style="font-size:3rem;margin-bottom:1rem;">📂</div><div style="color:{C_MUTED};font-size:.95rem;">CSV-Export in der Seitenleiste hochladen</div></div>', unsafe_allow_html=True)
    st.stop()

df  = load_csv(uploaded.read())
act = df[~df["Ist_Verloren"]].copy()
if act.empty:
    st.warning("Keine aktiven Leads — bitte CSV prüfen.")
    st.stop()

# ── KPIs ──────────────────────────────────────────────────────────────────────

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
    st.markdown(f'<div style="background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.3);border-radius:8px;padding:.8rem 1.25rem;color:#fca5a5;font-size:.875rem;">⚠️ &nbsp; Handlungsbedarf: {" &nbsp;·&nbsp; ".join(alerts)}</div>', unsafe_allow_html=True)
else:
    st.markdown(f'<div style="background:rgba(34,197,94,.1);border:1px solid rgba(34,197,94,.3);border-radius:8px;padding:.8rem 1.25rem;color:#86efac;font-size:.875rem;">✓ &nbsp; Pipeline vollständig – alle Leads mit WV und Wert</div>', unsafe_allow_html=True)

st.markdown("<div style='height:1.25rem'></div>", unsafe_allow_html=True)

# ── Phase Cards ───────────────────────────────────────────────────────────────

section("Pipeline nach Phase")

phases_in_data = [p for p in PHASE_ORDER if "Phase" in act.columns and p in act["Phase"].values]
if "Phase" in act.columns:
    phases_in_data += [p for p in act["Phase"].dropna().unique() if p not in PHASE_ORDER]

WV_ORDER  = ["Überfällig", "Keine WV", "≤ 3 Tage", "≤ 5 Tage", "Später"]
WV_COLORS = {"Überfällig": C_RED, "Keine WV": C_ORA, "≤ 3 Tage": C_YEL, "≤ 5 Tage": C_BLUE, "Später": C_GREEN}
WV_ICONS  = {"Überfällig": "⏰", "Keine WV": "⚠️", "≤ 3 Tage": "🟡", "≤ 5 Tage": "🔵", "Später": "✓"}

if phases_in_data:
    pcols = st.columns(len(phases_in_data))
    for i, phase in enumerate(phases_in_data):
        ph   = act[act["Phase"] == phase]
        n    = len(ph)
        val  = ph["Potenzieller Wert"].sum() if "Potenzieller Wert" in ph.columns else 0
        n_ov = int(ph["Flag_WV_Ueberfaellig"].sum())
        n_wv = int(ph["Flag_Keine_WV"].sum())
        n_vl = int(ph["Flag_Kein_Wert"].sum())
        top  = C_RED if n_ov else (C_YEL if (n_wv or n_vl) else C_GREEN)

        # WV breakdown pills
        wv_pills = ""
        for bucket in WV_ORDER:
            cnt = int((ph["WV_Bucket"] == bucket).sum())
            if cnt == 0: continue
            bc  = WV_COLORS[bucket]
            ico = WV_ICONS[bucket]
            r,g,b = int(bc[1:3],16), int(bc[3:5],16), int(bc[5:7],16)
            wv_pills += f'<span style="background:rgba({r},{g},{b},.15);color:{bc};border:1px solid rgba({r},{g},{b},.35);font-size:.6rem;padding:2px 8px;border-radius:100px;font-weight:700;white-space:nowrap;">{ico} {cnt} {bucket}</span> '

        with pcols[i]:
            st.markdown(f"""<div style="background:{C_CARD};border:1px solid {C_BDR};border-radius:12px;padding:1.25rem;border-top:3px solid {top};height:100%;">
<div style="color:{C_MUTED};font-size:.6rem;text-transform:uppercase;letter-spacing:.1em;margin-bottom:.75rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;" title="{phase}">{phase}</div>
<div style="color:{C_TEXT};font-size:2.2rem;font-weight:700;line-height:1;">{n}</div>
<div style="color:{C_MUTED};font-size:.65rem;margin-bottom:.5rem;">Leads</div>
<div style="color:{C_BLUE};font-size:.95rem;font-weight:600;margin-bottom:.9rem;">{fmt_eur(val)}</div>
<div style="display:flex;flex-wrap:wrap;gap:4px;line-height:1.8;">{wv_pills}</div>
</div>""", unsafe_allow_html=True)

cline()

# ── Tabs ──────────────────────────────────────────────────────────────────────

tab_focus, tab_funnel, tab_wv, tab_table = st.tabs(["TAGES-FOKUS", "FUNNEL & ANALYSE", "WIEDERVORLAGEN", "ALLE LEADS"])

# ─ Tab 1: Tages-Fokus ────────────────────────────────────────────────────────
with tab_focus:
    c_a, c_b = st.columns(2)
    with c_a:
        ov = act[act["Flag_WV_Ueberfaellig"]]
        if "earliest_todo_due_at" in ov.columns: ov = ov.sort_values("earliest_todo_due_at")
        st.markdown(f'<div style="color:{C_RED};font-size:.8rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;margin-bottom:.75rem;">⏰ Überfällig ({len(ov)})</div>', unsafe_allow_html=True)
        if not ov.empty: lead_table(ov, "earliest_todo_due_at")
        else: st.markdown(f'<div style="color:{C_GREEN};padding:1.5rem 0;font-size:.9rem;">✓ Keine überfälligen WV</div>', unsafe_allow_html=True)
    with c_b:
        td = act[act["Flag_WV_Heute"]]
        if "Potenzieller Wert" in td.columns: td = td.sort_values("Potenzieller Wert", ascending=False)
        st.markdown(f'<div style="color:{C_YEL};font-size:.8rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;margin-bottom:.75rem;">📅 Heute fällig ({len(td)})</div>', unsafe_allow_html=True)
        if not td.empty: lead_table(td, "Potenzieller Wert")
        else: st.markdown(f'<div style="color:{C_MUTED};padding:1.5rem 0;font-size:.9rem;">Keine WV für heute</div>', unsafe_allow_html=True)

    cline()
    c_c, c_d = st.columns(2)
    with c_c:
        no_wv = act[act["Flag_Keine_WV"]]
        if "Alter_Tage" in no_wv.columns: no_wv = no_wv.sort_values("Alter_Tage", ascending=False)
        st.markdown(f'<div style="color:{C_ORA};font-size:.8rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;margin-bottom:.75rem;">○ Ohne WV ({len(no_wv)})</div>', unsafe_allow_html=True)
        if not no_wv.empty: lead_table(no_wv)
        else: st.markdown(f'<div style="color:{C_GREEN};padding:1.5rem 0;font-size:.9rem;">✓ Alle Leads haben WV</div>', unsafe_allow_html=True)
    with c_d:
        no_val = act[act["Flag_Kein_Wert"]]
        if "Alter_Tage" in no_val.columns: no_val = no_val.sort_values("Alter_Tage", ascending=False)
        st.markdown(f'<div style="color:{C_ORA};font-size:.8rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;margin-bottom:.75rem;">€ Ohne Wert ({len(no_val)})</div>', unsafe_allow_html=True)
        if not no_val.empty: lead_table(no_val)
        else: st.markdown(f'<div style="color:{C_GREEN};padding:1.5rem 0;font-size:.9rem;">✓ Alle Leads haben Wert</div>', unsafe_allow_html=True)

    cline()
    section("🏆 Top-Chancen")
    if "Potenzieller Wert" in act.columns:
        top = act[act["Potenzieller Wert"] > 0].sort_values("Potenzieller Wert", ascending=False).head(10)
        if not top.empty: lead_table(top, "Potenzieller Wert")

# ─ Tab 2: Funnel & Analyse ───────────────────────────────────────────────────
with tab_funnel:
    count_col = "Vorgang #" if "Vorgang #" in act.columns else act.columns[0]
    if "Phase" in act.columns:
        ps = act.groupby("Phase").agg(Leads=(count_col,"count"), Wert=("Potenzieller Wert","sum")).reset_index()
        ps["_o"] = ps["Phase"].apply(_phase_key)
        ps = ps.sort_values("_o").drop("_o",axis=1)
        if len(ps): ps["Ø Wert"] = (ps["Wert"]/ps["Leads"]).round(0)
    else:
        ps = pd.DataFrame(columns=["Phase","Leads","Wert"])

    c_f1, c_f2 = st.columns(2)
    with c_f1:
        n_phases = len(ps)
        blues = [f"hsl(210,{70-i*6}%,{55+i*4}%)" for i in range(n_phases)]
        fig_f = go.Figure(go.Funnel(
            y=ps["Phase"], x=ps["Leads"],
            textinfo="value+percent initial",
            textfont=dict(color=C_TEXT, size=13),
            marker=dict(color=blues, line=dict(color=C_CARD, width=2)),
        ))
        fig_f.update_layout(title=dict(text="Leads-Funnel", font=dict(size=14,color=C_MUTED)), height=500, **plot_cfg())
        st.plotly_chart(fig_f, use_container_width=True)

    with c_f2:
        fig_v = px.bar(ps, x="Phase", y="Wert", text="Wert",
                       color="Leads", color_continuous_scale=["#1e3a5f","#60a5fa"], height=500)
        fig_v.update_traces(texttemplate="%{text:,.0f} €", textposition="outside",
                            textfont=dict(color=C_MUTED,size=11), marker_line_color=C_BDR, marker_line_width=1)
        fig_v.update_layout(title=dict(text="Pipeline-Wert je Phase", font=dict(size=14,color=C_MUTED)),
                            coloraxis_showscale=False, **plot_cfg())
        st.plotly_chart(fig_v, use_container_width=True)

    if len(ps):
        disp = ps.copy()
        if "Wert"   in disp.columns: disp["Wert"]   = disp["Wert"].map(fmt_eur)
        if "Ø Wert" in disp.columns: disp["Ø Wert"] = disp["Ø Wert"].map(fmt_eur)
        st.dataframe(disp, use_container_width=True, hide_index=True)

    if "Zuständig" in act.columns:
        cline()
        op = act.groupby(["Zuständig","Phase"]).agg(Leads=(count_col,"count"), Wert=("Potenzieller Wert","sum")).reset_index()
        oc1,oc2 = st.columns(2)
        with oc1:
            f4 = px.bar(op,x="Zuständig",y="Leads",color="Phase",barmode="stack",
                        color_discrete_sequence=px.colors.sequential.Blues_r,height=380)
            f4.update_layout(title=dict(text="Leads pro Mitarbeiter",font=dict(size=14,color=C_MUTED)),**plot_cfg())
            st.plotly_chart(f4,use_container_width=True)
        with oc2:
            f5 = px.bar(op,x="Zuständig",y="Wert",color="Phase",barmode="stack",
                        color_discrete_sequence=px.colors.sequential.Blues_r,height=380)
            f5.update_layout(title=dict(text="Wert pro Mitarbeiter",font=dict(size=14,color=C_MUTED)),**plot_cfg())
            st.plotly_chart(f5,use_container_width=True)

# ─ Tab 3: Wiedervorlagen ─────────────────────────────────────────────────────
with tab_wv:
    section("Wiedervorlagen-Status je Phase")

    if "Phase" in act.columns and "WV_Bucket" in act.columns:
        wv_data = act.groupby(["Phase","WV_Bucket"]).size().reset_index(name="Anzahl")
        wv_data["_o"] = wv_data["Phase"].apply(_phase_key)
        wv_data = wv_data.sort_values("_o").drop("_o",axis=1)

        fig_wv = px.bar(wv_data, x="Phase", y="Anzahl", color="WV_Bucket",
                        barmode="stack", height=480,
                        color_discrete_map=WV_COLORS,
                        category_orders={"WV_Bucket": WV_ORDER})
        fig_wv.update_layout(
            title=dict(text="WV-Status je Phase", font=dict(size=14,color=C_MUTED)),
            **plot_cfg(),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                        bgcolor="rgba(0,0,0,0)", font=dict(color=C_MUTED)),
        )
        st.plotly_chart(fig_wv, use_container_width=True)

        cline()

        # Pivot table: Phase × WV_Bucket
        section("Übersicht nach Phase")
        pivot_wv = act.groupby(["Phase","WV_Bucket"]).size().unstack(fill_value=0)
        for b in WV_ORDER:
            if b not in pivot_wv.columns: pivot_wv[b] = 0
        pivot_wv = pivot_wv[WV_ORDER]
        pivot_wv["Gesamt"] = pivot_wv.sum(axis=1)
        pivot_wv = pivot_wv.reset_index()
        pivot_wv["_o"] = pivot_wv["Phase"].apply(_phase_key)
        pivot_wv = pivot_wv.sort_values("_o").drop("_o",axis=1)
        st.dataframe(pivot_wv, use_container_width=True, hide_index=True)

    cline()
    section("Leads ohne Wiedervorlage — Details")
    no_wv_tab = act[act["Flag_Keine_WV"]].copy()
    if "Alter_Tage" in no_wv_tab.columns: no_wv_tab = no_wv_tab.sort_values("Alter_Tage", ascending=False)
    if not no_wv_tab.empty: lead_table(no_wv_tab)
    else: st.markdown(f'<div style="color:{C_GREEN};padding:1.5rem 0;">✓ Alle Leads haben eine Wiedervorlage</div>', unsafe_allow_html=True)

# ─ Tab 4: Alle Leads ─────────────────────────────────────────────────────────
with tab_table:
    f1,f2,f3,f4 = st.columns(4)
    phases_opts = ["Alle"] + sorted(act["Phase"].dropna().unique().tolist()) if "Phase" in act.columns else ["Alle"]
    typen_opts  = ["Alle"] + sorted(act["Typ"].dropna().unique().tolist())   if "Typ"   in act.columns else ["Alle"]
    own_opts    = ["Alle"] + sorted(act["Zuständig"].dropna().unique().tolist()) if "Zuständig" in act.columns else ["Alle"]
    sel_phase = f1.selectbox("Phase",     phases_opts)
    sel_typ   = f2.selectbox("Typ",       typen_opts)
    sel_own   = f3.selectbox("Zuständig", own_opts)
    sel_flags = f4.multiselect("Filter",  ["Ohne WV","Ohne Wert","WV überfällig",f"Alter ≥ {warn_days} T."])

    filt = act.copy()
    if sel_phase != "Alle": filt = filt[filt["Phase"] == sel_phase]
    if sel_typ   != "Alle" and "Typ"       in filt.columns: filt = filt[filt["Typ"]       == sel_typ]
    if sel_own   != "Alle" and "Zuständig" in filt.columns: filt = filt[filt["Zuständig"] == sel_own]
    if "Ohne WV"       in sel_flags: filt = filt[filt["Flag_Keine_WV"]]
    if "Ohne Wert"     in sel_flags: filt = filt[filt["Flag_Kein_Wert"]]
    if "WV überfällig" in sel_flags: filt = filt[filt["Flag_WV_Ueberfaellig"]]
    if f"Alter ≥ {warn_days} T." in sel_flags and "Alter_Tage" in filt.columns:
        filt = filt[filt["Alter_Tage"] >= warn_days]

    st.markdown(f'<div style="color:{C_MUTED};font-size:.8rem;margin-bottom:.75rem;"><b style="color:{C_TEXT}">{len(filt)}</b> von {len(act)} aktiven Leads</div>', unsafe_allow_html=True)
    lead_table(filt)

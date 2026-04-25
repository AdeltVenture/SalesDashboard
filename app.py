import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date

st.set_page_config(
    page_title="Sales Pipeline",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Config ────────────────────────────────────────────────────────────────────

LOST_KEYWORDS = [
    "kein interesse", "verloren", "abgeschlossen", "closed lost",
    "closed won", "gewonnen", "won", "lost",
]

# Preferred display order for Phase inside the funnel
PHASE_ORDER = [
    "Termin offen",
    "Termin vereinbart",
    "Angebot raus",
    "Angebot angenommen",
    "Vertrag in Prüfung",
    "Abschluss",
]

# Preferred display order for Typ (Welcome Call before Beratung)
TYP_ORDER = ["Welcome Call", "Beratung"]

AGE_BUCKETS = [
    ("≤ 2 Wo. (frisch)",    0,  14, "#4CAF50"),
    ("2–4 Wo. (normal)",   14,  28, "#FFC107"),
    ("4–6 Wo. (kritisch)", 28,  42, "#FF9800"),
    ("> 6 Wo. (überfällig)", 42, 9999, "#F44336"),
]
AGE_LABELS  = [b[0] for b in AGE_BUCKETS]
AGE_COLORS  = {b[0]: b[3] for b in AGE_BUCKETS}


# ── Data helpers ──────────────────────────────────────────────────────────────

def _phase_key(p):
    try:
        return PHASE_ORDER.index(p)
    except ValueError:
        return len(PHASE_ORDER)


def _typ_key(t):
    try:
        return TYP_ORDER.index(t)
    except ValueError:
        return len(TYP_ORDER)


def _age_bucket(days):
    if pd.isna(days):
        return "Unbekannt"
    for label, lo, hi, _ in AGE_BUCKETS:
        if lo <= days < hi:
            return label
    return AGE_BUCKETS[-1][0]


def _is_lost(phase):
    if pd.isna(phase):
        return False
    return any(kw in str(phase).lower() for kw in LOST_KEYWORDS)


def _parse_number(series):
    """Handle both German (1.234,56) and international (1234.56) formats."""
    s = series.astype(str).str.strip()
    # If comma appears after dot → international; if dot appears after comma → German
    has_german = s.str.contains(r"\d\.\d{3},", regex=True).any()
    if has_german:
        s = s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    return pd.to_numeric(s, errors="coerce")


@st.cache_data(show_spinner="Daten laden …")
def load_csv(raw_bytes: bytes) -> pd.DataFrame:
    import io
    for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:
            df = pd.read_csv(io.BytesIO(raw_bytes), encoding=enc)
            break
        except Exception:
            continue

    df.columns = df.columns.str.strip()

    # ── Date parsing
    for col in ("Erstellt", "earliest_todo_due_at", "Frist"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], dayfirst=True, errors="coerce")

    # ── Numeric
    for col in ("Potenzieller Wert", "Provision", "attr_case_potential_value"):
        if col in df.columns:
            df[col] = _parse_number(df[col]).fillna(0)
    if "Aufgaben" in df.columns:
        df["Aufgaben"] = pd.to_numeric(df["Aufgaben"], errors="coerce").fillna(0)

    today = pd.Timestamp(date.today())

    # ── Derived
    df["Alter_Tage"]    = (today - df.get("Erstellt", pd.NaT)).dt.days
    df["Alter_Bucket"]  = df["Alter_Tage"].apply(_age_bucket)
    df["Ist_Verloren"]  = df["Phase"].apply(_is_lost)

    todo_dt = df.get("earliest_todo_due_at", pd.Series(pd.NaT, index=df.index))

    df["Flag_Keine_WV"]    = (~df["Ist_Verloren"]) & todo_dt.isna()
    df["Flag_Kein_Wert"]   = (~df["Ist_Verloren"]) & (df.get("Potenzieller Wert", 0) == 0)
    df["Flag_WV_Ueberfaellig"] = (
        (~df["Ist_Verloren"]) & todo_dt.notna() & (todo_dt < today)
    )
    df["Flag_WV_Heute"] = (
        (~df["Ist_Verloren"]) & todo_dt.notna() & (todo_dt.dt.date == date.today())
    )

    return df


# ── UI helpers ────────────────────────────────────────────────────────────────

def fmt_eur(val):
    return f"€ {val:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")


def show_lead_table(df, sort_col="Alter_Tage"):
    COLS = [
        "Vorgang #", "Titel", "Typ", "Phase", "Zuständig", "Kontakte",
        "earliest_todo_due_at", "Erstellt", "Alter_Tage", "Potenzieller Wert",
    ]
    cols = [c for c in COLS if c in df.columns]
    st.dataframe(
        df[cols].sort_values(sort_col, ascending=False) if sort_col in df.columns else df[cols],
        use_container_width=True,
        hide_index=True,
    )


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("📁 CSV hochladen")
    uploaded = st.file_uploader("Täglicher Export", type=["csv"])
    st.divider()
    st.markdown("**Einstellungen**")
    warn_days = st.slider("Kritisches Alter (Tage)", 14, 60, 28,
                          help="Leads über diesem Alter werden als kritisch markiert.")

# ── Guard ─────────────────────────────────────────────────────────────────────

st.title("📊 Sales Pipeline Dashboard")
st.caption(f"Stand: {date.today().strftime('%d.%m.%Y')}")

if not uploaded:
    st.info("⬅️ Bitte lade das tägliche Export-CSV in der Seitenleiste hoch.")
    st.stop()

df  = load_csv(uploaded.read())
act = df[~df["Ist_Verloren"]].copy()

if act.empty:
    st.warning("Keine aktiven Leads gefunden – bitte CSV prüfen.")
    st.stop()

# ── KPI strip ─────────────────────────────────────────────────────────────────

pipeline_val   = act["Potenzieller Wert"].sum()
n_no_wv        = int(act["Flag_Keine_WV"].sum())
n_no_val       = int(act["Flag_Kein_Wert"].sum())
n_overdue      = int(act["Flag_WV_Ueberfaellig"].sum())
n_critical_age = int((act["Alter_Tage"] >= warn_days).sum())

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Aktive Leads",        len(act))
c2.metric("Pipeline-Wert",       fmt_eur(pipeline_val))
c3.metric("Ohne Wiedervorlage",  n_no_wv,  delta=None)
c4.metric("Ohne Wert",           n_no_val, delta=None)
c5.metric("Überfällige WV",      n_overdue,delta=None)

# Banner wenn Handlungsbedarf
alerts = []
if n_overdue:  alerts.append(f"**{n_overdue} überfällige Wiedervorlagen**")
if n_no_wv:    alerts.append(f"**{n_no_wv} Leads ohne Wiedervorlage**")
if n_no_val:   alerts.append(f"**{n_no_val} Leads ohne Wert**")
if alerts:
    st.warning("⚠️ Handlungsbedarf: " + " · ".join(alerts))
else:
    st.success("✅ Alle Leads haben Wiedervorlage und Wert – Pipeline sauber.")

st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────

tab_focus, tab_funnel, tab_age, tab_table = st.tabs([
    "🎯 Tages-Fokus",
    "📈 Funnel",
    "⏱️ Alter & Reife",
    "📋 Alle Leads",
])

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 – TAGES-FOKUS
# ─────────────────────────────────────────────────────────────────────────────
with tab_focus:

    # Überfällige & heute
    col_od, col_today = st.columns(2)

    with col_od:
        ov = act[act["Flag_WV_Ueberfaellig"]].sort_values("earliest_todo_due_at")
        st.markdown(f"#### 🔴 Überfällige Wiedervorlagen ({len(ov)})")
        if not ov.empty:
            show_lead_table(ov, sort_col="earliest_todo_due_at")
        else:
            st.success("Alle Wiedervorlagen im Zeitplan ✓")

    with col_today:
        td = act[act["Flag_WV_Heute"]].sort_values("Potenzieller Wert", ascending=False)
        st.markdown(f"#### 🟡 Heute fällig ({len(td)})")
        if not td.empty:
            show_lead_table(td, sort_col="Potenzieller Wert")
        else:
            st.info("Keine Wiedervorlagen für heute eingetragen.")

    st.divider()

    # Datenvollständigkeit
    st.subheader("⚠️ Datenvollständigkeit")
    col_wv, col_val = st.columns(2)

    with col_wv:
        no_wv = act[act["Flag_Keine_WV"]].sort_values("Alter_Tage", ascending=False)
        st.markdown(f"**Ohne Wiedervorlage ({len(no_wv)})**")
        if not no_wv.empty:
            show_lead_table(no_wv)
        else:
            st.success("Alle Leads haben eine Wiedervorlage ✓")

    with col_val:
        no_val = act[act["Flag_Kein_Wert"]].sort_values("Alter_Tage", ascending=False)
        st.markdown(f"**Ohne Wert ({len(no_val)})**")
        if not no_val.empty:
            show_lead_table(no_val)
        else:
            st.success("Alle Leads haben einen Wert eingetragen ✓")

    # Top-Chancen
    st.divider()
    st.subheader("🏆 Top-Chancen (höchster Wert, aktive WV)")
    top = (
        act[act["Potenzieller Wert"] > 0]
        .sort_values("Potenzieller Wert", ascending=False)
        .head(10)
    )
    if not top.empty:
        show_lead_table(top, sort_col="Potenzieller Wert")

# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 – FUNNEL
# ─────────────────────────────────────────────────────────────────────────────
with tab_funnel:
    st.subheader("Pipeline-Übersicht")

    phase_stats = (
        act.groupby("Phase")
        .agg(Leads=("Vorgang #", "count"), Wert=("Potenzieller Wert", "sum"))
        .reset_index()
    )
    phase_stats["_ord"] = phase_stats["Phase"].apply(_phase_key)
    phase_stats = phase_stats.sort_values("_ord").drop("_ord", axis=1)
    phase_stats["Ø Wert"] = (phase_stats["Wert"] / phase_stats["Leads"]).round(0)

    col_f1, col_f2 = st.columns(2)

    with col_f1:
        fig_funnel = go.Figure(go.Funnel(
            y=phase_stats["Phase"],
            x=phase_stats["Leads"],
            textinfo="value+percent initial",
            marker=dict(color=px.colors.sequential.Blues_r[: len(phase_stats)]),
        ))
        fig_funnel.update_layout(title="Leads pro Phase", height=420, margin=dict(l=10, r=10))
        st.plotly_chart(fig_funnel, use_container_width=True)

    with col_f2:
        fig_val = px.bar(
            phase_stats, x="Phase", y="Wert",
            title="Pipeline-Wert pro Phase (€)",
            text="Wert",
            color="Wert",
            color_continuous_scale="Blues",
            height=420,
        )
        fig_val.update_traces(
            texttemplate="%{text:,.0f} €",
            textposition="outside",
        )
        fig_val.update_layout(coloraxis_showscale=False, margin=dict(t=50))
        st.plotly_chart(fig_val, use_container_width=True)

    # Zusammenfassung-Tabelle
    disp = phase_stats.copy()
    disp["Wert"]   = disp["Wert"].map(fmt_eur)
    disp["Ø Wert"] = disp["Ø Wert"].map(fmt_eur)
    st.dataframe(disp, use_container_width=True, hide_index=True)

    # Aufschlüsselung Typ × Phase
    if "Typ" in act.columns:
        st.subheader("Funnel nach Typ")
        typ_phase = (
            act.groupby(["Typ", "Phase"])
            .agg(Leads=("Vorgang #", "count"), Wert=("Potenzieller Wert", "sum"))
            .reset_index()
        )
        typ_phase["_phase_ord"] = typ_phase["Phase"].apply(_phase_key)
        typ_phase["_typ_ord"]   = typ_phase["Typ"].apply(_typ_key)
        typ_phase = typ_phase.sort_values(["_typ_ord", "_phase_ord"])

        fig_tp = px.bar(
            typ_phase, x="Phase", y="Leads", color="Typ",
            title="Leads nach Typ und Phase", barmode="group",
            category_orders={"Typ": TYP_ORDER}, height=350,
        )
        st.plotly_chart(fig_tp, use_container_width=True)

    # Nach Zuständigem
    if "Zuständig" in act.columns:
        st.subheader("Pipeline nach Mitarbeiter")
        owner_phase = (
            act.groupby(["Zuständig", "Phase"])
            .agg(Leads=("Vorgang #", "count"), Wert=("Potenzieller Wert", "sum"))
            .reset_index()
        )
        col_o1, col_o2 = st.columns(2)
        with col_o1:
            fig_o1 = px.bar(
                owner_phase, x="Zuständig", y="Leads", color="Phase",
                title="Leads pro Mitarbeiter", barmode="stack", height=350,
            )
            st.plotly_chart(fig_o1, use_container_width=True)
        with col_o2:
            fig_o2 = px.bar(
                owner_phase, x="Zuständig", y="Wert", color="Phase",
                title="Pipeline-Wert pro Mitarbeiter (€)", barmode="stack", height=350,
            )
            st.plotly_chart(fig_o2, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 – ALTER & REIFE
# ─────────────────────────────────────────────────────────────────────────────
with tab_age:
    st.subheader("Lead-Alter & Reifegrad")

    avg_age     = act["Alter_Tage"].mean()
    max_age     = act["Alter_Tage"].max()
    pct_crit    = (act["Alter_Tage"] >= warn_days).mean() * 100

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Ø Lead-Alter",       f"{avg_age:.0f} Tage")
    m2.metric("Ältester Lead",      f"{max_age:.0f} Tage")
    m3.metric(f"Kritisch (≥ {warn_days} T.)", f"{pct_crit:.0f} %")
    m4.metric("Überfällig (> 6 Wo.)", int((act["Alter_Tage"] > 42).sum()))

    # Stacked bar: Phase × Alter
    age_phase = (
        act.groupby(["Phase", "Alter_Bucket"])
        .size()
        .reset_index(name="Anzahl")
    )
    age_phase["_p"] = age_phase["Phase"].apply(_phase_key)
    age_phase["_b"] = age_phase["Alter_Bucket"].apply(
        lambda x: AGE_LABELS.index(x) if x in AGE_LABELS else 99
    )
    age_phase = age_phase.sort_values(["_p", "_b"])

    fig_age = px.bar(
        age_phase, x="Phase", y="Anzahl", color="Alter_Bucket",
        title="Lead-Alter nach Phase",
        color_discrete_map=AGE_COLORS,
        category_orders={"Alter_Bucket": AGE_LABELS},
        barmode="stack", height=400,
    )
    st.plotly_chart(fig_age, use_container_width=True)

    # Heatmap
    st.subheader("Heatmap: Phase × Alter")
    pivot = act.pivot_table(
        values="Vorgang #", index="Phase", columns="Alter_Bucket",
        aggfunc="count", fill_value=0,
    )
    cols_ok = [c for c in AGE_LABELS if c in pivot.columns]
    if cols_ok:
        pivot = pivot[cols_ok]
        fig_heat = px.imshow(
            pivot, text_auto=True,
            color_continuous_scale=["#4CAF50", "#FFC107", "#FF9800", "#F44336"],
            title="Anzahl Leads je Phase & Alter",
            aspect="auto", height=360,
        )
        st.plotly_chart(fig_heat, use_container_width=True)

    # Liste kritischer Leads
    old = act[act["Alter_Tage"] >= warn_days].sort_values("Alter_Tage", ascending=False)
    st.markdown(f"#### 🔴 Leads älter als {warn_days} Tage ({len(old)})")
    if not old.empty:
        show_lead_table(old)
    else:
        st.success(f"Keine Leads älter als {warn_days} Tage ✓")

# ─────────────────────────────────────────────────────────────────────────────
# TAB 4 – ALLE LEADS
# ─────────────────────────────────────────────────────────────────────────────
with tab_table:
    st.subheader("Alle aktiven Leads")

    f1, f2, f3, f4 = st.columns(4)

    sel_phase = f1.selectbox(
        "Phase", ["Alle"] + sorted(act["Phase"].dropna().unique()),
    )
    sel_typ = f2.selectbox(
        "Typ",
        ["Alle"] + sorted(act["Typ"].dropna().unique()) if "Typ" in act.columns else ["Alle"],
    )
    sel_owner = f3.selectbox(
        "Zuständig",
        ["Alle"] + sorted(act["Zuständig"].dropna().unique()) if "Zuständig" in act.columns else ["Alle"],
    )
    sel_flags = f4.multiselect(
        "Nur Leads mit …",
        ["Keine Wiedervorlage", "Kein Wert", "WV überfällig", f"Alter ≥ {warn_days} T."],
    )

    filtered = act.copy()
    if sel_phase != "Alle":
        filtered = filtered[filtered["Phase"] == sel_phase]
    if sel_typ != "Alle" and "Typ" in filtered.columns:
        filtered = filtered[filtered["Typ"] == sel_typ]
    if sel_owner != "Alle" and "Zuständig" in filtered.columns:
        filtered = filtered[filtered["Zuständig"] == sel_owner]
    if "Keine Wiedervorlage"  in sel_flags: filtered = filtered[filtered["Flag_Keine_WV"]]
    if "Kein Wert"            in sel_flags: filtered = filtered[filtered["Flag_Kein_Wert"]]
    if "WV überfällig"        in sel_flags: filtered = filtered[filtered["Flag_WV_Ueberfaellig"]]
    if f"Alter ≥ {warn_days} T." in sel_flags:
        filtered = filtered[filtered["Alter_Tage"] >= warn_days]

    st.caption(f"{len(filtered)} von {len(act)} aktiven Leads")
    show_lead_table(filtered)

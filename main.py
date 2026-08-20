import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# --- PAGE SETUP ---
st.set_page_config(layout="wide", page_title="Haushaltstagebuch", page_icon="✨")

# --- HIGH-END CSS ---
st.markdown("""
    <style>
    .gradient-text {
        background: -webkit-linear-gradient(45deg, #38bdf8, #a78bfa);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 900; font-size: 3.5rem; margin-bottom: 0; padding-bottom: 0;
    }
    .subtitle { color: #94a3b8; font-size: 1.1rem; margin-top: -10px; margin-bottom: 30px; }
    [data-testid="stMetricValue"] { font-size: 3rem !important; font-weight: 800 !important; color: #38bdf8 !important; }
    .stButton>button { width: 100%; border-radius: 8px; font-weight: 600; border: 1px solid rgba(150,150,150,0.2); }
    .stButton>button:hover { border-color: #38bdf8; color: #38bdf8; }
    </style>
""", unsafe_allow_html=True)

# --- GOOGLE SHEETS VERBINDUNG ---
GSHEETS_URL = "https://docs.google.com/spreadsheets/d/1Dj3_N9ybEhIDX5HukIELYtE2E3LToq4DiuPV3EBjOiA/edit?usp=sharing"

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except:
    st.error("Verbindung zur Datenbank fehlgeschlagen.")
    st.stop()

def load_haushalt():
    try:
        df = conn.read(spreadsheet=GSHEETS_URL, worksheet="Haushalt", ttl=0).dropna(subset=['Aufgabe'])
        return df.to_dict(orient="records") if not df.empty else []
    except:
        return []

def save_haushalt(data):
    try:
        df = pd.DataFrame(data)
        if df.empty: df = pd.DataFrame(columns=["Aufgabe", "Letztes_Datum", "Intervall_Tage"])
        conn.update(spreadsheet=GSHEETS_URL, worksheet="Haushalt", data=df)
        st.cache_data.clear()
    except: pass

aufgaben = load_haushalt()
heute = datetime.now().date()

# --- HEADER ---
st.markdown('<h1 class="gradient-text">✨ Haushaltstagebuch</h1>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">Lena & Jonas — Smart Home Management</p>', unsafe_allow_html=True)

# --- NEUE AUFGABE ---
with st.expander("➕ Neue Aufgabe hinzufügen"):
    with st.form("neue_aufgabe_form", border=False, clear_on_submit=True):
        col1, col2, col3, col4 = st.columns([4, 2, 2, 2])
        with col1: aufgabe_name = st.text_input("Was?", placeholder="z.B. Kaffeemaschine entkalken")
        with col2: letztes_mal = st.date_input("Zuletzt erledigt:", heute)
        with col3: intervall = st.number_input("Intervall (Tage)", min_value=1, value=14, step=1)
        with col4:
            st.write("")
            st.write("")
            submit = st.form_submit_button("Speichern 💾")
        
        if submit and aufgabe_name:
            aufgaben.append({"Aufgabe": aufgabe_name, "Letztes_Datum": str(letztes_mal), "Intervall_Tage": int(intervall)})
            save_haushalt(aufgaben)
            st.rerun()

st.divider()

# --- AUFGABEN LOGIK (STATUS-CARDS) ---
akut, bald, entspannt = [], [], []

for i, item in enumerate(aufgaben):
    try: letztes_dt = datetime.strptime(str(item["Letztes_Datum"]), "%Y-%m-%d").date()
    except: letztes_dt = heute
    
    intervall_tage = int(float(item.get("Intervall_Tage", 14)))
    naechstes_dt = letztes_dt + timedelta(days=intervall_tage)
    tage_uebrig = (naechstes_dt - heute).days
    
    task_data = {"index": i, "Aufgabe": item["Aufgabe"], "Letztes": letztes_dt, "Intervall": intervall_tage, "Uebrig": tage_uebrig}
    if tage_uebrig <= 0: akut.append(task_data)
    elif tage_uebrig <= 3: bald.append(task_data)
    else: entspannt.append(task_data)

akut = sorted(akut, key=lambda x: x["Uebrig"])
bald = sorted(bald, key=lambda x: x["Uebrig"])
entspannt = sorted(entspannt, key=lambda x: x["Uebrig"])

# --- METRIKEN ---
m1, m2, m3 = st.columns(3)
m1.metric("🔥 Fällig / Überfällig", len(akut))
m2.metric("⏳ Demnächst (1-3 Tage)", len(bald))
m3.metric("✅ Erledigt", len(entspannt))
st.write("")

def render_task(item):
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([5, 3, 2, 1])
        with c1:
            st.markdown(f"**{item['Aufgabe']}**")
            st.caption(f"🔄 Alle {item['Intervall']} Tage • Zuletzt: {item['Letztes'].strftime('%d.%m.')}")
        with c2:
            st.write("") 
            if item["Uebrig"] < 0: st.error(f"**🔴 {abs(item['Uebrig'])} Tage überfällig**")
            elif item["Uebrig"] == 0: st.warning("**🟡 Heute fällig**")
            else: st.success(f"**🟢 In {item['Uebrig']} Tagen**")
        with c3:
            st.write("")
            if st.button("✔ Erledigt", key=f"done_{item['index']}"):
                aufgaben[item['index']]["Letztes_Datum"] = str(heute)
                save_haushalt(aufgaben)
                st.rerun()
        with c4:
            st.write("")
            if st.button("🗑", key=f"del_{item['index']}"):
                aufgaben.pop(item['index'])
                save_haushalt(aufgaben)
                st.rerun()

tab1, tab2, tab3 = st.tabs(["🔥 Akut", "⏳ Demnächst", "✅ Erledigt"])
with tab1:
    if not akut: st.success("Alles sauber! Hier steht nichts an.")
    for task in akut: render_task(task)
with tab2:
    if not bald: st.info("Keine Aufgaben für die nächsten Tage.")
    for task in bald: render_task(task)
with tab3:
    if not entspannt: st.write("Noch nichts in dieser Kategorie.")
    for task in entspannt: render_task(task)

st.divider()

# ==========================================
# CHRONOLOGISCHER WORKLOAD-RADAR
# ==========================================
st.markdown('<h3>📊 Chronologischer Auslastungs-Radar</h3>', unsafe_allow_html=True)
st.caption("Dieses Diagramm zeigt dir chronologisch, an welchem Tag wie viele Aufgaben anfallen. Fahre mit der Maus über einen Balken, um die Aufgaben zu sehen.")

def create_workload_chart(aufgaben_liste, days_ahead, title):
    end_date = heute + timedelta(days=days_ahead)
    
    instances = []
    for item in aufgaben_liste:
        try: letztes_dt = datetime.strptime(str(item["Letztes_Datum"]), "%Y-%m-%d").date()
        except: letztes_dt = heute
        
        intervall = int(float(item.get("Intervall_Tage", 14)))
        kat = "Täglich" if intervall <= 1 else "Wöchentlich" if intervall <= 7 else "Seltener"
        
        # Den ersten Termin ab HEUTE finden
        diff_days = (heute - letztes_dt).days
        if diff_days > 0:
            erste_faelligkeit = letztes_dt + timedelta(days=(diff_days // intervall) * intervall)
            if erste_faelligkeit < heute: 
                erste_faelligkeit += timedelta(days=intervall)
        else:
            erste_faelligkeit = letztes_dt - timedelta(days=(abs(diff_days) // intervall) * intervall)
            if erste_faelligkeit > heute: 
                erste_faelligkeit -= timedelta(days=intervall)
                
        # Alle Vorkommnisse in die Zukunft berechnen
        curr = erste_faelligkeit
        while curr <= end_date:
            instances.append({
                "Datum": curr,
                "Aufgabe": item["Aufgabe"],
                "Kategorie": kat
            })
            curr += timedelta(days=intervall)
            
    if not instances: return None
    
    df_inst = pd.DataFrame(instances)
    
    # Gruppieren: Zählen wie viele Aufgaben pro Datum & Kategorie anstehen
    df_grouped = df_inst.groupby(['Datum', 'Kategorie']).agg(
        Anzahl=('Aufgabe', 'count'),
        Aufgaben=('Aufgabe', lambda x: '<br>• ' + '<br>• '.join(x))
    ).reset_index()
    
    # Sortieren, damit tägliche Aufgaben immer unten im Balken sind
    df_grouped['Kat_Order'] = df_grouped['Kategorie'].map({'Täglich': 1, 'Wöchentlich': 2, 'Seltener': 3})
    df_grouped = df_grouped.sort_values(['Datum', 'Kat_Order'])
    
    color_map = {"Täglich": "#38bdf8", "Wöchentlich": "#a78bfa", "Seltener": "#fbbf24"}
    
    fig = px.bar(
        df_grouped, 
        x="Datum", 
        y="Anzahl", 
        color="Kategorie",
        color_discrete_map=color_map,
        custom_data=['Aufgaben']
    )
    
    fig.update_traces(
        hovertemplate="<b>%{x|%d.%m.%Y}</b><br>Kategorie: %{color}<br>Fällig: %{y} Aufgaben<br><br><b>Anstehend:</b>%{customdata[0]}<extra></extra>",
        marker_line_width=0
    )
    
    # X-Achsen Beschriftung je nach Länge dynamisch anpassen
    dtick = 86400000 if days_ahead <= 30 else 86400000 * 7 # Zeige jeden Tag oder jede Woche
    
    fig.update_layout(
        font_family="system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        title=dict(text=f"<b>{title}</b>", font=dict(size=18)),
        xaxis=dict(
            title=None, 
            tickformat="%d.%m.", 
            dtick=dtick, 
            showgrid=False,
            range=[heute - timedelta(days=1), end_date + timedelta(days=1)]
        ),
        yaxis=dict(title="Anzahl Aufgaben", showgrid=True, gridcolor='rgba(150,150,150,0.1)', dtick=1),
        barmode="stack", # Stapelt die Kategorien aufeinander
        height=350,
        margin=dict(t=50, b=20, l=10, r=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, title=None),
        hoverlabel=dict(bgcolor="#1e293b", font_size=14, bordercolor="rgba(255,255,255,0.1)")
    )
    return fig

# Diagramme anzeigen
with st.container(border=True):
    fig_14 = create_workload_chart(aufgaben, 14, "Kurzfristig (Nächste 14 Tage)")
    if fig_14: st.plotly_chart(fig_14, use_container_width=True)

with st.container(border=True):
    fig_30 = create_workload_chart(aufgaben, 30, "Monats-Trend (Nächste 30 Tage)")
    if fig_30: st.plotly_chart(fig_30, use_container_width=True)

with st.container(border=True):
    fig_90 = create_workload_chart(aufgaben, 90, "Quartals-Prognose (Nächste 90 Tage)")
    if fig_90: st.plotly_chart(fig_90, use_container_width=True)
import streamlit as st
import pandas as pd
import plotly.express as px
import calendar
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# --- PAGE SETUP ---
st.set_page_config(layout="wide", page_title="Haushaltstagebuch", page_icon="✨")

# Minimales CSS nur für durchgehende Buttons, KEINE Farb-Überschreibungen mehr!
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 6px; }
    </style>
""", unsafe_allow_html=True)

# --- GOOGLE SHEETS VERBINDUNG ---
GSHEETS_URL = "https://docs.google.com/spreadsheets/d/1Dj3_N9ybEhIDX5HukIELYtE2E3LToq4DiuPV3EBjOiA/edit?usp=sharing"

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except:
    st.error("Verbindung zur Datenbank fehlgeschlagen. Sind die Secrets hinterlegt?")
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
st.title("✨ Haushaltstagebuch")
st.caption("Lena & Jonas - Ein perfektes System für Sauberkeit und Routine.")

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

# --- AUFGABEN LOGIK ---
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

# --- TASK RENDER FUNKTION (ALS NATIVE CARDS) ---
def render_task(item):
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([5, 3, 2, 1])
        with c1:
            st.markdown(f"**{item['Aufgabe']}**")
            st.caption(f"🔄 Alle {item['Intervall']} Tage • Zuletzt: {item['Letztes'].strftime('%d.%m.')}")
        with c2:
            st.write("") # Spacing für vertikale Zentrierung
            if item["Uebrig"] < 0:
                st.markdown(f"**🔴 {abs(item['Uebrig'])} Tage überfällig**")
            elif item["Uebrig"] == 0:
                st.markdown("**🟡 Heute fällig**")
            else:
                st.markdown(f"**🟢 In {item['Uebrig']} Tagen**")
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

# --- TABS ---
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
# GANTT CHARTS (NATIVE THEME)
# ==========================================
st.header("📊 Langzeit-Übersicht")

monate_namen = ["", "Jan.", "Feb.", "März", "Apr.", "Mai", "Juni", "Juli", "Aug.", "Sep.", "Okt.", "Nov.", "Dez."]

def create_clean_gantt(aufgaben_liste, view_type):
    if view_type == "Monat":
        start_date = heute.replace(day=1)
        letzter_tag = calendar.monthrange(heute.year, heute.month)[1]
        end_date = heute.replace(day=letzter_tag)
        title = f"{monate_namen[heute.month]} {heute.year}"
        dtick, tickformat = 86400000, "%d."
    elif view_type == "Quartal":
        current_quarter = (heute.month - 1) // 3 + 1
        start_month = 3 * current_quarter - 2
        start_date = heute.replace(month=start_month, day=1)
        letzter_monat = start_month + 2
        letzter_tag = calendar.monthrange(heute.year, letzter_monat)[1]
        end_date = heute.replace(month=letzter_monat, day=letzter_tag)
        title = f"Quartal {current_quarter} ({heute.year})"
        dtick, tickformat = 86400000 * 7, "%d.%m."
    else:
        start_date, end_date = heute.replace(month=1, day=1), heute.replace(month=12, day=31)
        title = f"Jahresübersicht {heute.year}"
        dtick, tickformat = "M1", "%b"

    gantt_data = []
    for item in aufgaben_liste:
        try: letztes_dt = datetime.strptime(str(item["Letztes_Datum"]), "%Y-%m-%d").date()
        except: letztes_dt = heute
        
        intervall = int(float(item.get("Intervall_Tage", 14)))
        kat = "Täglich" if intervall <= 1 else "Wöchentlich" if intervall <= 7 else "Seltener"
        
        diff_days = (start_date - letztes_dt).days
        if diff_days > 0:
            erste_faelligkeit = letztes_dt + timedelta(days=(diff_days // intervall) * intervall)
            if erste_faelligkeit < start_date: erste_faelligkeit += timedelta(days=intervall)
        else:
            erste_faelligkeit = letztes_dt - timedelta(days=(abs(diff_days) // intervall) * intervall)
            if erste_faelligkeit > start_date: erste_faelligkeit -= timedelta(days=intervall)
                
        curr = erste_faelligkeit
        while curr <= end_date:
            if curr >= start_date:
                gantt_data.append({
                    "Aufgabe": item["Aufgabe"],
                    "Start": f"{curr} 00:00:00",
                    "End": f"{curr} 20:00:00",
                    "Kategorie": kat,
                    "Intervall": intervall
                })
            curr += timedelta(days=intervall)
            
    if not gantt_data: return None
        
    df_g = pd.DataFrame(gantt_data).sort_values(by=["Intervall", "Aufgabe"], ascending=[True, True])
    
    fig = px.timeline(df_g, x_start="Start", x_end="End", y="Aufgabe", color="Kategorie", 
                      color_discrete_map={"Täglich": "#1f77b4", "Wöchentlich": "#2ca02c", "Seltener": "#ff7f0e"},
                      hover_data={"Start": False, "End": False, "Kategorie": False, "Intervall": True})
    
    fig.update_yaxes(autorange="reversed", title=None) 
    fig.update_xaxes(
        title=None, range=[f"{start_date} 00:00:00", f"{end_date + timedelta(days=1)} 00:00:00"], 
        tickformat=tickformat, dtick=dtick, showgrid=True, gridwidth=1
    )
    
    fig.add_vline(x=f"{heute} 12:00:00", line_width=2, line_dash="solid", line_color="#EF4444")
    
    fig.update_traces(marker_line_width=0, opacity=0.9)
    fig.update_layout(
        title=title,
        height=max(200, len(aufgaben_liste) * 30),
        margin=dict(t=40, b=0, l=0, r=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1, title=None)
    )
    return fig

with st.container(border=True):
    fig_monat = create_clean_gantt(aufgaben, "Monat")
    if fig_monat: st.plotly_chart(fig_monat, use_container_width=True, theme="streamlit")

with st.container(border=True):
    fig_quartal = create_clean_gantt(aufgaben, "Quartal")
    if fig_quartal: st.plotly_chart(fig_quartal, use_container_width=True, theme="streamlit")

with st.container(border=True):
    fig_jahr = create_clean_gantt(aufgaben, "Jahr")
    if fig_jahr: st.plotly_chart(fig_jahr, use_container_width=True, theme="streamlit")
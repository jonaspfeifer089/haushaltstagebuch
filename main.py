import streamlit as st
import pandas as pd
import plotly.express as px
import calendar
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# --- PAGE SETUP ---
st.set_page_config(layout="wide", page_title="Haushalt", page_icon="✨")

# --- MODERNES NOTION/APPLE-STYLE CSS ---
st.markdown("""
    <style>
    /* Generelles Spacing und Hintergrund */
    .stApp { background-color: #FAFAFA; }
    
    /* Clean Buttons */
    .stButton>button { 
        width: 100%; border-radius: 8px; border: 1px solid #E5E7EB; 
        background-color: #FFFFFF; color: #374151; font-weight: 500; 
        transition: all 0.2s ease; padding: 0.5rem;
    }
    .stButton>button:hover { background-color: #F3F4F6; border-color: #D1D5DB; color: #000; }
    
    /* Tabs Redesign */
    .stTabs [data-baseweb="tab-list"] { gap: 10px; padding-bottom: 10px; }
    .stTabs [data-baseweb="tab"] { 
        height: 40px; border-radius: 8px; padding: 0 20px; 
        background-color: #FFFFFF; border: 1px solid #E5E7EB; color: #6B7280; font-weight: 500;
    }
    .stTabs [aria-selected="true"] { 
        background-color: #111827 !important; color: #FFFFFF !important; border: none;
    }
    
    /* Metric Cards */
    div[data-testid="metric-container"] {
        background-color: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 12px; padding: 15px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);
    }
    </style>
""", unsafe_allow_html=True)

# --- GOOGLE SHEETS VERBINDUNG ---
GSHEETS_URL = "HIER_DEINEN_NEUEN_GOOGLE_SHEETS_LINK_EINFÜGEN"

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except:
    st.error("Verbindung fehlgeschlagen.")
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
st.markdown("<h1 style='text-align: center; color: #111827; margin-bottom: 0;'>✨ Haushaltstagebuch</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #6B7280; margin-bottom: 2rem;'>Lena & Jonas</p>", unsafe_allow_html=True)

# --- NEUE AUFGABE (CLEAN EXPANDER) ---
with st.expander("Neue Aufgabe hinzufügen", expanded=False):
    with st.form("neue_aufgabe_form", clear_on_submit=True, border=False):
        col1, col2, col3, col4 = st.columns([4, 2, 2, 2])
        with col1: aufgabe_name = st.text_input("Was?", placeholder="z.B. Kaffeemaschine entkalken")
        with col2: letztes_mal = st.date_input("Zuletzt erledigt:", heute)
        with col3: intervall = st.number_input("Intervall (Tage)", min_value=1, value=14, step=1)
        with col4:
            st.write("")
            st.write("")
            submit = st.form_submit_button("Speichern")
        
        if submit and aufgabe_name:
            aufgaben.append({"Aufgabe": aufgabe_name, "Letztes_Datum": str(letztes_mal), "Intervall_Tage": int(intervall)})
            save_haushalt(aufgaben)
            st.rerun()

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

st.write("")

# --- METRIKEN ---
m1, m2, m3 = st.columns(3)
m1.metric("🔥 Fällig / Überfällig", len(akut))
m2.metric("⏳ Demnächst", len(bald))
m3.metric("✅ Erledigt", len(entspannt))

st.write("")

# --- TASK RENDER FUNKTION (ALS CARDS) ---
def render_task(item):
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([5, 3, 2, 1])
        with c1:
            st.markdown(f"<span style='font-size: 1.1em; font-weight: 600; color: #111827;'>{item['Aufgabe']}</span>", unsafe_allow_html=True)
            st.markdown(f"<span style='color: #6B7280; font-size: 0.85em;'>🔄 Alle {item['Intervall']} Tage • Zuletzt: {item['Letztes'].strftime('%d.%m.')}</span>", unsafe_allow_html=True)
        with c2:
            st.write("") # Spacing
            if item["Uebrig"] < 0:
                st.markdown(f"<div style='background: #FEE2E2; color: #991B1B; padding: 4px 12px; border-radius: 20px; font-size: 0.85em; font-weight: 600; display: inline-block;'>🔴 {abs(item['Uebrig'])} Tage überfällig</div>", unsafe_allow_html=True)
            elif item["Uebrig"] == 0:
                st.markdown("<div style='background: #FEF3C7; color: #9A3412; padding: 4px 12px; border-radius: 20px; font-size: 0.85em; font-weight: 600; display: inline-block;'>🟡 Heute fällig</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div style='background: #D1FAE5; color: #065F46; padding: 4px 12px; border-radius: 20px; font-size: 0.85em; font-weight: 600; display: inline-block;'>🟢 In {item['Uebrig']} Tagen</div>", unsafe_allow_html=True)
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
tab1, tab2, tab3 = st.tabs(["Akut", "Demnächst", "Erledigt"])

with tab1:
    if not akut: st.markdown("<p style='color: #6B7280; padding: 20px 0;'>Alles sauber! Hier steht nichts an.</p>", unsafe_allow_html=True)
    for task in akut: render_task(task)

with tab2:
    if not bald: st.markdown("<p style='color: #6B7280; padding: 20px 0;'>Keine Aufgaben für die nächsten Tage.</p>", unsafe_allow_html=True)
    for task in bald: render_task(task)

with tab3:
    if not entspannt: st.markdown("<p style='color: #6B7280; padding: 20px 0;'>Noch nichts in dieser Kategorie.</p>", unsafe_allow_html=True)
    for task in entspannt: render_task(task)

st.markdown("<br><br>", unsafe_allow_html=True)

# ==========================================
# MODERN GANTT CHARTS (APPLE STYLE)
# ==========================================
st.markdown("<h3 style='color: #111827;'>📊 Langzeit-Übersicht</h3>", unsafe_allow_html=True)

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
    
    # Cleane Pastell-Farben
    color_map = {"Täglich": "#93C5FD", "Wöchentlich": "#86EFAC", "Seltener": "#FDBA74"}
    
    fig = px.timeline(df_g, x_start="Start", x_end="End", y="Aufgabe", color="Kategorie", 
                      color_discrete_map=color_map, hover_data={"Start": False, "End": False, "Kategorie": False, "Intervall": True},
                      template="simple_white") # Apple-Style Clean Template
    
    fig.update_yaxes(autorange="reversed", title=None, tickfont=dict(color="#4B5563")) 
    fig.update_xaxes(
        title=None, range=[f"{start_date} 00:00:00", f"{end_date + timedelta(days=1)} 00:00:00"], 
        tickformat=tickformat, dtick=dtick, tickfont=dict(color="#9CA3AF"),
        showgrid=True, gridwidth=1, gridcolor='#F3F4F6', zeroline=False
    )
    
    fig.add_vline(x=f"{heute} 12:00:00", line_width=2, line_dash="solid", line_color="#EF4444")
    
    fig.update_traces(marker_line_width=0, opacity=0.9)
    fig.update_layout(
        title=dict(text=title, font=dict(size=16, color="#374151")),
        height=max(200, len(aufgaben_liste) * 30),
        margin=dict(t=40, b=0, l=0, r=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1, title=None, font=dict(color="#6B7280"))
    )
    return fig

with st.container(border=True):
    fig_monat = create_clean_gantt(aufgaben, "Monat")
    if fig_monat: st.plotly_chart(fig_monat, use_container_width=True)

with st.container(border=True):
    fig_quartal = create_clean_gantt(aufgaben, "Quartal")
    if fig_quartal: st.plotly_chart(fig_quartal, use_container_width=True)

with st.container(border=True):
    fig_jahr = create_clean_gantt(aufgaben, "Jahr")
    if fig_jahr: st.plotly_chart(fig_jahr, use_container_width=True)
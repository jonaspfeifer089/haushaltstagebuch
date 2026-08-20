import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

st.set_page_config(layout="wide", page_title="Haushalt OS", page_icon="🏠")

# Notion-Style CSS
st.markdown("""
    <style>
    .stApp { background-color: #ffffff; }
    .css-1r6slp0 { padding: 1rem; }
    .task-container { 
        background: #f9f9f9; border-radius: 8px; padding: 12px; 
        margin-bottom: 8px; border-left: 5px solid #e0e0e0;
    }
    .status-overdue { border-left-color: #ef4444; }
    .status-due { border-left-color: #f59e0b; }
    .status-fine { border-left-color: #10b981; }
    </style>
""", unsafe_allow_html=True)

GSHEETS_URL = "https://docs.google.com/spreadsheets/d/1Dj3_N9ybEhIDX5HukIELYtE2E3LToq4DiuPV3EBjOiA/edit?usp=sharing"
conn = st.connection("gsheets", type=GSheetsConnection)

def get_data():
    df = conn.read(spreadsheet=GSHEETS_URL, worksheet="Haushalt", ttl=0)
    if 'Zuletzt_Erledigt_Von' not in df.columns: df['Zuletzt_Erledigt_Von'] = "Keiner"
    df['Letztes_Datum'] = df['Letztes_Datum'].fillna(str(datetime.now().date()))
    return df.to_dict(orient="records")

def save_data(data):
    conn.update(spreadsheet=GSHEETS_URL, worksheet="Haushalt", data=pd.DataFrame(data))
    st.cache_data.clear()

aufgaben = get_data()
heute = datetime.now().date()

# Dashboard Header mit Score
st.title("🏠 Haushalt OS")
total = len(aufgaben)
overdue = len([t for t in aufgaben if (datetime.strptime(str(t['Letztes_Datum']), "%Y-%m-%d").date() + timedelta(days=int(t['Intervall_Tage']))) <= heute])
score = ((total - overdue) / total) * 100
st.progress(score/100, text=f"Sauberkeits-Index: {int(score)}%")

# Kanban-artige Sektionen
cols = st.columns(3)
sections = ["🔥 Dringend", "⏳ Bald fällig", "✅ Kürzlich erledigt"]

for i, section in enumerate(sections):
    with cols[i]:
        st.subheader(section)
        for idx, t in enumerate(aufgaben):
            last = datetime.strptime(str(t['Letztes_Datum']), "%Y-%m-%d").date()
            due = last + timedelta(days=int(t['Intervall_Tage']))
            days_left = (due - heute).days
            
            # Logik für Sektionen
            if (section == "🔥 Dringend" and days_left <= 0) or \
               (section == "⏳ Bald fällig" and 0 < days_left <= 3) or \
               (section == "✅ Kürzlich erledigt" and days_left > 3):
                
                with st.container():
                    st.write(f"**{t['Aufgabe']}**")
                    col_a, col_b = st.columns([2, 1])
                    p = col_a.selectbox("Wer?", ["Lena", "Jonas"], key=f"p_{i}_{idx}")
                    if col_b.button("Done", key=f"d_{i}_{idx}"):
                        t['Letztes_Datum'] = str(heute)
                        t['Zuletzt_Erledigt_Von'] = p
                        save_data(aufgaben)
                        st.rerun()
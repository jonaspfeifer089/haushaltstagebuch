import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

st.set_page_config(layout="centered", page_title="Haushalt", page_icon="✨")

GSHEETS_URL = "https://docs.google.com/spreadsheets/d/1Dj3_N9ybEhIDX5HukIELYtE2E3LToq4DiuPV3EBjOiA/edit?usp=sharing"
conn = st.connection("gsheets", type=GSheetsConnection)

def get_data():
    df = conn.read(spreadsheet=GSHEETS_URL, worksheet="Haushalt", ttl=0)
    # Neue Spalte hinzufügen, falls sie noch nicht existiert
    if 'Zuletzt_Erledigt_Von' not in df.columns: df['Zuletzt_Erledigt_Von'] = "Keiner"
    df['Letztes_Datum'] = df['Letztes_Datum'].fillna(str(datetime.now().date()))
    return df.to_dict(orient="records")

def save_data(data):
    conn.update(spreadsheet=GSHEETS_URL, worksheet="Haushalt", data=pd.DataFrame(data))
    st.cache_data.clear()

aufgaben = get_data()
heute = datetime.now().date()

st.title("✨ Haushalt")

# Hilfsfunktion zum Abhaken
def complete_task(index, person):
    aufgaben[index]['Letztes_Datum'] = str(heute)
    aufgaben[index]['Zuletzt_Erledigt_Von'] = person
    save_data(aufgaben)
    st.rerun()

# Aufgaben-Logik
tasks = []
for i, t in enumerate(aufgaben):
    try: last = datetime.strptime(str(t['Letztes_Datum']), "%Y-%m-%d").date()
    except: last = heute
    due = last + timedelta(days=int(t['Intervall_Tage']))
    days_left = (due - heute).days
    tasks.append({**t, "index": i, "days_left": days_left})

# UI: Fällig / Demnächst
for section in ["🔥 Fällig / Überfällig", "⏳ Demnächst"]:
    st.subheader(section)
    items = [t for t in tasks if (t['days_left'] <= 0 if section == "🔥 Fällig / Überfällig" else t['days_left'] > 0)]
    
    for t in items:
        c1, c2, c3 = st.columns([3, 1, 1])
        c1.write(f"**{t['Aufgabe']}**")
        person = c2.selectbox("Wer?", ["Lena", "Jonas"], key=f"sel_{t['index']}")
        if c3.button("✔", key=f"done_{t['index']}"):
            complete_task(t['index'], person)

# Statistik
st.divider()
st.subheader("📊 Wer hat mehr getan?")
df = pd.DataFrame(aufgaben)
stats = df['Zuletzt_Erledigt_Von'].value_counts()
st.bar_chart(stats)
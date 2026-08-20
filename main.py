import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

st.set_page_config(layout="centered", page_title="Haushalt", page_icon="✨")

# Minimales, modernes Styling
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 6px; }
    .task-card { padding: 10px; border-radius: 8px; border: 1px solid #ddd; margin-bottom: 5px; }
    </style>
""", unsafe_allow_html=True)

GSHEETS_URL = "https://docs.google.com/spreadsheets/d/1Dj3_N9ybEhIDX5HukIELYtE2E3LToq4DiuPV3EBjOiA/edit?usp=sharing"
conn = st.connection("gsheets", type=GSheetsConnection)

def get_data():
    df = conn.read(spreadsheet=GSHEETS_URL, worksheet="Haushalt", ttl=0)
    # Fehlende Daten füllen, falls das Sheet leer ist
    if 'Letztes_Datum' not in df.columns: df['Letztes_Datum'] = str(datetime.now().date())
    return df.to_dict(orient="records")

def save_data(data):
    conn.update(spreadsheet=GSHEETS_URL, worksheet="Haushalt", data=pd.DataFrame(data))
    st.cache_data.clear()

aufgaben = get_data()
heute = datetime.now().date()

st.title("✨ Haushalt")

# Logik: Dringlichkeit berechnen
tasks = []
for i, t in enumerate(aufgaben):
    try: last = datetime.strptime(str(t['Letztes_Datum']), "%Y-%m-%d").date()
    except: last = heute
    due = last + timedelta(days=int(t['Intervall_Tage']))
    days_left = (due - heute).days
    tasks.append({**t, "index": i, "days_left": days_left, "due": due})

# Sortieren: Die dringendsten nach oben
tasks.sort(key=lambda x: x['days_left'])

# --- FOCUS BEREICH (Fällig/Überfällig) ---
st.subheader("Fällig")
for t in [t for t in tasks if t['days_left'] <= 0]:
    c1, c2 = st.columns([4, 1])
    c1.markdown(f"**{t['Aufgabe']}** (fällig seit {abs(t['days_left'])} Tagen)")
    if c2.button("✅", key=f"done_{t['index']}"):
        aufgaben[t['index']]['Letztes_Datum'] = str(heute)
        save_data(aufgaben); st.rerun()

st.divider()

# --- ÜBERSICHT ---
st.subheader("Demnächst")
for t in [t for t in tasks if t['days_left'] > 0]:
    progress = max(0, min(1, 1 - (t['days_left'] / t['Intervall_Tage'])))
    c1, c2 = st.columns([3, 2])
    c1.write(t['Aufgabe'])
    c2.progress(progress, text=f"{t['days_left']} Tage")

with st.expander("➕ Neue Aufgabe"):
    with st.form("new", clear_on_submit=True):
        n = st.text_input("Name")
        it = st.number_input("Intervall (Tage)", value=7)
        if st.form_submit_button("Speichern"):
            aufgaben.append({"Aufgabe": n, "Letztes_Datum": str(heute), "Intervall_Tage": it})
            save_data(aufgaben); st.rerun()
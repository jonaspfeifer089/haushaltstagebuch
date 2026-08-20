import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

st.set_page_config(layout="wide", page_title="Haushalt OS", page_icon="🏠")

# KEIN erzwungenes weißes CSS mehr! Wir nutzen den nativen Dark Mode.

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
score = int(((total - overdue) / max(total, 1)) * 100)
st.progress(score/100, text=f"Sauberkeits-Index: {score}%")

st.divider()

# Kanban-artige Sektionen in Containern
cols = st.columns(3)
sections = ["🔥 Dringend", "⏳ Bald fällig", "✅ Kürzlich erledigt"]

for i, section in enumerate(sections):
    with cols[i]:
        st.subheader(section)
        for idx, t in enumerate(aufgaben):
            try: last = datetime.strptime(str(t['Letztes_Datum']), "%Y-%m-%d").date()
            except: last = heute
            due = last + timedelta(days=int(t['Intervall_Tage']))
            days_left = (due - heute).days
            
            # Logik für Sektionen
            show = False
            if section == "🔥 Dringend" and days_left <= 0: show = True
            elif section == "⏳ Bald fällig" and 0 < days_left <= 3: show = True
            elif section == "✅ Kürzlich erledigt" and days_left > 3: show = True
            
            if show:
                with st.container(border=True):
                    st.write(f"**{t['Aufgabe']}**")
                    col_a, col_b = st.columns([2, 1])
                    p = col_a.selectbox("Wer?", ["Lena", "Jonas"], key=f"p_{i}_{idx}")
                    if col_b.button("Done", key=f"d_{i}_{idx}"):
                        t['Letztes_Datum'] = str(heute)
                        t['Zuletzt_Erledigt_Von'] = p
                        save_data(aufgaben)
                        st.rerun()

# Neue Aufgabe hinzufügen
with st.expander("➕ Neue Aufgabe"):
    with st.form("new_task", clear_on_submit=True):
        n = st.text_input("Name der Aufgabe")
        it = st.number_input("Intervall (Tage)", min_value=1, value=7)
        if st.form_submit_button("Hinzufügen"):
            aufgaben.append({"Aufgabe": n, "Letztes_Datum": str(heute), "Intervall_Tage": it, "Zuletzt_Erledigt_Von": "Keiner"})
            save_data(aufgaben)
            st.rerun()
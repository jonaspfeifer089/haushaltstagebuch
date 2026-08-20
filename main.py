import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# 1. Konfiguration
st.set_page_config(layout="wide", page_title="Haushaltsplan", page_icon="📝")

# 2. Verbindung
GSHEETS_URL = "https://docs.google.com/spreadsheets/d/1Dj3_N9ybEhIDX5HukIELYtE2E3LToq4DiuPV3EBjOiA/edit?usp=sharing"
conn = st.connection("gsheets", type=GSheetsConnection)

# 3. Daten laden & speichern
def get_data():
    df = conn.read(spreadsheet=GSHEETS_URL, worksheet="Haushalt", ttl=0)
    return df.to_dict(orient="records")

def save_data(data):
    df = pd.DataFrame(data)
    conn.update(spreadsheet=GSHEETS_URL, worksheet="Haushalt", data=df)
    st.cache_data.clear()

aufgaben = get_data()
heute = datetime.now().date()

# 4. Header & Eingabe
st.title("📝 HAUSHALTSPLAN")
with st.expander("➕ Neue Aufgabe hinzufügen"):
    with st.form("add_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        aufgabe = c1.text_input("Aufgabenname")
        intervall = c2.number_input("Intervall (Tage)", value=7)
        if c3.form_submit_button("Speichern"):
            aufgaben.append({"Aufgabe": aufgabe, "Letztes_Datum": str(heute), "Intervall_Tage": intervall})
            save_data(aufgaben)
            st.rerun()

st.divider()

# 5. Spalten-Logik (Die 4-Spalten-Vorlage)
cols = st.columns(4)
titles = ["TÄGLICH", "WÖCHENTLICH", "14-TÄGIG / MONATLICH", "SELTENER"]

for i, col in enumerate(cols):
    col.subheader(titles[i])
    for task in aufgaben:
        inv = int(float(task["Intervall_Tage"]))
        
        # Logik: Welche Aufgabe gehört in welche Spalte?
        belongs = False
        if i == 0 and inv <= 1: belongs = True
        elif i == 1 and 1 < inv <= 7: belongs = True
        elif i == 2 and 7 < inv <= 31: belongs = True
        elif i == 3 and inv > 31: belongs = True
        
        if belongs:
            # Zeile: Text + Button
            r1, r2 = col.columns([6, 1])
            r1.write(task["Aufgabe"])
            if r2.button("⬜", key=f"btn_{task['Aufgabe']}"):
                task["Letztes_Datum"] = str(heute)
                save_data(aufgaben)
                st.rerun()

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

# --- HEADER & EINGABE ---
c_head1, c_head2 = st.columns([3, 1])
with c_head1:
    st.markdown("<h1 style='font-size: 3rem; text-transform: uppercase; border-bottom: 2px solid #333; padding-bottom: 10px;'>Haushaltsplan</h1>", unsafe_allow_html=True)
with c_head2:
    with st.popover("➕ Neue Aufgabe"):
        with st.form("neue_aufgabe_form", clear_on_submit=True):
            aufgabe_name = st.text_input("Aufgabe")
            intervall = st.number_input("Intervall (Tage)", min_value=1, value=7, step=1)
            letztes_mal = st.date_input("Zuletzt erledigt:", heute)
            if st.form_submit_button("Hinzufügen") and aufgabe_name:
                aufgaben.append({"Aufgabe": aufgabe_name, "Letztes_Datum": str(letztes_mal), "Intervall_Tage": int(intervall)})
                save_haushalt(aufgaben)
                st.rerun()

st.write("")
st.write("")

# --- DATEN-SORTIERUNG IN DIE 4 SPALTEN ---
taeglich, woechentlich, monatlich, seltener = [], [], [], []

for i, item in enumerate(aufgaben):
    try: letztes_dt = datetime.strptime(str(item["Letztes_Datum"]), "%Y-%m-%d").date()
    except: letztes_dt = heute
    
    intervall = int(float(item.get("Intervall_Tage", 14)))
    naechstes_dt = letztes_dt + timedelta(days=intervall)
    uebrig = (naechstes_dt - heute).days
    
    task_obj = {"index": i, "Aufgabe": item["Aufgabe"], "Erledigt": uebrig > 0}
    
    if intervall <= 1: taeglich.append(task_obj)
    elif intervall <= 7: woechentlich.append(task_obj)
    elif intervall <= 31: monatlich.append(task_obj)
    else: seltener.append(task_obj)

# --- DIE 4-SPALTEN ANSICHT ---
col1, col2, col3, col4 = st.columns(4)

def render_task_list(task_list, column_obj):
    for task in task_list:
        c_text, c_btn, c_del = column_obj.columns([7, 2, 1])
        
        # Abhaken-Button
        if task["Erledigt"]:
            if c_btn.button("✅", key=f"btn_{task['index']}"):
                pass # Wenn schon erledigt, macht ein Klick aktuell nichts (Schutz vor Fehlklicks)
            # Text durchgestrichen und ausgegraut
            c_text.markdown(f"<span style='color: #aaa; text-decoration: line-through; line-height: 2.2;'>{task['Aufgabe']}</span>", unsafe_allow_html=True)
        else:
            if c_btn.button("⬜", key=f"btn_{task['index']}"):
                aufgaben[task['index']]["Letztes_Datum"] = str(heute)
                save_haushalt(aufgaben)
                st.rerun()
            # Text normal
            c_text.markdown(f"<span style='color: #333; line-height: 2.2;'>{task['Aufgabe']}</span>", unsafe_allow_html=True)
            
        # Unsichtbarer Löschen-Button (zeigt sich als kleines 'x')
        if c_del.button("×", key=f"del_{task['index']}", help="Aufgabe löschen"):
            aufgaben.pop(task['index'])
            save_haushalt(aufgaben)
            st.rerun()
            
        column_obj.markdown("<hr style='margin: 0;'>", unsafe_allow_html=True)

with col1:
    st.markdown("<h3>TÄGLICH</h3>", unsafe_allow_html=True)
    st.markdown("<hr style='border-top: 2px dotted #ccc;'>", unsafe_allow_html=True)
    render_task_list(taeglich, st)

with col2:
    st.markdown("<h3>WÖCHENTLICH</h3>", unsafe_allow_html=True)
    st.markdown("<hr style='border-top: 2px dotted #ccc;'>", unsafe_allow_html=True)
    render_task_list(woechentlich, st)

with col3:
    st.markdown("<h3>14-TÄGIG / MONATLICH</h3>", unsafe_allow_html=True)
    st.markdown("<hr style='border-top: 2px dotted #ccc;'>", unsafe_allow_html=True)
    render_task_list(monatlich, st)

with col4:
    st.markdown("<h3>SELTENER</h3>", unsafe_allow_html=True)
    st.markdown("<hr style='border-top: 2px dotted #ccc;'>", unsafe_allow_html=True)
    render_task_list(seltener, st)
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# --- PAGE SETUP ---
st.set_page_config(layout="wide", page_title="Haushaltstagebuch", page_icon="🧹")

# CSS für eine saubere Optik
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 8px; }
    </style>
""", unsafe_allow_html=True)

st.title("🧹 Das intelligente Haushaltstagebuch")
st.caption("Dokumentiere und verwalte Putzpläne, Filterwechsel und Wartungsintervalle.")

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
        if df.empty: 
            df = pd.DataFrame(columns=["Aufgabe", "Letztes_Datum", "Intervall_Tage"])
        conn.update(spreadsheet=GSHEETS_URL, worksheet="Haushalt", data=df)
        st.cache_data.clear()
    except:
        pass

aufgaben = load_haushalt()
heute = datetime.now().date()

# --- NEUE AUFGABE HINZUFÜGEN ---
st.subheader("➕ Neue Aufgabe anlegen")
with st.form("neue_aufgabe_form", clear_on_submit=True):
    col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
    with col1:
        aufgabe_name = st.text_input("Was? (z.B. Kaffeemaschine entkalken, Bettwäsche)")
    with col2:
        letztes_mal = st.date_input("Zuletzt erledigt am:", heute)
    with col3:
        intervall = st.number_input("Intervall (in Tagen)", min_value=1, value=14, step=1)
    with col4:
        st.write("")
        st.write("")
        submit = st.form_submit_button("Speichern 💾")
    
    if submit and aufgabe_name:
        aufgaben.append({
            "Aufgabe": aufgabe_name,
            "Letztes_Datum": str(letztes_mal),
            "Intervall_Tage": int(intervall)
        })
        save_haushalt(aufgaben)
        st.rerun()

st.markdown("---")

# --- AUFGABEN-ÜBERSICHT & LOGIK ---
if not aufgaben:
    st.info("Aktuell hast du noch keine Haushaltsaufgaben angelegt. Leg los!")
else:
    angereicherte_aufgaben = []
    for i, item in enumerate(aufgaben):
        try:
            letztes_dt = datetime.strptime(str(item["Letztes_Datum"]), "%Y-%m-%d").date()
        except:
            letztes_dt = heute
        
        intervall_tage = int(float(item.get("Intervall_Tage", 14)))
        naechstes_dt = letztes_dt + timedelta(days=intervall_tage)
        tage_uebrig = (naechstes_dt - heute).days
        
        angereicherte_aufgaben.append({
            "index": i,
            "Aufgabe": item["Aufgabe"],
            "Letztes_Datum": letztes_dt,
            "Intervall_Tage": intervall_tage,
            "Naechstes_Datum": naechstes_dt,
            "Tage_Uebrig": tage_uebrig
        })
        
    angereicherte_aufgaben = sorted(angereicherte_aufgaben, key=lambda x: x["Tage_Uebrig"])
    
    st.subheader("📋 Dein Radar")
    
    h1, h2, h3, h4, h5 = st.columns([3, 2, 2, 2, 1])
    with h1: st.markdown("**Aufgabe**")
    with h2: st.markdown("**Zuletzt erledigt**")
    with h3: st.markdown("**Status**")
    with h4: st.markdown("**Aktion**")
    with h5: st.markdown("**Löschen**")
    
    st.write("")
    
    for item in angereicherte_aufgaben:
        c1, c2, c3, c4, c5 = st.columns([3, 2, 2, 2, 1])
        with c1:
            st.write(f"🧽 **{item['Aufgabe']}**")
            st.caption(f"Intervall: alle {item['Intervall_Tage']} Tage")
        with c2:
            st.write(f"{item['Letztes_Datum'].strftime('%d.%m.%Y')}")
        with c3:
            if item["Tage_Uebrig"] < 0:
                st.error(f"⚠️ Seit {abs(item['Tage_Uebrig'])} Tagen überfällig!")
            elif item["Tage_Uebrig"] == 0:
                st.warning("⏳ Heute fällig!")
            elif item["Tage_Uebrig"] <= 3:
                st.info(f"Steht in {item['Tage_Uebrig']} Tagen an")
            else:
                st.success(f"Noch {item['Tage_Uebrig']} Tage Zeit")
        with c4:
            if st.button("✅ Heute erledigt", key=f"done_{item['index']}"):
                aufgaben[item['index']]["Letztes_Datum"] = str(heute)
                save_haushalt(aufgaben)
                st.rerun()
        with c5:
            if st.button("🗑️", key=f"del_{item['index']}"):
                aufgaben.pop(item['index'])
                save_haushalt(aufgaben)
                st.rerun()
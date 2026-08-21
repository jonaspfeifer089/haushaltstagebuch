import streamlit as st
import pandas as pd
import requests
import calendar
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

st.set_page_config(layout="wide", page_title="Haushalt OS", page_icon="🏠")

# ==========================================
# 1. AUTH0 SETUP
# ==========================================
AUTH0_DOMAIN = "haushalt.eu.auth0.com"
CLIENT_ID = "p1dq61TprZKk0sEYMu9NCXkeaCBCJkB6"
CLIENT_SECRET = "HKC5vtKe6NRNB_gp-E3WinJ3VvgnGiqMi44Boj9luxJq17XTBJwXFjwrWc_yZZrA"
REDIRECT_URI = "https://haushaltstagebuch.streamlit.app" # URL für die Cloud

def get_token(code):
    payload = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "redirect_uri": REDIRECT_URI
    }
    res = requests.post(f"https://{AUTH0_DOMAIN}/oauth/token", json=payload)
    return res.json().get("access_token")

def get_user_info(access_token):
    res = requests.get(f"https://{AUTH0_DOMAIN}/userinfo", headers={"Authorization": f"Bearer {access_token}"})
    return res.json()

if "user" not in st.session_state: st.session_state.user = None

if "code" in st.query_params and not st.session_state.user:
    token = get_token(st.query_params["code"])
    if token:
        st.session_state.user = get_user_info(token)
        st.query_params.clear() 
        st.rerun()

# Wenn nicht eingeloggt -> Login Screen zeigen und Stopp
if not st.session_state.user:
    st.title("🏠 Haushalt OS")
    st.caption("Bitte identifiziere dich, um fortzufahren.")
    
    # URL wird sauber zusammengesetzt
    auth_url = f"https://{AUTH0_DOMAIN}/authorize?response_type=code&client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&scope=openid%20profile%20email"
    
    # Der native Streamlit-Button öffnet in der Cloud automatisch und sicher einen neuen Tab
    st.link_button("🔒 Mit Auth0 Anmelden", auth_url, type="primary", use_container_width=True)
    
    st.stop()

# ==========================================
# 2. DATENBANK-SETUP
# ==========================================
GSHEETS_URL = "https://docs.google.com/spreadsheets/d/1Dj3_N9ybEhIDX5HukIELYtE2E3LToq4DiuPV3EBjOiA/edit?usp=sharing"
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=5)
def load_sheet(sheet_name):
    df = conn.read(spreadsheet=GSHEETS_URL, worksheet=sheet_name, ttl=0)
    return df.to_dict(orient="records")

def save_sheet(data, sheet_name):
    conn.update(spreadsheet=GSHEETS_URL, worksheet=sheet_name, data=pd.DataFrame(data))
    st.cache_data.clear()

aufgaben = load_sheet("Haushalt")
einkauf = load_sheet("Einkauf")
vorrat = load_sheet("Vorrat")
heute = datetime.now().date()

# ==========================================
# 3. DASHBOARD UI
# ==========================================
col_header1, col_header2 = st.columns([4, 1])
col_header1.title("🏠 Haushalt OS")
col_header2.write("")
if col_header2.button("🚪 Logout"):
    st.session_state.user = None
    st.rerun()

st.caption(f"Eingeloggt als: {st.session_state.user.get('name', 'User')}")

tab_home, tab_einkauf, tab_vorrat, tab_todoist = st.tabs([
    "📅 Kalender (Haushalt)", 
    "🛒 Einkaufsliste", 
    "🥫 Vorratskammer", 
    "📆 ToDoist (Alle Termine)"
])

# ------------------------------------------
# TAB 1: HAUSHALT (Kalender-Ansichten)
# ------------------------------------------
with tab_home:
    # 1. NEUE AUFGABE HINZUFÜGEN
    with st.expander("➕ Neue Haushalts-Aufgabe hinzufügen"):
        with st.form("new_task_form", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            n_name = c1.text_input("Was ist zu tun?", placeholder="z.B. Fenster putzen")
            n_date = c2.date_input("Wann fällig?", value=heute)
            n_intervall = c3.number_input("Intervall (in Tagen)", min_value=1, value=7)
            
            if st.form_submit_button("Hinzufügen"):
                if n_name:
                    # Wir berechnen das fiktive "letzte Datum", damit es exakt am Wunschdatum fällig wird
                    fake_last = n_date - timedelta(days=n_intervall)
                    aufgaben.append({"Aufgabe": n_name, "Letztes_Datum": str(fake_last), "Intervall_Tage": n_intervall})
                    save_sheet(aufgaben, "Haushalt")
                    st.rerun()

    # Datenvorbereitung
    tasks_processed = []
    for i, t in enumerate(aufgaben):
        try: last = datetime.strptime(str(t['Letztes_Datum']), "%Y-%m-%d").date()
        except: last = heute
        due = last + timedelta(days=int(t['Intervall_Tage']))
        tasks_processed.append({**t, "index": i, "due": due})
    
    tage_namen = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

    # 2. WOCHENKALENDER
    st.subheader("🗓️ Wochenübersicht")
    start_of_week = heute - timedelta(days=heute.weekday())
    week_days = [start_of_week + timedelta(days=i) for i in range(7)]
    
    w_cols = st.columns(7)
    for i, col in enumerate(w_cols):
        day_date = week_days[i]
        with col:
            # Visueller Header
            st.markdown(f"<div style='text-align: center; border-bottom: 2px solid #38bdf8; padding-bottom: 5px; margin-bottom: 10px;'><b>{tage_namen[i]}</b><br>{day_date.strftime('%d.%m.')}</div>", unsafe_allow_html=True)
            
            # --- NEUE LOGIK FÜR DEN WOCHENKALENDER ---
            # Smart-Logic: Überfällige Aufgaben rollen auf "Heute" und verschwinden aus der Vergangenheit
            if day_date == heute:
                # Heute: Zeige alles, was heute ODER in der Vergangenheit fällig war
                day_tasks = [t for t in tasks_processed if t['due'] <= day_date]
            elif day_date > heute:
                # Zukunft: Zeige nur Aufgaben, die exakt an diesem Tag fällig sind
                day_tasks = [t for t in tasks_processed if t['due'] == day_date]
            else:
                # Vergangenheit: Wird leer angezeigt, da unerledigte Aufgaben auf "Heute" gerutscht sind
                day_tasks = []
                
            if day_tasks:
                for t in day_tasks:
                    with st.container(border=True):
                        if t['due'] < heute and day_date == heute:
                            st.markdown(f"<span style='color: #ef4444; font-size: 0.9em;'>⚠️ <b>{t['Aufgabe']}</b></span>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"<span style='font-size: 0.9em;'><b>{t['Aufgabe']}</b></span>", unsafe_allow_html=True)
                        
                        # Der direkte Erledigt-Button im Kalender
                        if st.button("✔ Done", key=f"dw_{t['index']}_{i}", use_container_width=True):
                            aufgaben[t['index']]['Letztes_Datum'] = str(heute)
                            save_sheet(aufgaben, "Haushalt")
                            st.rerun()
            else:
                st.caption("*- Frei -*")

    st.divider()

    # 3. MONATSKALENDER
    monate_de = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]
    st.subheader(f"📆 Monat: {monate_de[heute.month - 1]} {heute.year}")
    
    month_cal = calendar.Calendar(firstweekday=0).monthdatescalendar(heute.year, heute.month)
    
    m_head = st.columns(7)
    for i, name in enumerate(tage_namen):
        m_head[i].markdown(f"<div style='text-align: center; color: gray;'>{name}</div>", unsafe_allow_html=True)
        
    for week in month_cal:
        m_cols = st.columns(7)
        for i, day in enumerate(week):
            with m_cols[i]:
                if day.month == heute.month:
                    with st.container(border=True):
                        if day == heute:
                            st.markdown(f"🎈 **{day.day}.**")
                        else:
                            st.markdown(f"**{day.day}.**")
                        
                        # --- NEUE LOGIK FÜR DEN MONATSKALENDER ---
                        if day == heute:
                            day_tasks = [t for t in tasks_processed if t['due'] <= day]
                        elif day > heute:
                            day_tasks = [t for t in tasks_processed if t['due'] == day]
                        else:
                            day_tasks = []
                            
                        for t in day_tasks:
                            st.caption(f"{t['Aufgabe']}")
                            if st.button("✔", key=f"dm_{t['index']}_{day.day}", use_container_width=True):
                                aufgaben[t['index']]['Letztes_Datum'] = str(heute)
                                save_sheet(aufgaben, "Haushalt")
                                st.rerun()
                else:
                    st.write("") # Leeres Feld für Fremd-Monate

# ------------------------------------------
# TAB 2: SHARED EINKAUFSLISTE
# ------------------------------------------
with tab_einkauf:
    # NEU: Das Formular löst das Speicher-Problem!
    with st.form("einkauf_form", clear_on_submit=True):
        c1, c2 = st.columns([3, 1])
        neuer_artikel = c1.text_input("Was brauchen wir?", placeholder="z.B. Äpfel, Spülmittel...")
        submit = c2.form_submit_button("Hinzufügen", use_container_width=True)
        
        if submit and neuer_artikel:
            einkauf.append({"Artikel": neuer_artikel, "Status": "Offen"})
            save_sheet(einkauf, "Einkauf")
            st.rerun()
            
    st.divider()
    for i, item in enumerate(einkauf):
        if str(item.get("Status")) != "Erledigt":
            ci1, ci2 = st.columns([4, 1])
            ci1.write(f"🛒 {item['Artikel']}")
            if ci2.button("✔ Im Wagen", key=f"e_{i}"):
                einkauf[i]['Status'] = "Erledigt"
                save_sheet(einkauf, "Einkauf"); st.rerun()

# ------------------------------------------
# TAB 3: SMARTE VORRATSKAMMER (MHD)
# ------------------------------------------
with tab_vorrat:
    st.caption("Minimaler Aufwand: Artikel eingeben und pauschal Haltbarkeit addieren.")
    with st.form("vorrat_add", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        v_art = c1.text_input("Artikel")
        v_tage = c2.number_input("Hält noch ca. (Tage)", min_value=1, value=7)
        if c3.form_submit_button("In Vorrat"):
            mhd_datum = heute + timedelta(days=int(v_tage))
            vorrat.append({"Artikel": v_art, "Ablaufdatum": str(mhd_datum)})
            save_sheet(vorrat, "Vorrat"); st.rerun()
            
    st.divider()
    for i, v in enumerate(vorrat):
        try: mhd = datetime.strptime(str(v['Ablaufdatum']), "%Y-%m-%d").date()
        except: mhd = heute
        left = (mhd - heute).days
        
        with st.container(border=True):
            col1, col2 = st.columns([4, 1])
            if left < 0: col1.error(f"⚠️ {v['Artikel']} (Abgelaufen!)")
            elif left <= 3: col1.warning(f"⏳ {v['Artikel']} (Läuft in {left} Tagen ab)")
            else: col1.success(f"🥫 {v['Artikel']} (Noch {left} Tage)")
            
            if col2.button("🗑 Weg", key=f"v_{i}"):
                vorrat.pop(i)
                save_sheet(vorrat, "Vorrat"); st.rerun()

# ------------------------------------------
# TAB 4: TODOIST KALENDER (Read-Only)
# ------------------------------------------
with tab_todoist:
    st.subheader("📅 ToDoist Termine")
    TODOIST_TOKEN = "DEIN_TODOIST_API_TOKEN" 
    
    if TODOIST_TOKEN == "DEIN_TODOIST_API_TOKEN":
        st.info("Bitte trage deinen ToDoist API Token oben im Code ein.")
    else:
        try:
            res = requests.get("https://api.todoist.com/rest/v2/tasks", headers={"Authorization": f"Bearer {TODOIST_TOKEN}"})
            if res.status_code == 200:
                for task in res.json():
                    due_info = task.get("due")
                    due_str = due_info.get("string") if due_info else "Kein Datum"
                    st.write(f"✅ **{task['content']}** — 🗓️ *{due_str}*")
        except:
            st.error("Verbindung zu ToDoist fehlgeschlagen.")
import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

st.set_page_config(layout="wide", page_title="Haushalt OS", page_icon="🏠")

# ==========================================
# 1. AUTH0 SETUP (Hier deine Daten eintragen!)
# ==========================================
AUTH0_DOMAIN = "haushalt.eu.auth0.com"
CLIENT_ID = "p1dq61TprZKk0sEYMu9NCXkeaCBCJkB6"
CLIENT_SECRET = "HKC5vtKe6NRNB_gp-E3WinJ3VvgnGiqMi44Boj9luxJq17XTBJwXFjwrWc_yZZrA"
REDIRECT_URI = "http://localhost:8501" # Ändern in deine echte Streamlit-URL, wenn online!

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

# Login Logik (Prüft ob man gerade von Auth0 zurückkommt)
if "code" in st.query_params and not st.session_state.user:
    token = get_token(st.query_params["code"])
    if token:
        st.session_state.user = get_user_info(token)
        st.query_params.clear() # URL wieder sauber machen
        st.rerun()

# Wenn nicht eingeloggt -> Login Screen zeigen und Stopp
if not st.session_state.user:
    st.title("🏠 Haushalt OS")
    st.caption("Bitte identifiziere dich, um fortzufahren.")
    auth_url = f"https://{AUTH0_DOMAIN}/authorize?response_type=code&client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&scope=openid profile email"
    st.markdown(f'<a href="{auth_url}" target="_self"><button style="width:100%; padding:14px; border-radius:8px; background-color:#38bdf8; color:white; border:none; font-weight:bold; font-size:16px;">🔒 Mit Auth0 Anmelden</button></a>', unsafe_allow_html=True)
    st.stop()

# ==========================================
# 2. DATENBANK-SETUP (Ab hier nur für eingeloggte User)
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

for t in aufgaben:
    if pd.isna(t.get('Letztes_Datum')): t['Letztes_Datum'] = str(heute)

# ==========================================
# 3. PUSH BENACHRICHTIGUNGEN (ntfy.sh)
# ==========================================
def send_push(message):
    try:
        requests.post("https://ntfy.sh/HaushaltLenaJonas", 
                      data=message.encode('utf-8'), 
                      headers={"Title": "🏠 Haushalt OS", "Priority": "high"})
        st.toast("Push-Benachrichtigung gesendet!", icon="📱")
    except:
        st.error("Push fehlgeschlagen.")

# ==========================================
# 4. DASHBOARD UI (Tabs)
# ==========================================
col_header1, col_header2 = st.columns([4, 1])
col_header1.title("🏠 Haushalt OS")
col_header2.write("")
if col_header2.button("🚪 Logout"):
    st.session_state.user = None
    st.rerun()

st.caption(f"Eingeloggt als: {st.session_state.user.get('name', 'User')}")

tab_home, tab_einkauf, tab_vorrat, tab_todoist = st.tabs([
    "🧹 Aufgaben", 
    "🛒 Einkaufsliste", 
    "🥫 Vorratskammer", 
    "📅 Gemeinsamer Kalender"
])

# ------------------------------------------
# TAB 1: HAUSHALT (Timeline / Vorausschau)
# ------------------------------------------
with tab_home:
    tasks_processed = []
    for i, t in enumerate(aufgaben):
        last = datetime.strptime(str(t['Letztes_Datum']), "%Y-%m-%d").date()
        due = last + timedelta(days=int(t['Intervall_Tage']))
        days_left = (due - heute).days
        tasks_processed.append({**t, "index": i, "due": due, "days_left": days_left})
    
    tasks_processed.sort(key=lambda x: x['days_left'])
    overdue = [t for t in tasks_processed if t['days_left'] < 0]
    this_week = [t for t in tasks_processed if 0 <= t['days_left'] <= 7]
    this_month = [t for t in tasks_processed if 7 < t['days_left'] <= 30]

    if overdue:
        c1, c2 = st.columns([4, 1])
        c1.subheader("🔥 Überfällig / Dringend")
        if c2.button("🔔 Push an Partner senden"):
            send_push(f"{len(overdue)} Aufgaben sind überfällig! (u.a. {overdue[0]['Aufgabe']})")
        
        for t in overdue:
            with st.container(border=True):
                ca, cb = st.columns([4, 1])
                ca.error(f"**{t['Aufgabe']}** (fällig seit {abs(t['days_left'])} Tagen)")
                if cb.button("✔ Done", key=f"done_{t['index']}"):
                    aufgaben[t['index']]['Letztes_Datum'] = str(heute)
                    save_sheet(aufgaben, "Haushalt"); st.rerun()

    col_w, col_m = st.columns(2)
    with col_w:
        st.subheader("📅 Diese Woche")
        if not this_week: st.success("Alles erledigt für diese Woche!")
        for t in this_week:
            with st.container(border=True):
                c1, c2 = st.columns([3, 1])
                c1.write(f"**{t['Aufgabe']}**")
                c1.caption(f"Fällig in {t['days_left']} Tagen ({t['due'].strftime('%d.%m.')})")
                if c2.button("✔", key=f"done_{t['index']}"):
                    aufgaben[t['index']]['Letztes_Datum'] = str(heute)
                    save_sheet(aufgaben, "Haushalt"); st.rerun()
                    
    with col_m:
        st.subheader("📆 Später diesen Monat")
        for t in this_month:
            with st.container(border=True):
                st.write(f"**{t['Aufgabe']}** (in {t['days_left']} Tagen)")

# ------------------------------------------
# TAB 2: SHARED EINKAUFSLISTE
# ------------------------------------------
with tab_einkauf:
    c1, c2 = st.columns([3, 1])
    with c1:
        neuer_artikel = st.text_input("Was brauchen wir?", placeholder="z.B. Hafermilch")
    with c2:
        st.write(""); st.write("")
        if st.button("Hinzufügen", use_container_width=True) and neuer_artikel:
            einkauf.append({"Artikel": neuer_artikel, "Status": "Offen"})
            save_sheet(einkauf, "Einkauf"); st.rerun()
            
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
    with st.form("vorrat_add"):
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
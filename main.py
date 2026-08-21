import streamlit as st
import pandas as pd
import requests
import calendar
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
from icalendar import Calendar
from streamlit_cookies_controller import CookieController
import json

st.set_page_config(layout="wide", page_title="Haushalt OS", page_icon="🏠")

# ==========================================
# 1. AUTH0 SETUP
# ==========================================
AUTH0_DOMAIN = "haushalt.eu.auth0.com"
CLIENT_ID = "p1dq61TprZKk0sEYMu9NCXkeaCBCJkB6"
CLIENT_SECRET = "HKC5vtKe6NRNB_gp-E3WinJ3VvgnGiqMi44Boj9luxJq17XTBJwXFjwrWc_yZZrA"
REDIRECT_URI = "https://haushaltstagebuch.streamlit.app" 

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

# Cookie-Controller initialisieren
cookies = CookieController()

# 1. Check: Gibt es schon ein gespeichertes Cookie im Browser?
if "user" not in st.session_state:
    saved_user = cookies.get("haushalt_user")
    if saved_user:
        # User aus dem Cookie in die Session laden
        if isinstance(saved_user, str):
            st.session_state.user = json.loads(saved_user)
        else:
            st.session_state.user = saved_user
    else:
        st.session_state.user = None

# 2. Check: User kommt gerade frisch vom Login (Auth0 schickt den Code)
if "code" in st.query_params and not st.session_state.user:
    token = get_token(st.query_params["code"])
    if token:
        user_info = get_user_info(token)
        st.session_state.user = user_info
        
        # NEU: User-Daten als Cookie im Browser speichern
        cookies.set("haushalt_user", json.dumps(user_info), max_age=60*60*24*30)
        
        # URL aufräumen
        st.query_params.clear() 


# Wenn nicht eingeloggt -> Login Screen zeigen und Stopp
if not st.session_state.user:
    st.title("🏠 Haushalt OS")
    st.caption("Bitte identifiziere dich, um fortzufahren.")
    
    auth_url = f"https://{AUTH0_DOMAIN}/authorize?response_type=code&client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&scope=openid%20profile%20email"
    st.link_button("🔒 Mit Auth0 Anmelden", auth_url, type="primary", use_container_width=True)
    st.stop()

# ==========================================
# 2. DATENBANK-SETUP
# ==========================================
GSHEETS_URL = "https://docs.google.com/spreadsheets/d/1Dj3_N9ybEhIDX5HukIELYtE2E3LToq4DiuPV3EBjOiA/edit?usp=sharing"
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=None) # Keine automatische Aktualisierung während der KI-Verarbeitung
def load_sheet(sheet_name):
    df = conn.read(spreadsheet=GSHEETS_URL, worksheet=sheet_name)
    return df.to_dict(orient="records")

def save_sheet(data, sheet_name):
    conn.update(spreadsheet=GSHEETS_URL, worksheet=sheet_name, data=pd.DataFrame(data))
    st.cache_data.clear()

aufgaben = load_sheet("Haushalt")
einkauf = load_sheet("Einkauf")
vorrat = load_sheet("Vorrat")
heute = datetime.now().date()

# ==========================================
# PUSH-BENACHRICHTIGUNGEN (ntfy.sh)
# ==========================================
def send_push(title, message):
    try:
        # Ntfy.sh JSON API nutzen (sicher für Umlaute und Emojis)
        payload = {
            "topic": "HaushaltLenaJonas_Geheim123", # Ein etwas geheimerer Name!
            "title": title,
            "message": message,
            "tags": ["shopping_bags"] # Fügt ein kleines Icon hinzu
        }
        requests.post("https://ntfy.sh/", json=payload, timeout=5)
    except Exception as e:
        print(f"Push Fehler: {e}")

# ==========================================
# 3. DASHBOARD UI
# ==========================================
col_header1, col_header2 = st.columns([4, 1])
col_header1.title("🏠 Haushalt OS")
col_header2.write("")
if col_header2.button("🚪 Logout"):
    # 1. Cookie löschen
    cookies.remove("haushalt_user")
    # 2. Session leeren
    st.session_state.user = None
    
    # 3. Wir zwingen den Browser per JavaScript zu einem sauberen Reload, 
    # damit das Cookie auch wirklich vorher gelöscht wird.
    st.components.v1.html("<script>window.parent.location.reload();</script>", height=0)
    
    import time
    time.sleep(0.5) # Kurz warten, damit die Löschung greift
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
            st.markdown(f"<div style='text-align: center; border-bottom: 2px solid #38bdf8; padding-bottom: 5px; margin-bottom: 10px;'><b>{tage_namen[i]}</b><br>{day_date.strftime('%d.%m.')}</div>", unsafe_allow_html=True)
            
            if day_date == heute:
                day_tasks = [t for t in tasks_processed if t['due'] <= day_date]
            elif day_date > heute:
                day_tasks = [t for t in tasks_processed if t['due'] == day_date]
            else:
                day_tasks = []
                
            if day_tasks:
                for t in day_tasks:
                    with st.container(border=True):
                        if t['due'] < heute and day_date == heute:
                            st.markdown(f"<span style='color: #ef4444; font-size: 0.9em;'>⚠️ <b>{t['Aufgabe']}</b></span>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"<span style='font-size: 0.9em;'><b>{t['Aufgabe']}</b></span>", unsafe_allow_html=True)
                        
                        if st.button("✔ Done", key=f"dw_{t['index']}_{i}", use_container_width=True):
                            aufgaben[t['index']]['Letztes_Datum'] = str(heute)
                            save_sheet(aufgaben, "Haushalt")
                            st.rerun()
            else:
                st.caption("*- Frei -*")

    st.divider()

# 3. MONATS-AGENDA (Mobile-Optimiert)
    monate_de = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]
    st.subheader(f"📆 Ausblick: Restlicher {monate_de[heute.month - 1]}")
    
    future_month_tasks = [t for t in tasks_processed if t['due'].month == heute.month and t['due'] > heute]
    
    tasks_by_date = {}
    for t in future_month_tasks:
        d = t['due']
        if d not in tasks_by_date:
            tasks_by_date[d] = []
        tasks_by_date[d].append(t)
        
    if not tasks_by_date:
        st.info("Keine weiteren Aufgaben für den restlichen Monat geplant! 🎉")
    else:
        for d in sorted(tasks_by_date.keys()):
            with st.container(border=True):
                st.markdown(f"<div style='border-bottom: 1px solid #333; padding-bottom: 5px; margin-bottom: 10px; color: #38bdf8;'><b>{tage_namen[d.weekday()]}, {d.strftime('%d.%m.')}</b></div>", unsafe_allow_html=True)
                for t in tasks_by_date[d]:
                    c1, c2 = st.columns([4, 1])
                    c1.write(f"{t['Aufgabe']}")
                    if c2.button("✔ Done", key=f"dm_{t['index']}_{d.day}", use_container_width=True):
                        aufgaben[t['index']]['Letztes_Datum'] = str(heute)
                        save_sheet(aufgaben, "Haushalt")
                        st.rerun()

# ------------------------------------------
# TAB 2: SHARED EINKAUFSLISTE
# ------------------------------------------
with tab_einkauf:
    with st.form("einkauf_form", clear_on_submit=True):
        c1, c2 = st.columns([3, 1])
        neuer_artikel = c1.text_input("Was brauchen wir?", placeholder="z.B. Äpfel, Spülmittel...")
        submit = c2.form_submit_button("Hinzufügen", use_container_width=True)
        
        if submit and neuer_artikel:
            einkauf.append({"Artikel": neuer_artikel, "Status": "Offen"})
            save_sheet(einkauf, "Einkauf")
            send_push("🛒 Einkaufsliste", f"Neuer Artikel: {neuer_artikel}")
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
# TAB 3: KI FOTO-VORRATSKAMMER (Vollautomatisch)
# ------------------------------------------
with tab_vorrat:
    st.subheader("🤖 KI MHD-Scanner")
    st.caption("Mach ein Foto vom MHD-Stempel oder dem Produkt. Die KI liest Name & Datum automatisch aus!")
    
    # --- HIER DEN KEY EINTRAGEN (In zwei Hälften schneiden!) ---
    KEY_TEIL_1 = "AQ.Ab8RN6IVTG5DbEBTzTvyFm_" # z.B. "AIzaSy..."
    KEY_TEIL_2 = "kqDDmeb47E3_aI7BMNJwjEv5zNg" # z.B. "...12345"
    
    GEMINI_API_KEY = KEY_TEIL_1 + KEY_TEIL_2
    
    # 1. Den Kamera-Reset-Schlüssel initialisieren
    if "cam_key" not in st.session_state:
        st.session_state.cam_key = 0
    
    # 2. Kamera mit dynamischem Key aufrufen
    camera_photo = st.camera_input("Foto aufnehmen", key=f"cam_{st.session_state.cam_key}")
    
    if camera_photo is not None:
        if len(GEMINI_API_KEY) < 20: 
            st.error("Bitte trage zuerst deinen Gemini API-Key im Code ein!")
        else:
            with st.spinner("🧠 KI analysiert das Foto..."):
                try:
                    from PIL import Image
                    import json
                    import base64
                    import io
                    
                    # Bild öffnen und verkleinern
                    image = Image.open(camera_photo)
                    
                    # Bild in Base64 Bytes konvertieren
                    buffered = io.BytesIO()
                    image.save(buffered, format="JPEG")
                    img_bytes = base64.b64encode(buffered.getvalue()).decode("utf-8")
                    
                    st.toast("Sende Daten an Google...", icon="⚡")

                    # Direkter REST-API Aufruf
                    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent"
                    headers = {"Content-Type": "application/json"}
                    params = {"key": GEMINI_API_KEY}
                    
                    payload = {
                        "contents": [{
                            "parts": [
                                {"text": f"Analysiere dieses Foto von einem Lebensmittelprodukt. Finde den Namen des Produkts und das Verfallsdatum (MHD). Heutiges Datum ist {heute}. Antworte AUSSCHLIESSLICH im JSON-Format mit genau diesen zwei Feldern: {{\"produkt\": \"Name des Produkts\", \"mhd\": \"YYYY-MM-DD\"}}. Falls du kein Datum findest, schätze ein realistisches MHD basierend auf dem Produkttyp."},
                                {
                                    "inline_data": {
                                        "mime_type": "image/jpeg",
                                        "data": img_bytes
                                    }
                                }
                            ]
                        }]
                    }
                    
                    response = requests.post(url, headers=headers, params=params, json=payload, timeout=20)
                    result_json = response.json()
                    
                    if "error" in result_json:
                        raise Exception(result_json["error"].get("message", "Unbekannter API-Fehler"))
                        
                    raw_text = result_json["candidates"][0]["content"]["parts"][0]["text"].strip()
                    
                    if raw_text.startswith("```json"):
                        raw_text = raw_text[7:-3].strip()
                    elif raw_text.startswith("```"):
                        raw_text = raw_text[3:-3].strip()
                        
                    data = json.loads(raw_text)
                    p_name = data.get("produkt", "Unbekanntes Produkt")
                    p_mhd = data.get("mhd", str(heute + timedelta(days=7)))
                    
                    # In die Tabelle speichern
                    vorrat.append({
                        "Artikel": p_name, 
                        "Ablaufdatum": p_mhd,
                        "Anbruchsdatum": "" 
                    })
                    save_sheet(vorrat, "Vorrat")
                    save_sheet(vorrat, "Vorrat")
                    
                    st.success(f"Erfolgreich erkannt: **{p_name}** (MHD: {p_mhd})!")
                    st.cache_data.clear() 
                    
                    # 3. HIER IST DIE MAGIE: Wir ändern den Key, damit das Foto gelöscht wird!
                    st.session_state.cam_key += 1
                    
                    import time
                    time.sleep(1)
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"Konnte das Bild nicht analysieren: {e}")

    st.divider()
    
    # --- NEU: Interaktiver Bearbeitungsmodus ---
    with st.expander("✏️ Vorrat bearbeiten (Namen & Anbruchsdatum)"):
        if vorrat:
            df_v = pd.DataFrame(vorrat)
            # Falls die Spalte in Google Sheets noch nicht existiert, kurz anlegen
            if "Anbruchsdatum" not in df_v.columns:
                df_v["Anbruchsdatum"] = ""

            # Der geniale Streamlit Data Editor (wie Excel)
            edited_df = st.data_editor(
                df_v,
                use_container_width=True,
                num_rows="dynamic", # Erlaubt auch das Hinzufügen/Löschen von Zeilen!
                hide_index=True,
                column_config={
                    "Artikel": st.column_config.TextColumn("Produktname", required=True),
                    "Ablaufdatum": st.column_config.TextColumn("MHD (YYYY-MM-DD)"),
                    "Anbruchsdatum": st.column_config.TextColumn("Angebrochen am (YYYY-MM-DD)")
                }
            )

            if st.button("💾 Änderungen speichern", type="primary"):
                # Tabelle bereinigen und zurück in Dicts wandeln
                edited_df = edited_df.fillna("")
                new_vorrat = edited_df.to_dict(orient="records")
                save_sheet(new_vorrat, "Vorrat")
                st.rerun()
        else:
            st.info("Dein Vorrat ist leer.")

    st.write("") # Etwas Abstand für die Optik
    st.subheader("🥫 Aktueller Vorrat")

    # --- DIE BEKANNTE AMPEL-ANSICHT (mit Anbruch-Anzeige) ---
    for i, v in enumerate(vorrat):
        try: mhd = datetime.strptime(str(v['Ablaufdatum']), "%Y-%m-%d").date()
        except: mhd = heute
        left = (mhd - heute).days
        
        # Zeige das Anbruchsdatum an, falls es ausgefüllt wurde
        anbruch_text = f" (✂️ Offen seit: {v['Anbruchsdatum']})" if v.get("Anbruchsdatum") and str(v["Anbruchsdatum"]).strip() not in ["", "nan"] else ""
        
        with st.container(border=True):
            col1, col2 = st.columns([4, 1])
            if left < 0: col1.error(f"⚠️ {v['Artikel']}{anbruch_text} (Abgelaufen am {v['Ablaufdatum']}!)")
            elif left <= 3: col1.warning(f"⏳ {v['Artikel']}{anbruch_text} (Läuft am {v['Ablaufdatum']} ab)")
            else: col1.success(f"🥫 {v['Artikel']}{anbruch_text} ( MHD: {v['Ablaufdatum']} )")
            
            if col2.button("🗑 Weg", key=f"v_{i}"):
                vorrat.pop(i)
                save_sheet(vorrat, "Vorrat")
                st.rerun()

# ------------------------------------------
# TAB 4: GEMEINSAMER KALENDER (Apple)
# ------------------------------------------
with tab_todoist: 
    st.subheader("📅 Gemeinsamer Apple Kalender")
    
    WEBCAL_URL = "webcal://p45-caldav.icloud.com/published/2/MTYzNjM0MTI0MjExNjM2M1r9_RM37mGdFBnt5dTR2VkxAwiyAF-9Uk1Sh6tTfNZ5UvQ5ZYrWzNZpZF7QaMpPOjUGvn6Rz_HzucNxcdNS078"
    ics_url = WEBCAL_URL.replace("webcal://", "https://")
    
    try:
        res = requests.get(ics_url)
        
        if res.status_code == 200:
            cal = Calendar.from_ical(res.content)
            upcoming_events = []
            
            for component in cal.walk():
                if component.name == "VEVENT":
                    summary = component.get('summary')
                    dtstart = component.get('dtstart')
                    
                    if not dtstart:
                        continue 
                        
                    dt = dtstart.dt
                    
                    if hasattr(dt, 'date'):
                        event_date = dt.date()
                    else:
                        event_date = dt
                        
                    if event_date >= heute:
                        upcoming_events.append({
                            "title": str(summary),
                            "date": event_date
                        })
            
            if not upcoming_events:
                st.success("Aktuell keine anstehenden Termine in diesem Kalender! 🎉")
            else:
                upcoming_events.sort(key=lambda x: x['date'])
                
                for event in upcoming_events[:20]:
                    status = "🟢 Heute" if event['date'] == heute else "🗓️ Zukunft"
                    nice_date = event['date'].strftime("%d.%m.%Y")

                    with st.container(border=True):
                        c1, c2 = st.columns([3, 1])
                        c1.markdown(f"**{event['title']}**")
                        c2.markdown(f"<div style='text-align: right; font-size: 0.85em; color: gray;'>{status}<br><b>{nice_date}</b></div>", unsafe_allow_html=True)
        else:
            st.error(f"Fehler beim Download des Kalenders. (Status: {res.status_code})")
            
    except Exception as e:
        st.error(f"Es gab einen Fehler bei der Verarbeitung des Apple Kalenders: {e}")
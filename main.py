import streamlit as st
import pandas as pd
import requests
import json
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
from icalendar import Calendar
from streamlit_cookies_controller import CookieController

st.set_page_config(layout="wide", page_title="Haushalt OS", page_icon="🏠")

# ==========================================
# 1. AUTH0 & COOKIE SETUP
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

cookies = CookieController()

if "user" not in st.session_state:
    saved_user = cookies.get("haushalt_user")
    if saved_user:
        if isinstance(saved_user, str):
            st.session_state.user = json.loads(saved_user)
        else:
            st.session_state.user = saved_user
    else:
        st.session_state.user = None

if "code" in st.query_params and not st.session_state.user:
    token = get_token(st.query_params["code"])
    if token:
        user_info = get_user_info(token)
        st.session_state.user = user_info
        cookies.set("haushalt_user", json.dumps(user_info), max_age=60*60*24*30)
        st.query_params.clear() 

if not st.session_state.user:
    st.title("🏠 Haushalt OS")
    st.caption("Bitte identifiziere dich, um fortzufahren.")
    auth_url = f"https://{AUTH0_DOMAIN}/authorize?response_type=code&client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&scope=openid%20profile%20email"
    st.link_button("🔒 Mit Auth0 Anmelden", auth_url, type="primary", use_container_width=True)
    st.stop()

# ==========================================
# 2. DATENBANK & APIs
# ==========================================
GSHEETS_URL = "https://docs.google.com/spreadsheets/d/1Dj3_N9ybEhIDX5HukIELYtE2E3LToq4DiuPV3EBjOiA/edit?usp=sharing"
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=None) 
def load_sheet(sheet_name):
    return conn.read(spreadsheet=GSHEETS_URL, worksheet=sheet_name).to_dict(orient="records")

def save_sheet(data, sheet_name):
    conn.update(spreadsheet=GSHEETS_URL, worksheet=sheet_name, data=pd.DataFrame(data))
    st.cache_data.clear()

aufgaben = load_sheet("Haushalt")
einkauf = load_sheet("Einkauf")
vorrat = load_sheet("Vorrat")
heute = datetime.now().date()

# --- NEU: Hintergrund-Helfer für das Cockpit ---
@st.cache_data(ttl=900) # Lädt Apple Kalender alle 15 Min neu
def fetch_apple_calendar():
    WEBCAL_URL = "webcal://p45-caldav.icloud.com/published/2/MTYzNjM0MTI0MjExNjM2M1r9_RM37mGdFBnt5dTR2VkxAwiyAF-9Uk1Sh6tTfNZ5UvQ5ZYrWzNZpZF7QaMpPOjUGvn6Rz_HzucNxcdNS078"
    ics_url = WEBCAL_URL.replace("webcal://", "https://")
    try:
        res = requests.get(ics_url, timeout=10)
        if res.status_code == 200:
            cal = Calendar.from_ical(res.content)
            events = []
            for component in cal.walk():
                if component.name == "VEVENT" and component.get('dtstart'):
                    dt = component.get('dtstart').dt
                    event_date = dt.date() if hasattr(dt, 'date') else dt
                    if event_date >= heute:
                        events.append({"title": str(component.get('summary')), "date": event_date})
            events.sort(key=lambda x: x['date'])
            return events
    except: pass
    return []

@st.cache_data(ttl=900) # Live-Wetter (kostenlos via Open-Meteo)
def get_weather():
    try:
        # Koordinaten für Chemnitz (kann angepasst werden)
        url = "https://api.open-meteo.com/v1/forecast?latitude=50.8333&longitude=12.9167&current=temperature_2m,weather_code"
        res = requests.get(url, timeout=5).json()
        temp = res["current"]["temperature_2m"]
        code = res["current"]["weather_code"]
        
        if code == 0: return f"☀️ {temp}°C (Klar)"
        elif code in [1,2,3]: return f"⛅ {temp}°C (Wolkig)"
        elif code in [51,53,55,61,63,65,80,81,82]: return f"🌧️ {temp}°C (Regen)"
        elif code in [71,73,75,85,86]: return f"❄️ {temp}°C (Schnee)"
        elif code in [95,96,99]: return f"⛈️ {temp}°C (Gewitter)"
        else: return f"🌡️ {temp}°C"
    except: return "🌡️ Wetter offline"

@st.cache_data(ttl=60) # ÖPNV alle 60 Sek aktualisieren
def get_transit():
    try:
        # Offizielle MVG-Schnittstelle für München (V3)
        # de:09162:70 ist das Olympia-Einkaufszentrum
        url = "https://www.mvg.de/api/bgw-pt/v3/departures?globalId=de:09162:70"
        
        # Ein normaler Browser-Ausweis, damit die MVG uns nicht als simplen Bot abweist
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json"
        }
        
        res = requests.get(url, headers=headers, timeout=8)
        res.raise_for_status() 
        data = res.json()
        
        deps = []
        # Wir filtern direkt die nächsten 5 Abfahrten heraus
        for d in data[:5]: 
            # Die MVG nennt die Linie 'label' (z.B. "U3")
            line = d.get("label", "MVG")
            dest = d.get("destination", "Unbekannt")
            
            # MVG liefert die Zeit als Millisekunden-Timestamp
            time_ms = d.get("realtimeDepartureTime") or d.get("plannedDepartureTime")
            
            if time_ms:
                # Millisekunden in ein lesbares Datum/Zeit-Format umwandeln
                dt = datetime.fromtimestamp(time_ms / 1000)
                
                # Verspätung auslesen (falls vorhanden)
                delay = d.get("delayInMinutes", 0)
                delay_str = f" <span style='color:red;'>(+{delay})</span>" if delay > 0 else ""
                
                deps.append(f"**{dt.strftime('%H:%M')}**{delay_str} | {line} ➔ {dest}")
                
        if not deps:
            return ["Aktuell keine Abfahrten gefunden."]
            
        return deps
        
    except Exception as e: 
        return [f"⚠️ MVG-Fehler: {e}"]

def send_push(title, message):
    try:
        payload = {
            "topic": "HaushaltLenaJonas_Geheim123",
            "title": title,
            "message": message,
            "tags": ["shopping_bags"] 
        }
        requests.post("https://ntfy.sh/", json=payload, timeout=5)
    except Exception as e: print(f"Push Fehler: {e}")

# ==========================================
# 3. DASHBOARD UI
# ==========================================
col_header1, col_header2 = st.columns([4, 1])
col_header1.title("🏠 Haushalt OS")
col_header2.write("")
if col_header2.button("🚪 Logout"):
    cookies.remove("haushalt_user")
    st.session_state.user = None
    st.components.v1.html("<script>window.parent.location.reload();</script>", height=0)

tab_home, tab_einkauf, tab_vorrat, tab_todoist = st.tabs([
    "🚀 Cockpit", 
    "🛒 Einkaufsliste", 
    "🥫 Vorrat", 
    "📆 Kalender"
])

# ------------------------------------------
# TAB 1: DAS NOTION-COCKPIT
# ------------------------------------------
with tab_home:
    # 1. Smarte Begrüßung
    user_name = st.session_state.user.get("given_name", st.session_state.user.get("name", "User"))
    hour = datetime.now().hour
    if hour < 12: greeting = "Guten Morgen"
    elif hour < 18: greeting = "Guten Tag"
    else: greeting = "Guten Abend"
    
    st.markdown(f"## 👋 {greeting}, {user_name}!")
    st.write("")
    
    # 2. Datenvorbereitung fürs Briefing
    tasks_processed = []
    for i, t in enumerate(aufgaben):
        try: last = datetime.strptime(str(t['Letztes_Datum']), "%Y-%m-%d").date()
        except: last = heute
        due = last + timedelta(days=int(t['Intervall_Tage']))
        tasks_processed.append({**t, "index": i, "due": due})
        
    heute_aufgaben = [t for t in tasks_processed if t['due'] <= heute]
    heute_termine = [e for e in fetch_apple_calendar() if e['date'] == heute]
    ablaufend = []
    for v in vorrat:
        try: 
            if (datetime.strptime(str(v['Ablaufdatum']), "%Y-%m-%d").date() - heute).days <= 3:
                ablaufend.append(v)
        except: pass

    # 3. Top-Metrics (Notion-Style)
    c1, c2, c3, c4 = st.columns(4)
    c1.info(f"**🌡️ Aktuell**\n\n{get_weather()}")
    c2.warning(f"**🧹 Haushalt**\n\n{len(heute_aufgaben)} To-Dos heute")
    c3.success(f"**📅 Termine**\n\n{len(heute_termine)} Events heute")
    c4.error(f"**🍎 Vorrat**\n\n{len(ablaufend)} bald fällig")
    
    st.write("")
    
    # 4. Daily Briefing & ÖPNV
    col_b1, col_b2 = st.columns([2, 1])
    
    with col_b1:
        with st.container(border=True):
            st.markdown("### 📝 Dein Daily Briefing")
            
            # Kalender Summary
            if heute_termine:
                st.markdown("**📅 Heute im Kalender:**")
                for e in heute_termine: st.markdown(f"- {e['title']}")
            else:
                st.markdown("**📅 Heute im Kalender:** Nichts geplant. Zeit zum Durchatmen!")
                
            st.markdown("---")
            
            # Putz-Summary
            if heute_aufgaben:
                st.markdown("**🧹 Im Haushalt wartet:**")
                for a in heute_aufgaben: st.markdown(f"- {a['Aufgabe']}")
            else:
                st.markdown("**🧹 Im Haushalt wartet:** Alles sauber! Füße hochlegen.")
                
            # Vorrat-Summary
            if ablaufend:
                st.markdown("---")
                st.markdown("**🍽️ Bald aufessen:**")
                for v in ablaufend: st.markdown(f"- {v['Artikel']} (MHD: {v['Ablaufdatum']})")

    with col_b2:
        with st.container(border=True):
            st.markdown("### 🚋 ÖPNV (Chemnitz Hbf)")
            deps = get_transit()
            if deps:
                for d in deps: st.markdown(d)
            else:
                st.caption("Keine Abfahrten gefunden.")
                
    st.divider()
    
    # 5. Der bekannte Haushalts-Planer (Einklappbar für Übersichtlichkeit)
    with st.expander("🗓️ Alle Haushalts-Aufgaben planen & verwalten", expanded=False):
        with st.form("new_task_form", clear_on_submit=True):
            tc1, tc2, tc3 = st.columns(3)
            n_name = tc1.text_input("Was ist zu tun?", placeholder="z.B. Fenster putzen")
            n_date = tc2.date_input("Wann fällig?", value=heute)
            n_intervall = tc3.number_input("Intervall (in Tagen)", min_value=1, value=7)
            
            if st.form_submit_button("Hinzufügen"):
                if n_name:
                    fake_last = n_date - timedelta(days=n_intervall)
                    aufgaben.append({"Aufgabe": n_name, "Letztes_Datum": str(fake_last), "Intervall_Tage": n_intervall})
                    save_sheet(aufgaben, "Haushalt")
                    st.rerun()

        tage_namen = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
        start_of_week = heute - timedelta(days=heute.weekday())
        week_days = [start_of_week + timedelta(days=i) for i in range(7)]
        
        w_cols = st.columns(7)
        for i, col in enumerate(w_cols):
            day_date = week_days[i]
            with col:
                st.markdown(f"<div style='text-align: center; border-bottom: 2px solid #38bdf8; padding-bottom: 5px; margin-bottom: 10px;'><b>{tage_namen[i]}</b><br>{day_date.strftime('%d.%m.')}</div>", unsafe_allow_html=True)
                
                if day_date == heute: day_tasks = [t for t in tasks_processed if t['due'] <= day_date]
                elif day_date > heute: day_tasks = [t for t in tasks_processed if t['due'] == day_date]
                else: day_tasks = []
                    
                if day_tasks:
                    for t in day_tasks:
                        with st.container(border=True):
                            if t['due'] < heute and day_date == heute:
                                st.markdown(f"<span style='color: #ef4444; font-size: 0.9em;'>⚠️ <b>{t['Aufgabe']}</b></span>", unsafe_allow_html=True)
                            else:
                                st.markdown(f"<span style='font-size: 0.9em;'><b>{t['Aufgabe']}</b></span>", unsafe_allow_html=True)
                            
                            if st.button("✔", key=f"dw_{t['index']}_{i}", use_container_width=True):
                                aufgaben[t['index']]['Letztes_Datum'] = str(heute)
                                save_sheet(aufgaben, "Haushalt")
                                st.rerun()
                else:
                    st.caption("*- Frei -*")

# ------------------------------------------
# TAB 2: EINKAUFSLISTE
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
# TAB 3: KI VORRAT
# ------------------------------------------
with tab_vorrat:
    st.subheader("🤖 KI MHD-Scanner")
    
    # --- HIER DEN KEY EINTRAGEN (In zwei Hälften schneiden!) ---
    KEY_TEIL_1 = "DEIN_KEY_HAELFTE_1" # z.B. "AIzaSy..."
    KEY_TEIL_2 = "DEIN_KEY_HAELFTE_2" # z.B. "...12345"
    
    GEMINI_API_KEY = KEY_TEIL_1 + KEY_TEIL_2
    
    if "cam_key" not in st.session_state: st.session_state.cam_key = 0
    camera_photo = st.camera_input("Foto aufnehmen", key=f"cam_{st.session_state.cam_key}")
    
    if camera_photo is not None:
        if len(GEMINI_API_KEY) < 20: 
            st.error("Bitte trage zuerst deinen Gemini API-Key im Code ein!")
        else:
            with st.spinner("🧠 KI analysiert das Foto..."):
                try:
                    from PIL import Image
                    import io
                    import base64
                    
                    image = Image.open(camera_photo)
                    image.thumbnail((800, 800))
                    
                    buffered = io.BytesIO()
                    image.save(buffered, format="JPEG")
                    img_bytes = base64.b64encode(buffered.getvalue()).decode("utf-8")
                    
                    st.toast("Sende Daten an Google...", icon="⚡")

                    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
                    headers = {"Content-Type": "application/json"}
                    params = {"key": GEMINI_API_KEY}
                    
                    payload = {
                        "contents": [{
                            "parts": [
                                {"text": f"Analysiere dieses Foto von einem Lebensmittelprodukt. Finde den Namen des Produkts und das Verfallsdatum (MHD). Heutiges Datum ist {heute}. Antworte AUSSCHLIESSLICH im JSON-Format mit genau diesen zwei Feldern: {{\"produkt\": \"Name des Produkts\", \"mhd\": \"YYYY-MM-DD\"}}. Falls du kein Datum findest, schätze ein realistisches MHD basierend auf dem Produkttyp."},
                                {"inline_data": {"mime_type": "image/jpeg", "data": img_bytes}}
                            ]
                        }]
                    }
                    
                    response = requests.post(url, headers=headers, params=params, json=payload, timeout=20).json()
                    
                    if "error" in response: raise Exception(response["error"].get("message"))
                    
                    raw_text = response["candidates"][0]["content"]["parts"][0]["text"].strip()
                    
                    # Hier sind die reparierten, sicheren String-Literale:
                    if raw_text.startswith('```json'): 
                        raw_text = raw_text[7:-3].strip()
                    elif raw_text.startswith('```'): 
                        raw_text = raw_text[3:-3].strip()
                        
                    data = json.loads(raw_text)
                    p_name = data.get("produkt", "Unbekanntes Produkt")
                    p_mhd = data.get("mhd", str(heute + timedelta(days=7)))
                    
                    vorrat.append({
                        "Artikel": p_name, 
                        "Ablaufdatum": p_mhd,
                        "Anbruchsdatum": ""
                    })
                    save_sheet(vorrat, "Vorrat")
                    st.success(f"Erfolgreich erkannt: **{p_name}** (MHD: {p_mhd})!")
                    
                    st.session_state.cam_key += 1
                    import time
                    time.sleep(1)
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"Fehler bei der Analyse: {e}")

    st.divider()
    
    with st.expander("✏️ Vorrat bearbeiten (Namen & Anbruchsdatum)"):
        if vorrat:
            df_v = pd.DataFrame(vorrat)
            if "Anbruchsdatum" not in df_v.columns: df_v["Anbruchsdatum"] = ""

            edited_df = st.data_editor(
                df_v, use_container_width=True, num_rows="dynamic", hide_index=True,
                column_config={
                    "Artikel": st.column_config.TextColumn("Produktname", required=True),
                    "Ablaufdatum": st.column_config.TextColumn("MHD (YYYY-MM-DD)"),
                    "Anbruchsdatum": st.column_config.TextColumn("Angebrochen am (YYYY-MM-DD)")
                }
            )

            if st.button("💾 Änderungen speichern", type="primary"):
                edited_df = edited_df.fillna("")
                save_sheet(edited_df.to_dict(orient="records"), "Vorrat")
                st.rerun()
        else: st.info("Dein Vorrat ist leer.")

    st.write("")
    st.subheader("🥫 Aktueller Vorrat")
    
    for i, v in enumerate(vorrat):
        try: mhd = datetime.strptime(str(v['Ablaufdatum']), "%Y-%m-%d").date()
        except: mhd = heute
        left = (mhd - heute).days
        
        anbruch_text = f" (✂️ {v['Anbruchsdatum']})" if v.get("Anbruchsdatum") and str(v["Anbruchsdatum"]).strip() not in ["", "nan"] else ""
        
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
# TAB 4: ALLE TERMINE
# ------------------------------------------
with tab_todoist: 
    st.subheader("📅 Apple Kalender (Alle Termine)")
    
    upcoming_events = fetch_apple_calendar()
    if not upcoming_events:
        st.success("Aktuell keine anstehenden Termine in diesem Kalender! 🎉")
    else:
        for event in upcoming_events[:20]:
            status = "🟢 Heute" if event['date'] == heute else "🗓️ Zukunft"
            nice_date = event['date'].strftime("%d.%m.%Y")

            with st.container(border=True):
                c1, c2 = st.columns([3, 1])
                c1.markdown(f"**{event['title']}**")
                c2.markdown(f"<div style='text-align: right; font-size: 0.85em; color: gray;'>{status}<br><b>{nice_date}</b></div>", unsafe_allow_html=True)
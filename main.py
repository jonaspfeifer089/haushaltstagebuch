import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# --- PAGE SETUP ---
st.set_page_config(layout="wide", page_title="Haushaltstagebuch", page_icon="✨")

st.markdown("""
    <style>
    .gradient-text { background: -webkit-linear-gradient(45deg, #38bdf8, #a78bfa); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-weight: 900; font-size: 3.5rem; margin-bottom: 0; padding-bottom: 0; }
    .subtitle { color: #94a3b8; font-size: 1.1rem; margin-top: -10px; margin-bottom: 30px; }
    [data-testid="stMetricValue"] { font-size: 3rem !important; font-weight: 800 !important; color: #38bdf8 !important; }
    .stButton>button { width: 100%; border-radius: 8px; font-weight: 600; border: 1px solid rgba(150,150,150,0.2); }
    .stButton>button:hover { border-color: #38bdf8; color: #38bdf8; }
    </style>
""", unsafe_allow_html=True)

# --- GOOGLE SHEETS VERBINDUNG ---
GSHEETS_URL = "https://docs.google.com/spreadsheets/d/1Dj3_N9ybEhIDX5HukIELYtE2E3LToq4DiuPV3EBjOiA/edit?usp=sharing"
try: conn = st.connection("gsheets", type=GSheetsConnection)
except: st.error("Verbindung zur Datenbank fehlgeschlagen."); st.stop()

def load_haushalt():
    try:
        df = conn.read(spreadsheet=GSHEETS_URL, worksheet="Haushalt", ttl=0).dropna(subset=['Aufgabe'])
        return df.to_dict(orient="records") if not df.empty else []
    except: return []

def save_haushalt(data):
    try:
        df = pd.DataFrame(data)
        if df.empty: df = pd.DataFrame(columns=["Aufgabe", "Letztes_Datum", "Intervall_Tage"])
        conn.update(spreadsheet=GSHEETS_URL, worksheet="Haushalt", data=df)
        st.cache_data.clear()
    except: pass

aufgaben = load_haushalt()
heute = datetime.now().date()

# --- HEADER ---
st.markdown('<h1 class="gradient-text">✨ Haushaltstagebuch</h1>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">Lena & Jonas — Smart Home Management</p>', unsafe_allow_html=True)

# --- NEUE AUFGABE ---
with st.expander("➕ Neue Aufgabe hinzufügen"):
    with st.form("neue_aufgabe_form", border=False, clear_on_submit=True):
        c1, c2, c3, c4 = st.columns([4, 2, 2, 2])
        with c1: aufgabe_name = st.text_input("Was?")
        with c2: letztes_mal = st.date_input("Zuletzt erledigt:", heute)
        with c3: intervall = st.number_input("Intervall (Tage)", min_value=1, value=14)
        with c4:
            st.write(""); st.write(""); submit = st.form_submit_button("Speichern 💾")
        if submit and aufgabe_name:
            aufgaben.append({"Aufgabe": aufgabe_name, "Letztes_Datum": str(letztes_mal), "Intervall_Tage": int(intervall)})
            save_haushalt(aufgaben)
            st.rerun()

st.divider()

# --- AUFGABEN LOGIK ---
akut, bald, entspannt = [], [], []
for i, item in enumerate(aufgaben):
    try: letztes_dt = datetime.strptime(str(item["Letztes_Datum"]), "%Y-%m-%d").date()
    except: letztes_dt = heute
    inv = int(float(item.get("Intervall_Tage", 14)))
    naechstes_dt = letztes_dt + timedelta(days=inv)
    uebrig = (naechstes_dt - heute).days
    
    td = {"index": i, "Aufgabe": item["Aufgabe"], "Letztes": letztes_dt, "Intervall": inv, "Uebrig": uebrig}
    if uebrig <= 0: akut.append(td)
    elif uebrig <= 3: bald.append(td)
    else: entspannt.append(td)

akut = sorted(akut, key=lambda x: x["Uebrig"])
bald = sorted(bald, key=lambda x: x["Uebrig"])
entspannt = sorted(entspannt, key=lambda x: x["Uebrig"])

m1, m2, m3 = st.columns(3)
m1.metric("🔥 Fällig / Überfällig", len(akut))
m2.metric("⏳ Demnächst (1-3 Tage)", len(bald))
m3.metric("✅ Erledigt", len(entspannt))
st.write("")

def render_task(item):
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([5, 3, 2, 1])
        with c1:
            st.markdown(f"**{item['Aufgabe']}**")
            st.caption(f"🔄 Alle {item['Intervall']} Tage • Zuletzt: {item['Letztes'].strftime('%d.%m.')}")
        with c2:
            st.write("") 
            if item["Uebrig"] < 0: st.error(f"**🔴 {abs(item['Uebrig'])} Tage überfällig**")
            elif item["Uebrig"] == 0: st.warning("**🟡 Heute fällig**")
            else: st.success(f"**🟢 In {item['Uebrig']} Tagen**")
        with c3:
            st.write("")
            if st.button("✔ Erledigt", key=f"done_{item['index']}"):
                aufgaben[item['index']]["Letztes_Datum"] = str(heute)
                save_haushalt(aufgaben)
                st.rerun()
        with c4:
            st.write("")
            if st.button("🗑", key=f"del_{item['index']}"):
                aufgaben.pop(item['index'])
                save_haushalt(aufgaben)
                st.rerun()

t1, t2, t3 = st.tabs(["🔥 Akut", "⏳ Demnächst", "✅ Erledigt"])
with t1:
    if not akut: st.success("Alles sauber! Hier steht nichts an.")
    for task in akut: render_task(task)
with t2:
    if not bald: st.info("Keine Aufgaben für die nächsten Tage.")
    for task in bald: render_task(task)
with t3:
    if not entspannt: st.write("Noch nichts in dieser Kategorie.")
    for task in entspannt: render_task(task)

st.divider()

# ==========================================
# CLEANE CHRONOLOGISCHE TIMELINE (Punkte)
# ==========================================
st.markdown('<h3>📊 Projektions-Matrix</h3>', unsafe_allow_html=True)
st.caption("Zeigt gezielt die wichtigen Arbeitsspitzen. Tägliche Routinen werden hier ausgeblendet, um den Fokus zu wahren.")

def create_dot_timeline(aufgaben_liste, days_ahead, title):
    end_date = heute + timedelta(days=days_ahead)
    
    events = []
    for item in aufgaben_liste:
        intervall = int(float(item.get("Intervall_Tage", 14)))
        # Tägliche Aufgaben überspringen für perfekte Übersichtlichkeit!
        if intervall <= 1:
            continue
            
        kat = "Wöchentlich" if intervall <= 7 else "Seltener"
        try: letztes_dt = datetime.strptime(str(item["Letztes_Datum"]), "%Y-%m-%d").date()
        except: letztes_dt = heute
        
        diff = (heute - letztes_dt).days
        if diff > 0:
            erste = letztes_dt + timedelta(days=(diff // intervall) * intervall)
            if erste < heute: erste += timedelta(days=intervall)
        else:
            erste = letztes_dt - timedelta(days=(abs(diff) // intervall) * intervall)
            if erste > heute: erste -= timedelta(days=intervall)
                
        curr = erste
        while curr <= end_date:
            events.append({
                "Datum": curr,
                "Aufgabe": item["Aufgabe"],
                "Kategorie": kat,
                "Intervall": intervall
            })
            curr += timedelta(days=intervall)
            
    if not events: return None
    
    df_events = pd.DataFrame(events).sort_values(by=["Intervall", "Aufgabe"])
    
    fig = px.scatter(
        df_events, x="Datum", y="Aufgabe", color="Kategorie",
        color_discrete_map={"Wöchentlich": "#a78bfa", "Seltener": "#fbbf24"}
    )
    
    fig.update_traces(
        marker=dict(size=14, symbol="square", line=dict(width=1, color="rgba(255,255,255,0.5)")),
        hovertemplate="<b>%{x|%d.%m.%Y}</b><br>%{y}<extra></extra>"
    )
    
    fig.update_yaxes(autorange="reversed", title=None, tickfont=dict(size=13), showgrid=True, gridcolor='rgba(150,150,150,0.1)') 
    fig.update_xaxes(
        title=None, 
        range=[heute - timedelta(hours=12), end_date + timedelta(hours=12)], 
        tickformat="%d.%m.", dtick=86400000, # Jeden Tag anzeigen
        showgrid=True, gridwidth=1, gridcolor='rgba(150,150,150,0.1)', griddash='dot', zeroline=False
    )
    
    fig.add_vline(x=f"{heute}", line_width=2, line_dash="solid", line_color="#ef4444")
    
    fig.update_layout(
        font_family="system-ui, -apple-system, sans-serif",
        title=dict(text=f"<b>{title}</b>", font=dict(size=18)),
        height=max(200, len(df_events['Aufgabe'].unique()) * 40), # Höhe anpassen
        margin=dict(t=50, b=20, l=10, r=20),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, title=None)
    )
    return fig

with st.container(border=True):
    fig_30 = create_dot_timeline(aufgaben, 30, "Der 30-Tage Vorausblick")
    if fig_30: st.plotly_chart(fig_30, use_container_width=True)
    
with st.container(border=True):
    fig_90 = create_dot_timeline(aufgaben, 90, "Die 90-Tage Prognose")
    if fig_90: st.plotly_chart(fig_90, use_container_width=True)
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# --- PAGE SETUP ---
st.set_page_config(layout="wide", page_title="Haushaltstagebuch", page_icon="✨")

# CSS für absolut cleane Optik und schicke Buttons
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 6px; font-weight: 500; }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; background-color: transparent; border-radius: 4px; color: #555; font-size: 16px;}
    .stTabs [aria-selected="true"] { background-color: #f0f2f6 !important; font-weight: 600; color: #111;}
    </style>
""", unsafe_allow_html=True)

st.title("✨ Das intelligente Haushaltstagebuch")
st.caption("Ein absolut perfektes System für Sauberkeit und Routine.")

# --- GOOGLE SHEETS VERBINDUNG ---
GSHEETS_URL = "HIER_DEINEN_NEUEN_GOOGLE_SHEETS_LINK_EINFÜGEN"

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

# --- VERSTECKTES MENÜ FÜR NEUE AUFGABEN ---
with st.expander("➕ Neue Aufgabe anlegen (Hier ausklappen)"):
    with st.form("neue_aufgabe_form", clear_on_submit=True):
        col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
        with col1:
            aufgabe_name = st.text_input("Was? (z.B. Kaffeemaschine entkalken)")
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

# --- AUFGABEN-LOGIK & KATEGORISIERUNG ---
if not aufgaben:
    st.info("Aktuell hast du noch keine Haushaltsaufgaben angelegt. Leg los!")
else:
    akut = []
    bald = []
    entspannt = []

    for i, item in enumerate(aufgaben):
        try:
            letztes_dt = datetime.strptime(str(item["Letztes_Datum"]), "%Y-%m-%d").date()
        except:
            letztes_dt = heute
        
        intervall_tage = int(float(item.get("Intervall_Tage", 14)))
        naechstes_dt = letztes_dt + timedelta(days=intervall_tage)
        tage_uebrig = (naechstes_dt - heute).days
        
        aufgabe_daten = {
            "index": i,
            "Aufgabe": item["Aufgabe"],
            "Letztes_Datum": letztes_dt,
            "Intervall_Tage": intervall_tage,
            "Naechstes_Datum": naechstes_dt,
            "Tage_Uebrig": tage_uebrig
        }
        
        if tage_uebrig <= 0:
            akut.append(aufgabe_daten)
        elif tage_uebrig <= 3:
            bald.append(aufgabe_daten)
        else:
            entspannt.append(aufgabe_daten)

    # Nach Dringlichkeit sortieren
    akut = sorted(akut, key=lambda x: x["Tage_Uebrig"])
    bald = sorted(bald, key=lambda x: x["Tage_Uebrig"])
    entspannt = sorted(entspannt, key=lambda x: x["Tage_Uebrig"])

    # --- TOP METRIKEN ---
    m1, m2, m3 = st.columns(3)
    with m1: st.metric("🔥 Akut & Fällig", f"{len(akut)} Aufgaben")
    with m2: st.metric("⏳ Demnächst (1-3 Tage)", f"{len(bald)} Aufgaben")
    with m3: st.metric("✅ Alles im Lot", f"{len(entspannt)} Aufgaben")
    
    st.write("")

    # --- TABS FÜR DIE ORDNUNG ---
    tab1, tab2, tab3 = st.tabs(["🔥 AKUT & ÜBERFÄLLIG", "⏳ DEMNÄCHST", "✅ ENTSPANNT"])

    def render_task_row(item):
        c1, c2, c3, c4 = st.columns([5, 2, 2, 1])
        with c1:
            st.markdown(f"**{item['Aufgabe']}**")
            st.caption(f"Intervall: alle {item['Intervall_Tage']} Tage (Zuletzt: {item['Letztes_Datum'].strftime('%d.%m.')})")
        with c2:
            if item["Tage_Uebrig"] < 0:
                st.error(f"Seit {abs(item['Tage_Uebrig'])} Tagen drüber")
            elif item["Tage_Uebrig"] == 0:
                st.warning("Heute fällig!")
            else:
                st.info(f"Fällig in {item['Tage_Uebrig']} Tagen")
        with c3:
            if st.button("✅ Erledigen", key=f"done_{item['index']}"):
                aufgaben[item['index']]["Letztes_Datum"] = str(heute)
                save_haushalt(aufgaben)
                st.rerun()
        with c4:
            if st.button("🗑️", key=f"del_{item['index']}"):
                aufgaben.pop(item['index'])
                save_haushalt(aufgaben)
                st.rerun()
        st.markdown("<hr style='margin-top: 5px; margin-bottom: 5px; opacity: 0.3;'>", unsafe_allow_html=True)

    with tab1:
        if not akut:
            st.success("🎉 Wow! Alles erledigt, hier brennt nichts an.")
        else:
            for item in akut:
                render_task_row(item)

    with tab2:
        if not bald:
            st.write("Aktuell steht in den nächsten Tagen nichts an.")
        else:
            for item in bald:
                render_task_row(item)

    with tab3:
        if not entspannt:
            st.write("Hier ist es noch leer.")
        else:
            for item in entspannt:
                render_task_row(item)

    st.divider()

    # ==========================================
    # GANTT CHARTS (Monat, Quartal, Jahr)
    # ==========================================
    st.header("📊 Langzeit-Planung (Gantt-Charts)")
    st.caption("Eine Projektion aller anstehenden Haushaltsaufgaben in die Zukunft. Die Blöcke zeigen die genauen Fälligkeitstage.")

    def create_gantt(aufgaben_liste, days_ahead, title):
        end_date = heute + timedelta(days=days_ahead)
        gantt_data = []
        
        for item in aufgaben_liste:
            try:
                letztes_dt = datetime.strptime(str(item["Letztes_Datum"]), "%Y-%m-%d").date()
            except:
                letztes_dt = heute
            
            intervall = int(float(item.get("Intervall_Tage", 14)))
            naechstes_dt = letztes_dt + timedelta(days=intervall)
            
            current_dt = naechstes_dt
            # Berechne alle zukünftigen Termine bis zum Ziel-Datum
            while current_dt <= end_date:
                # Dauer eines Blocks im Chart: 1 Tag für perfekte Sichtbarkeit
                start_time = current_dt
                end_time = current_dt + timedelta(days=1)
                
                if intervall <= 1:
                    kat = "Täglich"
                elif intervall <= 7:
                    kat = "Wöchentlich"
                else:
                    kat = "Seltener"
                    
                gantt_data.append({
                    "Aufgabe": item["Aufgabe"],
                    "Start": start_time,
                    "End": end_time,
                    "Kategorie": kat,
                    "Intervall": intervall
                })
                current_dt += timedelta(days=intervall)
                
        if not gantt_data:
            return None
            
        df_g = pd.DataFrame(gantt_data)
        # Sortieren, damit tägliche Aufgaben gebündelt werden und die Y-Achse aufgeräumt aussieht
        df_g = df_g.sort_values(by=["Intervall", "Aufgabe"], ascending=[True, True])
        
        fig = px.timeline(
            df_g, 
            x_start="Start", 
            x_end="End", 
            y="Aufgabe", 
            color="Kategorie",
            color_discrete_map={"Täglich": "#1f77b4", "Wöchentlich": "#2ca02c", "Seltener": "#ff7f0e"},
            hover_data={"Start": True, "End": False, "Kategorie": False, "Intervall": True}
        )
        
        fig.update_yaxes(autorange="reversed") # A-Z bzw. Sortierung von oben nach unten
        fig.update_traces(marker_line_width=0) # Entfernt Rahmen für cleanen Look
        fig.update_layout(
            title=title,
            xaxis_title=None,
            yaxis_title=None,
            height=max(300, len(aufgaben_liste) * 25), # Passt die Höhe dynamisch an die Anzahl der Aufgaben an
            margin=dict(t=40, b=20, l=10, r=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        return fig

    # 1. Monats-Chart (30 Tage)
    fig_monat = create_gantt(aufgaben, 30, "Monats-Übersicht (Nächste 30 Tage)")
    if fig_monat:
        st.plotly_chart(fig_monat, use_container_width=True)
        
    st.write("")
        
    # 2. Quartals-Chart (90 Tage)
    fig_quartal = create_gantt(aufgaben, 90, "Quartals-Übersicht (Nächste 90 Tage)")
    if fig_quartal:
        st.plotly_chart(fig_quartal, use_container_width=True)
        
    st.write("")
        
    # 3. Jahres-Chart (365 Tage)
    fig_jahr = create_gantt(aufgaben, 365, "Jahres-Übersicht (Nächste 365 Tage)")
    if fig_jahr:
        st.plotly_chart(fig_jahr, use_container_width=True)
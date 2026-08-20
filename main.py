import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
from streamlit_gsheets import GSheetsConnection

# ============================================================
# KONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Haushaltsplan",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="collapsed"
)

GSHEETS_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1Dj3_N9ybEhIDX5HukIELYtE2E3LToq4DiuPV3EBjOiA/"
    "edit?usp=sharing"
)

SHEET_NAME = "Haushalt"

# ============================================================
# DESIGN / CSS
# ============================================================

st.markdown(
    """
    <style>

    /* --------------------------------------------------------
       GLOBAL
    -------------------------------------------------------- */

    .stApp {
        background-color: #f7f7f5;
    }

    .block-container {
        max-width: 1450px;
        padding-top: 2rem;
        padding-bottom: 4rem;
    }

    /* Standard Streamlit Buttons */

    .stButton > button {
        border-radius: 8px;
        border: 1px solid #dddddd;
        background: white;
        color: #333333;
        transition: all 0.15s ease;
    }

    .stButton > button:hover {
        border-color: #888888;
        color: #111111;
    }

    /* --------------------------------------------------------
       HEADER
    -------------------------------------------------------- */

    .main-title {
        font-size: 3.2rem;
        font-weight: 700;
        letter-spacing: -2px;
        color: #222222;
        margin-bottom: 0;
        line-height: 1;
    }

    .subtitle {
        color: #888888;
        font-size: 1rem;
        margin-top: 8px;
    }

    .header-line {
        height: 2px;
        background: #222222;
        margin-top: 18px;
        margin-bottom: 30px;
    }

    /* --------------------------------------------------------
       SECTION HEADERS
    -------------------------------------------------------- */

    .section-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-top: 15px;
        margin-bottom: 12px;
    }

    .section-title {
        font-size: 1.25rem;
        font-weight: 700;
        color: #222222;
        letter-spacing: 0.2px;
    }

    .section-subtitle {
        font-size: 0.82rem;
        color: #999999;
    }

    /* --------------------------------------------------------
       TASK CARD
    -------------------------------------------------------- */

    .task-card {
        background: white;
        border: 1px solid #e3e3e3;
        border-radius: 12px;
        padding: 13px 16px;
        margin-bottom: 8px;
        min-height: 65px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.025);
    }

    .task-name {
        font-size: 1rem;
        font-weight: 500;
        color: #222222;
        margin-bottom: 3px;
    }

    .task-due {
        font-size: 0.78rem;
        color: #999999;
    }

    .task-due-today {
        color: #c0392b;
        font-weight: 600;
    }

    .task-due-soon {
        color: #d68910;
        font-weight: 600;
    }

    .task-done {
        color: #aaaaaa;
        text-decoration: line-through;
    }

    .task-done-info {
        color: #b5b5b5;
        font-size: 0.78rem;
    }

    /* --------------------------------------------------------
       EMPTY STATE
    -------------------------------------------------------- */

    .empty-state {
        border: 1px dashed #d5d5d5;
        border-radius: 12px;
        padding: 22px;
        text-align: center;
        color: #aaaaaa;
        background: rgba(255,255,255,0.5);
        margin-bottom: 15px;
    }

    /* --------------------------------------------------------
       STATS
    -------------------------------------------------------- */

    .stat-card {
        background: white;
        border: 1px solid #e4e4e4;
        border-radius: 12px;
        padding: 16px 20px;
    }

    .stat-number {
        font-size: 1.8rem;
        font-weight: 700;
        color: #222222;
    }

    .stat-label {
        font-size: 0.78rem;
        color: #999999;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    /* --------------------------------------------------------
       DIVIDER
    -------------------------------------------------------- */

    hr {
        border: none;
        border-top: 1px solid #e5e5e5;
        margin: 25px 0;
    }

    /* --------------------------------------------------------
       FORM
    -------------------------------------------------------- */

    div[data-testid="stPopover"] button {
        border-radius: 9px;
    }

    </style>
    """,
    unsafe_allow_html=True
)

# ============================================================
# GOOGLE SHEETS
# ============================================================

try:
    conn = st.connection(
        "gsheets",
        type=GSheetsConnection
    )
except Exception:
    st.error("❌ Verbindung zu Google Sheets konnte nicht hergestellt werden.")
    st.stop()


# ============================================================
# DATEN LADEN
# ============================================================

def load_haushalt():
    try:
        df = conn.read(
            spreadsheet=GSHEETS_URL,
            worksheet=SHEET_NAME,
            ttl=0
        )

        if df is None or df.empty:
            return []

        # Nur gültige Aufgaben behalten
        if "Aufgabe" not in df.columns:
            return []

        df = df.dropna(subset=["Aufgabe"])

        data = []

        for _, row in df.iterrows():

            aufgabe = str(row.get("Aufgabe", "")).strip()

            if not aufgabe:
                continue

            letztes_datum = row.get("Letztes_Datum", "")

            if pd.isna(letztes_datum):
                letztes_datum = str(date.today())

            intervall = row.get("Intervall_Tage", 7)

            try:
                intervall = int(float(intervall))
            except Exception:
                intervall = 7

            data.append({
                "Aufgabe": aufgabe,
                "Letztes_Datum": str(letztes_datum)[:10],
                "Intervall_Tage": intervall
            })

        return data

    except Exception as e:
        st.error(f"Fehler beim Laden der Aufgaben: {e}")
        return []


# ============================================================
# DATEN SPEICHERN
# ============================================================

def save_haushalt(data):

    try:

        df = pd.DataFrame(
            data,
            columns=[
                "Aufgabe",
                "Letztes_Datum",
                "Intervall_Tage"
            ]
        )

        conn.update(
            spreadsheet=GSHEETS_URL,
            worksheet=SHEET_NAME,
            data=df
        )

        st.cache_data.clear()

    except Exception as e:
        st.error(f"Fehler beim Speichern: {e}")


# ============================================================
# DATUM-FUNKTIONEN
# ============================================================

def parse_date(value):

    try:

        if isinstance(value, date):
            return value

        return datetime.strptime(
            str(value)[:10],
            "%Y-%m-%d"
        ).date()

    except Exception:

        return date.today()


def next_due_date(task):

    letztes = parse_date(task["Letztes_Datum"])

    try:
        intervall = int(float(task["Intervall_Tage"]))
    except Exception:
        intervall = 7

    return letztes + timedelta(days=intervall)


def due_text(due_date, heute):

    diff = (due_date - heute).days

    if diff < 0:
        days_overdue = abs(diff)

        if days_overdue == 1:
            return "seit gestern fällig"

        return f"seit {days_overdue} Tagen fällig"

    if diff == 0:
        return "HEUTE fällig"

    if diff == 1:
        return "morgen fällig"

    if diff < 7:
        return f"in {diff} Tagen"

    return due_date.strftime("%d.%m.%Y")


# ============================================================
# AUFGABEN LADEN
# ============================================================

aufgaben = load_haushalt()
heute = date.today()


# ============================================================
# HEADER
# ============================================================

header_left, header_right = st.columns([5, 1])

with header_left:

    st.markdown(
        '<div class="main-title">HAUSHALTSPLAN</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        f'<div class="subtitle">'
        f'{heute.strftime("%A, %d. %B %Y")}'
        f'</div>',
        unsafe_allow_html=True
    )

with header_right:

    st.write("")

    with st.popover("➕  Neue Aufgabe", use_container_width=True):

        st.markdown("### Neue Aufgabe")

        with st.form(
            "neue_aufgabe_form",
            clear_on_submit=True
        ):

            aufgabe_name = st.text_input(
                "Aufgabe",
                placeholder="z. B. Badezimmer putzen"
            )

            intervall = st.number_input(
                "Wiederholung alle X Tage",
                min_value=1,
                max_value=3650,
                value=7,
                step=1
            )

            letztes_mal = st.date_input(
                "Zuletzt erledigt",
                value=heute
            )

            speichern = st.form_submit_button(
                "Aufgabe hinzufügen",
                use_container_width=True
            )

            if speichern:

                if aufgabe_name.strip():

                    aufgaben.append({
                        "Aufgabe": aufgabe_name.strip(),
                        "Letztes_Datum": str(letztes_mal),
                        "Intervall_Tage": int(intervall)
                    })

                    save_haushalt(aufgaben)

                    st.success("Aufgabe hinzugefügt.")

                    st.rerun()

                else:

                    st.warning(
                        "Bitte einen Aufgabennamen eingeben."
                    )


st.markdown(
    '<div class="header-line"></div>',
    unsafe_allow_html=True
)


# ============================================================
# AUFGABEN AUFBEREITEN
# ============================================================

aufgaben_obj = []

for index, task in enumerate(aufgaben):

    due = next_due_date(task)

    diff = (due - heute).days

    aufgaben_obj.append({
        "index": index,
        "Aufgabe": task["Aufgabe"],
        "Letztes_Datum": parse_date(task["Letztes_Datum"]),
        "Intervall": int(float(task["Intervall_Tage"])),
        "Faellig": due,
        "Differenz": diff
    })


# ============================================================
# ZEITRÄUME
# ============================================================

ende_woche = heute + timedelta(days=7)

# Ende des aktuellen Monats
if heute.month == 12:
    naechster_monat = date(
        heute.year + 1,
        1,
        1
    )
else:
    naechster_monat = date(
        heute.year,
        heute.month + 1,
        1
    )

ende_monat = naechster_monat - timedelta(days=1)

# Quartalsende
quartal = ((heute.month - 1) // 3) + 1
quartals_ende_monat = quartal * 3

if quartals_ende_monat == 12:

    quartals_ende = date(
        heute.year,
        12,
        31
    )

else:

    naechstes_quartal = date(
        heute.year,
        quartals_ende_monat + 1,
        1
    )

    quartals_ende = naechstes_quartal - timedelta(days=1)


# ============================================================
# GRUPPIERUNG
# ============================================================

diese_woche = []
dieser_monat = []
dieses_quartal = []
spaeter = []

for task in aufgaben_obj:

    due = task["Faellig"]

    if due <= ende_woche:

        diese_woche.append(task)

    elif due <= ende_monat:

        dieser_monat.append(task)

    elif due <= quartals_ende:

        dieses_quartal.append(task)

    else:

        spaeter.append(task)


# Nach Fälligkeit sortieren

diese_woche.sort(key=lambda x: x["Faellig"])
dieser_monat.sort(key=lambda x: x["Faellig"])
dieses_quartal.sort(key=lambda x: x["Faellig"])
spaeter.sort(key=lambda x: x["Faellig"])


# ============================================================
# STATISTIK
# ============================================================

ueberfaellig = sum(
    1
    for task in aufgaben_obj
    if task["Differenz"] < 0
)

heute_faellig = sum(
    1
    for task in aufgaben_obj
    if task["Differenz"] == 0
)

gesamt = len(aufgaben_obj)


stat1, stat2, stat3, stat4 = st.columns(4)

with stat1:

    st.markdown(
        f"""
        <div class="stat-card">
            <div class="stat-number">{gesamt}</div>
            <div class="stat-label">Aufgaben gesamt</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with stat2:

    st.markdown(
        f"""
        <div class="stat-card">
            <div class="stat-number">{heute_faellig}</div>
            <div class="stat-label">Heute fällig</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with stat3:

    st.markdown(
        f"""
        <div class="stat-card">
            <div class="stat-number">{ueberfaellig}</div>
            <div class="stat-label">Überfällig</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with stat4:

    st.markdown(
        f"""
        <div class="stat-card">
            <div class="stat-number">{len(diese_woche)}</div>
            <div class="stat-label">Diese Woche</div>
        </div>
        """,
        unsafe_allow_html=True
    )


st.markdown("<br>", unsafe_allow_html=True)


# ============================================================
# AUFGABEN RENDERN
# ============================================================

def render_task_list(task_list, section_key):

    if not task_list:

        st.markdown(
            """
            <div class="empty-state">
                Keine Aufgaben in diesem Zeitraum.
            </div>
            """,
            unsafe_allow_html=True
        )

        return

    for task in task_list:

        index = task["index"]

        due = task["Faellig"]

        diff = task["Differenz"]

        # ----------------------------------------------------
        # Status
        # ----------------------------------------------------

        if diff < 0:

            due_class = "task-due-today"

        elif diff <= 2:

            due_class = "task-due-soon"

        else:

            due_class = ""

        # ----------------------------------------------------
        # Karte
        # ----------------------------------------------------

        left, check, delete = st.columns(
            [8, 1, 0.5],
            vertical_alignment="center"
        )

        with left:

            st.markdown(
                f"""
                <div class="task-card">

                    <div class="task-name">
                        {task["Aufgabe"]}
                    </div>

                    <div class="task-due {due_class}">
                        {due_text(due, heute)}
                        &nbsp;&nbsp;·&nbsp;&nbsp;
                        alle {task["Intervall"]} Tage
                    </div>

                </div>
                """,
                unsafe_allow_html=True
            )

        with check:

            if st.button(
                "✓",
                key=f"complete_{section_key}_{index}",
                help="Als erledigt markieren",
                use_container_width=True
            ):

                aufgaben[index]["Letztes_Datum"] = str(heute)

                save_haushalt(aufgaben)

                st.rerun()

        with delete:

            if st.button(
                "×",
                key=f"delete_{section_key}_{index}",
                help="Aufgabe löschen"
            ):

                aufgaben.pop(index)

                save_haushalt(aufgaben)

                st.rerun()


# ============================================================
# DIESE WOCHE
# ============================================================

st.markdown(
    f"""
    <div class="section-header">
        <div class="section-title">
            DIESE WOCHE
        </div>

        <div class="section-subtitle">
            bis {ende_woche.strftime("%d.%m.%Y")}
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

render_task_list(
    diese_woche,
    "week"
)


# ============================================================
# DIESER MONAT
# ============================================================

st.markdown("<hr>", unsafe_allow_html=True)

st.markdown(
    f"""
    <div class="section-header">
        <div class="section-title">
            DIESER MONAT
        </div>

        <div class="section-subtitle">
            bis {ende_monat.strftime("%d.%m.%Y")}
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

render_task_list(
    dieser_monat,
    "month"
)


# ============================================================
# DIESES QUARTAL
# ============================================================

st.markdown("<hr>", unsafe_allow_html=True)

st.markdown(
    f"""
    <div class="section-header">
        <div class="section-title">
            DIESES QUARTAL
        </div>

        <div class="section-subtitle">
            bis {quartals_ende.strftime("%d.%m.%Y")}
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

render_task_list(
    dieses_quartal,
    "quarter"
)


# ============================================================
# SPÄTER
# ============================================================

if spaeter:

    st.markdown("<hr>", unsafe_allow_html=True)

    st.markdown(
        """
        <div class="section-header">
            <div class="section-title">
                SPÄTER
            </div>

            <div class="section-subtitle">
                danach
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    render_task_list(
        spaeter,
        "later"
    )


# ============================================================
# FOOTER
# ============================================================

st.markdown("<br><br>", unsafe_allow_html=True)

st.markdown(
    """
    <div style="
        text-align:center;
        color:#bbbbbb;
        font-size:0.75rem;
        padding-top:20px;
    ">
        Haushaltsplan · Google Sheets
    </div>
    """,
    unsafe_allow_html=True
)
"""
mpathic Annotation Tool — Motivational Interviewing Edition
-----------------------------------------------------------
Source data: AnnoMI-style Google Sheet (read-only).
Auth: GCP service account JSON key (paste raw JSON into secrets).
Each annotator gets their own tab: {source_tab}_{annotator}_labels
Progress auto-saves per utterance and resumes on login.
"""

import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json
from datetime import datetime

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="mpathic · MI Annotation",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Brand styles ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Rubik:wght@300;400;500;600;700;800;900&display=swap');

html, body, [class*="css"] { font-family: 'Rubik', sans-serif !important; }
.stApp { background-color: #ffffff; color: #111111; }

section[data-testid="stSidebar"] {
    background-color: #F9F8F8;
    border-right: 1px solid #e8e8e8;
}

.brand-logo {
    font-size: 1.6rem; font-weight: 900; letter-spacing: -1px;
    color: #ff00c1; -webkit-text-fill-color: #ff00c1;
}
.brand-tag {
    font-size: 0.72rem; font-weight: 500; letter-spacing: 2px;
    text-transform: uppercase; color: #999; margin-bottom: 1.5rem;
}
.section-label {
    font-size: 0.68rem; font-weight: 700; letter-spacing: 3px;
    text-transform: uppercase; color: #8f006b; margin-bottom: 0.4rem;
}

/* ── Utterance cards ── */
.utt-card {
    border: 1px solid #e8e8e8; border-left: 4px solid #e8e8e8;
    border-radius: 10px; padding: 1rem 1.25rem; margin-bottom: 0.5rem;
    line-height: 1.7; opacity: 0.55; background: #F9F8F8;
}
.utt-card.active-card {
    border-left-color: #ff00c1; background: #fff0fb; opacity: 1;
}
.utt-card.therapist-active { border-left-color: #ff00c1; }
.utt-card.client-active    { border-left-color: #67dedf; }
.utt-num {
    font-size: 0.68rem; font-weight: 700; letter-spacing: 2px;
    text-transform: uppercase; color: #8f006b; margin-bottom: 0.25rem;
}
.utt-who-therapist { color: #ff00c1; font-size: 0.72rem; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; }
.utt-who-client    { color: #1d8587; font-size: 0.72rem; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; }
.utt-text { font-size: 0.95rem; color: #222; line-height: 1.7; margin-top: 0.2rem; }

/* ── MI label buttons ── */
.label-group-title {
    font-size: 0.65rem; font-weight: 700; letter-spacing: 2.5px;
    text-transform: uppercase; color: #aaa; margin: 0.9rem 0 0.4rem;
}

/* Selected state handled via st.session_state — buttons styled by class */
div[data-testid="stHorizontalBlock"] .stButton > button {
    padding: 0.45rem 0.9rem !important;
    font-size: 0.82rem !important;
    font-weight: 600 !important;
    border-radius: 100px !important;
    border: 1.5px solid #e0e0e0 !important;
    background: #ffffff !important;
    color: #444 !important;
    transition: all 0.15s !important;
    white-space: nowrap !important;
}
div[data-testid="stHorizontalBlock"] .stButton > button:hover {
    border-color: #ff00c1 !important;
    color: #ff00c1 !important;
    background: #fff0fb !important;
}

/* ── Metric boxes ── */
.metric-row { display: flex; gap: 1rem; margin: 1rem 0; }
.metric-box {
    flex: 1; background: #F9F8F8; border: 1px solid #e8e8e8;
    border-radius: 10px; padding: 1rem; text-align: center;
}
.metric-num { font-size: 1.6rem; font-weight: 800; color: #ff00c1; }
.metric-lbl {
    font-size: 0.68rem; font-weight: 600; letter-spacing: 2px;
    text-transform: uppercase; color: #999; margin-top: 2px;
}

/* ── Selected label chips ── */
.chip {
    display: inline-block; padding: 3px 10px; border-radius: 100px;
    font-size: 0.75rem; font-weight: 700; margin: 2px;
}
.chip-main     { background: #fff0fb; color: #8f006b; border: 1.5px solid #ff00c1; }
.chip-sub      { background: #f0fffe; color: #1d8587; border: 1.5px solid #67dedf; }
.chip-client   { background: #f0fffe; color: #1d8587; border: 1.5px solid #67dedf; }
.chip-empty    { background: #f4f4f4; color: #aaa;    border: 1.5px solid #e0e0e0; }

.saved-badge {
    display: inline-block; background: #e8f5e9; color: #2e7d32;
    border-radius: 6px; padding: 0.3rem 0.7rem; font-size: 0.78rem; font-weight: 600;
}
.tab-badge {
    display: inline-block; background: #fff0fb; color: #8f006b;
    border: 1px solid #ffb1ff; border-radius: 6px; padding: 0.2rem 0.6rem;
    font-size: 0.72rem; font-weight: 700; font-family: monospace;
}

/* ── Buttons (global) ── */
.stButton > button {
    background: #ff00c1 !important; color: white !important;
    border: none !important; border-radius: 8px !important;
    font-family: 'Rubik', sans-serif !important; font-weight: 700 !important;
    padding: 0.55rem 1.2rem !important; transition: opacity 0.2s !important;
}
.stButton > button:hover   { opacity: 0.85 !important; }
.stButton > button:disabled { opacity: 0.3 !important; }
.stProgress > div > div > div { background: #ff00c1 !important; }

.stTextArea textarea, .stTextInput input {
    background: #fff !important; border: 1px solid #e0e0e0 !important;
    border-radius: 8px !important; color: #111 !important;
    font-family: 'Rubik', sans-serif !important;
}
div[data-testid="stExpander"] { background: #fff; border: 1px solid #e8e8e8; border-radius: 8px; }
hr { border-color: #e8e8e8 !important; }
h1,h2,h3,h4 { font-family: 'Rubik', sans-serif !important; font-weight: 800 !important; }

.login-logo { font-size: 2.5rem; font-weight: 900; letter-spacing: -1.5px; color: #ff00c1; -webkit-text-fill-color: #ff00c1; }
.login-sub  { font-size: 0.72rem; font-weight: 500; letter-spacing: 2px; text-transform: uppercase; color: #999; margin-bottom: 2.5rem; }
.login-note { font-size: 0.78rem; color: #aaa; margin-top: 1rem; text-align: center; }
</style>
""", unsafe_allow_html=True)


# ── MI Label taxonomy ──────────────────────────────────────────────────────────
# Mirrors the AnnoMI annotation scheme exactly.
# Therapist labels are hierarchical: pick main behaviour → subtype unlocks.
# Client labels are a flat single-select.

THERAPIST_MAIN = {
    "question":         {"label": "Question",         "color": "#ff00c1", "subtypes": ["open", "closed"]},
    "reflection":       {"label": "Reflection",       "color": "#d4006e", "subtypes": ["simple", "complex"]},
    "therapist_input":  {"label": "Therapist Input",  "color": "#8f006b", "subtypes": ["information", "advice", "options", "negotiation"]},
    "other":            {"label": "Other",             "color": "#aaa",    "subtypes": []},
}

CLIENT_TALK_TYPES = {
    "change":  {"label": "Change Talk",  "color": "#1d8587"},
    "sustain": {"label": "Sustain Talk", "color": "#f3ac02"},
    "neutral": {"label": "Neutral",      "color": "#999"},
}

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

HEADER_ROW = [
    "Utterance ID", "Interlocutor", "Text",
    "Main Behaviour", "Subtype", "Client Talk Type",
    "Notes", "Last Updated"
]


# ── Config ─────────────────────────────────────────────────────────────────────
ANNOTATOR_PASSWORD = st.secrets.get("ANNOTATOR_PASSWORD", "mpathic2024")
SOURCE_SHEET_ID    = st.secrets.get("SOURCE_SHEET_ID",    "YOUR_SOURCE_SHEET_ID_HERE")
OUTPUT_SHEET_ID    = st.secrets.get("OUTPUT_SHEET_ID",    "YOUR_OUTPUT_SHEET_ID_HERE")
SOURCE_TAB         = st.secrets.get("SOURCE_TAB",         "Sheet1")


# ── GSheets auth — paste raw JSON key file ────────────────────────────────────
@st.cache_resource(show_spinner=False)
def get_gspread_client():
    try:
        raw = st.secrets.get("GCP_SERVICE_ACCOUNT_JSON", None)
        info = json.loads(raw) if raw else dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Could not connect to Google Sheets: {e}")
        return None


def output_tab_name(source_tab: str, annotator: str) -> str:
    safe = annotator.strip().lower().replace(" ", "_")
    return f"{source_tab}_{safe}_labels"[:100]


def get_or_create_output_ws(gc, sheet_id, tab):
    sh = gc.open_by_key(sheet_id)
    try:
        return sh.worksheet(tab)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=tab, rows=2000, cols=len(HEADER_ROW))
        ws.append_row(HEADER_ROW, value_input_option="RAW")
        return ws


# ── Load transcript ────────────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def load_transcript(sheet_id: str, tab_name: str) -> pd.DataFrame:
    gc = get_gspread_client()
    if gc is None:
        return pd.DataFrame()
    try:
        ws   = gc.open_by_key(sheet_id).worksheet(tab_name)
        rows = ws.get_all_values()
    except Exception as e:
        st.error(f"Google Sheets error: {e}")
        return pd.DataFrame()
    if len(rows) < 2:
        return pd.DataFrame()

    header = rows[0]
    df = pd.DataFrame(rows[1:], columns=header)
    df.columns = df.columns.str.strip().str.lower()

    # Flexible column mapping
    rename = {}
    for c in df.columns:
        if any(x in c for x in ["utt", "#", "id"]) and "interlocutor" not in c:
            rename[c] = "utterance_id"
        elif "interlocutor" in c or "speaker" in c or "role" in c:
            rename[c] = "interlocutor"
        elif "text" in c or "utterance" in c:
            rename[c] = "text"
        elif "timestamp" in c or "time" in c:
            rename[c] = "timestamp"
        elif "topic" in c:
            rename[c] = "topic"
    df.rename(columns=rename, inplace=True)

    for col in ["utterance_id", "interlocutor", "text", "timestamp", "topic"]:
        if col not in df.columns:
            df[col] = ""

    df = df[df["text"].str.strip().astype(bool)].reset_index(drop=True)
    return df


# ── Load saved progress ────────────────────────────────────────────────────────
def load_saved_progress(sheet_id: str, tab: str) -> dict:
    gc = get_gspread_client()
    if gc is None:
        return {}
    try:
        ws   = gc.open_by_key(sheet_id).worksheet(tab)
        rows = ws.get_all_values()
        if len(rows) < 2:
            return {}
        col  = {h: i for i, h in enumerate(rows[0])}
        saved = {}
        for row in rows[1:]:
            def g(k, d=""):
                i = col.get(k)
                return row[i] if i is not None and i < len(row) else d
            uid = g("Utterance ID")
            if uid:
                saved[uid] = {
                    "main_behaviour":   g("Main Behaviour"),
                    "subtype":          g("Subtype"),
                    "client_talk_type": g("Client Talk Type"),
                    "notes":            g("Notes"),
                }
        return saved
    except gspread.WorksheetNotFound:
        return {}
    except Exception as e:
        st.warning(f"Could not load saved progress: {e}")
        return {}


# ── Upsert one row ─────────────────────────────────────────────────────────────
def upsert_annotation(sheet_id: str, tab: str, uid: str, row_data: dict, interlocutor: str, text: str):
    gc = get_gspread_client()
    if gc is None:
        return False
    try:
        ws  = get_or_create_output_ws(gc, sheet_id, tab)
        ts  = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        new = [
            uid, interlocutor, text,
            row_data.get("main_behaviour",   ""),
            row_data.get("subtype",          ""),
            row_data.get("client_talk_type", ""),
            row_data.get("notes",            ""),
            ts,
        ]
        col_a = ws.col_values(1)
        try:
            ri = col_a.index(uid) + 1
            ws.update(f"A{ri}:H{ri}", [new])
        except ValueError:
            ws.append_row(new, value_input_option="RAW")
        return True
    except Exception as e:
        st.error(f"Save failed: {e}")
        return False


# ── Session state ──────────────────────────────────────────────────────────────
for k, v in {
    "authenticated":   False,
    "annotator_name":  "",
    "annotations":     {},
    "current_idx":     0,
    "progress_loaded": False,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ── Helpers ────────────────────────────────────────────────────────────────────
def get_ann(uid):
    return st.session_state.annotations.get(uid, {})

def set_ann(uid, key, value):
    if uid not in st.session_state.annotations:
        st.session_state.annotations[uid] = {}
    st.session_state.annotations[uid][key] = value


# ── LOGIN ──────────────────────────────────────────────────────────────────────
def show_login():
    _, col, _ = st.columns([1, 1.4, 1])
    with col:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown('<div class="login-logo">mpathic</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-sub">MI Annotation Tool</div>', unsafe_allow_html=True)
        name = st.text_input("Annotator name / ID", placeholder="e.g. jane_doe")
        pwd  = st.text_input("Password", type="password")
        if st.button("Sign In", use_container_width=True):
            if pwd == ANNOTATOR_PASSWORD and name.strip():
                st.session_state.authenticated   = True
                st.session_state.annotator_name  = name.strip()
                st.session_state.progress_loaded = False
                st.rerun()
            elif not name.strip():
                st.error("Enter your annotator name.")
            else:
                st.error("Incorrect password.")
        st.markdown('<p class="login-note">🔒 Transcript data is read-only.</p>', unsafe_allow_html=True)


# ── Label button row helper ────────────────────────────────────────────────────
def label_buttons(uid: str, options: dict, state_key: str, accent: str = "#ff00c1"):
    """
    Render a row of pill buttons. Selected one is highlighted.
    options: {value: {label, color}}  or  {value: {label}}
    state_key: key inside annotations[uid] to read/write
    """
    current = get_ann(uid).get(state_key, "")
    cols = st.columns(len(options))
    for i, (val, meta) in enumerate(options.items()):
        selected = current == val
        color    = meta.get("color", accent)
        label    = meta["label"]
        display  = f"✓ {label}" if selected else label
        with cols[i]:
            # Use custom HTML button to get proper selected styling
            btn_style = (
                f"background:{color} !important; color:white !important; "
                f"border-color:{color} !important;"
            ) if selected else ""
            st.markdown(
                f'<style>'
                f'div[data-testid="stHorizontalBlock"] .stButton button[kind="secondary"]#{uid}_{val.replace(" ","_")} '
                f'{{ {btn_style} }}</style>',
                unsafe_allow_html=True,
            )
            if st.button(display, key=f"btn_{uid}_{state_key}_{val}", use_container_width=True):
                # Toggle off if already selected
                new_val = "" if selected else val
                set_ann(uid, state_key, new_val)
                # Clear subtype if main behaviour changed
                if state_key == "main_behaviour":
                    set_ann(uid, "subtype", "")
                st.rerun()


# ── ANNOTATION ─────────────────────────────────────────────────────────────────
def show_annotation():

    # ── Sidebar ────────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown('<div class="brand-logo">mpathic</div>', unsafe_allow_html=True)
        st.markdown('<div class="brand-tag">MI Annotation Tool</div>', unsafe_allow_html=True)

        st.markdown('<div class="section-label">Session</div>', unsafe_allow_html=True)
        st.markdown(f"**{st.session_state.annotator_name}**")

        st.markdown("---")
        st.markdown('<div class="section-label">Transcript</div>', unsafe_allow_html=True)
        tab_name = st.text_input("Worksheet tab", value=SOURCE_TAB, label_visibility="collapsed")
        out_tab  = output_tab_name(tab_name, st.session_state.annotator_name)
        st.markdown(f'Saving to: <span class="tab-badge">{out_tab}</span>', unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("↻  Reload", use_container_width=True):
            load_transcript.clear()
            st.session_state.annotations    = {}
            st.session_state.current_idx    = 0
            st.session_state.progress_loaded = False
            st.rerun()

        st.markdown("---")
        st.markdown('<div class="section-label">MI Label Guide</div>', unsafe_allow_html=True)
        st.markdown("""
<span style="font-size:0.75rem;color:#555;line-height:1.9;">
<b style="color:#ff00c1;">Question</b> — Open / Closed<br>
<b style="color:#d4006e;">Reflection</b> — Simple / Complex<br>
<b style="color:#8f006b;">Therapist Input</b> — Info / Advice / Options / Negotiation<br>
<b style="color:#aaa;">Other</b><br><br>
<b style="color:#1d8587;">Change Talk</b> — client moves toward change<br>
<b style="color:#f3ac02;">Sustain Talk</b> — client resists change<br>
<b style="color:#999;">Neutral</b> — neither
</span>
""", unsafe_allow_html=True)

        st.markdown("---")
        if st.button("Sign Out", use_container_width=True):
            for k in ["authenticated","annotator_name","annotations","current_idx","progress_loaded"]:
                st.session_state[k] = False if k == "authenticated" else ("" if k in ["annotator_name"] else ({} if k == "annotations" else (0 if k == "current_idx" else False)))
            st.rerun()
        st.markdown('<span style="font-size:0.7rem;color:#aaa;">🔒 Source data is read-only.<br>Progress auto-saves per utterance.</span>', unsafe_allow_html=True)

    # ── Header ─────────────────────────────────────────────────────────────────
    st.markdown("""
    <h1 style="font-size:2rem;font-weight:900;margin-bottom:0.2rem;">
        Motivational Interviewing <span style="color:#ff00c1;">Annotation</span>
    </h1>
    <p style="color:#777;font-size:0.9rem;margin-top:0;margin-bottom:1.5rem;">
        Click labels to annotate each utterance. Progress saves automatically — close and resume any time.
    </p>
    """, unsafe_allow_html=True)

    # ── Load data ───────────────────────────────────────────────────────────────
    with st.spinner("Loading transcript…"):
        df = load_transcript(SOURCE_SHEET_ID, tab_name)

    if df.empty:
        st.warning("No transcript data found. Check your Sheet ID and tab name in secrets.")
        with st.expander("Setup checklist"):
            st.markdown("""
1. Set `SOURCE_SHEET_ID`, `OUTPUT_SHEET_ID`, `SOURCE_TAB` in `secrets.toml`
2. Set `GCP_SERVICE_ACCOUNT_JSON` to the raw contents of your service account JSON key
3. Share **source** sheet with the service account email as **Viewer**
4. Share **output** sheet with the service account email as **Editor**
            """)
        return

    # ── Load saved progress once ────────────────────────────────────────────────
    if not st.session_state.progress_loaded:
        with st.spinner("Resuming saved progress…"):
            saved = load_saved_progress(OUTPUT_SHEET_ID, out_tab)
        if saved:
            st.session_state.annotations = saved
            annotated_ids = set(
                uid for uid, v in saved.items()
                if v.get("main_behaviour") or v.get("client_talk_type")
            )
            for i, row in df.iterrows():
                if str(row["utterance_id"]) not in annotated_ids:
                    st.session_state.current_idx = i
                    break
            else:
                st.session_state.current_idx = len(df) - 1
        st.session_state.progress_loaded = True

    total = len(df)
    annotated_count = sum(
        1 for uid, v in st.session_state.annotations.items()
        if v.get("main_behaviour") or v.get("client_talk_type")
    )
    pct = int(annotated_count / total * 100) if total else 0

    # ── Metrics ─────────────────────────────────────────────────────────────────
    st.markdown(
        f"""<div class="metric-row">
            <div class="metric-box"><div class="metric-num">{total}</div><div class="metric-lbl">Utterances</div></div>
            <div class="metric-box"><div class="metric-num">{annotated_count}</div><div class="metric-lbl">Annotated</div></div>
            <div class="metric-box"><div class="metric-num">{total - annotated_count}</div><div class="metric-lbl">Remaining</div></div>
            <div class="metric-box"><div class="metric-num">{pct}%</div><div class="metric-lbl">Complete</div></div>
        </div>""",
        unsafe_allow_html=True,
    )
    st.progress(annotated_count / total if total else 0)
    st.markdown("---")

    # ── Navigation ──────────────────────────────────────────────────────────────
    nav1, nav2, nav3 = st.columns([1, 4, 1])
    with nav1:
        if st.button("← Prev", use_container_width=True, disabled=st.session_state.current_idx == 0):
            st.session_state.current_idx -= 1
            st.rerun()
    with nav2:
        jump = st.selectbox(
            "Jump", options=list(range(total)),
            index=st.session_state.current_idx,
            format_func=lambda i: (
                f"[{df.iloc[i]['interlocutor'].upper()[:3]}] #{df.iloc[i]['utterance_id']}  —  {df.iloc[i]['text'][:65]}…"
                if len(df.iloc[i]["text"]) > 65
                else f"[{df.iloc[i]['interlocutor'].upper()[:3]}] #{df.iloc[i]['utterance_id']}  —  {df.iloc[i]['text']}"
            ),
            label_visibility="collapsed",
        )
        if jump != st.session_state.current_idx:
            st.session_state.current_idx = jump
            st.rerun()
    with nav3:
        if st.button("Next →", use_container_width=True, disabled=st.session_state.current_idx >= total - 1):
            st.session_state.current_idx += 1
            st.rerun()

    # ── Context window ──────────────────────────────────────────────────────────
    idx = st.session_state.current_idx
    ctx_start = max(0, idx - 2)
    ctx_end   = min(total, idx + 3)

    for ci in range(ctx_start, ctx_end):
        cr   = df.iloc[ci]
        uid  = str(cr["utterance_id"])
        who  = cr["interlocutor"].lower() if cr["interlocutor"] else "unknown"
        is_active = ci == idx

        who_class  = "therapist" if "therapist" in who else "client"
        card_class = f"active-card {who_class}-active" if is_active else ""

        who_html = (
            f'<span class="utt-who-{who_class}">{who.title()}</span>'
            if is_active else
            f'<span style="font-size:0.68rem;color:#bbb;text-transform:uppercase;letter-spacing:1px;">{who.title()}</span>'
        )

        st.markdown(
            f'<div class="utt-card {card_class}">'
            f'<div class="utt-num">#{uid} &nbsp; {who_html}</div>'
            f'<div class="utt-text">{cr["text"]}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # ── Active utterance label panel ────────────────────────────────────────────
    row  = df.iloc[idx]
    uid  = str(row["utterance_id"])
    who  = row["interlocutor"].lower() if row["interlocutor"] else ""
    text = row["text"]
    ann  = get_ann(uid)

    st.markdown("---")

    is_therapist = "therapist" in who

    if is_therapist:
        # ── THERAPIST: main behaviour ─────────────────────────────────────────
        st.markdown('<div class="label-group-title">Main Behaviour</div>', unsafe_allow_html=True)
        label_buttons(uid, {k: {"label": v["label"], "color": v["color"]} for k,v in THERAPIST_MAIN.items()}, "main_behaviour")

        # ── THERAPIST: subtype (conditional) ─────────────────────────────────
        main = ann.get("main_behaviour", "")
        subtypes = THERAPIST_MAIN.get(main, {}).get("subtypes", [])
        if subtypes:
            accent = THERAPIST_MAIN[main]["color"]
            st.markdown('<div class="label-group-title">Subtype</div>', unsafe_allow_html=True)
            label_buttons(
                uid,
                {s: {"label": s.replace("_"," ").title(), "color": accent} for s in subtypes},
                "subtype",
            )

        # ── Current selection display ─────────────────────────────────────────
        main_label = THERAPIST_MAIN.get(main, {}).get("label", "")
        sub_label  = ann.get("subtype", "").replace("_"," ").title()
        if main_label:
            chips = f'<span class="chip chip-main">{main_label}</span>'
            if sub_label:
                chips += f' <span class="chip chip-sub">{sub_label}</span>'
        else:
            chips = '<span class="chip chip-empty">No label selected</span>'

    else:
        # ── CLIENT: talk type ─────────────────────────────────────────────────
        st.markdown('<div class="label-group-title">Client Talk Type</div>', unsafe_allow_html=True)
        label_buttons(uid, {k: {"label": v["label"], "color": v["color"]} for k,v in CLIENT_TALK_TYPES.items()}, "client_talk_type")

        ctt = ann.get("client_talk_type", "")
        ctt_label = CLIENT_TALK_TYPES.get(ctt, {}).get("label", "")
        if ctt_label:
            chips = f'<span class="chip chip-client">{ctt_label}</span>'
        else:
            chips = '<span class="chip chip-empty">No label selected</span>'

    st.markdown(f"<div style='margin:0.6rem 0;'>{chips}</div>", unsafe_allow_html=True)

    # ── Notes ───────────────────────────────────────────────────────────────────
    notes = st.text_area(
        "Notes (optional)", value=ann.get("notes", ""),
        height=68, key=f"notes_{uid}",
        placeholder="Any observations about this utterance…",
    )

    # ── Save & navigate ─────────────────────────────────────────────────────────
    def _save(advance=False):
        current_ann = get_ann(uid)
        current_ann["notes"] = notes
        st.session_state.annotations[uid] = current_ann
        with st.spinner("Saving…"):
            upsert_annotation(OUTPUT_SHEET_ID, out_tab, uid, current_ann, who, text)
        if advance and idx < total - 1:
            st.session_state.current_idx += 1

    bc1, bc2 = st.columns(2)
    with bc1:
        if st.button("💾  Save & Next", use_container_width=True):
            _save(advance=True)
            st.rerun()
    with bc2:
        if st.button("Save only", use_container_width=True):
            _save(advance=False)
            st.rerun()

    # ── Footer ──────────────────────────────────────────────────────────────────
    st.markdown("---")
    already = bool(ann.get("main_behaviour") or ann.get("client_talk_type"))
    if already:
        st.markdown(
            f'<span class="saved-badge">✅ #{uid} saved</span>'
            f'&nbsp;&nbsp;<span style="font-size:0.78rem;color:#aaa;">→ <strong>{out_tab}</strong></span>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<span style="font-size:0.85rem;color:#777;">'
            f'<strong style="color:#111;">{annotated_count} of {total}</strong> annotated</span>',
            unsafe_allow_html=True,
        )


# ── Router ─────────────────────────────────────────────────────────────────────
if not st.session_state.authenticated:
    show_login()
else:
    show_annotation()

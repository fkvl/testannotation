"""
mpathic Annotation Tool - proof of concept to connect to gsheets without them downloading data
-----------------------
Loads one transcript at a time for speed.
Auth: GCP service account JSON key (paste raw JSON into secrets).
Each annotator gets their own output tab: {source_tab}_{annotator}_labels
Annotations are appended (not upserted) — fast, no column scanning.
Previously saved labels are reloaded when a transcript is reopened.
"""

import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json
from datetime import datetime

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="mpathic Annotation",
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
.utt-card {
    border: 1px solid #e8e8e8; border-left: 4px solid #e8e8e8;
    border-radius: 10px; padding: 1rem 1.25rem; margin-bottom: 0.5rem;
    line-height: 1.7; opacity: 0.55; background: #F9F8F8;
}
.utt-card.active-card  { border-left-color: #ff00c1; background: #fff0fb; opacity: 1; }
.utt-card.therapist-active { border-left-color: #ff00c1; }
.utt-card.client-active    { border-left-color: #67dedf; }
.utt-num {
    font-size: 0.68rem; font-weight: 700; letter-spacing: 2px;
    text-transform: uppercase; color: #8f006b; margin-bottom: 0.25rem;
}
.utt-who-therapist { color: #ff00c1; font-size: 0.72rem; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; }
.utt-who-client    { color: #1d8587; font-size: 0.72rem; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; }
.utt-text { font-size: 0.95rem; color: #222; line-height: 1.7; margin-top: 0.2rem; }
.label-group-title {
    font-size: 0.65rem; font-weight: 700; letter-spacing: 2.5px;
    text-transform: uppercase; color: #aaa; margin: 0.9rem 0 0.4rem;
}
div[data-testid="stHorizontalBlock"] .stButton > button {
    padding: 0.45rem 0.9rem !important; font-size: 0.82rem !important;
    font-weight: 600 !important; border-radius: 100px !important;
    border: 1.5px solid #e0e0e0 !important; background: #ffffff !important;
    color: #444 !important; transition: all 0.15s !important; white-space: nowrap !important;
}
div[data-testid="stHorizontalBlock"] .stButton > button:hover {
    border-color: #ff00c1 !important; color: #ff00c1 !important; background: #fff0fb !important;
}
.metric-row { display: flex; gap: 1rem; margin: 1rem 0; }
.metric-box {
    flex: 1; background: #F9F8F8; border: 1px solid #e8e8e8;
    border-radius: 10px; padding: 1rem; text-align: center;
}
.metric-num { font-size: 1.6rem; font-weight: 800; color: #ff00c1; }
.metric-lbl { font-size: 0.68rem; font-weight: 600; letter-spacing: 2px; text-transform: uppercase; color: #999; margin-top: 2px; }
.chip { display: inline-block; padding: 3px 10px; border-radius: 100px; font-size: 0.75rem; font-weight: 700; margin: 2px; }
.chip-main   { background: #fff0fb; color: #8f006b; border: 1.5px solid #ff00c1; }
.chip-sub    { background: #f0fffe; color: #1d8587; border: 1.5px solid #67dedf; }
.chip-client { background: #f0fffe; color: #1d8587; border: 1.5px solid #67dedf; }
.chip-empty  { background: #f4f4f4; color: #aaa;    border: 1.5px solid #e0e0e0; }
.saved-badge { display: inline-block; background: #e8f5e9; color: #2e7d32; border-radius: 6px; padding: 0.3rem 0.7rem; font-size: 0.78rem; font-weight: 600; }
.transcript-card {
    background: #F9F8F8; border: 1px solid #e8e8e8; border-radius: 10px;
    padding: 1.25rem 1.5rem; margin-bottom: 0.5rem; cursor: pointer;
}
.stButton > button {
    background: #ff00c1 !important; color: white !important; border: none !important;
    border-radius: 8px !important; font-family: 'Rubik', sans-serif !important;
    font-weight: 700 !important; padding: 0.55rem 1.2rem !important; transition: opacity 0.2s !important;
}
.stButton > button:hover    { opacity: 0.85 !important; }
.stButton > button:disabled { opacity: 0.3 !important; }
.stProgress > div > div > div { background: #ff00c1 !important; }
.stTextArea textarea, .stTextInput input {
    background: #fff !important; border: 1px solid #e0e0e0 !important;
    border-radius: 8px !important; color: #111 !important; font-family: 'Rubik', sans-serif !important;
}
div[data-testid="stExpander"] { background: #fff; border: 1px solid #e8e8e8; border-radius: 8px; }
hr { border-color: #e8e8e8 !important; }
h1,h2,h3,h4 { font-family: 'Rubik', sans-serif !important; font-weight: 800 !important; }
.login-logo { font-size: 2.5rem; font-weight: 900; letter-spacing: -1.5px; color: #ff00c1; -webkit-text-fill-color: #ff00c1; }
.login-sub  { font-size: 0.72rem; font-weight: 500; letter-spacing: 2px; text-transform: uppercase; color: #999; margin-bottom: 2.5rem; }

/* Hover help "?" badge */
.mp-help { position: relative; display: inline-block; margin-bottom: 0.5rem; }
.mp-help > .q {
    width: 24px; height: 24px; line-height: 22px; text-align: center;
    display: inline-block; border-radius: 50%;
    border: 1.5px solid #ff00c1; color: #ff00c1; background: #fff;
    font-weight: 700; font-size: 0.9rem; cursor: help; user-select: none;
}
.mp-help .tip {
    visibility: hidden; opacity: 0; transition: opacity .12s ease;
    position: absolute; top: 30px; left: 0; z-index: 99999;
    width: 250px; background: #fff; color: #555;
    border: 1px solid #e8e8e8; border-radius: 10px;
    padding: 0.85rem 1rem; box-shadow: 0 10px 30px rgba(143,0,107,0.15);
    font-size: 0.74rem; line-height: 1.85; font-weight: 400;
}
.mp-help:hover .tip { visibility: visible; opacity: 1; }
.mp-help .tip b { font-weight: 700; }
</style>
""", unsafe_allow_html=True)


# ── Label taxonomy ─────────────────────────────────────────────────────────────
THERAPIST_MAIN = {
    "question":        {"label": "Question",        "color": "#ff00c1", "subtypes": ["open", "closed"]},
    "reflection":      {"label": "Reflection",      "color": "#d4006e", "subtypes": ["simple", "complex"]},
    "therapist_input": {"label": "Therapist Input", "color": "#8f006b", "subtypes": ["information", "advice", "options", "negotiation"]},
    "other":           {"label": "Other",            "color": "#aaa",    "subtypes": []},
}
CLIENT_TALK_TYPES = {
    "change":  {"label": "Change Talk",  "color": "#1d8587"},
    "sustain": {"label": "Sustain Talk", "color": "#f3ac02"},
    "neutral": {"label": "Neutral",      "color": "#999"},
}

# Speaker detection: anything matching these hints is treated as the therapist;
# everything else (incl. blank/unknown) is treated as the client so Client Talk
# Type buttons reliably appear.
THERAPIST_HINTS = (
    "therapist", "counselor", "counsellor", "clinician", "provider",
    "interviewer", "doctor", "dr", "coach", "practitioner", "facilitator",
)

def is_therapist_speaker(who: str) -> bool:
    w = (who or "").strip().lower()
    return any(h in w for h in THERAPIST_HINTS)

# Hover tooltip content for the "?" help badge
LABEL_HELP_HTML = """<div class="mp-help"><span class="q">?</span>
<div class="tip">
<b style="color:#ff00c1;">Question</b> — Open / Closed<br>
<b style="color:#d4006e;">Reflection</b> — Simple / Complex<br>
<b style="color:#8f006b;">Therapist Input</b> — Info / Advice / Options / Negotiation<br>
<b style="color:#aaa;">Other</b><br>
<br>
<b style="color:#1d8587;">Change Talk</b> — toward change<br>
<b style="color:#f3ac02;">Sustain Talk</b> — resists change<br>
<b style="color:#999;">Neutral</b><br>
<br>
<span style="color:#aaa;font-style:italic;">Client talk appears on client turns.</span>
</div></div>"""

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]
HEADER_ROW = ["Transcript ID", "Utterance ID", "Interlocutor", "Text",
              "Main Behaviour", "Subtype", "Client Talk Type", "Notes",
              "Annotator", "Timestamp"]

# ── Config ─────────────────────────────────────────────────────────────────────
SOURCE_SHEET_ID = st.secrets.get("SOURCE_SHEET_ID", "")
OUTPUT_SHEET_ID = st.secrets.get("OUTPUT_SHEET_ID", "")
SOURCE_TAB      = st.secrets.get("SOURCE_TAB", "Sheet1")


# ── Auth ───────────────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def get_gc():
    try:
        raw  = st.secrets.get("GCP_SERVICE_ACCOUNT_JSON", None)
        info = json.loads(raw) if raw else dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Auth error: {e}")
        return None


# ── Load transcript index (just transcript_id + topic, tiny) ──────────────────
@st.cache_data(ttl=600, show_spinner=False)
def load_transcript_index(sheet_id: str, tab: str) -> pd.DataFrame:
    """Loads only transcript_id and topic columns — fast, small."""
    gc = get_gc()
    if gc is None:
        return pd.DataFrame()
    try:
        ws   = gc.open_by_key(sheet_id).worksheet(tab)
        all_vals = ws.get_all_values()
        if len(all_vals) < 2:
            return pd.DataFrame()
        header = [h.strip().lower() for h in all_vals[0]]
        df = pd.DataFrame(all_vals[1:], columns=header)
        tid_col   = next((c for c in df.columns if c == "transcript_id"), None)
        topic_col = next((c for c in df.columns if c == "topic"), None)
        if not tid_col:
            return pd.DataFrame()
        cols = [tid_col] + ([topic_col] if topic_col else [])
        index = df[cols].drop_duplicates(subset=[tid_col]).reset_index(drop=True)
        index[tid_col] = index[tid_col].astype(str)
        return index
    except Exception as e:
        st.error(f"Could not load transcript list: {e}")
        return pd.DataFrame()


# ── Load one transcript by transcript_id ──────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def load_one_transcript(sheet_id: str, tab: str, transcript_id: str) -> pd.DataFrame:
    """Loads all rows for a single transcript_id — small and fast."""
    gc = get_gc()
    if gc is None:
        return pd.DataFrame()
    try:
        ws   = gc.open_by_key(sheet_id).worksheet(tab)
        all_vals = ws.get_all_values()
        if len(all_vals) < 2:
            return pd.DataFrame()
        header = [h.strip().lower() for h in all_vals[0]]
        df = pd.DataFrame(all_vals[1:], columns=header)
        tid_col = next((c for c in df.columns if c == "transcript_id"), None)
        if not tid_col:
            return pd.DataFrame()
        df = df[df[tid_col].astype(str) == str(transcript_id)].reset_index(drop=True)
        rename = {}
        for c in df.columns:
            if c == "utterance_id":    rename[c] = "utterance_id"
            elif c == "utterance_text": rename[c] = "text"
            elif c == "interlocutor":  rename[c] = "interlocutor"
            elif c == "timestamp":     rename[c] = "timestamp"
            elif c == "topic":         rename[c] = "topic"
            elif c == "transcript_id": rename[c] = "transcript_id"
        df.rename(columns=rename, inplace=True)
        for col in ["utterance_id", "interlocutor", "text", "transcript_id"]:
            if col not in df.columns:
                df[col] = ""
        df = df[df["text"].str.strip().astype(bool)].reset_index(drop=True)
        return df
    except Exception as e:
        st.error(f"Could not load transcript: {e}")
        return pd.DataFrame()


# ── Load this annotator's previously saved labels for a transcript ────────────
@st.cache_data(ttl=120, show_spinner=False)
def load_existing_annotations(out_tab: str, transcript_id: str) -> dict:
    """Reads back saved labels so reopened transcripts show prior work.
    Sheet is append-only, so the last row for each utterance wins (most recent)."""
    gc = get_gc()
    if gc is None:
        return {}
    try:
        sh = gc.open_by_key(OUTPUT_SHEET_ID)
        try:
            ws = sh.worksheet(out_tab)
        except gspread.WorksheetNotFound:
            return {}  # nothing saved yet for this annotator
        vals = ws.get_all_values()
        if len(vals) < 2:
            return {}
        header = vals[0]
        col = {name: i for i, name in enumerate(header)}

        def cell(row, name):
            i = col.get(name)
            return row[i] if (i is not None and i < len(row)) else ""

        out = {}
        for r in vals[1:]:
            if str(cell(r, "Transcript ID")) != str(transcript_id):
                continue
            uid = str(cell(r, "Utterance ID"))
            if not uid:
                continue
            out[uid] = {  # later rows overwrite earlier → keeps most recent save
                "main_behaviour":   cell(r, "Main Behaviour"),
                "subtype":          cell(r, "Subtype"),
                "client_talk_type": cell(r, "Client Talk Type"),
                "notes":            cell(r, "Notes"),
            }
        return out
    except Exception as e:
        st.error(f"Could not load saved annotations: {e}")
        return {}


# ── Output worksheet ───────────────────────────────────────────────────────────
def get_or_create_output_ws(sheet_id: str, tab: str):
    gc = get_gc()
    if gc is None:
        return None
    sh = gc.open_by_key(sheet_id)
    try:
        return sh.worksheet(tab)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=tab, rows=5000, cols=len(HEADER_ROW))
        ws.append_row(HEADER_ROW, value_input_option="RAW")
        return ws


# ── Append annotation row (no scanning — always fast) ─────────────────────────
def save_annotation(out_tab: str, transcript_id: str, uid: str,
                    ann: dict, interlocutor: str, text: str):
    ws = get_or_create_output_ws(OUTPUT_SHEET_ID, out_tab)
    if ws is None:
        return False
    try:
        ts  = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        row = [
            transcript_id, uid, interlocutor, text,
            ann.get("main_behaviour",   ""),
            ann.get("subtype",          ""),
            ann.get("client_talk_type", ""),
            ann.get("notes",            ""),
            st.session_state.annotator_name,
            ts,
        ]
        ws.append_row(row, value_input_option="RAW")
        return True
    except Exception as e:
        st.error(f"Save failed: {e}")
        return False


# ── Output tab name ────────────────────────────────────────────────────────────
def out_tab_name(annotator: str) -> str:
    safe = annotator.strip().lower().replace(" ", "_")
    return f"{SOURCE_TAB}_{safe}_labels"[:100]


# ── Session state ──────────────────────────────────────────────────────────────
for k, v in {
    "authenticated":    False,
    "annotator_name":   "",
    "transcript_id":    None,   # currently selected transcript
    "annotations":      {},     # {uid: {main_behaviour, subtype, client_talk_type, notes}}
    "current_idx":      0,
    "loaded_tid":       None,   # which transcript's saved labels are loaded into session
}.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ── Helpers ────────────────────────────────────────────────────────────────────
def get_ann(uid):
    return st.session_state.annotations.get(str(uid), {})

def set_ann(uid, key, value):
    uid = str(uid)
    if uid not in st.session_state.annotations:
        st.session_state.annotations[uid] = {}
    st.session_state.annotations[uid][key] = value


# ── LOGIN ──────────────────────────────────────────────────────────────────────
def show_login():
    _, col, _ = st.columns([1, 1.4, 1])
    with col:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown('<div class="login-logo">mpathic</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-sub">Annotation Tool</div>', unsafe_allow_html=True)
        name = st.text_input("Annotator name / ID")
        if st.button("Sign In", use_container_width=True):
            if name.strip():
                st.session_state.authenticated  = True
                st.session_state.annotator_name = name.strip()
                st.session_state.transcript_id  = None
                st.session_state.loaded_tid     = None
                st.rerun()
            else:
                st.error("Enter your annotator name.")


# ── TRANSCRIPT PICKER ──────────────────────────────────────────────────────────
def show_transcript_picker():
    with st.sidebar:
        st.markdown(LABEL_HELP_HTML, unsafe_allow_html=True)
        st.markdown('<div class="brand-logo">mpathic</div>', unsafe_allow_html=True)
        st.markdown('<div class="brand-tag">Annotation Tool</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-label">Session</div>', unsafe_allow_html=True)
        st.markdown(f"**{st.session_state.annotator_name}**")
        st.markdown("---")
        if st.button("Sign Out", use_container_width=True):
            st.session_state.authenticated  = False
            st.session_state.annotator_name = ""
            st.session_state.transcript_id  = None
            st.session_state.annotations    = {}
            st.session_state.loaded_tid     = None
            st.rerun()

    st.markdown("""
    <h1 style="font-size:2rem;font-weight:900;margin-bottom:0.2rem;">
        Pick a <span style="color:#ff00c1;">Transcript</span>
    </h1>
    <p style="color:#777;font-size:0.9rem;margin-top:0;margin-bottom:1.5rem;">
        Select a transcript to annotate. Each one loads in under a second.
    </p>
    """, unsafe_allow_html=True)

    with st.spinner("Loading transcript list…"):
        index = load_transcript_index(SOURCE_SHEET_ID, SOURCE_TAB)

    if index.empty:
        st.error("Could not load transcript list. Check your Sheet ID and tab name in secrets.")
        return

    tid_col   = "transcript_id"
    topic_col = "topic" if "topic" in index.columns else None

    # Search / filter
    search = st.text_input("Search by topic or ID", placeholder="e.g. alcohol, depression, 42…")
    if search:
        mask = index[tid_col].str.contains(search, case=False, na=False)
        if topic_col:
            mask = mask | index[topic_col].str.contains(search, case=False, na=False)
        index = index[mask]

    st.markdown(f'<div class="section-label">{len(index)} transcripts</div>', unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    for _, row in index.iterrows():
        tid   = str(row[tid_col])
        topic = str(row[topic_col]).replace("_", " ").title() if topic_col else ""
        topic_html = (
            f'<span style="color:#777;font-size:0.85rem;margin-left:0.7rem;">{topic}</span>'
            if topic else ""
        )
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown(
                f'<div style="padding:0.6rem 0;">'
                f'<span style="font-weight:700;color:#111;">Transcript {tid}</span>'
                f'{topic_html}'
                f'</div>',
                unsafe_allow_html=True,
            )
        with col2:
            if st.button("Annotate →", key=f"pick_{tid}", use_container_width=True):
                st.session_state.transcript_id = tid
                st.session_state.annotations   = {}
                st.session_state.loaded_tid    = None  # force reload of saved labels
                st.session_state.current_idx   = 0
                st.rerun()


# ── LABEL BUTTONS ──────────────────────────────────────────────────────────────
def label_buttons(uid: str, options: dict, state_key: str):
    current = get_ann(uid).get(state_key, "")
    cols = st.columns(len(options))
    for i, (val, meta) in enumerate(options.items()):
        selected = current == val
        color    = meta.get("color", "#ff00c1")
        display  = f"✓ {meta['label']}" if selected else meta["label"]
        with cols[i]:
            if selected:
                st.markdown(
                    f'<style>div[data-testid="stHorizontalBlock"] '
                    f'button[data-testid="baseButton-secondary"][key="btn_{uid}_{state_key}_{val}"] '
                    f'{{ background:{color} !important; color:white !important; border-color:{color} !important; }}</style>',
                    unsafe_allow_html=True,
                )
            if st.button(display, key=f"btn_{uid}_{state_key}_{val}", use_container_width=True):
                set_ann(uid, state_key, "" if selected else val)
                if state_key == "main_behaviour":
                    set_ann(uid, "subtype", "")
                st.rerun()


# ── ANNOTATION ─────────────────────────────────────────────────────────────────
def show_annotation():
    tid     = st.session_state.transcript_id
    out_tab = out_tab_name(st.session_state.annotator_name)

    # Load this annotator's previously saved labels once per transcript entry
    if st.session_state.loaded_tid != tid:
        st.session_state.annotations = load_existing_annotations(out_tab, tid)
        st.session_state.loaded_tid  = tid

    # ── Sidebar ────────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown(LABEL_HELP_HTML, unsafe_allow_html=True)
        st.markdown('<div class="brand-logo">mpathic</div>', unsafe_allow_html=True)
        st.markdown('<div class="brand-tag">Annotation Tool</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-label">Session</div>', unsafe_allow_html=True)
        st.markdown(f"**{st.session_state.annotator_name}**")
        st.markdown("---")
        st.markdown('<div class="section-label">Transcript</div>', unsafe_allow_html=True)
        st.markdown(f"**#{tid}**")
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("← Back to Transcripts", use_container_width=True):
            st.session_state.transcript_id = None
            st.session_state.annotations   = {}
            st.session_state.loaded_tid    = None
            st.session_state.current_idx   = 0
            st.rerun()
        st.markdown("---")
        if st.button("Sign Out", use_container_width=True):
            st.session_state.authenticated  = False
            st.session_state.annotator_name = ""
            st.session_state.transcript_id  = None
            st.session_state.annotations    = {}
            st.session_state.loaded_tid     = None
            st.rerun()

    # ── Load this transcript ────────────────────────────────────────────────────
    with st.spinner(f"Loading transcript {tid}…"):
        df = load_one_transcript(SOURCE_SHEET_ID, SOURCE_TAB, tid)

    if df.empty:
        st.error(f"Could not load transcript {tid}.")
        return

    total = len(df)
    topic = df["topic"].iloc[0] if "topic" in df.columns and df["topic"].iloc[0] else ""

    # ── Header ─────────────────────────────────────────────────────────────────
    header_bits = []
    if topic:
        header_bits.append(topic.replace("_", " ").title())
    header_bits.append(f"{total} utterances")
    header_bits.append("Click labels, then Save & Next.")
    header_sub = " &nbsp;—&nbsp; ".join(header_bits)

    st.markdown(f"""
    <h1 style="font-size:2rem;font-weight:900;margin-bottom:0.2rem;">
        Transcript <span style="color:#ff00c1;">#{tid}</span>
    </h1>
    <p style="color:#777;font-size:0.9rem;margin-top:0;margin-bottom:1.5rem;">
        {header_sub}
    </p>
    """, unsafe_allow_html=True)

    annotated_count = sum(
        1 for uid, v in st.session_state.annotations.items()
        if v.get("main_behaviour") or v.get("client_talk_type")
    )
    pct = int(annotated_count / total * 100) if total else 0

    # ── Metrics ─────────────────────────────────────────────────────────────────
    st.markdown(f"""<div class="metric-row">
        <div class="metric-box"><div class="metric-num">{total}</div><div class="metric-lbl">Utterances</div></div>
        <div class="metric-box"><div class="metric-num">{annotated_count}</div><div class="metric-lbl">Annotated</div></div>
        <div class="metric-box"><div class="metric-num">{total - annotated_count}</div><div class="metric-lbl">Remaining</div></div>
        <div class="metric-box"><div class="metric-num">{pct}%</div><div class="metric-lbl">Complete</div></div>
    </div>""", unsafe_allow_html=True)
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
            index=min(st.session_state.current_idx, total - 1),
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
    idx       = st.session_state.current_idx
    ctx_start = max(0, idx - 2)
    ctx_end   = min(total, idx + 3)

    for ci in range(ctx_start, ctx_end):
        cr        = df.iloc[ci]
        uid       = str(cr["utterance_id"])
        who       = cr["interlocutor"].lower() if cr["interlocutor"] else "unknown"
        is_active = ci == idx
        who_class = "therapist" if is_therapist_speaker(who) else "client"
        card_cls  = f"active-card {who_class}-active" if is_active else ""
        who_html  = (
            f'<span class="utt-who-{who_class}">{who.title()}</span>'
            if is_active else
            f'<span style="font-size:0.68rem;color:#bbb;text-transform:uppercase;letter-spacing:1px;">{who.title()}</span>'
        )
        st.markdown(
            f'<div class="utt-card {card_cls}">'
            f'<div class="utt-num">#{uid} &nbsp; {who_html}</div>'
            f'<div class="utt-text">{cr["text"]}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # ── Label panel ─────────────────────────────────────────────────────────────
    row  = df.iloc[idx]
    uid  = str(row["utterance_id"])
    who  = row["interlocutor"].lower() if row["interlocutor"] else ""
    text = row["text"]
    ann  = get_ann(uid)

    st.markdown("---")
    is_therapist = is_therapist_speaker(who)

    if is_therapist:
        st.markdown('<div class="label-group-title">Main Behaviour</div>', unsafe_allow_html=True)
        label_buttons(uid, {k: {"label": v["label"], "color": v["color"]} for k,v in THERAPIST_MAIN.items()}, "main_behaviour")
        main     = ann.get("main_behaviour", "")
        subtypes = THERAPIST_MAIN.get(main, {}).get("subtypes", [])
        if subtypes:
            st.markdown('<div class="label-group-title">Subtype</div>', unsafe_allow_html=True)
            label_buttons(uid, {s: {"label": s.replace("_"," ").title(), "color": THERAPIST_MAIN[main]["color"]} for s in subtypes}, "subtype")
        main_label = THERAPIST_MAIN.get(main, {}).get("label", "")
        sub_label  = ann.get("subtype", "").replace("_"," ").title()
        chips = (
            f'<span class="chip chip-main">{main_label}</span>'
            + (f' <span class="chip chip-sub">{sub_label}</span>' if sub_label else "")
            if main_label else '<span class="chip chip-empty">No label selected</span>'
        )
    else:
        st.markdown('<div class="label-group-title">Client Talk Type</div>', unsafe_allow_html=True)
        label_buttons(uid, {k: {"label": v["label"], "color": v["color"]} for k,v in CLIENT_TALK_TYPES.items()}, "client_talk_type")
        ctt   = ann.get("client_talk_type", "")
        chips = (
            f'<span class="chip chip-client">{CLIENT_TALK_TYPES[ctt]["label"]}</span>'
            if ctt else '<span class="chip chip-empty">No label selected</span>'
        )

    st.markdown(f"<div style='margin:0.6rem 0;'>{chips}</div>", unsafe_allow_html=True)

    notes = st.text_area(
        "Notes (optional)", value=ann.get("notes", ""),
        height=68, key=f"notes_{uid}",
        placeholder="Any observations about this utterance…",
    )

    # ── Save ────────────────────────────────────────────────────────────────────
    def _save(advance=False):
        current_ann          = get_ann(uid)
        current_ann["notes"] = notes
        st.session_state.annotations[uid] = current_ann
        with st.spinner("Saving…"):
            save_annotation(out_tab, tid, uid, current_ann, who, text)
        # bust the read cache so a later reopen reflects this save
        load_existing_annotations.clear()
        if advance and idx < total - 1:
            st.session_state.current_idx += 1

    bc1, bc2 = st.columns(2)
    with bc1:
        if st.button("Save & Next", use_container_width=True):
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
            f'<span class="saved-badge"> #{uid} saved</span>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<span style="font-size:0.85rem;color:#777;">'
            f'<strong style="color:#111;">{annotated_count} of {total}</strong> annotated this session</span>',
            unsafe_allow_html=True,
        )


# ── Router ─────────────────────────────────────────────────────────────────────
if not st.session_state.authenticated:
    show_login()
elif st.session_state.transcript_id is None:
    show_transcript_picker()
else:
    show_annotation()

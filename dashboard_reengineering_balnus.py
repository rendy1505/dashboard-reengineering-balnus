#%% ============================================================
# STEP 1 - IMPORT LIBRARY
# ============================================================

import base64
import io
import json
import socket
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import streamlit as st
import streamlit.components.v1 as components
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

socket.setdefaulttimeout(120)


#%% ============================================================
# STEP 2 - STREAMLIT PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Dashboard Reengineering Balnus",
    page_icon="page_icon.png",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown(
    """
    <style>
    .block-container {
        padding-top: 3rem;
        padding-bottom: 0rem;
        padding-left: 0rem;
        padding-right: 0rem;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# The "Refresh Data" button in the dashboard's Data Sources menu navigates the
# parent window to this query param (it can't call back into Python directly
# since the dashboard is a static components.html iframe). Catch it here,
# before anything is fetched, and force past the daily auto-load cache below.
if st.query_params.get("refresh_data") == "1":
    fetch_data_sources_cache_clear_pending = True
    del st.query_params["refresh_data"]
else:
    fetch_data_sources_cache_clear_pending = False


#%% ============================================================
# STEP 2B - CELLULAR SIGNAL LOADER
# ============================================================

def show_signal_loader(text):

    placeholder = st.empty()

    placeholder.markdown(
        f"""
        <style>
        .signal-loader{{
            display:flex; flex-direction:column; align-items:center;
            justify-content:center; gap:16px; padding:70px 0;
        }}
        .signal-bars{{
            display:flex; align-items:flex-end; gap:6px; height:40px;
        }}
        .signal-bars span{{
            width:9px; border-radius:3px;
            background:linear-gradient(180deg,#4967ff,#2f46c7);
            animation:signal-pulse 1.1s ease-in-out infinite;
            transform-origin:bottom;
        }}
        .signal-bars span:nth-child(1){{height:12px; animation-delay:0s;}}
        .signal-bars span:nth-child(2){{height:20px; animation-delay:.12s;}}
        .signal-bars span:nth-child(3){{height:28px; animation-delay:.24s;}}
        .signal-bars span:nth-child(4){{height:36px; animation-delay:.36s;}}
        .signal-bars span:nth-child(5){{height:40px; animation-delay:.48s;}}
        @keyframes signal-pulse{{
            0%,100%{{opacity:.25; transform:scaleY(.35);}}
            50%{{opacity:1; transform:scaleY(1);}}
        }}
        .signal-text{{
            font-size:13px; font-weight:600; letter-spacing:.02em;
            color:#5b6b8c;
        }}
        </style>
        <div class="signal-loader">
          <div class="signal-bars"><span></span><span></span><span></span><span></span><span></span></div>
          <div class="signal-text">{text}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    return placeholder


#%% ============================================================
# STEP 2C - AUTO-RETRY ON ERROR
# ============================================================

MAX_AUTO_RETRIES = 3
RETRY_DELAY_SECONDS = 8


def handle_fetch_error(error, message, retry_key):

    attempts = st.session_state.get(retry_key, 0)

    st.error(message)

    if attempts < MAX_AUTO_RETRIES:

        st.session_state[retry_key] = attempts + 1

        st.warning(
            f"Retrying automatically in {RETRY_DELAY_SECONDS}s... "
            f"(attempt {attempts + 1}/{MAX_AUTO_RETRIES})"
        )

        st.exception(error)

        components.html(
            f"<script>setTimeout(() => window.parent.location.reload(), {RETRY_DELAY_SECONDS * 1000});</script>",
            height=0
        )

    else:

        st.error(
            "Auto-retry limit reached. Please check the error below and "
            "reload the page manually once it's fixed."
        )

        st.exception(error)


#%% ============================================================
# STEP 3 - GOOGLE DRIVE CLIENT
# ============================================================

DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


@st.cache_resource
def get_drive_credentials():

    return service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=DRIVE_SCOPES
    )


def get_drive_service():

    return build("drive", "v3", credentials=get_drive_credentials())


#%% ============================================================
# STEP 4 - DRIVE HELPERS
# ============================================================

def list_folder_files(service, folder_id):

    results = service.files().list(
        q=f"'{folder_id}' in parents and trashed=false",
        fields="files(id, name, mimeType, modifiedTime)"
    ).execute()

    files = results.get("files", [])

    return [
        f for f in files
        if not f["name"].startswith("~$")
        and f["name"] != ".DS_Store"
        and f["mimeType"] != "application/vnd.google-apps.folder"
    ]


def download_file_bytes(service, file_id):

    request = service.files().get_media(fileId=file_id)

    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)

    done = False
    while not done:
        _, done = downloader.next_chunk()

    return buffer.getvalue()


#%% ============================================================
# STEP 5 - FETCH DASHBOARD HTML
# ============================================================

@st.cache_data(ttl=300, show_spinner=False)
def fetch_html_from_drive(file_id):

    service = get_drive_service()

    content = download_file_bytes(service, file_id)

    return content.decode("utf-8")


html_file_id = st.secrets["gdrive"]["html_file_id"]

try:

    loader = show_signal_loader("Fetching dashboard from Google Drive, please wait...")

    html_content = fetch_html_from_drive(html_file_id)

    loader.empty()

    st.session_state.pop("retry_html", None)

except Exception as e:

    handle_fetch_error(
        e,
        "Failed to fetch the HTML file from Google Drive.",
        "retry_html"
    )

    st.stop()


#%% ============================================================
# STEP 6 - FETCH DATA SOURCES (IRR / BOQ / DEPLOYMENT / TRACKER / MSDB)
# ============================================================
#
# NOTE: TA LTE (ta_lte_folder_id) is still excluded from auto-load —
# it still works via the manual "Update Data" upload in that view.
#
# MSDB (msdb_folder_id) was re-added here (~48MB raw / ~64MB base64).
# This previously caused OOM crashes on the Community Cloud free tier
# combined with the other auto-loaded sources (see git history: "Revert
# TA LTE auto-load — caused OOM crash"). Only auto-load MSDB again once
# the Streamlit Cloud plan has been upgraded past the free tier's
# memory ceiling — otherwise expect the same "connection reset by peer"
# crash.

DATA_SOURCE_FOLDERS = {
    "irr": "irr_folder_id",
    "boq": "boq_folder_id",
    "deploy": "deploy_folder_id",
    "tracker": "tracker_folder_id",
    "msdb": "msdb_folder_id",
}

WITA = timezone(timedelta(hours=8))


def _daily_bucket_wita():

    # Data auto-refreshes once a day at 07:00 WITA. Until that hour, still
    # counts as the previous day's bucket so the cache doesn't flip early.
    now = datetime.now(WITA)

    if now.hour < 7:
        now -= timedelta(days=1)

    return now.strftime("%Y-%m-%d")


@st.cache_resource
def get_source_byte_cache():

    # Persists for the life of the app process (not tied to the
    # cache_data TTL below), keyed by Drive file id, so unchanged
    # files don't get re-downloaded every time the cache expires.
    return {}


def _download_entry(kind, file_meta):

    byte_cache = get_source_byte_cache()

    cached = byte_cache.get(file_meta["id"])

    if cached and cached["modifiedTime"] == file_meta["modifiedTime"]:

        return kind, {"name": cached["name"], "b64": cached["b64"]}

    service = get_drive_service()

    content = download_file_bytes(service, file_meta["id"])

    entry = {
        "name": file_meta["name"],
        "b64": base64.b64encode(content).decode("ascii"),
        "modifiedTime": file_meta["modifiedTime"]
    }

    byte_cache[file_meta["id"]] = entry

    return kind, {"name": entry["name"], "b64": entry["b64"]}


@st.cache_data(show_spinner=False)
def fetch_data_sources(_bucket):

    # _bucket (the WITA day, see _daily_bucket_wita) is the cache key: it
    # only changes once a day at 07:00 WITA, so this only re-runs then or
    # when the "Refresh Data" button clears the cache in between.
    service = get_drive_service()

    sources = {kind: [] for kind in DATA_SOURCE_FOLDERS}

    jobs = []

    for kind, secret_key in DATA_SOURCE_FOLDERS.items():

        folder_id = st.secrets["gdrive"][secret_key]

        for file_meta in list_folder_files(service, folder_id):

            jobs.append((kind, file_meta))

    with ThreadPoolExecutor(max_workers=3) as pool:

        for kind, entry in pool.map(lambda job: _download_entry(*job), jobs):

            sources[kind].append(entry)

    return sources


try:

    if fetch_data_sources_cache_clear_pending:
        fetch_data_sources.clear()

    loader = show_signal_loader("Fetching data sources from Google Drive, please wait...")

    data_sources = fetch_data_sources(_daily_bucket_wita())

    loader.empty()

    st.session_state.pop("retry_data_sources", None)

except Exception as e:

    handle_fetch_error(
        e,
        "Failed to fetch data sources from Google Drive.",
        "retry_data_sources"
    )

    data_sources = {}


#%% ============================================================
# STEP 7 - INJECT AUTO-LOAD SCRIPT INTO HTML
# ============================================================

auto_load_js = f"""
<script>
(function(){{
  const AUTO_SOURCES = {json.dumps(data_sources)};
  function b64ToBytes(b64){{
    const bin = atob(b64);
    const bytes = new Uint8Array(bin.length);
    for(let i=0;i<bin.length;i++) bytes[i] = bin.charCodeAt(i);
    return bytes;
  }}
  async function autoLoadTaLte(entries){{
    const already = (typeof TA_LTE_FILES !== 'undefined') ? TA_LTE_FILES : [];
    const names = entries.map(e => e.name);
    if(already.length && names.every(n => already.indexOf(n) !== -1)) return;
    const files = entries.map(e => new File([b64ToBytes(e.b64)], e.name));
    if(typeof window.sendTaLteFiles !== 'function'){{
      setTimeout(() => autoLoadTaLte(entries), 150);
      return;
    }}
    window.TA_LTE_FILES = names;
    if(typeof window.renderTaLteSourceStatus === 'function') window.renderTaLteSourceStatus();
    window.sendTaLteFiles(files);
  }}
  async function autoLoadSources(){{
    // Smallest sources first so the UI shows real progress quickly;
    // the biggest one (MSDB) — the slowest to parse and the main
    // cause of the post-login freeze — goes last.
    const kindsBySize = Object.keys(AUTO_SOURCES).sort((a, b) => {{
      const sizeOf = k => (AUTO_SOURCES[k] || []).reduce((s, e) => s + (e.b64 ? e.b64.length : 0), 0);
      return sizeOf(a) - sizeOf(b);
    }});
    for(const kind of kindsBySize){{
      let entries = AUTO_SOURCES[kind];
      if(!entries || !entries.length) continue;
      if(kind === 'ta_lte'){{
        try {{ await autoLoadTaLte(entries); }}
        catch(err) {{ console.error('Auto-load failed for', kind, err); }}
        continue;
      }}
      const already = (typeof FILES !== 'undefined' && FILES[kind]) ? FILES[kind].map(f => f.name) : [];
      entries = entries.filter(e => already.indexOf(e.name) === -1);
      if(!entries.length) continue;
      const files = entries.map(e => new File([b64ToBytes(e.b64)], e.name));
      try {{
        await loadFiles(files, kind);
      }} catch(err) {{
        console.error('Auto-load failed for', kind, err);
      }}
    }}
  }}
  let alreadyLoaded = false;
  function runAutoLoadOnce(){{
    if(alreadyLoaded) return;
    alreadyLoaded = true;
    autoLoadSources();
  }}
  function hookLogin(){{
    if(typeof window.doLogin !== 'function'){{
      setTimeout(hookLogin, 50);
      return;
    }}
    const origDoLogin = window.doLogin;
    window.doLogin = function(){{
      origDoLogin.apply(this, arguments);
      const overlay = document.getElementById('loginOverlay');
      const canSeeSources = (typeof currentUser !== 'undefined') && currentUser
        && Array.isArray(currentUser.views) && currentUser.views.indexOf('sources') !== -1;
      if(overlay && overlay.classList.contains('hidden') && canSeeSources){{
        runAutoLoadOnce();
      }}
    }};
  }}
  hookLogin();
}})();
</script>
"""

body_close_pos = html_content.rfind("</body>")

if body_close_pos != -1:
    html_content = (
        html_content[:body_close_pos]
        + auto_load_js
        + html_content[body_close_pos:]
    )
else:
    html_content += auto_load_js


#%% ============================================================
# STEP 8 - RENDER HTML
# ============================================================

try:

    loader = show_signal_loader("Loading dashboard, please wait...")

    components.html(
        html_content,
        height=1200,
        scrolling=True
    )

    loader.empty()

    st.session_state.pop("retry_render", None)

except Exception as e:

    handle_fetch_error(
        e,
        "Failed to render the HTML in Streamlit.",
        "retry_render"
    )

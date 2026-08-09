#%% ============================================================
# STEP 1 - IMPORT LIBRARY
# ============================================================

import base64
import io
import json
import socket

import streamlit as st
import streamlit.components.v1 as components
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

socket.setdefaulttimeout(30)


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


#%% ============================================================
# STEP 3 - GOOGLE DRIVE CLIENT
# ============================================================

DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


@st.cache_resource
def get_drive_service():

    credentials = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=DRIVE_SCOPES
    )

    return build("drive", "v3", credentials=credentials)


#%% ============================================================
# STEP 4 - DRIVE HELPERS
# ============================================================

def list_folder_files(service, folder_id):

    results = service.files().list(
        q=f"'{folder_id}' in parents and trashed=false",
        fields="files(id, name, mimeType)"
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

@st.cache_data(ttl=300, show_spinner="Mengambil dashboard dari Google Drive...")
def fetch_html_from_drive(file_id):

    service = get_drive_service()

    content = download_file_bytes(service, file_id)

    return content.decode("utf-8")


html_file_id = st.secrets["gdrive"]["html_file_id"]

try:

    html_content = fetch_html_from_drive(html_file_id)

except Exception as e:

    st.error(
        "Gagal mengambil file HTML dari Google Drive."
    )

    st.exception(e)

    st.stop()


#%% ============================================================
# STEP 6 - FETCH DATA SOURCES (IRR / BOQ / DEPLOYMENT / TRACKER / MSDB)
# ============================================================

DATA_SOURCE_FOLDERS = {
    "irr": "irr_folder_id",
    "boq": "boq_folder_id",
    "deploy": "deploy_folder_id",
    "tracker": "tracker_folder_id",
    "msdb": "msdb_folder_id",
}


@st.cache_data(ttl=300, show_spinner="Mengambil data source dari Google Drive...")
def fetch_data_sources():

    service = get_drive_service()

    sources = {}

    for kind, secret_key in DATA_SOURCE_FOLDERS.items():

        folder_id = st.secrets["gdrive"][secret_key]

        files = list_folder_files(service, folder_id)

        entries = []

        for f in files:

            content = download_file_bytes(service, f["id"])

            entries.append({
                "name": f["name"],
                "b64": base64.b64encode(content).decode("ascii")
            })

        sources[kind] = entries

    return sources


try:

    data_sources = fetch_data_sources()

except Exception as e:

    st.error(
        "Gagal mengambil data source dari Google Drive."
    )

    st.exception(e)

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
  async function autoLoadSources(){{
    for(const kind of Object.keys(AUTO_SOURCES)){{
      const entries = AUTO_SOURCES[kind];
      if(!entries || !entries.length) continue;
      const files = entries.map(e => new File([b64ToBytes(e.b64)], e.name));
      try {{
        await loadFiles(files, kind);
      }} catch(err) {{
        console.error('Auto-load gagal untuk', kind, err);
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
      if(overlay && overlay.classList.contains('hidden')){{
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

    with st.spinner("Memuat dashboard, mohon tunggu..."):

        components.html(
            html_content,
            height=1200,
            scrolling=True
        )

except Exception as e:

    st.error(
        "Gagal menampilkan HTML di Streamlit."
    )

    st.exception(e)

#%% ============================================================
# STEP 1 - IMPORT LIBRARY
# ============================================================

import io

import streamlit as st
import streamlit.components.v1 as components
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload


#%% ============================================================
# STEP 2 - STREAMLIT PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Dashboard Reengineering Balnus",
    page_icon="📊",
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
# STEP 4 - FETCH HTML FILE FROM DRIVE
# ============================================================

@st.cache_data(ttl=300)
def fetch_html_from_drive(file_id):

    service = get_drive_service()

    request = service.files().get_media(fileId=file_id)

    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)

    done = False
    while not done:
        _, done = downloader.next_chunk()

    return buffer.getvalue().decode("utf-8")


#%% ============================================================
# STEP 5 - LOAD HTML CONTENT
# ============================================================

file_id = st.secrets["gdrive"]["file_id"]

try:

    html_content = fetch_html_from_drive(file_id)

except Exception as e:

    st.error(
        "Gagal mengambil file HTML dari Google Drive."
    )

    st.exception(e)

    st.stop()


#%% ============================================================
# STEP 6 - RENDER HTML
# ============================================================

try:

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

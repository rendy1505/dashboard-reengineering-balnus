#%% ============================================================
# STEP 1 - IMPORT LIBRARY
# ============================================================

import streamlit as st
import streamlit.components.v1 as components
from pathlib import Path


#%% ============================================================
# STEP 2 - STREAMLIT PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Dashboard Reengineering Balnus",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)


#%% ============================================================
# STEP 3 - SET HTML DIRECTORY
# ============================================================

HTML_DIR = Path(__file__).parent / "HTML_DIR"


#%% ============================================================
# STEP 4 - CHECK HTML DIRECTORY
# ============================================================

if not HTML_DIR.exists():

    st.error(
        "Folder HTML tidak ditemukan."
    )

    st.code(
        str(HTML_DIR)
    )

    st.stop()


#%% ============================================================
# STEP 5 - FIND HTML FILE
# ============================================================

html_files = sorted(
    HTML_DIR.glob("*.html")
)

if not html_files:

    st.warning(
        "Tidak ada file HTML ditemukan."
    )

    st.code(
        str(HTML_DIR)
    )

    st.stop()

selected_html = html_files[0]


#%% ============================================================
# STEP 6 - READ HTML FILE
# ============================================================

try:

    html_content = selected_html.read_text(
        encoding="utf-8"
    )

except UnicodeDecodeError:

    st.error(
        "File HTML bukan UTF-8 atau encoding-nya berbeda."
    )

    st.stop()

except Exception as e:

    st.error(
        "Gagal membaca file HTML."
    )

    st.exception(e)

    st.stop()


#%% ============================================================
# STEP 7 - RENDER HTML
# ============================================================

try:

    components.html(
        html_content,
        height=1000,
        scrolling=True
    )

except Exception as e:

    st.error(
        "Gagal menampilkan HTML di Streamlit."
    )

    st.exception(e)

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
    initial_sidebar_state="expanded"
)


#%% ============================================================
# STEP 3 - SET HTML DIRECTORY
# ============================================================

HTML_DIR = Path(__file__).parent / "HTML_DIR"

print("HTML Directory:")
print(HTML_DIR)


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


print("Folder HTML ditemukan.")


#%% ============================================================
# STEP 5 - FIND ALL HTML FILES
# ============================================================

html_files = sorted(
    HTML_DIR.glob("*.html")
)

print("Jumlah HTML file:", len(html_files))

for file in html_files:
    print("-", file.name)


#%% ============================================================
# STEP 6 - SIDEBAR
# ============================================================

st.sidebar.title(
    "📊 Dashboard"
)

st.sidebar.markdown("---")


# Kalau ada HTML
if html_files:

    selected_html = st.sidebar.selectbox(
        "Pilih Dashboard",
        html_files,
        format_func=lambda x: x.name
    )

else:

    selected_html = None


#%% ============================================================
# STEP 7 - SIDEBAR INFORMATION
# ============================================================

st.sidebar.markdown("---")

st.sidebar.subheader(
    "HTML Directory"
)

st.sidebar.caption(
    str(HTML_DIR)
)


#%% ============================================================
# STEP 8 - MAIN HEADER
# ============================================================

st.title(
    "Dashboard Reengineering Balnus"
)

st.markdown(
    """
    **Dashboard HTML → Streamlit**
    
    Pilih dashboard dari menu sebelah kiri.
    """
)


#%% ============================================================
# STEP 9 - CHECK HTML FILE
# ============================================================

if selected_html is None:

    st.warning(
        "Tidak ada file HTML ditemukan."
    )

    st.info(
        "Pastikan file .html berada di folder:"
    )

    st.code(
        str(HTML_DIR)
    )

    st.stop()


#%% ============================================================
# STEP 10 - DISPLAY SELECTED FILE
# ============================================================

st.caption(
    f"Dashboard aktif: {selected_html.name}"
)


#%% ============================================================
# STEP 11 - READ HTML FILE
# ============================================================

try:

    html_content = selected_html.read_text(
        encoding="utf-8"
    )

    print(
        f"Berhasil membaca: {selected_html.name}"
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
# STEP 12 - HTML FILE SIZE
# ============================================================

file_size_kb = (
    selected_html.stat().st_size / 1024
)

st.caption(
    f"File size: {file_size_kb:.2f} KB"
)


#%% ============================================================
# STEP 13 - RENDER HTML
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


#%% ============================================================
# STEP 14 - FOOTER
# ============================================================

st.markdown("---")

st.caption(
    "Dashboard Reengineering Balnus | Streamlit"
)
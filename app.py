import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import date
import os
import time

# ─────────────────────────────
# PAGE CONFIG
# ─────────────────────────────
st.set_page_config(layout="wide")

# ─────────────────────────────
# CORPORATE THEME
# ─────────────────────────────
st.markdown("""
<style>
body { background-color: #f4f6f9; }

.block-container {
    padding-top: 3rem !important;
    padding-left: 2rem;
    padding-right: 2rem;
}

.erp-card {
    background-color: white;
    padding: 18px;
    border-radius: 10px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    margin-bottom: 15px;
}

.update-card {
    background-color: white;
    padding: 18px;
    border-radius: 10px;
    border: 1px solid #dcdcdc;
    box-shadow: 0 3px 10px rgba(0,0,0,0.06);
}

h1 { font-size: 22px !important; }
h3 { font-size: 16px !important; }

input, div[data-baseweb="select"] > div {
    height: 34px !important;
    font-size: 13px !important;
    text-align: left !important;
}

button {
    height: 34px !important;
    font-size: 13px !important;
}

.status-post {
    color: green;
    font-weight: 600;
}

.status-unpost {
    color: red;
    font-weight: 600;
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────
# HEADER
# ─────────────────────────────
col1, col2 = st.columns([7,2])

with col1:
    st.markdown("""
        <h1>📊 Citykart Vendor Credit Note Updation Tool</h1>
        <p style='color:gray;'>Select → Filter → Update</p>
    """, unsafe_allow_html=True)

with col2:
    logo_path = os.path.join(os.path.dirname(__file__), "logo.png")
    if os.path.exists(logo_path):
        st.image(logo_path, width=120)

# ─────────────────────────────
# DATABASE
# ─────────────────────────────
DB_URL = "oracle+oracledb://Report:Report@10.0.0.15:1521/?service_name=Ginesys"

@st.cache_resource
def get_engine():
    return create_engine(DB_URL)

engine = get_engine()

# ─────────────────────────────
# LOGIN
# ─────────────────────────────
st.sidebar.title("🔐 Login")

users = {
    "amit": {"password": "amit123", "role": "Admin"},
    "operator1": {"password": "op123", "role": "Operator"},
    "viewer1": {"password": "view123", "role": "Viewer"},
}

username = st.sidebar.text_input("Username")
password = st.sidebar.text_input("Password", type="password")

if username in users and password == users[username]["password"]:
    role = users[username]["role"]
    st.sidebar.success(role)
else:
    st.stop()

can_edit = role in ["Admin", "Operator"]

# ─────────────────────────────
# FILTER CARD
# ─────────────────────────────
st.markdown("<div class='erp-card'>", unsafe_allow_html=True)

col_d1, col_d2 = st.columns(2)

MIN_DATE = date(2025, 4, 1)

with col_d1:
    from_date = st.date_input("From Date", value=MIN_DATE, min_value=MIN_DATE)

with col_d2:
    to_date = st.date_input("To Date", value=date.today(), min_value=MIN_DATE)

@st.cache_data
def load_vendors():
    query = "SELECT SLCODE, SLNAME FROM SSRK.FINSL ORDER BY SLNAME"
    with engine.connect() as conn:
        df = pd.read_sql(text(query), conn)

    df.columns = df.columns.str.upper().str.strip()
    df["SLCODE"] = pd.to_numeric(df["SLCODE"], errors="coerce").fillna(0).astype(int)
    df["DISPLAY"] = df["SLNAME"] + " - " + df["SLCODE"].astype(str)
    return df

vendor_master = load_vendors()

col1, col2 = st.columns([3,2])

with col1:
    selected_display = st.selectbox(
        "Vendor (Name - Code)",
        ["Select Vendor"] + vendor_master["DISPLAY"].tolist()
    )

if selected_display == "Select Vendor":
    st.stop()

selected_slcode = int(selected_display.split(" - ")[1])

with col2:
    selected_type = st.selectbox(
        "Entry Type",
        ["Select Entry Type",
         "Purchase Debit Note",
         "Purchase Credit Note",
         "Finance Debit Note",
         "Finance Credit Note",
         "Purchase Return Note"]
    )

if selected_type == "Select Entry Type":
    st.stop()

st.markdown("</div>", unsafe_allow_html=True)

# ─────────────────────────────
# TABLE LOGIC
# ─────────────────────────────
if selected_type == "Purchase Debit Note":
    table_name = "PURINVJRNMAIN"
    condition = "JRNTYPE = 'D' AND PCODE = :code"
elif selected_type == "Purchase Credit Note":
    table_name = "PURINVJRNMAIN"
    condition = "JRNTYPE = 'C' AND PCODE = :code"
elif selected_type == "Finance Debit Note":
    table_name = "FINJRNMAIN"
    condition = "JRNTYPE = 'D' AND SLCODE = :code"
elif selected_type == "Finance Credit Note":
    table_name = "FINJRNMAIN"
    condition = "JRNTYPE = 'C' AND SLCODE = :code"
else:
    table_name = "PURRTMAIN"
    condition = "SLCODE = :code"

if table_name == "PURRTMAIN":
    date_col = "RTDT"
else:
    date_col = "JRNDT"

query = f"""
SELECT *
FROM SSRK.{table_name}
WHERE {condition}
AND UDFSTRING01 IS NULL
AND TRUNC({date_col}) >= TO_DATE('2025-04-01','YYYY-MM-DD')
AND TRUNC({date_col}) BETWEEN TO_DATE(:from_dt,'YYYY-MM-DD')
AND TO_DATE(:to_dt,'YYYY-MM-DD')
"""

with engine.connect() as conn:
    df = pd.read_sql(text(query), conn, params={
        "code": selected_slcode,
        "from_dt": str(from_date),
        "to_dt": str(to_date)
    })

if df.empty:
    st.warning("No Unfilled Credit Note Entries Found")
    st.stop()

df.columns = df.columns.str.upper().str.strip()

# ─────────────────────────────
# STATUS COLUMN
# ─────────────────────────────
if "RELEASE_STATUS" in df.columns:
    df["STATUS"] = df["RELEASE_STATUS"].apply(
        lambda x: "Post" if str(x).strip().upper() == "P" else "UnPost"
    )

# ─────────────────────────────
# ENTRY COLUMN DETECTION
# ─────────────────────────────
possible_entry_cols = ["SCHEME_DOCNO","JRNCODE","DOCNO","DOC_NO","VNO","JRNNO"]
entry_column = next((col for col in possible_entry_cols if col in df.columns), None)

if entry_column is None:
    st.error("No Entry No column found.")
    st.stop()

selected_entry_no = st.selectbox(
    "Select Entry No",
    df[entry_column].astype(str).unique()
)

# Show STATUS
selected_status = df.loc[
    df[entry_column].astype(str) == selected_entry_no,
    "STATUS"
].values[0]

if selected_status == "Post":
    st.markdown(f"<div class='status-post'>STATUS : POST</div>", unsafe_allow_html=True)
else:
    st.markdown(f"<div class='status-unpost'>STATUS : UNPOST</div>", unsafe_allow_html=True)



ATTACH_FOLDER = os.path.join(os.path.dirname(__file__), "attachments")

if not os.path.exists(ATTACH_FOLDER):
    os.makedirs(ATTACH_FOLDER)

# ─────────────────────────────
# UPDATE SECTION
# ─────────────────────────────
st.markdown("<div class='update-card'>", unsafe_allow_html=True)
st.markdown("### ✏ Manual Update Section")

credit_note_value = st.text_input("Enter Credit Note Value")

if "confirm_update" not in st.session_state:
    st.session_state.confirm_update = False

uploaded_file = st.file_uploader(
    "Attach Document (CSV, PDF, Excel, Image etc.)",
    type=None
)

if can_edit and st.button("💾 Update Record"):

    if not credit_note_value:
        st.warning("Enter value")
        st.stop()

    st.session_state.confirm_update = True


if st.session_state.confirm_update:

    st.warning(f"Confirm update for Entry '{selected_entry_no}'?")

    col_yes, col_no = st.columns(2)

    if col_yes.button("✅ Yes"):

        with engine.begin() as conn:
            conn.execute(text(f"""
                UPDATE SSRK.{table_name}
                SET UDFSTRING01 = :val
                WHERE {entry_column} = :j
            """), {
                "val": credit_note_value,
                "j": selected_entry_no
            })

        # ───────── FILE SAVE ─────────
        if uploaded_file is not None:

            ext = os.path.splitext(uploaded_file.name)[1]

            file_name = f"{selected_entry_no}_{credit_note_value}_{date.today()}{ext}"

            save_path = os.path.join(ATTACH_FOLDER, file_name)

            with open(save_path, "wb") as f:
                f.write(uploaded_file.getbuffer())

        st.success("✅ Credit Note Updated Successfully")
        st.session_state.confirm_update = False
        time.sleep(1)
        st.rerun()

    if col_no.button("❌ Cancel"):
        st.session_state.confirm_update = False

st.markdown("</div>", unsafe_allow_html=True)


# ─────────────────────────────
# AUDIT HISTORY
# ─────────────────────────────
st.markdown("## 📜 Audit History")

try:
    with engine.connect() as conn:
        audit_df = pd.read_sql(
            text("SELECT * FROM REPORT.T_NOTE_AUDIT_LOG ORDER BY ACTION_TIME DESC"),
            conn
        )
    st.dataframe(audit_df, use_container_width=True)
except:
    st.info("No audit history found")


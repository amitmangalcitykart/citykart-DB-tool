import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.types import VARCHAR, FLOAT, INTEGER, DATE
from datetime import datetime
import oracledb

# ─────────────────────────────
# PAGE CONFIG
# ─────────────────────────────
st.set_page_config(
    page_title="Citykart Enterprise DB Tool",
    layout="wide"
)

# ─────────────────────────────
# CUSTOM CSS (Professional UI)
# ─────────────────────────────
st.markdown("""
<style>
.main-title {
    font-size: 48px;
    font-weight: 700;
    color: #c62828;
}
.sub-title {
    font-size: 24px;
    color: #2e7d32;
    margin-bottom: 20px;
}
.card {
    background-color: white;
    padding: 25px;
    border-radius: 18px;
    box-shadow: 0px 4px 20px rgba(0,0,0,0.06);
}
.metric-card {
    background-color: #f8f9fa;
    padding: 20px;
    border-radius: 14px;
    text-align: center;
}
hr {
    margin-top: 10px;
    margin-bottom: 30px;
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────
# HEADER SECTION
# ─────────────────────────────
col_logo, col_title = st.columns([1,5])

with col_logo:
    st.image("logo.png.webp", width=120)

with col_title:
    st.markdown('<div class="main-title">Citykart Enterprise DB Tool</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Upload → Validate → Backup → Overwrite</div>', unsafe_allow_html=True)

st.markdown("<hr>", unsafe_allow_html=True)

# ─────────────────────────────
# DATABASE CONNECTION
# ─────────────────────────────
DB_URL = "oracle+oracledb://Report:Report@10.0.0.15:1521/?service_name=Ginesys"

@st.cache_resource
def get_engine():
    return create_engine(DB_URL)

engine = get_engine()

# ─────────────────────────────
# MAIN LAYOUT
# ─────────────────────────────
left, right = st.columns([2,1])

# ============================
# LEFT SIDE (Upload + Preview)
# ============================
with left:
    st.markdown('<div class="card">', unsafe_allow_html=True)

    st.subheader("📂 Upload CSV File")
    uploaded_file = st.file_uploader("", type=["csv"])

    if uploaded_file:
        csv_df = pd.read_csv(uploaded_file)
        csv_df.columns = csv_df.columns.str.upper()

        st.success("File Uploaded Successfully")
        st.dataframe(csv_df.head(), use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True)

# ============================
# RIGHT SIDE (DB CONFIG)
# ============================
with right:
    st.markdown('<div class="card">', unsafe_allow_html=True)

    st.subheader("🗄 Database Configuration")

    TABLE_SCHEMA = st.text_input("Schema Name", "MISRETAIL").upper()
    TABLE_NAME = st.text_input("Table Name", "T_USER_INPUT_TEMP_TABLE").upper()

    st.markdown('</div>', unsafe_allow_html=True)

# ─────────────────────────────
# VALIDATION SECTION
# ─────────────────────────────
if uploaded_file:

    try:
        with engine.connect() as conn:
            table_check = conn.execute(text(f"""
                SELECT COUNT(*) FROM ALL_TABLES
                WHERE OWNER = '{TABLE_SCHEMA}'
                AND TABLE_NAME = '{TABLE_NAME}'
            """)).scalar()

        if table_check == 0:
            st.error("❌ Main table does not exist.")
            st.stop()

    except Exception as e:
        st.error(f"Connection Error: {e}")
        st.stop()

    with engine.connect() as conn:
        db_df = pd.read_sql(
            text(f"SELECT * FROM {TABLE_SCHEMA}.{TABLE_NAME}"),
            conn
        )

    db_df.columns = db_df.columns.str.upper()

    if set(csv_df.columns) != set(db_df.columns):
        st.error("❌ Column mismatch detected.")
        st.stop()

    csv_df = csv_df[db_df.columns]

    total_rows = len(csv_df)
    unique_rows = len(csv_df.drop_duplicates())
    duplicate_rows = total_rows - unique_rows

    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("📊 Validation Summary")

    m1, m2, m3 = st.columns(3)

    with m1:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("Total Rows", total_rows)
        st.markdown('</div>', unsafe_allow_html=True)

    with m2:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("Unique Rows", unique_rows)
        st.markdown('</div>', unsafe_allow_html=True)

    with m3:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("Duplicate Rows", duplicate_rows)
        st.markdown('</div>', unsafe_allow_html=True)

    # ─────────────────────────────
    # ENTERPRISE BUTTON
    # ─────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)

    if st.button("🚀 Backup & Overwrite Table", use_container_width=True):

        if duplicate_rows > 0:
            st.error("Duplicate rows exist. Fix before overwrite.")
            st.stop()

        TEMP_TABLE = f"{TABLE_NAME}_TEMP"

        try:
            with engine.begin() as conn:

                conn.execute(text(f"""
                    BEGIN
                        EXECUTE IMMEDIATE 'DROP TABLE {TABLE_SCHEMA}.{TEMP_TABLE}';
                    EXCEPTION
                        WHEN OTHERS THEN
                            IF SQLCODE != -942 THEN RAISE; END IF;
                    END;
                """))

                conn.execute(text(f"""
                    CREATE TABLE {TABLE_SCHEMA}.{TEMP_TABLE}
                    AS SELECT * FROM {TABLE_SCHEMA}.{TABLE_NAME}
                """))

                conn.execute(text(f"DROP TABLE {TABLE_SCHEMA}.{TABLE_NAME}"))

            csv_df.to_sql(
                TABLE_NAME,
                engine,
                schema=TABLE_SCHEMA,
                if_exists="replace",
                index=False
            )

            st.success("🎉 Backup Created & Main Table Overwritten Successfully!")

        except Exception as e:
            st.error(f"Operation Failed: {e}")


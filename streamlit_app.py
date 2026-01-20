import sqlite3
import datetime as dt
from typing import Optional

import pandas as pd
import streamlit as st


# ======================
# 1. App config
# ======================
APP_NAME = "Astra"
DB_PATH = "astra.db"

st.set_page_config(page_title=APP_NAME, page_icon="🎫", layout="wide")
st.title("🎫 Astra")
st.caption("Simple, clean defect tracking with create & edit flow.")


# ======================
# 2. Constants
# ======================
COMPANY_CODES = ["4310", "8410"]
COMPANY_INDEX = {"4310": "1", "8410": "2"}

MODULES = ["PLM", "PP", "FI", "SD", "MM", "QM", "ABAP", "BASIS", "OTHER"]
DEFECT_TYPES = [
    "Functional",
    "Data Migration",
    "Test Data",
    "EDI set up",
    "Configuration",
    "Security/Authorization",
    "Performance",
    "Other",
]
PRIORITIES = ["P1 - Critical", "P2 - High", "P3 - Medium", "P4 - Low"]
STATUSES = ["New", "In Progress", "Blocked", "Resolved", "Closed", "Reopened"]
ENVIRONMENTS = ["P1S", "Q1S", "Q2S", "Q2C"]
OPEN_WITH = ["SDS", "SNP", "Client", "Other"]


# ======================
# 3. Database
# ======================
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    return conn


def init_db():
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS defects (
                defect_id TEXT PRIMARY KEY,
                company_code TEXT,
                open_date TEXT,
                module TEXT,
                defect_title TEXT,
                defect_type TEXT,
                priority TEXT,
                status TEXT,
                resolved_date TEXT,
                open_with TEXT,
                reported_by TEXT,
                responsible TEXT,
                environment TEXT,
                linked_test_id TEXT,
                description TEXT,
                steps TEXT,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        conn.commit()


# ======================
# 4. Helpers
# ======================
def today():
    return dt.date.today()


def parse_date(x) -> Optional[dt.date]:
    if not x:
        return None
    try:
        return pd.to_datetime(x).date()
    except Exception:
        return None


def date_str(d: Optional[dt.date]):
    return d.isoformat() if d else None


def compute_age(open_date, resolved_date, status):
    if not open_date:
        return None
    end = resolved_date if status in ["Resolved", "Closed"] and resolved_date else today()
    return (end - open_date).days


def next_defect_id(module, company_code):
    prefix = f"{module}-{COMPANY_INDEX[company_code]}-"
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT defect_id FROM defects WHERE defect_id LIKE ?",
            (prefix + "%",),
        ).fetchall()
    nums = []
    for r in rows:
        try:
            nums.append(int(r[0].split("-")[-1]))
        except Exception:
            pass
    nxt = max(nums) + 1 if nums else 1
    return f"{prefix}{nxt:03d}"


# ======================
# 5. CRUD
# ======================
def load_defects():
    init_db()
    with get_conn() as conn:
        df = pd.read_sql("SELECT * FROM defects ORDER BY created_at DESC", conn)

    if df.empty:
        return pd.DataFrame()

    df["Open Date"] = df["open_date"].apply(parse_date)
    df["Resolved Date"] = df["resolved_date"].apply(parse_date)
    df["Age (days)"] = df.apply(
        lambda r: compute_age(r["Open Date"], r["Resolved Date"], r["status"]), axis=1
    )

    return df.rename(
        columns={
            "company_code": "Company Code",
            "module": "Module",
            "defect_id": "Defect ID",
            "defect_title": "Defect Title",
            "defect_type": "Defect Type",
            "priority": "Priority",
            "status": "Status",
            "open_with": "Open with",
            "reported_by": "Reported By",
            "responsible": "Responsible",
            "environment": "Environment",
            "linked_test_id": "Linked Test ID",
            "description": "Description",
            "steps": "Description / Steps",
        }
    )


def insert_defect(data):
    now = dt.datetime.now().isoformat(timespec="seconds")
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO defects VALUES (
                :defect_id, :company_code, :open_date, :module,
                :defect_title, :defect_type, :priority, :status,
                :resolved_date, :open_with, :reported_by, :responsible,
                :environment, :linked_test_id, :description, :steps,
                :created_at, :updated_at
            )
            """,
            {**data, "created_at": now, "updated_at": now},
        )
        conn.commit()


def update_defect(defect_id, data):
    now = dt.datetime.now().isoformat(timespec="seconds")
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE defects SET
                company_code=:company_code,
                open_date=:open_date,
                module=:module,
                defect_title=:defect_title,
                defect_type=:defect_type,
                priority=:priority,
                status=:status,
                resolved_date=:resolved_date,
                open_with=:open_with,
                reported_by=:reported_by,
                responsible=:responsible,
                environment=:environment,
                linked_test_id=:linked_test_id,
                description=:description,
                steps=:steps,
                updated_at=:updated_at
            WHERE defect_id=:defect_id
            """,
            {**data, "defect_id": defect_id, "updated_at": now},
        )
        conn.commit()


# ======================
# 6. Sidebar filters
# ======================
st.sidebar.header("Filters")
company_f = st.sidebar.selectbox("Company Code", ["All"] + COMPANY_CODES)
module_f = st.sidebar.selectbox("Module", ["All"] + MODULES)
status_f = st.sidebar.selectbox("Status", ["All"] + STATUSES)
priority_f = st.sidebar.selectbox("Priority", ["All"] + PRIORITIES)
search = st.sidebar.text_input("Search").lower().strip()


# ======================
# 7. Create defect
# ======================
st.subheader("➕ Create Defect")

with st.form("create_form"):
    c1, c2, c3, c4 = st.columns(4)
    company_code = c1.selectbox("Company Code", COMPANY_CODES)
    open_date = c2.date_input("Open Date", today())
    module = c3.selectbox("Module", MODULES)
    defect_id = next_defect_id(module, company_code)
    c4.text_input("Defect ID", defect_id, disabled=True)

    defect_title = st.text_input("Defect Title *")
    defect_type = st.selectbox("Defect Type", DEFECT_TYPES)
    priority = st.selectbox("Priority", PRIORITIES, index=1)
    status = st.selectbox("Status", STATUSES, index=0)

    resolved_date = None
    if status in ["Resolved", "Closed"]:
        resolved_date = st.date_input("Resolved Date", today())

    open_with = st.selectbox("Open with", OPEN_WITH)
    reported_by = st.text_input("Reported By *")
    responsible = st.text_input("Responsible")
    environment = st.selectbox("Environment", ENVIRONMENTS)

    linked_test_id = st.text_input("Linked Test ID")
    description = st.text_area("Description")
    steps = st.text_area("Description / Steps")

    submit = st.form_submit_button("Create")

if submit:
    if not defect_title or not reported_by:
        st.error("Defect Title and Reported By are required.")
    else:
        insert_defect(
            {
                "defect_id": defect_id,
                "company_code": company_code,
                "open_date": date_str(open_date),
                "module": module,
                "defect_title": defect_title,
                "defect_type": defect_type,
                "priority": priority,
                "status": status,
                "resolved_date": date_str(resolved_date),
                "open_with": open_with,
                "reported_by": reported_by,
                "responsible": responsible,
                "environment": environment,
                "linked_test_id": linked_test_id,
                "description": description,
                "steps": steps,
            }
        )
        st.success(f"Defect {defect_id} created.")
        st.rerun()


# ======================
# 8. List defects
# ======================
st.divider()
st.subheader("📋 Defects")

df = load_defects()
if df.empty:
    st.info("No defects yet.")
else:
    if company_f != "All":
        df = df[df["Company Code"] == company_f]
    if module_f != "All":
        df = df[df["Module"] == module_f]
    if status_f != "All":
        df = df[df["Status"] == status_f]
    if priority_f != "All":
        df = df[df["Priority"] == priority_f]
    if search:
        df = df[
            df[["Defect ID", "Defect Title", "Reported By", "Responsible"]]
            .astype(str)
            .agg(" ".join, axis=1)
            .str.lower()
            .str.contains(search)
        ]

    st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown("### ✏️ Edit Defect")
    selected_id = st.selectbox("Select Defect ID", df["Defect ID"].tolist())

    edit_row = df[df["Defect ID"] == selected_id].iloc[0]

    with st.form("edit_form"):
        company_code = st.selectbox("Company Code", COMPANY_CODES, index=COMPANY_CODES.index(edit_row["Company Code"]))
        open_date = st.date_input("Open Date", edit_row["Open Date"])
        module = st.selectbox("Module", MODULES, index=MODULES.index(edit_row["Module"]))

        defect_title = st.text_input("Defect Title", edit_row["Defect Title"])
        defect_type = st.selectbox("Defect Type", DEFECT_TYPES, index=DEFECT_TYPES.index(edit_row["Defect Type"]))
        priority = st.selectbox("Priority", PRIORITIES, index=PRIORITIES.index(edit_row["Priority"]))
        status = st.selectbox("Status", STATUSES, index=STATUSES.index(edit_row["Status"]))

        resolved_date = edit_row["Resolved Date"]
        if status in ["Resolved", "Closed"]:
            resolved_date = st.date_input("Resolved Date", resolved_date or today())

        open_with = st.selectbox("Open with", OPEN_WITH, index=OPEN_WITH.index(edit_row["Open with"]))
        reported_by = st.text_input("Reported By", edit_row["Reported By"])
        responsible = st.text_input("Responsible", edit_row["Responsible"])
        environment = st.selectbox("Environment", ENVIRONMENTS, index=ENVIRONMENTS.index(edit_row["Environment"]))

        linked_test_id = st.text_input("Linked Test ID", edit_row["Linked Test ID"])
        description = st.text_area("Description", edit_row["Description"])
        steps = st.text_area("Description / Steps", edit_row["Description / Steps"])

        save = st.form_submit_button("Save Changes")

    if save:
        update_defect(
            selected_id,
            {
                "company_code": company_code,
                "open_date": date_str(open_date),
                "module": module,
                "defect_title": defect_title,
                "defect_type": defect_type,
                "priority": priority,
                "status": status,
                "resolved_date": date_str(resolved_date),
                "open_with": open_with,
                "reported_by": reported_by,
                "responsible": responsible,
                "environment": environment,
                "linked_test_id": linked_test_id,
                "description": description,
                "steps": steps,
            },
        )
        st.success("Defect updated.")
        st.rerun()

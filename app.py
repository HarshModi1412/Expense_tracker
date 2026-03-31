import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px
import uuid
from sqlalchemy import create_engine, text

# ---------------- ENGINE ----------------
@st.cache_resource
def get_engine():
    return create_engine(
        st.secrets["DATABASE_URL"],
        connect_args={"sslmode": "require"},
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=300
    )

engine = get_engine()

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Expense Tracker", layout="wide")

DEFAULT_CATEGORIES = [
    "Tea", "Office BF", "Zomato",
    "Quick Commerce", "Outside Eating"
]

# ---------------- CACHE LOAD ----------------
@st.cache_data(ttl=60)
def load_expenses():
    try:
        return pd.read_sql("SELECT * FROM expenses", engine)
    except:
        return pd.DataFrame(columns=["id","datetime","category","amount","details"])

@st.cache_data(ttl=60)
def load_investments():
    try:
        return pd.read_sql("SELECT * FROM investments", engine)
    except:
        return pd.DataFrame(columns=["id","datetime","amount","notes"])

@st.cache_data(ttl=300)
def load_categories():
    try:
        df = pd.read_sql("SELECT * FROM categories", engine)
        if df.empty:
            save_categories(DEFAULT_CATEGORIES)
            return DEFAULT_CATEGORIES
        return df["category"].tolist()
    except:
        save_categories(DEFAULT_CATEGORIES)
        return DEFAULT_CATEGORIES

@st.cache_data(ttl=60)
def load_planned():
    try:
        return pd.read_sql("SELECT * FROM planned_expenses", engine)
    except:
        return pd.DataFrame(columns=["id","name","amount","done"])

# ---------------- WRITE OPS ----------------
def insert_expense(row):
    pd.DataFrame([row]).to_sql("expenses", engine, if_exists="append", index=False)

def insert_investment(row):
    pd.DataFrame([row]).to_sql("investments", engine, if_exists="append", index=False)

def insert_planned(row):
    pd.DataFrame([row]).to_sql("planned_expenses", engine, if_exists="append", index=False)

def update_expense(id, cat, amt, det):
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE expenses
            SET category=:cat, amount=:amt, details=:det
            WHERE id=:id
        """), {"id": id, "cat": cat, "amt": amt, "det": det})

def delete_expense(id):
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM expenses WHERE id=:id"), {"id": id})

def toggle_planned(id, status):
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE planned_expenses
            SET done=:status
            WHERE id=:id
        """), {"id": id, "status": status})

def delete_planned(id):
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM planned_expenses WHERE id=:id"), {"id": id})

def save_categories(cats):
    pd.DataFrame({"category": cats}).to_sql("categories", engine, if_exists="replace", index=False)

def get_total_balance():
    try:
        df = pd.read_sql("SELECT * FROM balance", engine)
        return float(df["balance"][0])
    except:
        set_total_balance(0.0)
        return 0.0

def set_total_balance(val):
    pd.DataFrame({"id":[1],"balance":[val]}).to_sql("balance", engine, if_exists="replace", index=False)

# ---------------- BALANCE ----------------
def compute_balance(exp_df, inv_df):
    return get_total_balance() - exp_df["amount"].sum() - inv_df["amount"].sum()

# ---------------- LOAD ----------------
df = load_expenses()
inv_df = load_investments()
planned_df = load_planned()
categories = load_categories() + ["Manual"]

actual_balance = compute_balance(df, inv_df)
pending_planned = planned_df[planned_df["done"] == False]["amount"].sum() if not planned_df.empty else 0
projected_balance = actual_balance - pending_planned

# ---------------- MESSAGE ----------------
if "msg" in st.session_state:
    st.success(st.session_state["msg"])
    del st.session_state["msg"]

# ---------------- SIDEBAR ----------------
st.sidebar.title("💰 Wallet")
st.sidebar.metric("Balance", f"₹ {actual_balance:.2f}")
st.sidebar.metric("Projected Balance", f"₹ {projected_balance:.2f}")

add_money = st.sidebar.number_input("Add Balance", min_value=0.0)

if st.sidebar.button("Add Money"):
    set_total_balance(get_total_balance() + add_money)
    st.cache_data.clear()
    st.session_state["msg"] = "Balance Added"
    st.rerun()

page = st.sidebar.radio(
    "Navigate",
    ["Add Expense","Add Investment","Planned Expenses","Analysis","Category Deep Dive","Edit Expenses","Manage Categories"]
)

# ---------------- ADD EXPENSE ----------------
if page == "Add Expense":
    st.title("➕ Add Expense")

    with st.form("expense_form", clear_on_submit=True):
        category = st.selectbox("Category", categories)

        manual = ""
        if category == "Manual":
            manual = st.text_input("Enter Title")

        amount = st.number_input("Amount", min_value=0.0)
        details = st.text_input("Details")

        if st.form_submit_button("Add Expense"):
            final_cat = manual.strip() if category == "Manual" else category

            if amount <= 0:
                st.error("Invalid amount")
            elif amount > actual_balance:
                st.error("Insufficient balance")
            else:
                insert_expense({
                    "id": str(uuid.uuid4()),
                    "datetime": datetime.now(),
                    "category": final_cat,
                    "amount": amount,
                    "details": details
                })

                st.cache_data.clear()
                st.session_state["msg"] = "Expense Added"
                st.rerun()

# ---------------- ADD INVESTMENT ----------------
elif page == "Add Investment":
    st.title("📈 Add Investment")

    with st.form("investment_form", clear_on_submit=True):
        amount = st.number_input("Investment Amount", min_value=0.0)
        notes = st.text_input("Notes")

        if st.form_submit_button("Add Investment"):
            if amount <= 0:
                st.error("Invalid amount")
            elif amount > actual_balance:
                st.error("Not enough balance")
            else:
                insert_investment({
                    "id": str(uuid.uuid4()),
                    "datetime": datetime.now(),
                    "amount": amount,
                    "notes": notes
                })

                st.cache_data.clear()
                st.session_state["msg"] = "Investment Added"
                st.rerun()

    inv_df = load_investments()
    st.subheader("💼 Current Investments")
    st.dataframe(inv_df.sort_values("datetime", ascending=False), use_container_width=True)

# ---------------- PLANNED EXPENSES ----------------
elif page == "Planned Expenses":
    st.title("🧾 Planned Expenses")

    with st.form("planned_form", clear_on_submit=True):
        name = st.text_input("Expense Name")
        amount = st.number_input("Amount", min_value=0.0)

        if st.form_submit_button("Add Planned Expense"):
            if name and amount > 0:
                insert_planned({
                    "id": str(uuid.uuid4()),
                    "name": name,
                    "amount": amount,
                    "done": False
                })
                st.cache_data.clear()
                st.session_state["msg"] = "Planned Expense Added"
                st.rerun()

    st.divider()

    if planned_df.empty:
        st.info("No planned expenses")
    else:
        for _, row in planned_df.iterrows():
            col1, col2, col3, col4 = st.columns([3,2,2,1])

            col1.write(f"**{row['name']}**")
            col2.write(f"₹ {row['amount']:.0f}")

            status = col3.checkbox("Done", value=row["done"], key=row["id"])

            if status != row["done"]:

                # ADD TO EXPENSE when marked done
                if status is True and row["done"] is False:
                    insert_expense({
                        "id": str(uuid.uuid4()),
                        "datetime": datetime.now(),
                        "category": "Planned",
                        "amount": row["amount"],
                        "details": row["name"]
                    })

                toggle_planned(row["id"], status)

                st.cache_data.clear()
                st.session_state["msg"] = "Planned expense updated"
                st.rerun()

            if col4.button("❌", key=f"del_{row['id']}"):
                delete_planned(row["id"])
                st.cache_data.clear()
                st.rerun()

    st.divider()

    total_planned = planned_df["amount"].sum() if not planned_df.empty else 0
    pending = planned_df[planned_df["done"] == False]["amount"].sum() if not planned_df.empty else 0
    completed = planned_df[planned_df["done"] == True]["amount"].sum() if not planned_df.empty else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Planned", f"₹ {total_planned:.0f}")
    col2.metric("Pending", f"₹ {pending:.0f}")
    col3.metric("Completed", f"₹ {completed:.0f}")

# ---------------- ANALYSIS ----------------
elif page == "Analysis":
    st.title("📊 Analysis")

    if df.empty:
        st.warning("No data")
    else:
        df["datetime"] = pd.to_datetime(df["datetime"])
        df["date"] = df["datetime"].dt.date

        total = df["amount"].sum()
        st.metric("Total Spend", f"₹ {total:.0f}")

        daily = df.groupby("date")["amount"].sum().reset_index()
        st.plotly_chart(px.line(daily, x="date", y="amount"), use_container_width=True)

        cat = df.groupby("category")["amount"].sum().reset_index()
        st.plotly_chart(px.pie(cat, names="category", values="amount"), use_container_width=True)

# ---------------- EDIT EXPENSE ----------------
elif page == "Edit Expenses":
    st.title("✏️ Edit Expenses")

    if df.empty:
        st.warning("No data")
    else:
        st.dataframe(df.sort_values("datetime", ascending=False))

        selected = st.selectbox("Select Expense ID", df["id"])
        rec = df[df["id"] == selected].iloc[0]

        with st.form("edit_form"):
            cat = st.selectbox("Category", categories, index=categories.index(rec["category"]) if rec["category"] in categories else 0)
            amt = st.number_input("Amount", value=float(rec["amount"]))
            det = st.text_input("Details", value=rec["details"])

            col1, col2 = st.columns(2)

            if col1.form_submit_button("Update"):
                update_expense(selected, cat, amt, det)
                st.cache_data.clear()
                st.session_state["msg"] = "Expense Updated"
                st.rerun()

            if col2.form_submit_button("Delete"):
                delete_expense(selected)
                st.cache_data.clear()
                st.session_state["msg"] = "Expense Deleted"
                st.rerun()

# ---------------- MANAGE CATEGORIES ----------------
elif page == "Manage Categories":
    st.title("⚙️ Manage Categories")

    cats = load_categories()

    st.dataframe(pd.DataFrame({"Category": cats}))

    new_cat = st.text_input("Add New Category")

    if st.button("Add Category"):
        if new_cat and new_cat not in cats:
            cats.append(new_cat)
            save_categories(cats)

            st.session_state["msg"] = "Category Added"
            st.rerun()

    del_cat = st.selectbox("Delete Category", cats)

    if st.button("Delete Category"):
        cats.remove(del_cat)
        save_categories(cats)

        st.session_state["msg"] = "Category Deleted"
        st.rerun()

import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px
import uuid

# ✅ NEW: SQL CONNECTION (YOUR CODE)
from sqlalchemy import create_engine
from sqlalchemy import create_engine

engine = create_engine(st.secrets["DB_URL"])
# ---------------- CONFIG ----------------
st.set_page_config(page_title="Expense Tracker", layout="wide")

DEFAULT_CATEGORIES = [
    "Tea", "Office BF", "Zomato",
    "Quick Commerce", "Outside Eating"
]

# ---------------- LOAD / SAVE ----------------
def load_data():
    try:
        return pd.read_sql("SELECT * FROM expenses", engine)
    except:
        return pd.DataFrame(columns=["id","datetime","category","amount","details"])

def save_data(df):
    df.to_sql("expenses", engine, if_exists="replace", index=False)

def load_investments():
    try:
        return pd.read_sql("SELECT * FROM investments", engine)
    except:
        return pd.DataFrame(columns=["id","datetime","amount","notes"])

def save_investments(df):
    df.to_sql("investments", engine, if_exists="replace", index=False)

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
def compute_balance(exp_df):
    inv_df = load_investments()
    total_exp = exp_df["amount"].sum() if not exp_df.empty else 0
    total_inv = inv_df["amount"].sum() if not inv_df.empty else 0
    return get_total_balance() - total_exp - total_inv

# ---------------- START ----------------
df = load_data()
inv_df = load_investments()
categories = load_categories() + ["Manual"]

balance = compute_balance(df)

# ---------------- GLOBAL MESSAGE ----------------
if "msg" in st.session_state:
    st.success(st.session_state["msg"])
    del st.session_state["msg"]

# ---------------- SIDEBAR ----------------
st.sidebar.title("💰 Wallet")
st.sidebar.metric("Balance", f"₹ {balance:.2f}")

add_money = st.sidebar.number_input("Add Balance", min_value=0.0)

if st.sidebar.button("Add Money"):
    set_total_balance(get_total_balance() + add_money)
    st.session_state["msg"] = "Balance Added"
    st.rerun()

page = st.sidebar.radio(
    "Navigate",
    ["Add Expense","Add Investment","Analysis","Category Deep Dive","Edit Expenses","Manage Categories"]
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

        submit = st.form_submit_button("Add Expense")

        if submit:
            final_cat = manual.strip() if category == "Manual" else category

            if amount <= 0:
                st.error("Invalid amount")

            elif amount > balance:
                st.error("Insufficient balance")

            else:
                new = {
                    "id": str(uuid.uuid4()),
                    "datetime": datetime.now(),
                    "category": final_cat,
                    "amount": amount,
                    "details": details
                }

                df = pd.concat([df, pd.DataFrame([new])], ignore_index=True)
                save_data(df)

                st.session_state["msg"] = "Expense Added"
                st.rerun()

# ---------------- ADD INVESTMENT ----------------
elif page == "Add Investment":
    st.title("📈 Add Investment")

    with st.form("investment_form", clear_on_submit=True):
        amount = st.number_input("Investment Amount", min_value=0.0)
        notes = st.text_input("Notes")

        submit = st.form_submit_button("Add Investment")

        if submit:
            if amount <= 0:
                st.error("Invalid amount")

            elif amount > balance:
                st.error("Not enough balance")

            else:
                new = {
                    "id": str(uuid.uuid4()),
                    "datetime": datetime.now(),
                    "amount": amount,
                    "notes": notes
                }

                inv_df = pd.concat([inv_df, pd.DataFrame([new])], ignore_index=True)
                save_investments(inv_df)

                st.session_state["msg"] = "Investment Added"
                st.rerun()

    inv_df = load_investments()

    st.subheader("💼 Current Investments")

    if inv_df.empty:
        st.info("No investments yet")
    else:
        st.dataframe(inv_df.sort_values("datetime", ascending=False), use_container_width=True)

        col1, col2 = st.columns(2)
        col1.metric("Total Invested", f"₹ {inv_df['amount'].sum():.0f}")
        col2.metric("No. of Investments", len(inv_df))

# ---------------- ANALYSIS ----------------
elif page == "Analysis":
    st.title("📊 Analysis")

    if df.empty:
        st.warning("No data")
    else:
        df["datetime"] = pd.to_datetime(df["datetime"])
        df["date"] = df["datetime"].dt.date

        st.metric("Total Spend", f"₹ {df['amount'].sum():.0f}")

        daily = df.groupby("date")["amount"].sum().reset_index()
        st.plotly_chart(px.line(daily, x="date", y="amount"), use_container_width=True)

        cat = df.groupby("category")["amount"].sum().reset_index()
        st.plotly_chart(px.pie(cat, names="category", values="amount"), use_container_width=True)

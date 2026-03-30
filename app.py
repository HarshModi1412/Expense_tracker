import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px
import uuid
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Expense Tracker", layout="wide")

# ---------------- GOOGLE SHEETS SETUP ----------------
SHEET_NAME = "expense_tracker"

scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# ✅ CHANGED: Using Streamlit secrets instead of credentials.json
creds = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"],
    scopes=scope
)

client = gspread.authorize(creds)
sheet = client.open(SHEET_NAME)

expense_sheet = sheet.worksheet("expenses")
investment_sheet = sheet.worksheet("investments")
category_sheet = sheet.worksheet("categories")
balance_sheet = sheet.worksheet("balance")

DEFAULT_CATEGORIES = [
    "Tea", "Office BF", "Zomato",
    "Quick Commerce", "Outside Eating"
]

# ---------------- LOAD / SAVE ----------------
def load_data():
    data = expense_sheet.get_all_records()
    return pd.DataFrame(data)

def save_data(df):
    if df.empty:
        expense_sheet.clear()
        expense_sheet.update([["id","datetime","category","amount","details"]])
    else:
        expense_sheet.clear()
        expense_sheet.update([df.columns.values.tolist()] + df.values.tolist())

def load_investments():
    data = investment_sheet.get_all_records()
    return pd.DataFrame(data)

def save_investments(df):
    if df.empty:
        investment_sheet.clear()
        investment_sheet.update([["id","datetime","amount","notes"]])
    else:
        investment_sheet.clear()
        investment_sheet.update([df.columns.values.tolist()] + df.values.tolist())

def load_categories():
    data = category_sheet.get_all_records()
    if not data:
        save_categories(DEFAULT_CATEGORIES)
        return DEFAULT_CATEGORIES
    return [row["category"] for row in data]

def save_categories(cats):
    df = pd.DataFrame({"category": cats})
    category_sheet.clear()
    category_sheet.update([df.columns.values.tolist()] + df.values.tolist())

def get_total_balance():
    data = balance_sheet.get_all_records()
    if not data:
        set_total_balance(0.0)
        return 0.0
    return float(data[0]["balance"])

def set_total_balance(val):
    df = pd.DataFrame({"balance": [val]})
    balance_sheet.clear()
    balance_sheet.update([df.columns.values.tolist()] + df.values.tolist())

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
                    "datetime": datetime.now().isoformat(),
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
                    "datetime": datetime.now().isoformat(),
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

        inv_df["datetime"] = pd.to_datetime(inv_df["datetime"])
        inv_df["date"] = inv_df["datetime"].dt.date

        trend = inv_df.groupby("date")["amount"].sum().reset_index()

        st.plotly_chart(px.line(trend, x="date", y="amount", title="Investment Trend"),
                        use_container_width=True)

        selected = st.selectbox("Select Investment ID to Delete", inv_df["id"])

        if st.button("Delete Investment"):
            inv_df = inv_df[inv_df["id"] != selected]
            save_investments(inv_df)

            st.session_state["msg"] = "Investment Removed"
            st.rerun()

# ---------------- REST OF YOUR CODE (UNCHANGED) ----------------

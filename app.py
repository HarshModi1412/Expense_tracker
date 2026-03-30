import streamlit as st
import pandas as pd
from datetime import datetime
import os
import plotly.express as px
import uuid
import pytesseract
from PIL import Image
from pdf2image import convert_from_bytes

st.set_page_config(page_title="Expense Tracker", layout="wide")

DATA_FILE = "expenses.csv"
BAL_FILE = "balance.csv"

CATEGORIES = [
    "Tea",
    "Office BF",
    "Zomato",
    "Quick Commerce",
    "Outside Eating",
    "Manual"
]

# ---------------- INIT ----------------
def init_files():
    if not os.path.exists(DATA_FILE):
        pd.DataFrame(columns=["id", "datetime", "category", "amount", "details"]).to_csv(DATA_FILE, index=False)

    if not os.path.exists(BAL_FILE):
        pd.DataFrame({"balance": [0.0]}).to_csv(BAL_FILE, index=False)

def load_data():
    return pd.read_csv(DATA_FILE)

def save_data(df):
    df.to_csv(DATA_FILE, index=False)

def get_total_balance():
    return float(pd.read_csv(BAL_FILE)["balance"][0])

def set_total_balance(val):
    pd.DataFrame({"balance": [val]}).to_csv(BAL_FILE, index=False)

def compute_balance(df):
    total_added = get_total_balance()
    total_spent = df["amount"].sum() if not df.empty else 0
    return total_added - total_spent

init_files()

df = load_data()
balance = compute_balance(df)

# ---------------- SIDEBAR ----------------
st.sidebar.title("💰 Wallet")
st.sidebar.metric("Current Balance", f"₹ {balance:.2f}")

add_money = st.sidebar.number_input("Add Balance", min_value=0.0, step=10.0)

if st.sidebar.button("Add Money"):
    if add_money > 0:
        set_total_balance(get_total_balance() + add_money)
        st.sidebar.success("Balance updated")
        st.rerun()

page = st.sidebar.radio(
    "Navigate",
    ["Add Expense", "Analysis", "Edit Expenses", "Category View"]
)

# ---------------- ADD EXPENSE ----------------
if page == "Add Expense":
    st.title("➕ Add Expense")

    with st.form("form", clear_on_submit=True):
        category = st.selectbox("Category", CATEGORIES)

        manual_text = ""
        if category == "Manual":
            manual_text = st.text_input("Enter Expense Title")

        amount = st.number_input("Amount", min_value=0.0)
        details = st.text_input("Details (Optional)")

        # ✅ Upload Image OR PDF
        uploaded_file = st.file_uploader(
            "Upload Bill / Invoice (Image or PDF)",
            type=["png", "jpg", "jpeg", "pdf"]
        )

        extracted_text = ""

        if uploaded_file is not None:
            try:
                file_type = uploaded_file.type
                images = []

                # PDF → convert to images
                if "pdf" in file_type:
                    images = convert_from_bytes(uploaded_file.read())
                else:
                    image = Image.open(uploaded_file)
                    images = [image]

                full_text = ""

                for img in images:
                    text = pytesseract.image_to_string(img)
                    full_text += text + "\n"

                # Clean extracted text
                lines = [line.strip() for line in full_text.split("\n") if line.strip()]
                extracted_text = ", ".join(lines[:15])

                st.success("Content extracted")
                st.text_area("Extracted Details", extracted_text, height=150)

            except Exception as e:
                st.error("Failed to process file")

        submit = st.form_submit_button("Submit")

        if submit:
            final_category = manual_text.strip() if category == "Manual" else category

            if category == "Manual" and not final_category:
                st.error("Enter title")

            elif amount <= 0:
                st.error("Invalid amount")

            elif amount > balance:
                st.error("Insufficient balance")

            else:
                final_details = details
                if extracted_text:
                    final_details = (details + " | " if details else "") + extracted_text

                new_entry = {
                    "id": str(uuid.uuid4()),
                    "datetime": datetime.now(),
                    "category": final_category,
                    "amount": amount,
                    "details": final_details
                }

                df = pd.concat([df, pd.DataFrame([new_entry])], ignore_index=True)
                save_data(df)

                st.success("Added")

# ---------------- ANALYSIS ----------------
elif page == "Analysis":
    st.title("📊 Analysis")

    if df.empty:
        st.warning("No data")
    else:
        df = df.copy()
        df["datetime"] = pd.to_datetime(df["datetime"])
        df["date"] = df["datetime"].dt.date

        total = df["amount"].sum()
        avg = df["amount"].mean()
        days = df["date"].nunique()
        avg_daily = total / days if days > 0 else 0

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Spend", f"₹ {total:.0f}")
        col2.metric("Avg Spend", f"₹ {avg:.0f}")
        col3.metric("Avg Daily Spend", f"₹ {avg_daily:.0f}")

        st.divider()

        daily = df.groupby("date")["amount"].sum().reset_index()
        st.plotly_chart(px.line(daily, x="date", y="amount"), use_container_width=True)

        cat = df.groupby("category")["amount"].sum().reset_index()
        st.plotly_chart(px.pie(cat, names="category", values="amount"), use_container_width=True)

# ---------------- EDIT ----------------
elif page == "Edit Expenses":
    st.title("✏️ Edit Expenses")

    if df.empty:
        st.warning("No data")
    else:
        df = df.copy()
        df["datetime"] = pd.to_datetime(df["datetime"])

        st.subheader("All Expenses")
        st.dataframe(df.sort_values(by="datetime", ascending=False), use_container_width=True)

        st.divider()

        selected_id = st.selectbox("Select ID", df["id"])
        record = df[df["id"] == selected_id].iloc[0]

        with st.form("edit"):
            category = st.selectbox("Category", CATEGORIES)

            manual_text = record["category"]
            if category == "Manual":
                manual_text = st.text_input("Edit Title", value=record["category"])

            amount = st.number_input("Amount", value=float(record["amount"]))
            details = st.text_input("Details", value=record["details"])

            update = st.form_submit_button("Update")

            if update:
                new_cat = manual_text if category == "Manual" else category

                df.loc[df["id"] == selected_id, "category"] = new_cat
                df.loc[df["id"] == selected_id, "amount"] = amount
                df.loc[df["id"] == selected_id, "details"] = details

                save_data(df)

                st.success("Updated")

# ---------------- CATEGORY VIEW ----------------
elif page == "Category View":
    st.title("📂 Category Filter")

    if df.empty:
        st.warning("No data")
    else:
        df = df.copy()
        df["datetime"] = pd.to_datetime(df["datetime"])

        selected = st.multiselect(
            "Select Categories",
            options=df["category"].unique(),
            default=df["category"].unique()
        )

        filtered = df[df["category"].isin(selected)].copy()

        if not filtered.empty:
            filtered["date"] = filtered["datetime"].dt.date

            total = filtered["amount"].sum()
            avg = filtered["amount"].mean()
            days = filtered["date"].nunique()
            avg_daily = total / days if days > 0 else 0

            col1, col2, col3 = st.columns(3)
            col1.metric("Total Spend", f"₹ {total:.0f}")
            col2.metric("Avg Spend", f"₹ {avg:.0f}")
            col3.metric("Avg Daily Spend", f"₹ {avg_daily:.0f}")

            st.divider()

            st.subheader("Filtered Data")
            st.dataframe(filtered, use_container_width=True)

            st.subheader("Trend")
            trend = filtered.groupby("date")["amount"].sum().reset_index()
            st.plotly_chart(px.line(trend, x="date", y="amount"), use_container_width=True)

            st.subheader("Category Split")
            cat = filtered.groupby("category")["amount"].sum().reset_index()
            st.plotly_chart(px.bar(cat, x="category", y="amount"), use_container_width=True)

        else:
            st.warning("No data for selected categories")

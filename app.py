```python
import streamlit as st
import pandas as pd
from datetime import datetime
import os
import plotly.express as px
import uuid
from PIL import Image
import pytesseract
import cv2
import numpy as np
import io
import re
import shutil

st.set_page_config(page_title="Expense Tracker", layout="wide")

# ---------------- FILES ----------------
DATA_FILE = "expenses.csv"
BAL_FILE = "balance.csv"
CAT_FILE = "categories.csv"
INV_FILE = "investments.csv"

DEFAULT_CATEGORIES = [
    "Tea", "Office BF", "Zomato",
    "Quick Commerce", "Outside Eating"
]

# ---------------- OCR ----------------
pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"

def preprocess_image(image):
    img = np.array(image)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.convertScaleAbs(gray, alpha=1.5, beta=0)
    gray = cv2.medianBlur(gray, 3)

    thresh = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        11, 2
    )
    return thresh


def extract_text(uploaded_file):
    try:
        if shutil.which("tesseract") is None:
            st.error("Tesseract not available")
            return ""

        file_bytes = uploaded_file.read()

        if uploaded_file.type.startswith("image"):
            image = Image.open(io.BytesIO(file_bytes)).convert("RGB")
            processed = preprocess_image(image)
            return pytesseract.image_to_string(processed)

        return ""
    except Exception as e:
        st.error(f"OCR failed: {str(e)}")
        return ""

# ---------------- PARSER ----------------
def extract_all_lines(raw_text):
    lines = raw_text.split("\n")
    items = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        clean = line.replace("|", " ").replace("₹", "")
        clean = clean.replace("%", "").replace("O", "0")

        nums = re.findall(r"\d+", clean)

        if nums:
            price = nums[-1]
            name = re.sub(r"\d+", "", clean)
            name = re.sub(r"\s+", " ", name).strip()

            items.append({
                "name": name if name else "Unknown",
                "price": float(price)
            })

    return items

# ---------------- INIT ----------------
def init_files():
    if not os.path.exists(DATA_FILE):
        pd.DataFrame(columns=["id","datetime","category","amount","details"]).to_csv(DATA_FILE, index=False)

    if not os.path.exists(BAL_FILE):
        pd.DataFrame({"balance":[0.0]}).to_csv(BAL_FILE, index=False)

    if not os.path.exists(CAT_FILE):
        pd.DataFrame({"category": DEFAULT_CATEGORIES}).to_csv(CAT_FILE, index=False)

    if not os.path.exists(INV_FILE):
        pd.DataFrame(columns=["id","datetime","amount","notes"]).to_csv(INV_FILE, index=False)

# ---------------- LOAD/SAVE ----------------
def load_data():
    return pd.read_csv(DATA_FILE)

def save_data(df):
    df.to_csv(DATA_FILE, index=False)

def load_investments():
    return pd.read_csv(INV_FILE)

def save_investments(df):
    df.to_csv(INV_FILE, index=False)

def load_categories():
    return pd.read_csv(CAT_FILE)["category"].tolist()

def save_categories(cats):
    pd.DataFrame({"category": cats}).to_csv(CAT_FILE, index=False)

def get_total_balance():
    return float(pd.read_csv(BAL_FILE)["balance"][0])

def set_total_balance(val):
    pd.DataFrame({"balance":[val]}).to_csv(BAL_FILE, index=False)

# ---------------- BALANCE ----------------
def compute_balance(df):
    inv_df = load_investments()

    total_exp = df["amount"].sum() if not df.empty else 0
    total_inv = inv_df["amount"].sum() if not inv_df.empty else 0

    return get_total_balance() - total_exp - total_inv

# ---------------- START ----------------
init_files()

df = load_data()
inv_df = load_investments()
categories = load_categories() + ["Manual"]

balance = compute_balance(df)

# ---------------- SIDEBAR ----------------
st.sidebar.title("💰 Wallet")
st.sidebar.metric("Balance", f"₹ {balance:.2f}")

add_money = st.sidebar.number_input("Add Balance", min_value=0.0)

if st.sidebar.button("Add Money"):
    set_total_balance(get_total_balance() + add_money)
    st.rerun()

page = st.sidebar.radio(
    "Navigate",
    ["Add Expense","Add Investment","Analysis","Edit Expenses","Manage Categories"]
)

# ---------------- ADD EXPENSE ----------------
if page == "Add Expense":
    st.title("➕ Add Expense")

    with st.form("form", clear_on_submit=True):
        category = st.selectbox("Category", categories)

        manual = ""
        if category == "Manual":
            manual = st.text_input("Enter Title")

        amount = st.number_input("Amount", min_value=0.0)
        details = st.text_input("Details")

        uploaded_file = st.file_uploader("Upload Receipt", type=["png","jpg","jpeg"])

        selected_items = []

        if uploaded_file:
            raw = extract_text(uploaded_file)
            items = extract_all_lines(raw)

            for i, item in enumerate(items):
                keep = st.checkbox(f"{item['name']} - ₹{item['price']}", key=i)
                if keep:
                    selected_items.append(item)

        submit = st.form_submit_button("Submit")

        if submit:
            final_cat = manual.strip() if category=="Manual" else category

            if amount <= 0:
                st.error("Invalid amount")

            elif amount > balance:
                st.error("Insufficient balance")

            else:
                if selected_items:
                    extracted = "\n".join([f"{i['name']} - ₹{i['price']}" for i in selected_items])
                    details = (details + " | " if details else "") + extracted

                new = {
                    "id": str(uuid.uuid4()),
                    "datetime": datetime.now(),
                    "category": final_cat,
                    "amount": amount,
                    "details": details
                }

                df = pd.concat([df, pd.DataFrame([new])], ignore_index=True)
                save_data(df)

                st.success("Expense Added")
                st.rerun()

# ---------------- ADD INVESTMENT ----------------
elif page == "Add Investment":
    st.title("📈 Add Investment")

    with st.form("inv_form", clear_on_submit=True):
        amount = st.number_input("Amount", min_value=0.0)
        notes = st.text_input("Notes")

        submit = st.form_submit_button("Invest")

        if submit:
            if amount <= 0:
                st.error("Invalid")

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

                st.success("Investment Added")
                st.rerun()

    st.subheader("Your Investments")

    if not inv_df.empty:
        st.dataframe(inv_df)

        selected = st.selectbox("Select ID", inv_df["id"])

        if st.button("Delete Investment"):
            inv_df = inv_df[inv_df["id"] != selected]
            save_investments(inv_df)
            st.success("Removed")
            st.rerun()

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
        st.plotly_chart(px.line(daily, x="date", y="amount"))

        cat = df.groupby("category")["amount"].sum().reset_index()
        st.plotly_chart(px.pie(cat, names="category", values="amount"))

# ---------------- EDIT ----------------
elif page == "Edit Expenses":
    st.title("✏️ Edit Expenses")

    if not df.empty:
        st.dataframe(df)

        selected = st.selectbox("Select ID", df["id"])
        rec = df[df["id"] == selected].iloc[0]

        with st.form("edit"):
            amt = st.number_input("Amount", value=float(rec["amount"]))
            det = st.text_input("Details", value=rec["details"])

            col1, col2 = st.columns(2)

            if col1.form_submit_button("Update"):
                df.loc[df["id"] == selected, "amount"] = amt
                df.loc[df["id"] == selected, "details"] = det
                save_data(df)
                st.success("Updated")
                st.rerun()

            if col2.form_submit_button("Delete"):
                df = df[df["id"] != selected]
                save_data(df)
                st.success("Deleted")
                st.rerun()

# ---------------- CATEGORY ----------------
elif page == "Manage Categories":
    st.title("⚙️ Categories")

    cats = load_categories()

    st.dataframe(pd.DataFrame({"Category": cats}))

    new = st.text_input("Add Category")

    if st.button("Add"):
        if new and new not in cats:
            cats.append(new)
            save_categories(cats)
            st.rerun()

    delete = st.selectbox("Delete", cats)

    if st.button("Remove"):
        cats.remove(delete)
        save_categories(cats)
        st.rerun()


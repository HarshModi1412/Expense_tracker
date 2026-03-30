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

DATA_FILE = "expenses.csv"
BAL_FILE = "balance.csv"

CATEGORIES = [
    "Tea", "Office BF", "Zomato",
    "Quick Commerce", "Outside Eating", "Manual"
]

# ---------------- OCR SETUP ----------------
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

        elif uploaded_file.type == "application/pdf":
            st.warning("PDF not supported. Upload screenshot instead.")
            return ""

        return ""
    except Exception as e:
        st.error(f"OCR failed: {str(e)}")
        return ""


# ---------------- PARSER ----------------
def clean_extracted_text(raw_text):
    lines = raw_text.split("\n")
    items = []

    for line in lines:
        line = line.strip()

        if not line or len(line) < 5:
            continue

        if any(x in line.lower() for x in [
            "order", "delivered", "help",
            "summary", "rate", "again"
        ]):
            continue

        line = line.replace("|", " ")
        line = line.replace("₹", "")
        line = line.replace("%", "")
        line = line.replace("O", "0")

        nums = re.findall(r"\d{2,3}", line)

        if not nums:
            continue

        price = int(nums[-1])

        if price < 10 or price > 200:
            continue

        if price > 100:
            price = int(str(price)[-2:])

        name = re.sub(r"\d+[^\s]*", "", line)
        name = re.sub(r"\s+", " ", name).strip()

        if len(name) > 5:
            items.append({
                "name": name,
                "price": price
            })

    # remove duplicates
    seen = set()
    final = []
    for item in items:
        if item["name"] not in seen:
            seen.add(item["name"])
            final.append(item)

    return final


# ---------------- DATA ----------------
def init_files():
    if not os.path.exists(DATA_FILE):
        pd.DataFrame(columns=["id","datetime","category","amount","details"]).to_csv(DATA_FILE, index=False)

    if not os.path.exists(BAL_FILE):
        pd.DataFrame({"balance":[0.0]}).to_csv(BAL_FILE, index=False)

def load_data():
    return pd.read_csv(DATA_FILE)

def save_data(df):
    df.to_csv(DATA_FILE, index=False)

def get_total_balance():
    return float(pd.read_csv(BAL_FILE)["balance"][0])

def set_total_balance(val):
    pd.DataFrame({"balance":[val]}).to_csv(BAL_FILE, index=False)

def compute_balance(df):
    return get_total_balance() - (df["amount"].sum() if not df.empty else 0)


init_files()
df = load_data()
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
    ["Add Expense","Analysis","Edit Expenses","Category View"]
)

# ---------------- ADD EXPENSE ----------------
if page == "Add Expense":
    st.title("➕ Add Expense")

    with st.form("form", clear_on_submit=True):
        category = st.selectbox("Category", CATEGORIES)

        manual = ""
        if category == "Manual":
            manual = st.text_input("Enter Title")

        amount = st.number_input("Amount", min_value=0.0)
        details = st.text_input("Details")

        uploaded_file = st.file_uploader(
            "Upload Receipt (Image recommended)",
            type=["png","jpg","jpeg","pdf"]
        )

        selected_items = []
        extracted = ""

        if uploaded_file:
            raw = extract_text(uploaded_file)

            if raw:
                items = clean_extracted_text(raw)

                if items:
                    st.success("Select valid items")

                    for idx, item in enumerate(items):
                        col1, col2 = st.columns([1, 5])

                        keep = col1.checkbox("", value=True, key=f"chk_{idx}")
                        col2.write(f"{item['name']} - ₹{item['price']}")

                        if keep:
                            selected_items.append(item)

                    if selected_items:
                        extracted = "\n".join([
                            f"{i['name']} - ₹{i['price']}" for i in selected_items
                        ])

                        total_selected = sum(i["price"] for i in selected_items)

                        st.divider()
                        st.write(f"**Selected Total: ₹{total_selected}**")

                        if amount and abs(total_selected - amount) > 20:
                            st.warning("⚠️ Selected total does not match entered amount")

                        st.text_area("Final Items", extracted, height=150)

                else:
                    st.warning("No items detected")

            else:
                st.warning("No text detected")

        submit = st.form_submit_button("Submit")

        if submit:
            final_cat = manual.strip() if category=="Manual" else category

            if category=="Manual" and not final_cat:
                st.error("Enter title")

            elif amount <= 0:
                st.error("Invalid amount")

            elif amount > balance:
                st.error("Insufficient balance")

            else:
                final_details = details
                if selected_items:
                    extracted = "\n".join([
                        f"{i['name']} - ₹{i['price']}" for i in selected_items
                    ])
                    final_details = (details + " | " if details else "") + extracted

                new = {
                    "id": str(uuid.uuid4()),
                    "datetime": datetime.now(),
                    "category": final_cat,
                    "amount": amount,
                    "details": final_details
                }

                df = pd.concat([df, pd.DataFrame([new])], ignore_index=True)
                save_data(df)

                st.success("Added")


# ---------------- ANALYSIS ----------------
elif page == "Analysis":
    st.title("📊 Analysis")

    if df.empty:
        st.warning("No data")
    else:
        df["datetime"] = pd.to_datetime(df["datetime"])
        df["date"] = df["datetime"].dt.date

        total = df["amount"].sum()
        avg = df["amount"].mean()
        days = df["date"].nunique()
        avg_daily = total/days if days else 0

        c1,c2,c3 = st.columns(3)
        c1.metric("Total Spend", f"₹ {total:.0f}")
        c2.metric("Avg Spend", f"₹ {avg:.0f}")
        c3.metric("Avg Daily", f"₹ {avg_daily:.0f}")

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
        df["datetime"] = pd.to_datetime(df["datetime"])
        st.dataframe(df.sort_values("datetime", ascending=False))

        selected = st.selectbox("Select ID", df["id"])
        rec = df[df["id"]==selected].iloc[0]

        with st.form("edit"):
            cat = st.selectbox("Category", CATEGORIES)
            amt = st.number_input("Amount", value=float(rec["amount"]))
            det = st.text_input("Details", value=rec["details"])

            c1,c2 = st.columns(2)
            upd = c1.form_submit_button("Update")
            delete = c2.form_submit_button("Delete")

            if upd:
                df.loc[df["id"]==selected,"category"]=cat
                df.loc[df["id"]==selected,"amount"]=amt
                df.loc[df["id"]==selected,"details"]=det
                save_data(df)
                st.success("Updated")
                st.rerun()

            if delete:
                df = df[df["id"]!=selected]
                save_data(df)
                st.success("Deleted")
                st.rerun()


# ---------------- CATEGORY VIEW ----------------
elif page == "Category View":
    st.title("📂 Category View")

    if df.empty:
        st.warning("No data")
    else:
        df["datetime"] = pd.to_datetime(df["datetime"])

        sel = st.multiselect(
            "Categories",
            df["category"].unique(),
            default=df["category"].unique()
        )

        f = df[df["category"].isin(sel)].copy()

        if not f.empty:
            f["date"] = f["datetime"].dt.date

            total = f["amount"].sum()
            avg = f["amount"].mean()
            days = f["date"].nunique()
            avg_daily = total/days if days else 0

            c1,c2,c3 = st.columns(3)
            c1.metric("Total", f"₹ {total:.0f}")
            c2.metric("Avg", f"₹ {avg:.0f}")
            c3.metric("Daily Avg", f"₹ {avg_daily:.0f}")

            st.dataframe(f)

            trend = f.groupby("date")["amount"].sum().reset_index()
            st.plotly_chart(px.line(trend, x="date", y="amount"), use_container_width=True)

            cat = f.groupby("category")["amount"].sum().reset_index()
            st.plotly_chart(px.bar(cat, x="category", y="amount"), use_container_width=True)

        else:
            st.warning("No data for selected categories")

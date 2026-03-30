import streamlit as st
import pandas as pd
from datetime import datetime
import os
import plotly.express as px
import uuid
from PIL import Image
from google.cloud import vision
import json
import io

st.set_page_config(page_title="Expense Tracker", layout="wide")

DATA_FILE = "expenses.csv"
BAL_FILE = "balance.csv"

CATEGORIES = [
    "Tea", "Office BF", "Zomato",
    "Quick Commerce", "Outside Eating", "Manual"
]

# ---------------- INIT ----------------
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

# ---------------- OCR ----------------
def preprocess_image(image):
    image = image.convert("L")  # grayscale
    image = image.resize((image.width*2, image.height*2))
    return image

def extract_text(uploaded_file):
    try:
        credentials = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
        client = vision.ImageAnnotatorClient.from_service_account_info(credentials)

        file_bytes = uploaded_file.read()

        # Handle image
        if uploaded_file.type.startswith("image"):
            image = Image.open(io.BytesIO(file_bytes))
            image = preprocess_image(image)

            buf = io.BytesIO()
            image.save(buf, format="PNG")
            content = buf.getvalue()

            vision_image = vision.Image(content=content)
            response = client.text_detection(image=vision_image)

        # Handle PDF (basic)
        elif uploaded_file.type == "application/pdf":
            st.warning("PDF support is limited. Use images for best results.")
            vision_image = vision.Image(content=file_bytes)
            response = client.document_text_detection(image=vision_image)

        else:
            return ""

        if response.text_annotations:
            return response.text_annotations[0].description

        return ""

    except Exception as e:
        st.error(f"OCR failed: {str(e)}")
        return ""

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

page = st.sidebar.radio("Navigate", ["Add Expense","Analysis","Edit Expenses","Category View"])

# ---------------- ADD ----------------
if page == "Add Expense":
    st.title("➕ Add Expense")

    with st.form("form"):
        category = st.selectbox("Category", CATEGORIES)

        manual = ""
        if category == "Manual":
            manual = st.text_input("Enter Title")

        amount = st.number_input("Amount", min_value=0.0)
        details = st.text_input("Details")

        uploaded_file = st.file_uploader("Upload Receipt", type=["png","jpg","jpeg","pdf"])

        extracted = ""

        if uploaded_file:
            raw = extract_text(uploaded_file)

            if raw:
                lines = [l.strip() for l in raw.split("\n") if l.strip()]
                extracted = ", ".join(lines[:12])

                st.success("Text extracted")
                st.text_area("Preview", extracted, height=120)
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
                if extracted:
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
        c1.metric("Total", f"₹ {total:.0f}")
        c2.metric("Avg", f"₹ {avg:.0f}")
        c3.metric("Daily Avg", f"₹ {avg_daily:.0f}")

        daily = df.groupby("date")["amount"].sum().reset_index()
        st.plotly_chart(px.line(daily, x="date", y="amount"), use_container_width=True)

# ---------------- EDIT ----------------
elif page == "Edit Expenses":
    st.title("✏️ Edit")

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
                st.rerun()

            if delete:
                df = df[df["id"]!=selected]
                save_data(df)
                st.rerun()

# ---------------- CATEGORY ----------------
elif page == "Category View":
    st.title("📂 Category")

    if df.empty:
        st.warning("No data")
    else:
        df["datetime"] = pd.to_datetime(df["datetime"])

        sel = st.multiselect("Categories", df["category"].unique(), default=df["category"].unique())
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

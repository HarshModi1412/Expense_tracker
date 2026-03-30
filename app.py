# EXISTING IMPORTS (UNCHANGED)
import streamlit as st
import pandas as pd
from datetime import datetime
import os
import plotly.express as px
import uuid

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

# ---------------- LOAD / SAVE ----------------
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
def compute_balance(exp_df):
    inv_df = load_investments()
    total_exp = exp_df["amount"].sum() if not exp_df.empty else 0
    total_inv = inv_df["amount"].sum() if not inv_df.empty else 0
    return get_total_balance() - total_exp - total_inv

# ---------------- START ----------------
init_files()

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

    # ✅ RELOAD DATA (IMPORTANT FIX)
    inv_df = load_investments()

    # ✅ DISPLAY CURRENT INVESTMENTS
    st.subheader("💼 Current Investments")

    if inv_df.empty:
        st.info("No investments yet")
    else:
        st.dataframe(inv_df.sort_values("datetime", ascending=False), use_container_width=True)

        col1, col2 = st.columns(2)

        with col1:
            st.metric("Total Invested", f"₹ {inv_df['amount'].sum():.0f}")

        with col2:
            st.metric("No. of Investments", len(inv_df))

        # Optional chart (adds analytical feel)
        inv_df["datetime"] = pd.to_datetime(inv_df["datetime"])
        inv_df["date"] = inv_df["datetime"].dt.date

        trend = inv_df.groupby("date")["amount"].sum().reset_index()

        st.plotly_chart(
            px.line(trend, x="date", y="amount", title="Investment Trend"),
            use_container_width=True
        )

        # Delete option (you had earlier but lost it)
        selected = st.selectbox("Select Investment ID to Delete", inv_df["id"])

        if st.button("Delete Investment"):
            inv_df = inv_df[inv_df["id"] != selected]
            save_investments(inv_df)

            st.session_state["msg"] = "Investment Removed"
            st.rerun()

# ---------------- ANALYSIS (UPGRADED) ----------------
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
        st.plotly_chart(px.line(daily, x="date", y="amount", title="Daily Spend Trend"), use_container_width=True)

        cat = df.groupby("category")["amount"].sum().reset_index()
        st.plotly_chart(px.pie(cat, names="category", values="amount", title="Category Split"), use_container_width=True)

        st.plotly_chart(px.bar(cat.sort_values("amount", ascending=False),
                               x="category", y="amount",
                               title="Category Ranking"), use_container_width=True)

        # Insights
        st.subheader("📌 Insights")

        top_cat = cat.sort_values("amount", ascending=False).iloc[0]
        st.write(f"• Highest spend category: **{top_cat['category']} (₹ {top_cat['amount']:.0f})**")

        avg_daily = daily["amount"].mean()
        st.write(f"• Average daily spend: ₹ {avg_daily:.0f}")

        high_days = daily[daily["amount"] > avg_daily]
        st.write(f"• {len(high_days)} days above average spending")

        concentration = top_cat["amount"] / total * 100
        st.write(f"• {concentration:.1f}% of spend comes from one category → risk of overspending")

# ---------------- NEW PAGE ----------------
elif page == "Category Deep Dive":
    st.title("🔍 Category Deep Dive")

    if df.empty:
        st.warning("No data")
    else:
        df["datetime"] = pd.to_datetime(df["datetime"])
        df["date"] = df["datetime"].dt.date

        selected = st.multiselect("Select Categories", df["category"].unique())

        if not selected:
            st.info("Select at least one category")
        else:
            filtered = df[df["category"].isin(selected)]

            st.metric("Filtered Spend", f"₹ {filtered['amount'].sum():.0f}")

            daily = filtered.groupby("date")["amount"].sum().reset_index()
            st.plotly_chart(px.line(daily, x="date", y="amount",
                                   title="Trend (Selected Categories)"),
                            use_container_width=True)

            cat = filtered.groupby("category")["amount"].sum().reset_index()
            st.plotly_chart(px.bar(cat, x="category", y="amount",
                                  title="Selected Category Comparison"),
                            use_container_width=True)

            # Insights
            st.subheader("📌 Insights")

            top = cat.sort_values("amount", ascending=False).iloc[0]
            st.write(f"• Dominant category: **{top['category']}**")

            avg = filtered["amount"].mean()
            st.write(f"• Avg transaction: ₹ {avg:.0f}")

            spike = filtered.sort_values("amount", ascending=False).iloc[0]
            st.write(f"• Highest spend: ₹ {spike['amount']:.0f} on {spike['date']}")

            freq = filtered["category"].value_counts().iloc[0]
            st.write(f"• Most frequent category transactions: {freq}")

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
            cat = st.selectbox("Category", categories)

            amt = st.number_input("Amount", value=float(rec["amount"]))
            det = st.text_input("Details", value=rec["details"])

            col1, col2 = st.columns(2)

            if col1.form_submit_button("Update"):
                df.loc[df["id"] == selected, "category"] = cat
                df.loc[df["id"] == selected, "amount"] = amt
                df.loc[df["id"] == selected, "details"] = det

                save_data(df)
                st.session_state["msg"] = "Expense Updated"
                st.rerun()

            if col2.form_submit_button("Delete"):
                df = df[df["id"] != selected]
                save_data(df)
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

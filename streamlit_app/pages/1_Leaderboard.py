"""Customer leaderboard with TTM/Lifetime toggle, search, and click-through to profile."""

import streamlit as st

import data
from styles import apply_styles, hero_banner

st.set_page_config(page_title="Leaderboard - Green's Mowers", page_icon=":trophy:", layout="wide")
apply_styles()

hero_banner(
    eyebrow="Green's Mowers",
    title="Customer Leaderboard",
    subtitle="Posted invoices only. Use the Profile link to open the customer profile.",
    compact=True,
)

with st.container(border=True):
    c1, c2, c3, _ = st.columns([1, 2, 1, 4])
    view = c1.segmented_control(
        "View",
        options=["TTM (12 months)", "Lifetime"],
        default="TTM (12 months)",
    )
    search = c2.text_input("Search", placeholder="Customer name or number")
    limit = c3.selectbox("Show top", [50, 100, 250, 500], index=1)

ttm_only = view == "TTM (12 months)"

with st.spinner("Loading customers..."):
    df = data.leaderboard(ttm_only=ttm_only, limit=int(limit), search=search.strip() or None)

if df.empty:
    st.info("No customers match those filters.")
    st.stop()

display = df.copy()
display["Profile"] = display["customer_id"].map(lambda cid: f"/Customer_Profile?customer={int(cid)}")
display.rename(columns={
    "customer": "Customer",
    "customer_no": "Customer #",
    "invoices": "Invoices",
    "revenue": "TTM Revenue" if ttm_only else "Revenue",
    "lifetime_revenue": "Lifetime Revenue",
    "last_purchase": "Last Purchase",
    "days_since": "Days Since",
}, inplace=True)
display["Last Purchase"] = display["Last Purchase"].map(data.fmt_date)

shown = display[[
    "Profile", "Customer", "Customer #", "Invoices",
    "TTM Revenue" if ttm_only else "Revenue",
    "Lifetime Revenue", "Last Purchase", "Days Since",
]]

st.dataframe(
    shown,
    width="stretch",
    height=620,
    hide_index=True,
    column_config={
        "Profile":           st.column_config.LinkColumn(display_text="Open", width=70),
        "Customer":          st.column_config.Column(width=230),
        "Customer #":        st.column_config.Column(width=130),
        "Invoices":          st.column_config.NumberColumn(format="%d", width=90),
        "TTM Revenue":       st.column_config.NumberColumn(format="$%,.0f", width=130),
        "Revenue":           st.column_config.NumberColumn(format="$%,.0f", width=130),
        "Lifetime Revenue":  st.column_config.NumberColumn(format="$%,.0f", width=150),
        "Last Purchase":     st.column_config.Column(width=120),
        "Days Since":        st.column_config.NumberColumn(format="%d", width=100),
    },
)

st.caption(f"{len(df):,} rows")

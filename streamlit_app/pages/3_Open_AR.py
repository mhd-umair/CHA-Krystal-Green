"""Open A/R aging buckets and per-customer outstanding balances."""

import streamlit as st

import data
from styles import apply_styles, hero_banner

st.set_page_config(page_title="Open A/R - Green's Mowers", page_icon=":money_with_wings:", layout="wide")
apply_styles()

hero_banner(
    eyebrow="Green's Mowers",
    title="Open Accounts Receivable",
    subtitle=(
        "Outstanding = invoice total minus active payments. "
        "Aging is calculated from the invoice ActivityDate. Click a row to open that customer's profile."
    ),
    compact=True,
)

# ----------------------------------------------------------------------------
# Aging bucket cards
# ----------------------------------------------------------------------------

with st.spinner("Computing aging buckets..."):
    buckets = data.aging_buckets()

bucket_lookup = {row["bucket"]: row for _, row in buckets.iterrows()}
order = ["0-30", "31-60", "61-90", "90+"]

cols = st.columns(4)
for col, b in zip(cols, order):
    with col:
        row = bucket_lookup.get(b, {"outstanding": 0, "invoice_count": 0})
        color = data.BUCKET_COLOR[b]
        st.markdown(
            f"""
            <div style='background:{color};color:white;border-radius:12px;padding:16px;'>
              <div style='font-size:0.85rem;text-transform:uppercase;letter-spacing:0.5px;opacity:0.9;'>
                {b} days
              </div>
              <div style='font-size:1.6rem;font-weight:700;margin-top:4px;'>{data.fmt_currency(float(row['outstanding']))}</div>
              <div style='font-size:0.85rem;opacity:0.9;'>{int(row['invoice_count']):,} invoices</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.divider()

# ----------------------------------------------------------------------------
# Per-customer outstanding grid (with bucket filter)
# ----------------------------------------------------------------------------

st.subheader("Customers with Open Balances")
st.caption(
    "Click an aging bucket below to remove customers without invoices in that "
    "bucket. Outstanding totals then reflect just the selected bucket."
)

bucket_choice = st.segmented_control(
    "Aging bucket",
    options=["All", "0-30", "31-60", "61-90", "90+"],
    default="All",
    selection_mode="single",
    key="ar-bucket-filter",
)
active_bucket = None if bucket_choice in (None, "All") else bucket_choice

with st.spinner("Loading A/R..."):
    df = data.customer_ar_summary(limit=200, bucket=active_bucket)

if df.empty:
    if active_bucket:
        st.info(f"No customers have open invoices in the {active_bucket} day bucket.")
    else:
        st.success("No outstanding balances. Nicely done.")
    st.stop()

display = df.copy()
display["Profile"] = display["customer_id"].map(lambda cid: f"/Customer_Profile?customer={int(cid)}")
outstanding_label = (
    f"Outstanding ({active_bucket} days)" if active_bucket else "Outstanding"
)
oldest_label = (
    f"Oldest in bucket (days)" if active_bucket else "Oldest (days)"
)
display.rename(columns={
    "customer": "Customer",
    "customer_no": "Customer #",
    "open_invoices": "Open Invoices",
    "outstanding": outstanding_label,
    "oldest_days": oldest_label,
    "avg_days_to_pay": "Avg days to pay",
}, inplace=True)

st.dataframe(
    display[["Profile", "Customer", "Customer #", "Open Invoices", outstanding_label,
             oldest_label, "Avg days to pay"]],
    width="stretch",
    height=520,
    hide_index=True,
    column_config={
        "Profile":         st.column_config.LinkColumn(display_text="Open", width=70),
        "Customer":        st.column_config.Column(width=250),
        "Customer #":      st.column_config.Column(width=130),
        "Open Invoices":   st.column_config.NumberColumn(format="%d", width=120),
        outstanding_label: st.column_config.NumberColumn(format="$%,.0f", width=160),
        oldest_label:      st.column_config.NumberColumn(format="%d", width=160),
        "Avg days to pay": st.column_config.NumberColumn(format="%.1f", width=150),
    },
)

st.caption(
    f"Showing {len(df):,} customers"
    + (f" with open invoices in the {active_bucket} day bucket" if active_bucket else "")
)

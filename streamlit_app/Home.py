"""Perseus Equipment Customer Analytics - Landing dashboard.

Run from the repo root with:
    streamlit run streamlit_app/Home.py
"""

import plotly.express as px
import streamlit as st

import data
from styles import apply_styles, hero_banner

st.set_page_config(
    page_title="Green's Mowers - Customer Analytics",
    page_icon=":bar_chart:",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_styles()

hero_banner(
    eyebrow="Green's Mowers",
    title="Customer Analytics",
    subtitle=(
        "Trailing twelve month figures use posted invoices only "
        "(finalized + archived). Click any list item to drill into a customer profile."
    ),
)

# ----------------------------------------------------------------------------
# KPI tiles
# ----------------------------------------------------------------------------

with st.spinner("Loading KPIs..."):
    k = data.headline_kpis()

pct_active = (k["ttm_customers"] / k["active_customers"]) if k["active_customers"] else 0
avg_rev = (k["ttm_revenue"] / k["ttm_customers"]) if k["ttm_customers"] else 0

row1 = st.columns(4)
row1[0].metric("Active Customers",  data.fmt_int(k["active_customers"]),
               help=f"{k['new_customers_90d']:,} added in last 90 days")
row1[1].metric("TTM Customers",     data.fmt_int(k["ttm_customers"]),
               help=f"{pct_active:.0%} of active base transacting")
row1[2].metric("TTM Revenue",       data.fmt_currency(k["ttm_revenue"]),
               help=f"Avg {data.fmt_currency(avg_rev)} per TTM customer")
row1[3].metric("Top-10 Concentration", f"{k['top10_share_ttm']:.0%}",
               help="Share of TTM revenue from top 10 customers")

row2 = st.columns(4)
row2[0].metric("Open A/R",          data.fmt_currency(k["open_ar_total"]),
               help="Outstanding across all posted invoices")
row2[1].metric("Customers At Risk", data.fmt_int(k["at_risk_count"]),
               help="$5k+ customer, no purchase in 6-12 months")
row2[2].metric("Lifetime Revenue",  data.fmt_currency(k["lifetime_revenue"]),
               help="Posted invoices, all time")
row2[3].metric("New (90d)",         data.fmt_int(k["new_customers_90d"]),
               help="Customers added in last 90 days")

st.divider()

# ----------------------------------------------------------------------------
# Monthly revenue chart  +  Top 10 leaderboard
# ----------------------------------------------------------------------------

left, right = st.columns([2, 1], gap="large")

with left:
    st.subheader("Monthly Revenue")
    st.caption("Posted invoices only. Filter by invoice type or window below.")

    # ----- filter controls -----
    type_options = {
        "Parts / Counter":         "in",
        "Service / Work Orders":   "wo",
        "Rentals":                 "rl",
    }
    fcol1, fcol2 = st.columns([3, 1])
    selected_labels = fcol1.multiselect(
        "Invoice types",
        options=list(type_options.keys()),
        default=list(type_options.keys()),
        help="Removes non-matching types from the chart entirely.",
        key="home-rev-types",
    )
    months_window = fcol2.selectbox(
        "Window",
        options=[12, 24, 36, 48],
        index=1,
        format_func=lambda m: f"Last {m} months",
        key="home-rev-window",
    )

    if not selected_labels:
        st.info("Select at least one invoice type to see revenue.")
    else:
        selected_codes = tuple(type_options[t] for t in selected_labels)
        monthly = data.monthly_revenue_by_type(months=months_window, invoice_types=selected_codes)
        if monthly.empty:
            st.info(f"No revenue in the last {months_window} months for the selected types.")
        else:
            # Stacked bar coloured by invoice type — each user-selected type
            # has its own segment so you can see the mix at a glance.
            type_color_map = {
                "Parts / Counter":       "#3DA5D9",
                "Service / Work Orders": "#16A34A",
                "Rentals":               "#D97706",
            }
            fig = px.bar(
                monthly, x="month", y="revenue", color="label",
                color_discrete_map=type_color_map,
                category_orders={"label": ["Parts / Counter", "Service / Work Orders", "Rentals"]},
                labels={"month": "", "revenue": "Revenue (USD)", "label": "Type"},
                height=360,
            )
            fig.update_layout(
                margin=dict(l=10, r=10, t=10, b=10),
                xaxis_tickangle=-45,
                yaxis_tickprefix="$", yaxis_tickformat=",",
                hovermode="x unified",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
                barmode="stack",
            )
            st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("Top 10 Customers (TTM)")
    st.caption("Click a customer name to open their profile.")
    top10 = data.leaderboard(ttm_only=True, limit=10)
    if top10.empty:
        st.info("No TTM activity.")
    else:
        for _, row in top10.iterrows():
            cid = int(row["customer_id"])
            col_a, col_b = st.columns([3, 2])
            with col_a:
                # Tertiary buttons are styled in styles.py to look like
                # clickable headings (left-aligned, bold, link-like hover).
                if st.button(
                    row["customer"],
                    key=f"top10-{cid}",
                    type="tertiary",
                ):
                    st.session_state["selected_customer_id"] = cid
                    st.query_params["customer"] = cid
                    st.switch_page("pages/4_Customer_Profile.py")
                st.caption(f"{int(row['invoices']):,} invoices")
            with col_b:
                st.markdown(
                    f"<div class='top10-revenue'>{data.fmt_currency(row['revenue'])}</div>",
                    unsafe_allow_html=True,
                )

st.divider()

# ----------------------------------------------------------------------------
# Customer health segment summary
# ----------------------------------------------------------------------------

st.subheader("Customer Health Mix")
st.caption("RFM segmentation across active customers. Click a segment to drill in.")

seg = data.segment_counts()
if seg.empty:
    st.info("No segmentation data.")
else:
    cols = st.columns(len(seg))
    for col, (_, srow) in zip(cols, seg.iterrows()):
        with col:
            color = data.SEGMENT_COLOR.get(srow["segment"], "#94a3b8")
            st.markdown(
                f"""
                <div style='background:{color};color:white;border-radius:12px;padding:14px;text-align:center;'>
                  <div style='font-size:0.85rem;text-transform:uppercase;letter-spacing:0.5px;opacity:0.9;'>
                    {srow['segment']}
                  </div>
                  <div style='font-size:1.6rem;font-weight:700;margin-top:4px;'>{srow['count']:,}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button(f"Open {srow['segment']}", key=f"seg-{srow['segment']}", use_container_width=True):
                st.query_params["segment"] = srow["segment"]
                st.switch_page("pages/2_At_Risk.py")

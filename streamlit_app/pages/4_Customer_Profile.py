"""Customer profile drill-down. Reads the customer id from session_state (set by
other pages on row click) or falls back to ?customer=<id> in the URL or a search box."""

import plotly.express as px
import streamlit as st

import data
from styles import apply_styles, hero_banner

st.set_page_config(page_title="Customer Profile - Green's Mowers", page_icon=":bust_in_silhouette:", layout="wide")
apply_styles()

# ----------------------------------------------------------------------------
# Resolve the customer id
# Priority: 1) session_state (set by other pages on row-click, most reliable
#              cross-page hand-off in Streamlit), 2) URL ?customer=<id>
#              (kept for shareable links).
# ----------------------------------------------------------------------------


def _coerce_int(value) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


customer_id = _coerce_int(st.session_state.get("selected_customer_id"))
if customer_id is None:
    customer_id = _coerce_int(st.query_params.get("customer"))

# Keep the URL and session_state in sync when we successfully resolved an id.
if customer_id is not None:
    st.session_state["selected_customer_id"] = customer_id
    if str(st.query_params.get("customer", "")) != str(customer_id):
        st.query_params["customer"] = customer_id

if customer_id is None:
    hero_banner(
        eyebrow="Green's Mowers",
        title="Customer Profile",
        subtitle="Pick a customer to drill into.",
        compact=True,
    )
    candidates = data.leaderboard(ttm_only=False, limit=500)
    if candidates.empty:
        st.warning("No customers in the database.")
        st.stop()
    options = {
        f"{row['customer']} ({row['customer_no']})": int(row["customer_id"])
        for _, row in candidates.iterrows()
    }
    # `index=None` keeps the selectbox empty on first render so we don't
    # auto-navigate to the first customer in the list.
    pick = st.selectbox(
        "Select a customer",
        options=list(options.keys()),
        index=None,
        placeholder="Search and select a customer...",
    )
    if pick:
        chosen = options[pick]
        st.session_state["selected_customer_id"] = chosen
        st.query_params["customer"] = chosen
        st.rerun()
    st.stop()

# ----------------------------------------------------------------------------
# Header
# ----------------------------------------------------------------------------

profile = data.customer_profile(customer_id)
if profile is None:
    st.error(f"No customer found for ID {customer_id}.")
    st.stop()

hero_banner(
    eyebrow="Green's Mowers",
    title=profile["customer"],
    subtitle=(
        f"Customer #{profile['customer_no']} &middot; "
        f"Onboarded {data.fmt_date(profile['onboarded'])}"
    ),
    compact=True,
)
seg_color = data.SEGMENT_COLOR.get(profile["segment"], "#94a3b8")
st.markdown(
    f"""
    <div style='display:inline-block;background:{seg_color};color:white;border-radius:999px;
                padding:6px 16px;font-weight:600;font-size:0.95rem;margin:-12px 0 20px 0;'>
        Segment: {profile['segment']}
    </div>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------------
# KPI tiles
# ----------------------------------------------------------------------------

c1, c2, c3, c4 = st.columns(4)
c1.metric("Lifetime Revenue", data.fmt_currency(profile["lifetime_revenue"]),
          help=f"{int(profile['lifetime_invoices']):,} invoices")
c2.metric("TTM Revenue", data.fmt_currency(profile["ttm_revenue"]),
          help=f"{int(profile['ttm_invoices']):,} invoices in last 12 months")
c3.metric("Last Purchase", data.fmt_date(profile["last_activity"]),
          help=f"{int(profile['recency'])} days ago" if profile["recency"] is not None else "Never")
c4.metric("Open A/R", data.fmt_currency(profile["open_ar"]),
          help=f"Credit limit {data.fmt_currency(profile['credit_limit'])}")

st.divider()

# ----------------------------------------------------------------------------
# Shared filter: invoice types + months window. Drives the monthly-revenue
# chart and the recent-invoices table below. Revenue mix pie always shows
# the full TTM picture so the user can see what they're filtering against.
# ----------------------------------------------------------------------------

type_options = {
    "Parts / Counter":         "in",
    "Service / Work Orders":   "wo",
    "Rentals":                 "rl",
}
type_color_map = {
    "Parts / Counter":       "#3DA5D9",
    "Service / Work Orders": "#16A34A",
    "Rentals":               "#D97706",
}

with st.container(border=True):
    fc1, fc2 = st.columns([3, 1])
    selected_labels = fc1.multiselect(
        "Invoice types",
        options=list(type_options.keys()),
        default=list(type_options.keys()),
        help="Filters the monthly chart and recent invoices table.",
        key=f"prof-types-{customer_id}",
    )
    months_window = fc2.selectbox(
        "Window",
        options=[12, 24, 36, 48],
        index=1,
        format_func=lambda m: f"Last {m} months",
        key=f"prof-window-{customer_id}",
    )

selected_codes: tuple[str, ...] | None = (
    tuple(type_options[t] for t in selected_labels) if selected_labels else None
)

# ----------------------------------------------------------------------------
# Charts: monthly revenue + revenue mix
# ----------------------------------------------------------------------------

chart_left, chart_right = st.columns([2, 1], gap="large")

with chart_left:
    st.subheader("Monthly Revenue")
    st.caption(
        f"Last {months_window} months for this customer."
        + (" Filtered by selected types." if selected_labels and len(selected_labels) < 3 else "")
    )
    if not selected_labels:
        st.info("Select at least one invoice type to see revenue.")
    else:
        monthly = data.customer_monthly_by_type(
            customer_id, months=months_window, invoice_types=selected_codes,
        )
        if monthly.empty:
            st.info(f"No posted invoices in the last {months_window} months for the selected types.")
        else:
            fig = px.bar(
                monthly, x="month", y="revenue", color="label",
                color_discrete_map=type_color_map,
                category_orders={"label": ["Parts / Counter", "Service / Work Orders", "Rentals"]},
                labels={"month": "", "revenue": "Revenue (USD)", "label": "Type"},
                height=320,
            )
            fig.update_layout(
                margin=dict(l=10, r=10, t=10, b=10),
                xaxis_tickangle=-45,
                yaxis_tickprefix="$", yaxis_tickformat=",",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
                barmode="stack",
            )
            st.plotly_chart(fig, use_container_width=True)

with chart_right:
    st.subheader("Revenue Mix (TTM)")
    st.caption("Full TTM mix - independent of filters.")
    mix = data.customer_type_mix(customer_id, ttm=True)
    if mix.empty:
        st.info("No TTM activity.")
    else:
        fig = px.pie(mix, names="label", values="revenue", hole=0.55,
                     color_discrete_map=type_color_map,
                     color="label")
        fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h"))
        fig.update_traces(textinfo="percent+label", hovertemplate="%{label}<br>$%{value:,.0f}<extra></extra>")
        st.plotly_chart(fig, use_container_width=True)

st.divider()

# ----------------------------------------------------------------------------
# Recent invoices  +  Open A/R  +  Contacts
# ----------------------------------------------------------------------------

inv_col, side_col = st.columns([3, 2], gap="large")

with inv_col:
    st.subheader("Recent Invoices")

    filter_options = data.customer_invoice_filter_options(customer_id)
    available_reps = filter_options["salespeople"]
    min_total = float(filter_options["min_total"])
    max_total = float(filter_options["max_total"])

    with st.container(border=True):
        f1, f2 = st.columns([1, 2])
        status_choice = f1.segmented_control(
            "Status",
            options=["All", "Finalized only", "Archived only"],
            default="All",
            selection_mode="single",
            key=f"prof-status-{customer_id}",
        )
        invoice_type_labels = f2.multiselect(
            "Type",
            options=list(type_options.keys()),
            default=list(type_options.keys()),
            key=f"prof-invoice-types-{customer_id}",
            help="Filters this Recent Invoices table only.",
        )

        f3, f4 = st.columns([2, 2])
        selected_reps = f3.multiselect(
            "Salesperson",
            options=available_reps,
            default=available_reps,
            key=f"prof-salespeople-{customer_id}",
            help="Uncheck salespeople to remove their invoices from the table.",
        )
        if max_total > min_total:
            total_range = f4.slider(
                "Total",
                min_value=min_total,
                max_value=max_total,
                value=(min_total, max_total),
                step=1.0,
                format="$%.0f",
                key=f"prof-total-range-{customer_id}",
            )
        else:
            total_range = (min_total, max_total)
            f4.metric("Total", data.fmt_currency(max_total, digits=2))

    if status_choice == "Finalized only":
        statuses = ("finalized",)
    elif status_choice == "Archived only":
        statuses = ("archived",)
    else:
        statuses = None

    invoice_type_codes = tuple(type_options[t] for t in invoice_type_labels)
    salesperson_filter = (
        tuple(selected_reps) if selected_reps and len(selected_reps) < len(available_reps) else None
    )
    selected_min_total, selected_max_total = total_range

    no_type_selected = len(invoice_type_labels) == 0
    no_salesperson_selected = bool(available_reps) and len(selected_reps) == 0

    if no_type_selected:
        st.info("Select at least one invoice type to see recent invoices.")
        invoices = None
    elif no_salesperson_selected:
        st.info("Select at least one salesperson to see recent invoices.")
        invoices = None
    else:
        invoices = data.customer_invoices(
            customer_id,
            limit=100,
            invoice_types=invoice_type_codes,
            statuses=statuses,
            salespeople=salesperson_filter,
            min_total=selected_min_total,
            max_total=selected_max_total,
        )

    if invoices is None:
        pass
    elif invoices.empty:
        st.info("No posted invoices match the current filter.")
    else:
        display = invoices.copy()
        display["activity_date"] = display["activity_date"].map(data.fmt_date)
        display["invoice_type"] = display["invoice_type"].map(data.TYPE_LABEL).fillna(display["invoice_type"])
        display.rename(columns={
            "invoice_no": "Invoice #",
            "activity_date": "Date",
            "invoice_type": "Type",
            "status": "Status",
            "salesperson": "Salesperson",
            "total": "Total",
        }, inplace=True)
        st.dataframe(
            display[["Invoice #", "Date", "Type", "Status", "Salesperson", "Total"]],
            width="stretch", hide_index=True, height=400,
            column_config={
                "Invoice #":   st.column_config.Column(width=95),
                "Date":        st.column_config.Column(width=110),
                "Type":        st.column_config.Column(width=165),
                "Status":      st.column_config.Column(width=105),
                "Salesperson": st.column_config.Column(width=120),
                "Total":       st.column_config.NumberColumn(format="$%,.2f", width=135),
            },
        )

with side_col:
    st.subheader("Open Invoices")

    # Aging filter — exact buckets, not cumulative ranges. Selecting 31-60
    # should exclude 61-90 and 90+ invoices.
    age_choice = st.segmented_control(
        "Aging bucket",
        options=["All", "0-30", "31-60", "61-90", "90+"],
        default="All",
        selection_mode="single",
        key=f"prof-open-age-{customer_id}",
    )
    age_filter = None if age_choice in (None, "All") else age_choice
    if age_filter:
        st.caption(f"Showing only invoices in the {age_filter} day bucket.")

    open_inv = data.open_invoices(
        customer_id=customer_id, limit=50, bucket=age_filter,
    )
    if open_inv.empty:
        if age_filter:
            st.info(f"No open invoices in the {age_filter} day bucket.")
        else:
            st.success("No outstanding balance.")
    else:
        d = open_inv.copy()
        d.rename(columns={
            "invoice_no": "Invoice",
            "aging_bucket": "Aged",
            "outstanding": "Outstanding",
        }, inplace=True)
        st.dataframe(
            d[["Invoice", "Aged", "Outstanding"]],
            width="content", hide_index=True, height=180,
            column_config={
                "Invoice":     st.column_config.Column(width=120),
                "Aged":        st.column_config.Column(width=90),
                "Outstanding": st.column_config.NumberColumn(format="$%,.2f", width=180),
            },
        )

    st.subheader("Contacts")
    contacts = data.customer_contacts(customer_id)
    if contacts.empty:
        st.warning("No active contacts on file.")
    else:
        for _, c in contacts.iterrows():
            primary = " (primary)" if c["is_primary"] else ""
            name = f"{c['first_name']} {c['last_name']}".strip() or "(no name)"
            with st.container(border=True):
                st.markdown(f"**{name}**{primary}")
                if c["title_dept"]:
                    st.caption(c["title_dept"])
                if c["email"]:
                    st.markdown(f":email: {c['email']}")
                if c["phone"]:
                    st.markdown(f":telephone_receiver: {c['phone']}")

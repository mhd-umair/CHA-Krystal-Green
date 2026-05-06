"""RFM segmentation of all active customers with click-through to profile.

Recency = days since last posted invoice.
Frequency / Monetary use the last 24 months of posted invoices.
"""

import streamlit as st

import data
from styles import apply_styles, hero_banner

st.set_page_config(page_title="At Risk - Green's Mowers", page_icon=":warning:", layout="wide")
apply_styles()

hero_banner(
    eyebrow="Green's Mowers",
    title="Customer Health Segments",
    subtitle=(
        "RFM segmentation across all active customers. "
        "Click a segment chip to filter, then use the Profile link to open the profile."
    ),
    compact=True,
)

with st.spinner("Computing segments..."):
    rfm = data.rfm()

if rfm.empty:
    st.info("No customers found.")
    st.stop()

# ----------------------------------------------------------------------------
# Segment chips
# ----------------------------------------------------------------------------

initial = st.query_params.get("segment")
if "selected_segment" not in st.session_state:
    st.session_state.selected_segment = initial

counts = (rfm.groupby("segment").size()
            .sort_values(ascending=False).reset_index(name="count"))

chip_cols = st.columns(len(counts) + 1)
with chip_cols[0]:
    if st.button(f"All ({len(rfm):,})", use_container_width=True,
                 type="primary" if not st.session_state.selected_segment else "secondary"):
        st.session_state.selected_segment = None
        st.query_params.clear()
        st.rerun()

for col, (_, row) in zip(chip_cols[1:], counts.iterrows()):
    seg = row["segment"]
    is_selected = st.session_state.selected_segment == seg
    color = data.SEGMENT_COLOR.get(seg, "#94a3b8")
    label = f"{seg}: {row['count']:,}"
    with col:
        if st.button(label, key=f"chip-{seg}", use_container_width=True,
                     type="primary" if is_selected else "secondary"):
            st.session_state.selected_segment = None if is_selected else seg
            if st.session_state.selected_segment:
                st.query_params["segment"] = seg
            else:
                st.query_params.clear()
            st.rerun()
        st.markdown(
            f"<div style='height:4px;background:{color};border-radius:2px;margin-top:-12px;'></div>",
            unsafe_allow_html=True,
        )

# ----------------------------------------------------------------------------
# Filtered grid
# ----------------------------------------------------------------------------

filtered = rfm.copy()
if st.session_state.selected_segment:
    filtered = filtered[filtered["segment"] == st.session_state.selected_segment]

display = filtered.copy()
display["Profile"] = display["customer_id"].map(lambda cid: f"/Customer_Profile?customer={int(cid)}")
display["last_activity"] = display["last_activity"].map(data.fmt_date)
display.rename(columns={
    "customer": "Customer",
    "customer_no": "Customer #",
    "segment": "Segment",
    "recency": "Recency (days)",
    "frequency_24m": "Freq 24m",
    "monetary_24m": "Spend 24m",
    "last_activity": "Last Activity",
}, inplace=True)

shown = display[[
    "Profile", "Customer", "Customer #", "Segment", "Recency (days)",
    "Freq 24m", "Spend 24m", "Last Activity",
]]

st.dataframe(
    shown,
    width="stretch",
    height=600,
    hide_index=True,
    column_config={
        "Profile":        st.column_config.LinkColumn(display_text="Open", width=70),
        "Customer":       st.column_config.Column(width=240),
        "Customer #":     st.column_config.Column(width=130),
        "Segment":        st.column_config.Column(width=110),
        "Recency (days)": st.column_config.NumberColumn(format="%d", width=125),
        "Freq 24m":       st.column_config.NumberColumn(format="%d", width=95),
        "Spend 24m":      st.column_config.NumberColumn(format="$%,.0f", width=135),
        "Last Activity":  st.column_config.Column(width=120),
    },
)

st.caption(f"{len(filtered):,} rows")

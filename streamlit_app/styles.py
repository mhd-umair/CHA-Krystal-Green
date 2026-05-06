"""Shared CSS + hero banner helpers for the customer analytics app.

Streamlit's default st.metric ships small, gray labels. We bump the size
and weight so KPI tiles read clearly across the room during a demo.
Call apply_styles() once at the top of every page (after st.set_page_config).
Optionally call hero_banner() on the home page for a branded header.
"""

from __future__ import annotations

import streamlit as st

# Streamlit serves files from streamlit_app/static/ at /app/static/<file>
# when [server] enableStaticServing = true in .streamlit/config.toml.
HERO_IMAGE_URL = "app/static/zero_turn_mower.jpg"

_CSS = """
<style>
/* ---------- Hero banner (used on every page) ---------- */
.hero-banner {
    position: relative;
    border-radius: 16px;
    overflow: hidden;
    margin: 0 0 28px 0;
    min-height: 240px;
    background-image:
        linear-gradient(90deg,
            rgba(187, 247, 208, 0.97) 0%,
            rgba(187, 247, 208, 0.92) 45%,
            rgba(187, 247, 208, 0.55) 70%,
            rgba(187, 247, 208, 0.05) 90%),
        url("HERO_IMAGE_URL_PLACEHOLDER");
    background-size: cover;
    background-position: center right;
    box-shadow: 0 1px 3px rgba(15, 23, 42, 0.08);
    border: 1px solid #BBF7D0;
}
.hero-banner.hero-compact {
    min-height: 170px;
    margin-bottom: 24px;
}
.hero-content {
    position: relative;
    padding: 36px 40px;
    max-width: 65%;
}
.hero-banner.hero-compact .hero-content {
    padding: 22px 36px 26px 36px;
}
.hero-eyebrow {
    font-size: 0.85rem;
    font-weight: 700;
    color: #047857;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    margin: 0 0 6px 0;
}
.hero-title {
    font-size: 2.2rem;
    font-weight: 700;
    color: #064E3B;
    margin: 0 0 8px 0;
    letter-spacing: -0.01em;
    line-height: 1.15;
}
.hero-banner.hero-compact .hero-title {
    font-size: 1.6rem;
}
.hero-subtitle {
    font-size: 1rem;
    color: #FFFFFF;
    line-height: 1.5;
    margin: 0;
    font-weight: 600;
    text-shadow:
        0 1px 2px rgba(6, 78, 59, 0.95),
        0 0 6px rgba(6, 78, 59, 0.65),
        0 0 1px rgba(6, 78, 59, 0.9);
}
.hero-banner.hero-compact .hero-subtitle {
    font-size: 0.9rem;
}
@media (max-width: 900px) {
    .hero-banner { min-height: 200px; }
    .hero-banner.hero-compact { min-height: 150px; }
    .hero-content { padding: 24px; max-width: 80%; }
    .hero-title { font-size: 1.6rem; }
    .hero-banner.hero-compact .hero-title { font-size: 1.3rem; }
}

/* ---------- KPI metric tiles ---------- */
[data-testid="stMetric"] {
    background: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    padding: 18px 20px 16px 20px;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}
[data-testid="stMetric"] [data-testid="stMetricLabel"] {
    font-size: 0.95rem !important;
    font-weight: 600 !important;
    color: #475569 !important;
    text-transform: uppercase;
    letter-spacing: 0.4px;
    margin-bottom: 4px;
}
[data-testid="stMetric"] [data-testid="stMetricLabel"] p {
    font-size: 0.95rem !important;
    font-weight: 600 !important;
    color: #475569 !important;
}
[data-testid="stMetric"] [data-testid="stMetricValue"] {
    font-size: 2rem !important;
    font-weight: 700 !important;
    color: #0F172A !important;
    line-height: 1.15 !important;
}
[data-testid="stMetric"] [data-testid="stMetricDelta"] {
    font-size: 0.9rem !important;
}
[data-testid="stMetric"] [data-testid="stMetricHelpIcon"] {
    color: #64748B !important;
}

/* ---------- Section headers ---------- */
h1 {
    font-weight: 700 !important;
    color: #0F172A !important;
    letter-spacing: -0.01em;
}
h2, h3 {
    font-weight: 600 !important;
    color: #1F2937 !important;
}

/* ---------- Tables ---------- */
[data-testid="stDataFrame"] thead tr th {
    background: #F1F5F9 !important;
    font-weight: 600 !important;
    color: #1F2937 !important;
}

/* ---------- Caption text more readable ---------- */
[data-testid="stCaptionContainer"] {
    color: #475569 !important;
}

/* ---------- Tertiary buttons styled as clickable headings ----------
   Used for the customer-name links in the Top-10 list on the Home page.
   Streamlit renders st.button(type="tertiary") with kind="tertiary" on
   the underlying button. We strip the button chrome and turn it into
   a left-aligned, bold, link-coloured label so it reads as a clickable
   customer name rather than a generic button. */
.stButton > button[kind="tertiary"],
button[data-testid="stBaseButton-tertiary"] {
    font-weight: 700 !important;
    font-size: 1.02rem !important;
    color: #0F4C81 !important;
    background: transparent !important;
    border: none !important;
    padding: 4px 0 0 0 !important;
    text-align: left !important;
    justify-content: flex-start !important;
    min-height: 0 !important;
    box-shadow: none !important;
    width: auto !important;
}
.stButton > button[kind="tertiary"]:hover,
button[data-testid="stBaseButton-tertiary"]:hover {
    color: #047857 !important;
    background: transparent !important;
    text-decoration: underline !important;
}
.stButton > button[kind="tertiary"]:focus,
button[data-testid="stBaseButton-tertiary"]:focus {
    box-shadow: none !important;
    outline: 2px solid rgba(15, 76, 129, 0.25) !important;
    outline-offset: 2px;
}
/* Inner span/div alignment fix for tertiary buttons. */
.stButton > button[kind="tertiary"] > div,
.stButton > button[kind="tertiary"] p {
    text-align: left !important;
    margin: 0 !important;
}

/* ---------- Top-10 revenue figure (right-aligned dollar amount) ---------- */
.top10-revenue {
    text-align: right;
    font-weight: 700;
    font-size: 1.05rem;
    color: #0F172A;
    padding-top: 6px;
}

/* ---------- Always-visible scrollbars ----------
   Streamlit's st.dataframe (built on glide-data-grid) hides its scrollbar
   overlay until hover, which is easy to miss. We force WebKit scrollbars
   to always show with stronger contrast so the user has an obvious affordance
   that more rows are available below the fold.
   Firefox uses `scrollbar-width: thin; scrollbar-color` (also set below);
   Firefox can't be forced to always-visible but the colour helps. */

/* App-wide scrollbar styling (also covers the page-scroll on tall pages). */
::-webkit-scrollbar {
    width: 8px;
    height: 8px;
}
::-webkit-scrollbar-track {
    background: #E2E8F0;
    border-radius: 4px;
}
::-webkit-scrollbar-thumb {
    background: #64748B;
    border-radius: 4px;
}
::-webkit-scrollbar-thumb:hover {
    background: #334155;
}
::-webkit-scrollbar-corner {
    background: #E2E8F0;
}
* {
    scrollbar-width: thin;
    scrollbar-color: #64748B #E2E8F0;
}

/* Streamlit dataframes (glide-data-grid).
   We force the internal scroller to always show its vertical scrollbar
   AND give the canvas an 8px right gutter so the rightmost column's
   values aren't visually clipped behind the bar. The canvas is sized
   from the scroller's offset width, so without the gutter the rightmost
   pixels get hidden. */
[data-testid="stDataFrame"] *,
[data-testid="stDataFrameResizable"] * {
    scrollbar-width: thin !important;
    scrollbar-color: #64748B #E2E8F0 !important;
}
[data-testid="stDataFrame"] *::-webkit-scrollbar,
[data-testid="stDataFrameResizable"] *::-webkit-scrollbar {
    width: 8px !important;
    height: 8px !important;
    background: #E2E8F0 !important;
}
[data-testid="stDataFrame"] *::-webkit-scrollbar-track,
[data-testid="stDataFrameResizable"] *::-webkit-scrollbar-track {
    background: #E2E8F0 !important;
    border-radius: 4px !important;
}
[data-testid="stDataFrame"] *::-webkit-scrollbar-thumb,
[data-testid="stDataFrameResizable"] *::-webkit-scrollbar-thumb {
    background: #64748B !important;
    border-radius: 4px !important;
}
[data-testid="stDataFrame"] *::-webkit-scrollbar-thumb:hover,
[data-testid="stDataFrameResizable"] *::-webkit-scrollbar-thumb:hover {
    background: #334155 !important;
}

/* glide-data-grid internal scroller. The class hash changes per build,
   so we target with [class*=...] to stay robust across versions. */
[data-testid="stDataFrame"] [class*="dvn-scroller"] {
    overflow-y: scroll !important;
    overflow-x: auto !important;
}

</style>
"""


def apply_styles() -> None:
    st.markdown(_CSS.replace("HERO_IMAGE_URL_PLACEHOLDER", HERO_IMAGE_URL),
                unsafe_allow_html=True)


def hero_banner(
    title: str,
    subtitle: str,
    *,
    eyebrow: str | None = "Green's Mowers",
    compact: bool = False,
) -> None:
    """Render the light-green banner with the zero-turn mower in the background.

    Use compact=True on sub-pages so the banner doesn't dominate the screen.
    """
    classes = "hero-banner hero-compact" if compact else "hero-banner"
    eyebrow_html = f'<p class="hero-eyebrow">{eyebrow}</p>' if eyebrow else ""
    st.markdown(
        f"""
        <div class="{classes}">
            <div class="hero-content">
                {eyebrow_html}
                <h1 class="hero-title">{title}</h1>
                <p class="hero-subtitle">{subtitle}</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

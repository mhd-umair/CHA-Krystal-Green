"""Data access layer for the Perseus customer analytics dashboard.

All queries:
- run against `perseus_equipment_database.db` in read-only mode,
- filter revenue to posted statuses ('finalized', 'archived') per the data dictionary,
- use SQLite's julianday() and date('now', '-N months') for date math (dates are TEXT),
- are cached with @st.cache_data so repeated page visits don't re-hit SQLite.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

import pandas as pd
import streamlit as st


def _resolve_db_path() -> Path:
    override = os.environ.get("PERSEUS_DB_PATH")
    if override:
        return Path(override).expanduser().resolve()
    # streamlit_app/data.py -> repo root -> perseus_equipment_database.db
    return (Path(__file__).resolve().parent.parent / "perseus_equipment_database.db").resolve()


DB_PATH = _resolve_db_path()


@contextmanager
def _conn():
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"SQLite database not found at {DB_PATH}. "
            "Set PERSEUS_DB_PATH or place the file at the repo root."
        )
    # Read-only URI mode prevents accidental writes.
    uri = f"file:{DB_PATH.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        yield conn
    finally:
        conn.close()


def _df(sql: str, params: dict | None = None) -> pd.DataFrame:
    with _conn() as c:
        return pd.read_sql_query(sql, c, params=params or {})


# ----------------------------------------------------------------------------
# Headline KPIs
# ----------------------------------------------------------------------------

@st.cache_data(ttl=600, show_spinner=False)
def headline_kpis() -> dict:
    sql = """
        SELECT
          (SELECT COUNT(*) FROM Customer WHERE IsActive=1)                       AS active_customers,
          (SELECT COUNT(DISTINCT CustomerId) FROM InvoiceHeader
              WHERE Status IN ('finalized','archived')
              AND ActivityDate >= date('now','-12 months'))                      AS ttm_customers,
          (SELECT COUNT(*) FROM Customer
              WHERE IsActive=1 AND EntDate >= date('now','-90 days'))            AS new_customers_90d,
          (SELECT COALESCE(SUM(TotalInvoice),0) FROM InvoiceHeader
              WHERE Status IN ('finalized','archived')
              AND ActivityDate >= date('now','-12 months'))                      AS ttm_revenue,
          (SELECT COALESCE(SUM(TotalInvoice),0) FROM InvoiceHeader
              WHERE Status IN ('finalized','archived'))                          AS lifetime_revenue;
    """
    base = _df(sql).iloc[0].to_dict()

    top10 = _df("""
        WITH ttm AS (
          SELECT CustomerId, SUM(TotalInvoice) AS Revenue
          FROM InvoiceHeader
          WHERE Status IN ('finalized','archived')
            AND ActivityDate >= date('now','-12 months')
          GROUP BY CustomerId
        ),
        ranked AS (
          SELECT Revenue, ROW_NUMBER() OVER (ORDER BY Revenue DESC) AS rn,
                 SUM(Revenue) OVER () AS Total
          FROM ttm
        )
        SELECT
          COALESCE(SUM(CASE WHEN rn <= 10 THEN Revenue ELSE 0 END), 0) AS Top10,
          COALESCE(MAX(Total), 0)                                       AS Total
        FROM ranked;
    """).iloc[0]
    total = float(top10["Total"]) or 0.0
    base["top10_share_ttm"] = (float(top10["Top10"]) / total) if total > 0 else 0.0

    base["open_ar_total"] = float(_df("""
        WITH paid AS (
          SELECT InvoiceDocId, SUM(Amount) AS Paid FROM Payment WHERE IsActive=1 GROUP BY InvoiceDocId
        )
        SELECT COALESCE(SUM(ih.TotalInvoice - COALESCE(p.Paid,0)), 0) AS open_ar
        FROM InvoiceHeader ih
        LEFT JOIN paid p ON p.InvoiceDocId = ih.InvoiceDocId
        WHERE ih.Status IN ('finalized','archived')
          AND ih.TotalInvoice - COALESCE(p.Paid,0) > 0.01;
    """).iloc[0]["open_ar"])

    base["at_risk_count"] = int(_df("""
        WITH agg AS (
          SELECT CustomerId,
                 CAST(julianday('now') - julianday(MAX(ActivityDate)) AS INTEGER) AS Recency,
                 SUM(CASE WHEN ActivityDate >= date('now','-24 months') THEN TotalInvoice ELSE 0 END) AS M24
          FROM InvoiceHeader WHERE Status IN ('finalized','archived')
          GROUP BY CustomerId
        )
        SELECT COUNT(*) AS n FROM Customer c
        JOIN agg a ON a.CustomerId = c.CustomerId
        WHERE c.IsActive = 1 AND a.Recency > 180 AND a.Recency <= 365 AND a.M24 >= 5000;
    """).iloc[0]["n"])

    return base


def _build_type_filter(invoice_types: tuple[str, ...] | None, params: dict) -> str:
    """Build a parametrized `AND InvoiceType IN (...)` clause and inject params.

    Returns an empty string when no filter should be applied. We use named
    parameters so ordering is irrelevant.
    """
    if not invoice_types:
        return ""
    placeholders = ",".join(f":t{i}" for i in range(len(invoice_types)))
    for i, t in enumerate(invoice_types):
        params[f"t{i}"] = t
    return f"AND InvoiceType IN ({placeholders})"


@st.cache_data(ttl=600, show_spinner=False)
def monthly_revenue(
    months: int = 24,
    invoice_types: tuple[str, ...] | None = None,
) -> pd.DataFrame:
    """Total monthly revenue, optionally restricted to a subset of invoice types."""
    params: dict = {"cutoff": f"-{months} months"}
    type_clause = _build_type_filter(invoice_types, params)
    sql = f"""
        SELECT substr(ActivityDate, 1, 7) AS month,
               SUM(TotalInvoice)          AS revenue,
               COUNT(*)                   AS invoice_count
        FROM InvoiceHeader
        WHERE Status IN ('finalized','archived')
          AND ActivityDate >= date('now', :cutoff)
          {type_clause}
        GROUP BY month
        ORDER BY month;
    """
    return _df(sql, params)


@st.cache_data(ttl=600, show_spinner=False)
def monthly_revenue_by_type(
    months: int = 24,
    invoice_types: tuple[str, ...] | None = None,
) -> pd.DataFrame:
    """Same as `monthly_revenue` but split into one row per (month, InvoiceType)
    so the chart can render a stacked bar by type."""
    params: dict = {"cutoff": f"-{months} months"}
    type_clause = _build_type_filter(invoice_types, params)
    sql = f"""
        SELECT substr(ActivityDate, 1, 7) AS month,
               InvoiceType                AS invoice_type,
               SUM(TotalInvoice)          AS revenue
        FROM InvoiceHeader
        WHERE Status IN ('finalized','archived')
          AND ActivityDate >= date('now', :cutoff)
          {type_clause}
        GROUP BY month, InvoiceType
        ORDER BY month, invoice_type;
    """
    df = _df(sql, params)
    if not df.empty:
        df["label"] = df["invoice_type"].map(TYPE_LABEL).fillna(df["invoice_type"])
    return df


# ----------------------------------------------------------------------------
# Leaderboard
# ----------------------------------------------------------------------------

@st.cache_data(ttl=600, show_spinner=False)
def leaderboard(ttm_only: bool, limit: int = 100, search: str | None = None) -> pd.DataFrame:
    date_clause = "AND ih.ActivityDate >= date('now','-12 months')" if ttm_only else ""
    search_clause = "AND (c.CustomerName LIKE :q OR c.CustomerNo LIKE :q)" if search else ""
    sql = f"""
        SELECT c.CustomerId  AS customer_id,
               c.CustomerNo  AS customer_no,
               c.CustomerName AS customer,
               COUNT(ih.InvoiceDocId)            AS invoices,
               COALESCE(SUM(ih.TotalInvoice),0)  AS revenue,
               COALESCE((SELECT SUM(TotalInvoice) FROM InvoiceHeader
                          WHERE CustomerId = c.CustomerId
                            AND Status IN ('finalized','archived')),0) AS lifetime_revenue,
               MAX(ih.ActivityDate) AS last_purchase,
               CAST(julianday('now') - julianday(MAX(ih.ActivityDate)) AS INTEGER) AS days_since
        FROM Customer c
        JOIN InvoiceHeader ih ON ih.CustomerId = c.CustomerId
        WHERE ih.Status IN ('finalized','archived')
          {date_clause}
          {search_clause}
        GROUP BY c.CustomerId
        ORDER BY revenue DESC
        LIMIT :limit;
    """
    params = {"limit": limit}
    if search:
        params["q"] = f"%{search}%"
    return _df(sql, params)


# ----------------------------------------------------------------------------
# RFM segmentation
# ----------------------------------------------------------------------------

RFM_SQL = """
    WITH agg AS (
      SELECT CustomerId,
             MAX(ActivityDate) AS LastActivity,
             CAST(julianday('now') - julianday(MAX(ActivityDate)) AS INTEGER) AS Recency,
             SUM(CASE WHEN ActivityDate >= date('now','-24 months') THEN 1 ELSE 0 END)            AS Frequency24,
             SUM(CASE WHEN ActivityDate >= date('now','-24 months') THEN TotalInvoice ELSE 0 END) AS Monetary24
      FROM InvoiceHeader WHERE Status IN ('finalized','archived')
      GROUP BY CustomerId
    )
    SELECT c.CustomerId   AS customer_id,
           c.CustomerNo   AS customer_no,
           c.CustomerName AS customer,
           a.LastActivity AS last_activity,
           a.Recency      AS recency,
           COALESCE(a.Frequency24, 0) AS frequency_24m,
           COALESCE(a.Monetary24,  0) AS monetary_24m,
           CASE
             WHEN a.LastActivity IS NULL                                      THEN 'Dormant'
             WHEN a.Recency > 365                                             THEN 'Lost'
             WHEN a.Recency > 180 AND a.Monetary24 >= 5000                    THEN 'At Risk'
             WHEN COALESCE(a.Frequency24,0) >= 6
                  AND COALESCE(a.Monetary24,0) >= 10000                       THEN 'Champion'
             WHEN a.Recency <= 90                                             THEN 'Active'
             ELSE 'Standard'
           END AS segment
    FROM Customer c
    LEFT JOIN agg a ON a.CustomerId = c.CustomerId
    WHERE c.IsActive = 1;
"""


@st.cache_data(ttl=600, show_spinner=False)
def rfm() -> pd.DataFrame:
    return _df(RFM_SQL).sort_values("monetary_24m", ascending=False).reset_index(drop=True)


@st.cache_data(ttl=600, show_spinner=False)
def segment_counts() -> pd.DataFrame:
    return (rfm()
            .groupby("segment", as_index=False)
            .size()
            .rename(columns={"size": "count"})
            .sort_values("count", ascending=False)
            .reset_index(drop=True))


# ----------------------------------------------------------------------------
# Customer profile
# ----------------------------------------------------------------------------

@st.cache_data(ttl=600, show_spinner=False)
def customer_profile(customer_id: int) -> dict | None:
    df = _df(
        """
        WITH posted AS (
          SELECT * FROM InvoiceHeader WHERE Status IN ('finalized','archived')
        ),
        paid AS (
          SELECT InvoiceDocId, SUM(Amount) AS Paid FROM Payment WHERE IsActive=1 GROUP BY InvoiceDocId
        )
        SELECT c.CustomerId   AS customer_id,
               c.CustomerNo   AS customer_no,
               c.CustomerName AS customer,
               c.IsActive     AS is_active,
               c.CredLimit    AS credit_limit,
               c.EntDate      AS onboarded,
               (SELECT MAX(ActivityDate) FROM posted WHERE CustomerId = c.CustomerId) AS last_activity,
               CAST(julianday('now') - julianday(
                   (SELECT MAX(ActivityDate) FROM posted WHERE CustomerId = c.CustomerId)
               ) AS INTEGER) AS recency,
               (SELECT COUNT(*) FROM posted WHERE CustomerId = c.CustomerId) AS lifetime_invoices,
               COALESCE((SELECT SUM(TotalInvoice) FROM posted WHERE CustomerId = c.CustomerId),0) AS lifetime_revenue,
               (SELECT COUNT(*) FROM posted
                  WHERE CustomerId = c.CustomerId AND ActivityDate >= date('now','-12 months')) AS ttm_invoices,
               COALESCE((SELECT SUM(TotalInvoice) FROM posted
                  WHERE CustomerId = c.CustomerId AND ActivityDate >= date('now','-12 months')),0) AS ttm_revenue,
               COALESCE((SELECT SUM(p.TotalInvoice - COALESCE(pd.Paid,0))
                          FROM posted p LEFT JOIN paid pd ON pd.InvoiceDocId = p.InvoiceDocId
                          WHERE p.CustomerId = c.CustomerId
                            AND p.TotalInvoice - COALESCE(pd.Paid,0) > 0.01), 0) AS open_ar
        FROM Customer c
        WHERE c.CustomerId = :cid;
        """,
        {"cid": customer_id},
    )
    if df.empty:
        return None
    row = df.iloc[0].to_dict()
    last_activity = row.get("last_activity")
    recency = row.get("recency")
    monetary = row.get("ttm_revenue", 0) + row.get("lifetime_revenue", 0)
    if last_activity is None or pd.isna(last_activity):
        seg = "Dormant"
    elif recency is not None and recency > 365:
        seg = "Lost"
    elif recency is not None and recency > 180 and monetary >= 5000:
        seg = "At Risk"
    elif row["ttm_invoices"] >= 6 and row["ttm_revenue"] >= 10000:
        seg = "Champion"
    elif recency is not None and recency <= 90:
        seg = "Active"
    else:
        seg = "Standard"
    row["segment"] = seg
    return row


@st.cache_data(ttl=600, show_spinner=False)
def customer_invoices(
    customer_id: int,
    limit: int = 100,
    invoice_types: tuple[str, ...] | None = None,
    statuses: tuple[str, ...] | None = None,
    salespeople: tuple[str, ...] | None = None,
    min_total: float | None = None,
    max_total: float | None = None,
) -> pd.DataFrame:
    params: dict = {"cid": customer_id, "limit": limit}
    type_clause = _build_type_filter(invoice_types, params)

    # Status filter — restrict to a subset of ('finalized','archived'). When
    # `statuses` is None we keep the default of both posted statuses.
    if statuses:
        placeholders = ",".join(f":s{i}" for i in range(len(statuses)))
        for i, s in enumerate(statuses):
            params[f"s{i}"] = s
        status_clause = f"Status IN ({placeholders})"
    else:
        status_clause = "Status IN ('finalized','archived')"

    salesperson_clause = ""
    if salespeople:
        placeholders = ",".join(f":rep{i}" for i in range(len(salespeople)))
        for i, rep in enumerate(salespeople):
            params[f"rep{i}"] = rep
        salesperson_clause = f"AND SalesPersonName IN ({placeholders})"

    total_clause = ""
    if min_total is not None:
        params["min_total"] = min_total
        total_clause += " AND TotalInvoice >= :min_total"
    if max_total is not None:
        params["max_total"] = max_total
        total_clause += " AND TotalInvoice <= :max_total"

    # Many archived invoices have an empty `InvoiceNo` but a populated `DocNo`.
    # Fall back through both so the user always sees a stable identifier.
    sql = f"""
        SELECT InvoiceDocId   AS invoice_doc_id,
               COALESCE(NULLIF(InvoiceNo, ''),
                        NULLIF(DocNo, ''),
                        '#' || InvoiceDocId)            AS invoice_no,
               Status         AS status,
               InvoiceType    AS invoice_type,
               ActivityDate   AS activity_date,
               SalesPersonName AS salesperson,
               TotalInvoice   AS total
        FROM InvoiceHeader
        WHERE CustomerId = :cid AND {status_clause}
          {type_clause}
          {salesperson_clause}
          {total_clause}
        ORDER BY ActivityDate DESC
        LIMIT :limit;
    """
    return _df(sql, params)


@st.cache_data(ttl=600, show_spinner=False)
def customer_invoice_filter_options(customer_id: int) -> dict:
    """Distinct salesperson list and total range for this customer's posted invoices."""
    df = _df(
        """
        SELECT
          MIN(TotalInvoice) AS min_total,
          MAX(TotalInvoice) AS max_total
        FROM InvoiceHeader
        WHERE CustomerId = :cid
          AND Status IN ('finalized','archived');
        """,
        {"cid": customer_id},
    )
    totals = df.iloc[0].to_dict() if not df.empty else {"min_total": 0, "max_total": 0}

    reps = _df(
        """
        SELECT DISTINCT SalesPersonName AS salesperson
        FROM InvoiceHeader
        WHERE CustomerId = :cid
          AND Status IN ('finalized','archived')
          AND SalesPersonName IS NOT NULL
          AND SalesPersonName != ''
        ORDER BY SalesPersonName;
        """,
        {"cid": customer_id},
    )
    return {
        "salespeople": reps["salesperson"].tolist() if not reps.empty else [],
        "min_total": float(totals.get("min_total") or 0),
        "max_total": float(totals.get("max_total") or 0),
    }


@st.cache_data(ttl=600, show_spinner=False)
def customer_type_mix(customer_id: int, ttm: bool = True) -> pd.DataFrame:
    date_clause = "AND ActivityDate >= date('now','-12 months')" if ttm else ""
    df = _df(
        f"""
        SELECT InvoiceType AS invoice_type,
               SUM(TotalInvoice) AS revenue,
               COUNT(*)          AS invoices
        FROM InvoiceHeader
        WHERE CustomerId = :cid AND Status IN ('finalized','archived')
          {date_clause}
        GROUP BY InvoiceType
        ORDER BY revenue DESC;
        """,
        {"cid": customer_id},
    )
    label = {"in": "Parts / Counter", "wo": "Service / Work Orders", "rl": "Rentals"}
    df["label"] = df["invoice_type"].map(label).fillna(df["invoice_type"])
    return df


@st.cache_data(ttl=600, show_spinner=False)
def customer_monthly(
    customer_id: int,
    months: int = 24,
    invoice_types: tuple[str, ...] | None = None,
) -> pd.DataFrame:
    params: dict = {"cid": customer_id, "cutoff": f"-{months} months"}
    type_clause = _build_type_filter(invoice_types, params)
    sql = f"""
        SELECT substr(ActivityDate, 1, 7) AS month,
               SUM(TotalInvoice) AS revenue,
               COUNT(*)          AS invoices
        FROM InvoiceHeader
        WHERE CustomerId = :cid AND Status IN ('finalized','archived')
          AND ActivityDate >= date('now', :cutoff)
          {type_clause}
        GROUP BY month
        ORDER BY month;
    """
    return _df(sql, params)


@st.cache_data(ttl=600, show_spinner=False)
def customer_monthly_by_type(
    customer_id: int,
    months: int = 24,
    invoice_types: tuple[str, ...] | None = None,
) -> pd.DataFrame:
    """Per-customer monthly revenue split by InvoiceType for stacked bar charts."""
    params: dict = {"cid": customer_id, "cutoff": f"-{months} months"}
    type_clause = _build_type_filter(invoice_types, params)
    sql = f"""
        SELECT substr(ActivityDate, 1, 7) AS month,
               InvoiceType                AS invoice_type,
               SUM(TotalInvoice)          AS revenue
        FROM InvoiceHeader
        WHERE CustomerId = :cid AND Status IN ('finalized','archived')
          AND ActivityDate >= date('now', :cutoff)
          {type_clause}
        GROUP BY month, InvoiceType
        ORDER BY month, invoice_type;
    """
    df = _df(sql, params)
    if not df.empty:
        df["label"] = df["invoice_type"].map(TYPE_LABEL).fillna(df["invoice_type"])
    return df


@st.cache_data(ttl=600, show_spinner=False)
def customer_contacts(customer_id: int) -> pd.DataFrame:
    return _df(
        """
        SELECT ct.ContactId   AS contact_id,
               ct.FirstName   AS first_name,
               ct.LastName    AS last_name,
               ct.TitleDept   AS title_dept,
               ct.IsPrimary   AS is_primary,
               (SELECT Addr  FROM CustomerEmail e
                  WHERE e.ContactId = ct.ContactId AND e.IsActive = 1
                  ORDER BY e.IsDefault DESC LIMIT 1) AS email,
               (SELECT Phone FROM CustomerPhone p
                  WHERE p.ContactId = ct.ContactId AND p.IsActive = 1
                  ORDER BY p.IsDefault DESC LIMIT 1) AS phone
        FROM Contact ct
        WHERE ct.CustomerId = :cid AND ct.IsActive = 1
        ORDER BY ct.IsPrimary DESC, ct.LastName, ct.FirstName;
        """,
        {"cid": customer_id},
    )


# ----------------------------------------------------------------------------
# Open A/R
# ----------------------------------------------------------------------------

@st.cache_data(ttl=600, show_spinner=False)
def aging_buckets() -> pd.DataFrame:
    return _df(
        """
        WITH paid AS (
          SELECT InvoiceDocId, SUM(Amount) AS Paid FROM Payment WHERE IsActive=1 GROUP BY InvoiceDocId
        ),
        open_inv AS (
          SELECT ih.InvoiceDocId,
                 ih.TotalInvoice - COALESCE(p.Paid,0) AS Outstanding,
                 CAST(julianday('now') - julianday(ih.ActivityDate) AS INTEGER) AS DaysOpen
          FROM InvoiceHeader ih
          LEFT JOIN paid p ON p.InvoiceDocId = ih.InvoiceDocId
          WHERE ih.Status IN ('finalized','archived')
            AND ih.TotalInvoice - COALESCE(p.Paid,0) > 0.01
        )
        SELECT
          CASE
            WHEN DaysOpen <= 30 THEN '0-30'
            WHEN DaysOpen <= 60 THEN '31-60'
            WHEN DaysOpen <= 90 THEN '61-90'
            ELSE '90+'
          END AS bucket,
          SUM(Outstanding) AS outstanding,
          COUNT(*)         AS invoice_count
        FROM open_inv
        GROUP BY bucket;
        """
    )


_BUCKET_CLAUSES = {
    "0-30":  "AND DaysOpen <= 30",
    "31-60": "AND DaysOpen > 30 AND DaysOpen <= 60",
    "61-90": "AND DaysOpen > 60 AND DaysOpen <= 90",
    "90+":   "AND DaysOpen > 90",
    # Cumulative "older than" ranges, useful for the Customer Profile
    # "Open Invoices" age filter (30+ / 60+ / 90+).
    "30+":   "AND DaysOpen > 30",
    "60+":   "AND DaysOpen > 60",
}

# Same logic but applied directly to ih.ActivityDate (no DaysOpen alias).
_BUCKET_CLAUSES_INVOICE = {
    "0-30":  "AND (julianday('now') - julianday(ih.ActivityDate)) <= 30",
    "31-60": "AND (julianday('now') - julianday(ih.ActivityDate)) > 30 "
             "AND (julianday('now') - julianday(ih.ActivityDate)) <= 60",
    "61-90": "AND (julianday('now') - julianday(ih.ActivityDate)) > 60 "
             "AND (julianday('now') - julianday(ih.ActivityDate)) <= 90",
    "90+":   "AND (julianday('now') - julianday(ih.ActivityDate)) > 90",
    "30+":   "AND (julianday('now') - julianday(ih.ActivityDate)) > 30",
    "60+":   "AND (julianday('now') - julianday(ih.ActivityDate)) > 60",
}


@st.cache_data(ttl=600, show_spinner=False)
def customer_ar_summary(limit: int = 200, bucket: str | None = None) -> pd.DataFrame:
    """Per-customer outstanding A/R. When `bucket` is set, totals reflect only
    invoices in that aging bucket and customers without any qualifying invoices
    are filtered out entirely."""
    bucket_clause = _BUCKET_CLAUSES.get(bucket or "", "")
    sql = f"""
        WITH paid AS (
          SELECT InvoiceDocId, SUM(Amount) AS Paid, MIN(EntDate) AS FirstPmt
          FROM Payment WHERE IsActive=1 GROUP BY InvoiceDocId
        ),
        open_inv AS (
          SELECT ih.CustomerId,
                 ih.TotalInvoice - COALESCE(p.Paid,0) AS Outstanding,
                 CAST(julianday('now') - julianday(ih.ActivityDate) AS INTEGER) AS DaysOpen
          FROM InvoiceHeader ih
          LEFT JOIN paid p ON p.InvoiceDocId = ih.InvoiceDocId
          WHERE ih.Status IN ('finalized','archived')
            AND ih.TotalInvoice - COALESCE(p.Paid,0) > 0.01
        ),
        filtered_open AS (
          SELECT * FROM open_inv WHERE 1=1 {bucket_clause}
        ),
        paid_inv AS (
          SELECT ih.CustomerId,
                 julianday(p.FirstPmt) - julianday(ih.ActivityDate) AS DaysToPay
          FROM InvoiceHeader ih JOIN paid p ON p.InvoiceDocId = ih.InvoiceDocId
          WHERE ih.Status IN ('finalized','archived')
            AND ih.TotalInvoice - COALESCE(p.Paid,0) <= 0.01
            AND ih.ActivityDate >= date('now','-24 months')
        ),
        avg_pay AS (
          SELECT CustomerId, AVG(DaysToPay) AS AvgDaysToPay
          FROM paid_inv WHERE DaysToPay >= 0 GROUP BY CustomerId
        )
        SELECT c.CustomerId  AS customer_id,
               c.CustomerNo  AS customer_no,
               c.CustomerName AS customer,
               COUNT(o.Outstanding)        AS open_invoices,
               COALESCE(SUM(o.Outstanding),0) AS outstanding,
               COALESCE(MAX(o.DaysOpen),0)    AS oldest_days,
               ap.AvgDaysToPay                AS avg_days_to_pay
        FROM Customer c
        JOIN filtered_open o ON o.CustomerId = c.CustomerId
        LEFT JOIN avg_pay ap ON ap.CustomerId = c.CustomerId
        GROUP BY c.CustomerId
        ORDER BY outstanding DESC
        LIMIT :limit;
    """
    return _df(sql, {"limit": limit})


@st.cache_data(ttl=600, show_spinner=False)
def open_invoices(
    customer_id: int | None = None,
    limit: int = 200,
    bucket: str | None = None,
) -> pd.DataFrame:
    cust_clause = "AND ih.CustomerId = :cid" if customer_id else ""
    bucket_clause = _BUCKET_CLAUSES_INVOICE.get(bucket or "", "")
    # Same identifier fallback as customer_invoices so archived rows aren't blank.
    sql = f"""
        WITH paid AS (
          SELECT InvoiceDocId, SUM(Amount) AS Paid FROM Payment WHERE IsActive=1 GROUP BY InvoiceDocId
        )
        SELECT ih.InvoiceDocId AS invoice_doc_id,
               COALESCE(NULLIF(ih.InvoiceNo, ''),
                        NULLIF(ih.DocNo, ''),
                        '#' || ih.InvoiceDocId)         AS invoice_no,
               ih.CustomerId   AS customer_id,
               ih.CustomerName AS customer,
               ih.ActivityDate AS activity_date,
               ih.TotalInvoice AS total,
               COALESCE(p.Paid, 0)                      AS paid,
               ih.TotalInvoice - COALESCE(p.Paid, 0)    AS outstanding,
               CAST(julianday('now') - julianday(ih.ActivityDate) AS INTEGER) AS days_open
        FROM InvoiceHeader ih
        LEFT JOIN paid p ON p.InvoiceDocId = ih.InvoiceDocId
        WHERE ih.Status IN ('finalized','archived')
          AND ih.TotalInvoice - COALESCE(p.Paid, 0) > 0.01
          {cust_clause}
          {bucket_clause}
        ORDER BY outstanding DESC
        LIMIT :limit;
    """
    params: dict = {"limit": limit}
    if customer_id:
        params["cid"] = customer_id
    df = _df(sql, params)
    if not df.empty:
        df["aging_bucket"] = pd.cut(
            df["days_open"],
            bins=[-1, 30, 60, 90, 10**9],
            labels=["0-30", "31-60", "61-90", "90+"],
        ).astype(str)
    return df


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

# Slightly darker shades chosen to keep white text readable (>=4.5:1 contrast).
SEGMENT_COLOR = {
    "Champion": "#16A34A",
    "Active":   "#0284C7",
    "Standard": "#475569",
    "At Risk":  "#D97706",
    "Lost":     "#DC2626",
    "Dormant":  "#1E293B",
}

BUCKET_COLOR = {
    "0-30":  "#16A34A",
    "31-60": "#0284C7",
    "61-90": "#D97706",
    "90+":   "#DC2626",
}

TYPE_LABEL = {"in": "Parts / Counter", "wo": "Service / Work Orders", "rl": "Rentals"}


def fmt_currency(v: float | int | None, digits: int = 0) -> str:
    if v is None or pd.isna(v):
        return "-"
    return f"${v:,.{digits}f}"


def fmt_int(v: float | int | None) -> str:
    if v is None or pd.isna(v):
        return "-"
    return f"{int(v):,}"


def fmt_date(raw) -> str:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return "-"
    s = str(raw)
    return s[:10] if len(s) >= 10 else s

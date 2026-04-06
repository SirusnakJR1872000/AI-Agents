from __future__ import annotations

import io
from dataclasses import asdict

import pandas as pd
import plotly.express as px
import streamlit as st

from proto.attribution import AttributionConfig, run_attribution, validate_inputs
from proto.connectors import ConnectorConfig, load_external_context, load_from_netcore_s3, load_from_sfmc_sftp
from proto.insights import (
    InsightConfig,
    build_executive_one_pager,
    build_ops_report,
    campaign_kpis,
    creative_performance,
    frequency_meter,
    trend_flags,
)


st.set_page_config(page_title="Campaign Attribution + Intelligence (Prototype)", layout="wide")

st.title("Campaign Attribution + Intelligence Prototype")

with st.sidebar:
    st.header("Inputs")
    source = st.selectbox(
        "Data source (connectors)",
        [
            "Sample data (built-in)",
            "Manual upload (CSV)",
            "SFMC → SFTP (simulated folder)",
            "Netcore → S3 (simulated folder)",
        ],
        index=0,
    )

    st.divider()
    st.subheader("Connector settings")
    conn = ConnectorConfig()
    sfmc_dir = st.text_input("SFMC SFTP folder", value=conn.sfmc_sftp_dir)
    netcore_dir = st.text_input("Netcore S3 folder", value=conn.netcore_s3_dir)

    st.subheader("Manual upload (only used if source = Manual upload)")
    up_eng = st.file_uploader("Engagement events CSV", type=["csv"], key="up_eng")
    up_txn = st.file_uploader("Transactions CSV", type=["csv"], key="up_txn")
    up_id = st.file_uploader("Identity map CSV (optional)", type=["csv"], key="up_id")

    st.subheader("External context inputs (optional)")
    up_context = st.file_uploader(
        "Upload competitor/news/context notes (txt/csv)",
        type=["txt", "csv", "md"],
        accept_multiple_files=True,
        key="up_ctx",
    )

    st.divider()
    st.header("Attribution config")
    lookback = st.slider("Lookback window (days)", 1, 30, 7, 1)
    require_click = st.toggle("Require Click (vs any engagement)", value=True)

    st.header("Insights config")
    trend_days = st.slider("Trend window (days)", 3, 30, 7, 1)
    freq_cap = st.slider("Frequency cap (events per 7d)", 1, 20, 5, 1)

    st.divider()
    st.header("Human-in-the-loop")
    editor_notes = st.text_area(
        "Editor notes (context, reasons, overrides)",
        placeholder="E.g., Competitor campaign started Mar 24; likely impacted CTR on WhatsApp...",
        height=120,
    )
    approve = st.checkbox("Approve outputs for export", value=False)


@st.cache_data(show_spinner=False)
def _load_sample() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    e = pd.read_csv("data/sample_engagement.csv")
    t = pd.read_csv("data/sample_transactions.csv")
    i = pd.read_csv("data/sample_identity.csv")
    return e, t, i


def _read_upload(up) -> pd.DataFrame:
    if up is None:
        return pd.DataFrame()
    return pd.read_csv(up)

@st.cache_data(show_spinner=False)
def _load_sfmc(sfmc_sftp_dir: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    cfg = ConnectorConfig(sfmc_sftp_dir=sfmc_sftp_dir)
    return load_from_sfmc_sftp(cfg)


@st.cache_data(show_spinner=False)
def _load_netcore(netcore_s3_dir: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    cfg = ConnectorConfig(netcore_s3_dir=netcore_s3_dir)
    return load_from_netcore_s3(cfg)


def _context_text(files) -> str:
    if not files:
        return ""
    uploads = [f.getvalue() for f in files]
    names = [f.name for f in files]
    return load_external_context(uploads, names)


context_notes = _context_text(up_context)

if source == "Sample data (built-in)":
    engagement, txns, identity = _load_sample()
elif source == "Manual upload (CSV)":
    engagement = _read_upload(up_eng)
    txns = _read_upload(up_txn)
    identity = _read_upload(up_id)
elif source == "SFMC → SFTP (simulated folder)":
    engagement, txns = _load_sfmc(sfmc_dir)
    identity = _read_upload(up_id)
elif source == "Netcore → S3 (simulated folder)":
    engagement, txns = _load_netcore(netcore_dir)
    identity = _read_upload(up_id)
else:
    engagement, txns, identity = _load_sample()


st.subheader("1) Ingestion + Validation")
st.caption(
    f"Connector source: **{source}**. "
    "SFMC/Netcore connectors are simulated as local folders (latest CSV wins)."
)
colA, colB, colC = st.columns([2, 2, 1])
with colA:
    st.caption("Engagement (preview)")
    st.dataframe(engagement.head(50), use_container_width=True)
with colB:
    st.caption("Transactions (preview)")
    st.dataframe(txns.head(50), use_container_width=True)
with colC:
    st.caption("Identity map (preview)")
    st.dataframe(identity.head(50), use_container_width=True)

issues = validate_inputs(engagement, txns)
if issues:
    st.error("Input validation issues:\n- " + "\n- ".join(issues))
    st.stop()
else:
    st.success("Inputs look OK for prototype schema.")


st.subheader("2) Attribution Engine")
cfg = AttributionConfig(lookback_days=lookback, require_click=require_click, model="last_touch")

campaign_ids = sorted(engagement["campaign_id"].astype("string").dropna().unique().tolist()) if "campaign_id" in engagement.columns else []
selected_campaigns = st.multiselect("Filter campaigns (optional)", campaign_ids, default=[])

results = run_attribution(
    engagement=engagement,
    txns=txns,
    identity_map=identity if not identity.empty else None,
    cfg=cfg,
    campaign_filter=selected_campaigns if selected_campaigns else None,
)

cust = results["customer_level"]
camp = results["campaign_summary"]
chan = results["channel_summary"]
exc = results["exceptions"]

tab1, tab2, tab3, tab4 = st.tabs(
    ["Customer-level attribution", "Campaign summary", "Channel summary", "Exceptions"]
)
with tab1:
    st.dataframe(cust, use_container_width=True, height=380)
with tab2:
    st.dataframe(camp, use_container_width=True, height=380)
    if not camp.empty and "attributed_revenue" in camp.columns:
        fig = px.bar(camp.head(20), x="campaign_name", y="attributed_revenue", title="Top campaigns by attributed revenue")
        st.plotly_chart(fig, use_container_width=True)
with tab3:
    st.dataframe(chan, use_container_width=True, height=380)
    if not chan.empty and "attributed_revenue" in chan.columns:
        fig = px.bar(chan, x="channel", y="attributed_revenue", title="Revenue contribution by channel")
        st.plotly_chart(fig, use_container_width=True)
with tab4:
    st.dataframe(exc, use_container_width=True, height=380)


st.subheader("3) Campaign Intelligence (Insights Generator)")
icfg = InsightConfig(trend_window_days=trend_days, frequency_cap_per_7d=freq_cap)

kpi = campaign_kpis(engagement)
trend = trend_flags(engagement, icfg)
creative = creative_performance(engagement)
freq = frequency_meter(engagement, icfg)

left, right = st.columns([1.2, 1])
with left:
    st.caption("Campaign KPI report (prototype)")
    st.dataframe(kpi, use_container_width=True, height=280)
    st.caption("Creative-wise performance (prototype)")
    st.dataframe(creative, use_container_width=True, height=280)
with right:
    st.caption("Trend flags (CTR change vs previous window)")
    st.dataframe(trend, use_container_width=True, height=200)
    if not trend.empty:
        fig = px.bar(trend, x="channel", y="delta", color="flag", title="CTR delta by channel")
        st.plotly_chart(fig, use_container_width=True)
    st.caption("Frequency meter (events per identity in last 7 days)")
    st.dataframe(freq.head(200), use_container_width=True, height=260)

st.divider()
st.subheader("4) Human validation + Exports")

exec_md = build_executive_one_pager(camp, chan, trend, notes=editor_notes if editor_notes else None)
ops_md = build_ops_report(
    cfg=icfg,
    attribution_cfg=asdict(cfg),
    exceptions=exc,
    creative=creative,
    frequency=freq,
    context_notes="\n\n".join([x for x in [context_notes, editor_notes] if x]).strip() or None,
)

col1, col2 = st.columns(2)
with col1:
    st.caption("Executive one-pager (preview)")
    st.markdown(exec_md)
with col2:
    st.caption("Ops detailed report (preview)")
    st.markdown(ops_md)

if not approve:
    st.info("Enable **Approve outputs for export** in the sidebar to download artifacts.")
else:
    st.success("Approved. You can download artifacts below.")

    def to_csv_download(df: pd.DataFrame) -> bytes:
        return df.to_csv(index=False).encode("utf-8")

    dcol1, dcol2, dcol3, dcol4 = st.columns(4)
    with dcol1:
        st.download_button("Download customer-level CSV", data=to_csv_download(cust), file_name="customer_level_attribution.csv")
    with dcol2:
        st.download_button("Download campaign summary CSV", data=to_csv_download(camp), file_name="campaign_summary.csv")
    with dcol3:
        st.download_button("Download channel summary CSV", data=to_csv_download(chan), file_name="channel_summary.csv")
    with dcol4:
        st.download_button("Download exceptions CSV", data=to_csv_download(exc), file_name="exceptions.csv")

    st.download_button(
        "Download executive one-pager (MD)",
        data=exec_md.encode("utf-8"),
        file_name="executive_one_pager.md",
    )
    st.download_button(
        "Download ops report (MD)",
        data=ops_md.encode("utf-8"),
        file_name="full_detailed_report.md",
    )

st.caption(
    "Prototype notes: this app demonstrates the workflow and core attribution logic; connectors (SFMC SFTP, S3, etc.) and advanced agent checks are out of scope here."
)


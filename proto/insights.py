from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class InsightConfig:
    trend_window_days: int = 7
    frequency_cap_per_7d: int = 5


def campaign_kpis(engagement: pd.DataFrame) -> pd.DataFrame:
    e = engagement.copy()
    e["event_ts"] = pd.to_datetime(e["event_ts"], errors="coerce")
    e = e.dropna(subset=["event_ts"])

    # Normalize a few common engagement categories
    et = e["engagement_type"].astype("string").str.lower()
    e["_is_sent"] = et.isin(["sent"])
    e["_is_delivered"] = et.isin(["delivered"])
    e["_is_open"] = et.isin(["open", "read"])
    e["_is_click"] = et.isin(["click"])

    out = (
        e.groupby(["campaign_id", "campaign_name", "channel"], dropna=False)
        .agg(
            events=("engagement_type", "count"),
            unique_users=("user_id", lambda s: s.astype("string").nunique(dropna=True)),
            sent=("_is_sent", "sum"),
            delivered=("_is_delivered", "sum"),
            opened_read=("_is_open", "sum"),
            clicked=("_is_click", "sum"),
            first_event=("event_ts", "min"),
            last_event=("event_ts", "max"),
        )
        .reset_index()
    )

    # rates where denominator exists
    out["delivery_rate"] = np.where(out["sent"] > 0, out["delivered"] / out["sent"], np.nan)
    out["open_read_rate"] = np.where(out["delivered"] > 0, out["opened_read"] / out["delivered"], np.nan)
    out["click_rate"] = np.where(out["delivered"] > 0, out["clicked"] / out["delivered"], np.nan)
    return out.sort_values(["last_event"], ascending=False)


def trend_flags(engagement: pd.DataFrame, cfg: InsightConfig) -> pd.DataFrame:
    e = engagement.copy()
    e["event_ts"] = pd.to_datetime(e["event_ts"], errors="coerce")
    e = e.dropna(subset=["event_ts"])
    if e.empty:
        return pd.DataFrame(columns=["channel", "metric", "current", "previous", "delta", "flag"])

    end = e["event_ts"].max().normalize() + pd.Timedelta(days=1)
    cur_start = end - pd.Timedelta(days=cfg.trend_window_days)
    prev_start = cur_start - pd.Timedelta(days=cfg.trend_window_days)

    cur = e[(e["event_ts"] >= cur_start) & (e["event_ts"] < end)]
    prev = e[(e["event_ts"] >= prev_start) & (e["event_ts"] < cur_start)]

    def clicks(df: pd.DataFrame) -> pd.DataFrame:
        et = df["engagement_type"].astype("string").str.lower()
        df = df.assign(_is_click=et.eq("click"))
        return df.groupby("channel", dropna=False).agg(clicks=("_is_click", "sum"), events=("channel", "count")).reset_index()

    ccur = clicks(cur).rename(columns={"clicks": "current_clicks", "events": "current_events"})
    cprev = clicks(prev).rename(columns={"clicks": "prev_clicks", "events": "prev_events"})
    merged = ccur.merge(cprev, on="channel", how="outer").fillna(0)

    merged["current_ctr"] = np.where(merged["current_events"] > 0, merged["current_clicks"] / merged["current_events"], np.nan)
    merged["prev_ctr"] = np.where(merged["prev_events"] > 0, merged["prev_clicks"] / merged["prev_events"], np.nan)
    merged["delta"] = merged["current_ctr"] - merged["prev_ctr"]
    merged["flag"] = np.where(merged["delta"] > 0.03, "Up", np.where(merged["delta"] < -0.03, "Down", "Flat"))

    return merged[["channel", "current_ctr", "prev_ctr", "delta", "flag"]].sort_values(["delta"], ascending=False)


def creative_performance(engagement: pd.DataFrame) -> pd.DataFrame:
    e = engagement.copy()
    e["event_ts"] = pd.to_datetime(e["event_ts"], errors="coerce")
    e = e.dropna(subset=["event_ts"])
    if e.empty:
        return pd.DataFrame(columns=["creative_id", "campaign_id", "channel", "clicks", "events", "ctr"])

    et = e["engagement_type"].astype("string").str.lower()
    e["_is_click"] = et.eq("click")

    group_cols = [c for c in ["creative_id", "campaign_id", "campaign_name", "channel", "cta", "language"] if c in e.columns]
    if not group_cols:
        return pd.DataFrame(columns=["creative_id", "campaign_id", "channel", "clicks", "events", "ctr"])

    out = e.groupby(group_cols, dropna=False).agg(clicks=("_is_click", "sum"), events=("engagement_type", "count")).reset_index()
    out["ctr"] = np.where(out["events"] > 0, out["clicks"] / out["events"], np.nan)
    return out.sort_values(["ctr", "events"], ascending=[False, False])


def frequency_meter(engagement: pd.DataFrame, cfg: InsightConfig) -> pd.DataFrame:
    e = engagement.copy()
    e["event_ts"] = pd.to_datetime(e["event_ts"], errors="coerce")
    e = e.dropna(subset=["event_ts"])
    if e.empty:
        return pd.DataFrame(columns=["identity_key", "events_7d", "status"])

    # derive identity_key in the same priority as attribution prototype
    if "identity_key" not in e.columns:
        for c in ("user_id", "email", "phone"):
            if c in e.columns and e[c].notna().any():
                e["identity_key"] = e[c].astype("string")
                break
        if "identity_key" not in e.columns:
            e["identity_key"] = pd.Series([f"row_{i}" for i in range(len(e))], index=e.index, dtype="string")

    end = e["event_ts"].max()
    start = end - pd.Timedelta(days=7)
    w = e[(e["event_ts"] >= start) & (e["event_ts"] <= end)]

    out = w.groupby("identity_key", dropna=False).agg(events_7d=("engagement_type", "count")).reset_index()
    out["status"] = np.where(out["events_7d"] > cfg.frequency_cap_per_7d, "Over-cap", "OK")
    return out.sort_values(["events_7d"], ascending=False)


def build_executive_one_pager(
    campaign_summary: pd.DataFrame,
    channel_summary: pd.DataFrame,
    trend: pd.DataFrame,
    notes: Optional[str] = None,
) -> str:
    top_campaigns = campaign_summary.head(5) if campaign_summary is not None else pd.DataFrame()
    top_channels = channel_summary.head(5) if channel_summary is not None else pd.DataFrame()

    def md_table(df: pd.DataFrame, cols: list[str]) -> str:
        if df is None or df.empty:
            return "_No data_"
        try:
            return df[cols].to_markdown(index=False)
        except Exception:
            # Fallback to a simple pipe table (avoids optional tabulate dependency issues)
            sub = df[cols].copy()
            sub = sub.fillna("")
            header = "| " + " | ".join(cols) + " |"
            sep = "| " + " | ".join(["---"] * len(cols)) + " |"
            rows = ["| " + " | ".join(map(str, r)) + " |" for r in sub.astype(str).to_numpy().tolist()]
            return "\n".join([header, sep] + rows)

    s = []
    s.append("## Campaign → Revenue Impact (Prototype)")
    if notes:
        s.append(notes.strip())
    s.append("")
    s.append("### Top campaigns (attributed revenue)")
    if not top_campaigns.empty:
        cols = [c for c in ["campaign_id", "campaign_name", "converted_orders", "attributed_revenue"] if c in top_campaigns.columns]
        s.append(md_table(top_campaigns, cols))
    else:
        s.append("_No attributed campaigns_")

    s.append("")
    s.append("### Top channels (attributed revenue)")
    if not top_channels.empty:
        cols = [c for c in ["channel", "converted_orders", "attributed_revenue"] if c in top_channels.columns]
        s.append(md_table(top_channels, cols))
    else:
        s.append("_No attributed channels_")

    s.append("")
    s.append("### Trend flags (CTR change vs previous window)")
    if trend is not None and not trend.empty:
        cols = [c for c in ["channel", "current_ctr", "prev_ctr", "delta", "flag"] if c in trend.columns]
        s.append(md_table(trend, cols))
    else:
        s.append("_No trend data_")

    return "\n".join(s).strip() + "\n"


def build_ops_report(
    cfg: InsightConfig,
    attribution_cfg: dict,
    exceptions: pd.DataFrame,
    creative: pd.DataFrame,
    frequency: pd.DataFrame,
    context_notes: Optional[str] = None,
) -> str:
    exc = exceptions.head(30) if exceptions is not None else pd.DataFrame()
    cr = creative.head(30) if creative is not None else pd.DataFrame()
    fr = frequency.head(30) if frequency is not None else pd.DataFrame()

    def md_table(df: pd.DataFrame) -> str:
        if df is None or df.empty:
            return "_No data_"
        try:
            return df.to_markdown(index=False)
        except Exception:
            sub = df.copy().fillna("")
            cols = sub.columns.tolist()
            header = "| " + " | ".join(cols) + " |"
            sep = "| " + " | ".join(["---"] * len(cols)) + " |"
            rows = ["| " + " | ".join(map(str, r)) + " |" for r in sub.astype(str).to_numpy().tolist()]
            return "\n".join([header, sep] + rows)

    s = []
    s.append("## Full detailed report (Prototype)")
    if context_notes:
        s.append(context_notes.strip())
    s.append("")
    s.append("### Configuration")
    s.append(f"- Trend window: {cfg.trend_window_days} days")
    s.append(f"- Frequency cap: {cfg.frequency_cap_per_7d} events / 7d")
    s.append("")
    s.append("```")
    s.append(str(attribution_cfg))
    s.append("```")
    s.append("")
    s.append("### Exceptions (top)")
    s.append(md_table(exc))
    s.append("")
    s.append("### Creative performance (top)")
    s.append(md_table(cr))
    s.append("")
    s.append("### Frequency meter (top)")
    s.append(md_table(fr))
    s.append("")
    s.append("### Notes on transparency (prototype)")
    s.append("- Attribution implemented: last-touch click within window.")
    s.append("- Confidence scoring / probabilistic weights: not implemented in this prototype.")
    return "\n".join(s).strip() + "\n"


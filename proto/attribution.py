from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Iterable, Optional

import numpy as np
import pandas as pd


REQUIRED_ENGAGEMENT_COLS = {
    "event_ts",
    "channel",
    "campaign_id",
    "campaign_name",
    "campaign_type",
    "engagement_type",
}

REQUIRED_TXN_COLS = {
    "txn_ts",
    "order_id",
    "revenue",
    "product",
}


@dataclass(frozen=True)
class AttributionConfig:
    lookback_days: int = 7
    require_click: bool = True
    model: str = "last_touch"  # prototype supports: last_touch


def _coerce_dt(df: pd.DataFrame, col: str) -> pd.DataFrame:
    out = df.copy()
    out[col] = pd.to_datetime(out[col], errors="coerce")
    return out


def _pick_identity_key(df: pd.DataFrame) -> pd.Series:
    """
    Create a unified identity key using available identifiers.
    Priority: user_id > email > phone. Falls back to a unique row key.
    """
    for c in ("user_id", "email", "phone"):
        if c in df.columns:
            s = df[c].astype("string")
            if s.notna().any():
                return s.fillna(pd.NA)
    return pd.Series([f"row_{i}" for i in range(len(df))], index=df.index, dtype="string")


def _apply_identity_map(
    df: pd.DataFrame, identity_map: Optional[pd.DataFrame]
) -> pd.DataFrame:
    if identity_map is None or identity_map.empty:
        out = df.copy()
        out["identity_key"] = _pick_identity_key(out)
        return out

    idm = identity_map.copy()
    for c in ("user_id", "email", "phone"):
        if c in idm.columns:
            idm[c] = idm[c].astype("string")

    # explode identity mapping into a long format so any identifier can map to user_id
    rows = []
    if "user_id" in idm.columns:
        if "email" in idm.columns:
            rows.append(idm[["user_id", "email"]].rename(columns={"email": "identifier"}))
        if "phone" in idm.columns:
            rows.append(idm[["user_id", "phone"]].rename(columns={"phone": "identifier"}))
    if not rows:
        out = df.copy()
        out["identity_key"] = _pick_identity_key(out)
        return out

    long = pd.concat(rows, ignore_index=True)
    long["identifier"] = long["identifier"].astype("string")
    long = long.dropna(subset=["user_id", "identifier"]).drop_duplicates()

    out = df.copy()
    out["user_id"] = out.get("user_id", pd.Series([pd.NA] * len(out), index=out.index)).astype(
        "string"
    )
    # try map by email/phone into user_id
    mapped = out["user_id"].copy()
    for key in ("email", "phone"):
        if key in out.columns:
            ident = out[key].astype("string")
            j = ident.to_frame("identifier").merge(long, on="identifier", how="left")["user_id"]
            mapped = mapped.fillna(j.astype("string"))
    out["identity_key"] = mapped.fillna(_pick_identity_key(out))
    return out


def validate_inputs(engagement: pd.DataFrame, txns: pd.DataFrame) -> list[str]:
    issues: list[str] = []
    missing_e = sorted(REQUIRED_ENGAGEMENT_COLS - set(engagement.columns))
    missing_t = sorted(REQUIRED_TXN_COLS - set(txns.columns))
    if missing_e:
        issues.append(f"Engagement missing columns: {', '.join(missing_e)}")
    if missing_t:
        issues.append(f"Transactions missing columns: {', '.join(missing_t)}")
    return issues


def run_attribution(
    engagement: pd.DataFrame,
    txns: pd.DataFrame,
    identity_map: Optional[pd.DataFrame],
    cfg: AttributionConfig,
    campaign_filter: Optional[Iterable[str]] = None,
) -> dict[str, pd.DataFrame]:
    """
    Prototype attribution:
    - Uses identity_key stitching (user_id/email/phone)
    - Filters to Click events if require_click=True
    - Last-touch within lookback window per transaction
    - Direct vs Indirect based on product match; if product missing on engagement, uses LOB/category/brand match as indirect
    """
    e = engagement.copy()
    t = txns.copy()

    e = _coerce_dt(e, "event_ts")
    t = _coerce_dt(t, "txn_ts")

    e = _apply_identity_map(e, identity_map)
    t = _apply_identity_map(t, identity_map)

    if campaign_filter:
        e = e[e["campaign_id"].astype("string").isin(list(campaign_filter))]

    if cfg.require_click:
        e = e[e["engagement_type"].astype("string").str.lower().eq("click")]

    # drop invalid dates
    e = e.dropna(subset=["event_ts", "identity_key"])
    t = t.dropna(subset=["txn_ts", "identity_key", "order_id"])

    lookback = timedelta(days=int(cfg.lookback_days))

    # for efficiency, group engagements per identity
    e = e.sort_values(["identity_key", "event_ts"])
    t = t.sort_values(["identity_key", "txn_ts"])

    at_rows = []
    for ident, tgrp in t.groupby("identity_key", sort=False):
        egrp = e[e["identity_key"] == ident]
        if egrp.empty:
            # no eligible engagement, keep un-attributed transactions as exceptions
            for _, tr in tgrp.iterrows():
                at_rows.append(
                    {
                        "identity_key": ident,
                        "order_id": tr["order_id"],
                        "txn_ts": tr["txn_ts"],
                        "revenue": tr.get("revenue", np.nan),
                        "attributed": False,
                        "reason": "no_eligible_engagement",
                    }
                )
            continue

        e_times = egrp["event_ts"].to_numpy()
        for _, tr in tgrp.iterrows():
            txn_ts = tr["txn_ts"]
            # eligible engagements must be before txn and within lookback
            min_ts = txn_ts - lookback
            eligible = egrp[(egrp["event_ts"] <= txn_ts) & (egrp["event_ts"] >= min_ts)]
            if eligible.empty:
                at_rows.append(
                    {
                        "identity_key": ident,
                        "order_id": tr["order_id"],
                        "txn_ts": txn_ts,
                        "revenue": tr.get("revenue", np.nan),
                        "attributed": False,
                        "reason": "outside_window_or_after_txn",
                    }
                )
                continue

            # last-touch
            touch = eligible.iloc[-1]

            # direct vs indirect
            direct = False
            txn_product = str(tr.get("product", "") or "")
            tgt_product = str(touch.get("target_product", "") or "")
            if txn_product and tgt_product:
                direct = txn_product.strip().lower() == tgt_product.strip().lower()
            else:
                # fallback: if LOB/category/brand align, treat as indirect rather than unknown
                for dim in ("lob", "category", "brand"):
                    if dim in tr and dim in touch:
                        a = str(tr.get(dim, "") or "").strip().lower()
                        b = str(touch.get(dim, "") or "").strip().lower()
                        if a and b and a == b:
                            direct = False
                            break

            at_rows.append(
                {
                    "identity_key": ident,
                    "user_id": touch.get("user_id", pd.NA),
                    "email": touch.get("email", pd.NA),
                    "phone": touch.get("phone", pd.NA),
                    "campaign_id": touch.get("campaign_id", pd.NA),
                    "campaign_name": touch.get("campaign_name", pd.NA),
                    "campaign_type": touch.get("campaign_type", pd.NA),
                    "channel": touch.get("channel", pd.NA),
                    "engagement_type": touch.get("engagement_type", pd.NA),
                    "event_ts": touch.get("event_ts", pd.NaT),
                    "lookback_days": cfg.lookback_days,
                    "order_id": tr.get("order_id", pd.NA),
                    "txn_ts": txn_ts,
                    "revenue": tr.get("revenue", np.nan),
                    "product": tr.get("product", pd.NA),
                    "direct_indirect": "Direct" if direct else "Indirect",
                    "attributed": True,
                    "reason": "last_touch",
                }
            )

    customer_level = pd.DataFrame(at_rows)

    attributed_only = customer_level[customer_level["attributed"] == True].copy()
    attributed_only["revenue"] = pd.to_numeric(attributed_only["revenue"], errors="coerce").fillna(0.0)

    campaign_summary = (
        attributed_only.groupby(["campaign_id", "campaign_name", "campaign_type"], dropna=False)
        .agg(
            engaged_users=("identity_key", "nunique"),
            converted_orders=("order_id", "nunique"),
            attributed_revenue=("revenue", "sum"),
        )
        .reset_index()
    )
    if not campaign_summary.empty:
        campaign_summary["avg_revenue_per_order"] = (
            campaign_summary["attributed_revenue"] / campaign_summary["converted_orders"].replace(0, np.nan)
        )

    channel_summary = (
        attributed_only.groupby(["channel"], dropna=False)
        .agg(
            engaged_users=("identity_key", "nunique"),
            converted_orders=("order_id", "nunique"),
            attributed_revenue=("revenue", "sum"),
        )
        .reset_index()
    )
    if not channel_summary.empty:
        channel_summary["revenue_per_order"] = (
            channel_summary["attributed_revenue"] / channel_summary["converted_orders"].replace(0, np.nan)
        )

    exceptions = customer_level[customer_level["attributed"] == False].copy()

    return {
        "customer_level": customer_level.sort_values(["attributed", "txn_ts"], ascending=[False, True]),
        "campaign_summary": campaign_summary.sort_values(["attributed_revenue"], ascending=False),
        "channel_summary": channel_summary.sort_values(["attributed_revenue"], ascending=False),
        "exceptions": exceptions.sort_values(["txn_ts"]),
    }

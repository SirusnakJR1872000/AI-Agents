from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd


@dataclass(frozen=True)
class ConnectorConfig:
    """
    Prototype connector config.

    For realism, the SFTP/S3 connectors are simulated as local folders.
    """

    sfmc_sftp_dir: str = "connectors/sfmc_sftp"
    netcore_s3_dir: str = "connectors/netcore_s3"


def _latest_csv(folder: Path) -> Optional[Path]:
    if not folder.exists():
        return None
    csvs = sorted(folder.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    return csvs[0] if csvs else None


def load_from_sfmc_sftp(cfg: ConnectorConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Simulates: SFMC Automation Studio -> SFTP drop -> ingestion.

    Expected files (latest wins):
    - engagement_*.csv
    - transactions_*.csv
    """
    base = Path(cfg.sfmc_sftp_dir)
    eng = _latest_csv(base / "engagement")
    txn = _latest_csv(base / "transactions")
    engagement = pd.read_csv(eng) if eng else pd.DataFrame()
    txns = pd.read_csv(txn) if txn else pd.DataFrame()
    return engagement, txns


def load_from_netcore_s3(cfg: ConnectorConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Simulates: Netcore -> brand S3 bucket -> ingestion.
    """
    base = Path(cfg.netcore_s3_dir)
    eng = _latest_csv(base / "engagement")
    txn = _latest_csv(base / "transactions")
    engagement = pd.read_csv(eng) if eng else pd.DataFrame()
    txns = pd.read_csv(txn) if txn else pd.DataFrame()
    return engagement, txns


def load_external_context(uploads: list[bytes], names: list[str]) -> str:
    """
    External market/news/competitor context is treated as uploaded qualitative inputs.
    Prototype: concatenates text-ish uploads as notes.
    """
    chunks = []
    for b, n in zip(uploads, names):
        try:
            txt = b.decode("utf-8", errors="ignore")
        except Exception:
            txt = ""
        if txt.strip():
            chunks.append(f"### {n}\n{txt.strip()}")
    return "\n\n".join(chunks).strip()


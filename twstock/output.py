from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import HistoryBar, Quote


def _now_str() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _fetched_at() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def write_quotes(quotes: list[Quote], out_dir: str | Path, formats: list[str]) -> list[Path]:
    """將報價寫入 JSON / CSV 檔案，回傳實際寫出的檔案清單。"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = _now_str()
    written: list[Path] = []

    if "json" in formats:
        payload = {
            "fetched_at": _fetched_at(),
            "quotes": [q.to_dict() for q in quotes],
        }
        path = out_dir / f"quotes_{stamp}.json"
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        written.append(path)

    if "csv" in formats:
        path = out_dir / f"quotes_{stamp}.csv"
        rows = [q.to_flat_dict() for q in quotes]
        fieldnames = list(rows[0].keys()) if rows else []
        with path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        written.append(path)

    return written


def write_history(bars: list[HistoryBar], symbol: str, out_dir: str | Path) -> Path:
    """將歷史資料寫入 CSV，回傳檔案路徑。"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"history_{symbol}_{_now_str()}.csv"
    rows: list[dict[str, Any]] = [bar.to_dict() for bar in bars]
    fieldnames = ["datetime", "timestamp", "open", "high", "low", "close", "volume"]
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path

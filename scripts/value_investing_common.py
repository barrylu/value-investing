#!/usr/bin/env python3

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd


PERIOD_RE = re.compile(r"^(?P<year>\d{4})(?P<label>年报|三季报|半年报|一季报)$")
PERIOD_ORDER = {"一季报": 1, "半年报": 2, "三季报": 3, "年报": 4}


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def normalize_datayes_base_dir(path: str | Path) -> Path:
    resolved = Path(path).resolve()
    if resolved.name == "csv":
        return resolved.parents[1]
    if resolved.name == "整理":
        return resolved.parent
    return resolved


def company_slug_from_datayes_base(base_dir: str | Path) -> str:
    base = normalize_datayes_base_dir(base_dir)
    return base.parent.name


def company_name_from_slug(slug: str) -> str:
    if "-" in slug:
        return slug.rsplit("-", 1)[0]
    return slug


def ensure_directory(path: str | Path) -> Path:
    target = Path(path)
    target.mkdir(parents=True, exist_ok=True)
    return target


def csv_dir_for_base(base_dir: str | Path) -> Path:
    return normalize_datayes_base_dir(base_dir) / "整理" / "csv"


def data_output_dir_for_base(base_dir: str | Path) -> Path:
    return normalize_datayes_base_dir(base_dir) / "整理"


def load_statement(base_dir: str | Path, name: str) -> pd.DataFrame:
    path = csv_dir_for_base(base_dir) / f"{name}.csv"
    if not path.exists():
        raise FileNotFoundError(f"缺少 CSV 文件：{path}")
    return pd.read_csv(path)


def period_sort_key(label: str) -> tuple[int, int, str]:
    matched = PERIOD_RE.match(str(label))
    if not matched:
        return (9999, 999, str(label))
    year = int(matched.group("year"))
    phase = PERIOD_ORDER[matched.group("label")]
    return (year, phase, str(label))


def sort_periods(columns: Iterable[str], *, annual_only: bool = False) -> list[str]:
    periods: list[str] = []
    for column in columns:
        matched = PERIOD_RE.match(str(column))
        if not matched:
            continue
        if annual_only and matched.group("label") != "年报":
            continue
        periods.append(str(column))
    return sorted(periods, key=period_sort_key)


def filter_periods(periods: Sequence[str], *, min_year: int | None = None, max_year: int | None = None) -> list[str]:
    filtered: list[str] = []
    for period in periods:
        year = period_to_year(period)
        if min_year is not None and year is not None and year < min_year:
            continue
        if max_year is not None and year is not None and year > max_year:
            continue
        filtered.append(period)
    return filtered


def period_to_year(period: str) -> int | None:
    matched = PERIOD_RE.match(str(period))
    if not matched:
        return None
    return int(matched.group("year"))


def latest_period(periods: Sequence[str]) -> str:
    if not periods:
        raise ValueError("没有可用的期间列")
    return sorted(periods, key=period_sort_key)[-1]


def normalize_text(value: object) -> str:
    text = str(value or "")
    text = text.replace("：", ":")
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "", text).lower()


def _candidate_rows(
    frame: pd.DataFrame,
    *,
    code_candidates: Sequence[str] = (),
    exact_names: Sequence[str] = (),
    contains_names: Sequence[str] = (),
) -> pd.DataFrame:
    if frame.empty:
        return frame.head(0)

    if code_candidates and "字段代码" in frame.columns:
        matched = frame[frame["字段代码"].astype(str).isin([str(item) for item in code_candidates])]
        if not matched.empty:
            return matched

    name_columns = [column for column in ("字段名称", "展示名称") if column in frame.columns]
    if not name_columns:
        return frame.head(0)

    normalized_lookup = {
        column: frame[column].map(normalize_text) for column in name_columns
    }

    for name in exact_names:
        normalized = normalize_text(name)
        mask = pd.Series(False, index=frame.index)
        for column in name_columns:
            mask = mask | (normalized_lookup[column] == normalized)
        matched = frame[mask]
        if not matched.empty:
            return matched

    if contains_names:
        mask = pd.Series(True, index=frame.index)
        for token in contains_names:
            normalized_token = normalize_text(token)
            token_mask = pd.Series(False, index=frame.index)
            for column in name_columns:
                token_mask = token_mask | normalized_lookup[column].str.contains(normalized_token, na=False)
            mask = mask & token_mask
        matched = frame[mask]
        if not matched.empty:
            return matched

    return frame.head(0)


def first_row(
    frame: pd.DataFrame,
    *,
    code_candidates: Sequence[str] = (),
    exact_names: Sequence[str] = (),
    contains_names: Sequence[str] = (),
) -> pd.Series | None:
    matched = _candidate_rows(
        frame,
        code_candidates=code_candidates,
        exact_names=exact_names,
        contains_names=contains_names,
    )
    if matched.empty:
        return None
    return matched.iloc[0]


def numeric_series_from_row(row: pd.Series | None, periods: Sequence[str]) -> pd.Series:
    if row is None:
        return pd.Series(index=list(periods), dtype="float64")
    return pd.to_numeric(row.reindex(periods), errors="coerce")


def series_from_candidates(
    frame: pd.DataFrame,
    periods: Sequence[str],
    *,
    code_candidates: Sequence[str] = (),
    exact_names: Sequence[str] = (),
    contains_names: Sequence[str] = (),
) -> pd.Series:
    return numeric_series_from_row(
        first_row(
            frame,
            code_candidates=code_candidates,
            exact_names=exact_names,
            contains_names=contains_names,
        ),
        periods,
    )


def sum_series_from_candidates(
    frame: pd.DataFrame,
    periods: Sequence[str],
    *,
    code_candidates: Sequence[str] = (),
    exact_names: Sequence[str] = (),
    contains_names: Sequence[str] = (),
) -> pd.Series:
    matched = _candidate_rows(
        frame,
        code_candidates=code_candidates,
        exact_names=exact_names,
        contains_names=contains_names,
    )
    if matched.empty:
        return pd.Series(index=list(periods), dtype="float64")
    return matched.reindex(columns=list(periods)).apply(pd.to_numeric, errors="coerce").sum(axis=0, min_count=1)


def divide_series(numerator: pd.Series, denominator: pd.Series, *, scale: float = 1.0) -> pd.Series:
    denom = denominator.replace({0: pd.NA})
    result = numerator.astype(float).divide(denom.astype(float))
    if scale != 1.0:
        result = result * scale
    return result


def pct_change(series: pd.Series, *, scale: float = 100.0) -> pd.Series:
    result = series.astype(float).pct_change()
    if scale != 1.0:
        result = result * scale
    return result


def rolling_average(series: pd.Series) -> pd.Series:
    ordered = series.astype(float)
    prev = ordered.shift(1)
    return (ordered + prev) / 2.0


def infer_shares_outstanding(latest_row: pd.Series) -> float | None:
    candidates: list[float] = []

    equity = latest_row.get("归母权益")
    bps = latest_row.get("每股净资产")
    if pd.notna(equity) and pd.notna(bps) and float(bps) != 0:
        candidates.append(float(equity) / float(bps))

    net_profit = latest_row.get("归母净利润")
    eps = latest_row.get("每股收益")
    if pd.notna(net_profit) and pd.notna(eps) and float(eps) != 0:
        candidates.append(float(net_profit) / float(eps))

    filtered = [value for value in candidates if math.isfinite(value) and value > 0]
    if not filtered:
        return None
    return sum(filtered) / len(filtered)


def format_number(value: object, digits: int = 2) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)) or pd.isna(value):
        return "-"
    numeric = float(value)
    if abs(numeric) >= 1000:
        return f"{numeric:,.{digits}f}"
    return f"{numeric:.{digits}f}"


def dataframe_to_markdown(frame: pd.DataFrame, *, digits: int = 2) -> str:
    headers = list(frame.columns)
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for _, row in frame.iterrows():
        values: list[str] = []
        for column in headers:
            value = row[column]
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                values.append(format_number(value, digits=digits))
            else:
                values.append("-" if pd.isna(value) else str(value))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)

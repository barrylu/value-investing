#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_BASE_DIR = Path("/Users/luzuoguan/ai/value-investing/年报/长江电力-600900/萝卜投研-财务页下载")

UNIT_MAP = {
    0: "金额类",
    1: "比例类",
    2: "每股类",
    3: "分组/标题",
    4: "周转/次数类",
    None: "",
}


@dataclass(frozen=True)
class StandardFile:
    slug: str
    filename: str
    sheet_name: str


STANDARD_FILES = [
    StandardFile("financial_summary", "financial_summary_full_periods.json", "财务摘要"),
    StandardFile("balance_sheet", "balance_sheet_full_periods.json", "资产负债表"),
    StandardFile("income_statement", "income_statement_full_periods.json", "利润表"),
    StandardFile("cashflow", "cashflow_full_periods.json", "现金流量表"),
    StandardFile("key_indicators", "key_finance_indicators_full_periods.json", "关键指标"),
]

DISPLAY_UNIT_MAP = {
    "3": ("百万", 1_000_000.0),
    "4": ("亿元", 100_000_000.0),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="整理 Datayes 财务页原始 JSON")
    parser.add_argument("--base-dir", default=str(DEFAULT_BASE_DIR))
    parser.add_argument("--company-name", default="长江电力")
    parser.add_argument("--display-unit-code", default="")
    parser.add_argument("--display-unit-label", default="")
    parser.add_argument("--amount-divisor", type=float, default=0.0)
    return parser.parse_args()


def load_manifest(base_dir: Path) -> list[dict[str, Any]]:
    manifest_path = base_dir / "manifest.json"
    if not manifest_path.exists():
        return []
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def detect_display_unit(manifest: list[dict[str, Any]]) -> tuple[str, str, float]:
    for item in manifest:
        params = item.get("params") or {}
        unit_code = str(params.get("unit", "")).strip()
        if unit_code in DISPLAY_UNIT_MAP:
            label, divisor = DISPLAY_UNIT_MAP[unit_code]
            return unit_code, label, divisor
    return "", "原始数值", 1.0


def format_period_for_filename(interval: str) -> tuple[int, str]:
    interval = str(interval)
    year = int(interval[:4])
    if "三季报" in interval:
        suffix = "Q3"
    elif "半年报" in interval:
        suffix = "H1"
    elif "一季报" in interval:
        suffix = "Q1"
    else:
        suffix = ""
    return year, suffix


def derive_period_range(base_dir: Path) -> str:
    periods: list[str] = []
    for item in STANDARD_FILES:
        path = base_dir / "raw" / item.filename
        if not path.exists():
            continue
        payload = load_json(path)
        periods.extend(str(entry.get("interval", "")) for entry in payload.get("data", {}).get("titleBar", []))
    if not periods:
        return "unknown"
    parsed = sorted(format_period_for_filename(period) for period in periods)
    start_year, start_suffix = parsed[0]
    end_year, end_suffix = parsed[-1]
    start = f"{start_year}{start_suffix}"
    end = f"{end_year}{end_suffix}"
    return f"{start}至{end}"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_amount_value(value: Any, *, unit_code: Any, amount_divisor: float) -> Any:
    if amount_divisor <= 0 or pd.isna(unit_code) or int(unit_code) != 0:
        return value
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return value
    return round(numeric / amount_divisor, 6)


def make_standard_frame(
    payload: dict[str, Any],
    source_name: str,
    *,
    display_unit_label: str,
    amount_divisor: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = payload["data"]
    periods = [item["interval"] for item in data["titleBar"]]
    rows: list[dict[str, Any]] = []
    fields: list[dict[str, Any]] = []

    for order, item in enumerate(data["dataRow"], start=1):
        style = item.get("fdmtItemStyle") or {}
        row = {
            "序号": order,
            "字段代码": item.get("code"),
            "字段名称": style.get("name"),
            "展示名称": style.get("tableDisplayName"),
            "层级": style.get("level"),
            "单位代码": style.get("unit"),
            "单位说明": UNIT_MAP.get(style.get("unit"), f"未知({style.get('unit')})"),
            "展示口径": display_unit_label if style.get("unit") == 0 else UNIT_MAP.get(style.get("unit"), f"未知({style.get('unit')})"),
            "公式": style.get("formula"),
        }
        values = item.get("data") or []
        for idx, period in enumerate(periods):
            raw_value = values[idx] if idx < len(values) else None
            row[period] = normalize_amount_value(raw_value, unit_code=style.get("unit"), amount_divisor=amount_divisor)
        rows.append(row)

        fields.append(
            {
                "来源表": source_name,
                "字段代码": item.get("code"),
                "字段名称": style.get("name"),
                "展示名称": style.get("tableDisplayName"),
                "层级": style.get("level"),
                "单位代码": style.get("unit"),
                "单位说明": UNIT_MAP.get(style.get("unit"), f"未知({style.get('unit')})"),
                "展示口径": display_unit_label if style.get("unit") == 0 else UNIT_MAP.get(style.get("unit"), f"未知({style.get('unit')})"),
                "公式": style.get("formula"),
            }
        )

    return pd.DataFrame(rows), pd.DataFrame(fields)


def flatten_main_composition_node(
    *,
    parent_menu: str,
    dimension: str,
    node: dict[str, Any],
    periods: list[str],
    records: list[dict[str, Any]],
    amount_divisor: float,
    path_prefix: list[str] | None = None,
    depth: int = 1,
) -> None:
    path_prefix = path_prefix or []
    current_path = [*path_prefix, node.get("menu", "")]
    row = {
        "一级项目": parent_menu,
        "维度": dimension,
        "层级深度": depth,
        "当前节点": node.get("menu"),
        "路径": " / ".join(filter(None, current_path)),
        "apiKey": node.get("apiKey"),
        "isCompute": node.get("isCompute"),
        "fullName": node.get("fullName"),
    }
    values = node.get("data") or []
    for idx, period in enumerate(periods):
        raw_value = values[idx] if idx < len(values) else None
        row[period] = normalize_amount_value(raw_value, unit_code=0, amount_divisor=amount_divisor)
    records.append(row)

    for child in node.get("childMenus") or []:
        flatten_main_composition_node(
            parent_menu=parent_menu,
            dimension=dimension,
            node=child,
            periods=periods,
            records=records,
            amount_divisor=amount_divisor,
            path_prefix=current_path,
            depth=depth + 1,
        )


def make_main_composition_frame(
    payload: dict[str, Any],
    *,
    display_unit_label: str,
    amount_divisor: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = payload["data"]
    periods = [item["interval"] for item in data["titleBar"]]
    records: list[dict[str, Any]] = []
    fields: list[dict[str, Any]] = []

    for group in data["data"]:
        parent_menu = group.get("parentMenu")
        fields.append(
            {
                "来源表": "主营构成",
                "字段代码": group.get("apiKey"),
                "字段名称": parent_menu,
                "展示名称": parent_menu,
                "层级": 0,
                "单位代码": None,
                "单位说明": "",
                "展示口径": display_unit_label,
                "公式": None,
            }
        )
        group_row = {
            "一级项目": parent_menu,
            "维度": "汇总",
            "层级深度": 0,
            "当前节点": parent_menu,
            "路径": parent_menu,
            "apiKey": group.get("apiKey"),
            "isCompute": None,
            "fullName": None,
        }
        values = group.get("data") or []
        for idx, period in enumerate(periods):
            raw_value = values[idx] if idx < len(values) else None
            group_row[period] = normalize_amount_value(raw_value, unit_code=0, amount_divisor=amount_divisor)
        records.append(group_row)

        for node in group.get("childMenus") or []:
            flatten_main_composition_node(
                parent_menu=parent_menu,
                dimension=node.get("menu", ""),
                node=node,
                periods=periods,
                records=records,
                amount_divisor=amount_divisor,
            )

    return pd.DataFrame(records), pd.DataFrame(fields)


def build_field_doc(field_frames: list[pd.DataFrame], *, display_unit_label: str, amount_divisor: float) -> str:
    merged = pd.concat(field_frames, ignore_index=True).drop_duplicates()
    lines = [
        "# Datayes 字段对照说明",
        "",
        "说明：",
        "",
        "- 本文件基于 `萝卜投研-财务页下载/raw/` 下的原始 JSON 自动整理",
        "- 标准财务主表的列来自 `dataRow[].fdmtItemStyle`",
        "- `主营构成` 的层级字段来自 `parentMenu / childMenus` 结构",
        f"- 金额类字段已按展示口径换算为：`{display_unit_label}`（除数 `{amount_divisor:g}`）",
        "",
        "单位代码参考：",
        "",
        "- `0`: 金额类",
        "- `1`: 比例类",
        "- `2`: 每股类",
        "- `3`: 分组/标题",
        "- `4`: 周转/次数类",
        "",
    ]

    for source_name, group in merged.groupby("来源表", sort=False):
        lines.append(f"## {source_name}")
        lines.append("")
        lines.append(f"- 字段数：`{len(group)}`")
        lines.append("")
        lines.append("| 字段代码 | 字段名称 | 展示名称 | 层级 | 单位 | 展示口径 | 公式 |")
        lines.append("| --- | --- | --- | ---: | --- | --- | --- |")
        for _, row in group.iterrows():
            formula = row["公式"] if pd.notna(row["公式"]) and row["公式"] else ""
            lines.append(
                f"| {row['字段代码'] or ''} | {row['字段名称'] or ''} | {row['展示名称'] or ''} | "
                f"{'' if pd.isna(row['层级']) else int(row['层级'])} | {row['单位说明'] or ''} | {row.get('展示口径') or ''} | {formula} |"
            )
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    base_dir = Path(args.base_dir)
    raw_dir = base_dir / "raw"
    output_dir = base_dir / "整理"
    csv_dir = output_dir / "csv"
    manifest = load_manifest(base_dir)
    detected_code, detected_label, detected_divisor = detect_display_unit(manifest)
    display_unit_code = args.display_unit_code or detected_code
    display_unit_label = args.display_unit_label or detected_label
    amount_divisor = args.amount_divisor or detected_divisor

    output_dir.mkdir(parents=True, exist_ok=True)
    csv_dir.mkdir(parents=True, exist_ok=True)
    xlsx_path = output_dir / f"{args.company_name}-Datayes财务整理-{derive_period_range(base_dir)}.xlsx"
    field_doc_path = output_dir / "Datayes-字段对照说明.md"

    field_frames: list[pd.DataFrame] = []
    output_frames: list[tuple[str, pd.DataFrame]] = []

    for item in STANDARD_FILES:
        payload = load_json(raw_dir / item.filename)
        frame, fields = make_standard_frame(
            payload,
            item.sheet_name,
            display_unit_label=display_unit_label,
            amount_divisor=amount_divisor,
        )
        output_frames.append((item.sheet_name, frame))
        field_frames.append(fields)
        frame.to_csv(csv_dir / f"{item.sheet_name}.csv", index=False, encoding="utf-8-sig")

    mc_payload = load_json(raw_dir / "main_composition_full_periods.json")
    mc_frame, mc_fields = make_main_composition_frame(
        mc_payload,
        display_unit_label=display_unit_label,
        amount_divisor=amount_divisor,
    )
    output_frames.append(("主营构成", mc_frame))
    field_frames.append(mc_fields)
    mc_frame.to_csv(csv_dir / "主营构成.csv", index=False, encoding="utf-8-sig")

    all_fields = pd.concat(field_frames, ignore_index=True).drop_duplicates()
    output_frames.append(("字段说明", all_fields))
    all_fields.to_csv(csv_dir / "字段说明.csv", index=False, encoding="utf-8-sig")

    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        for sheet_name, frame in output_frames:
            frame.to_excel(writer, sheet_name=sheet_name[:31], index=False)

    field_doc_path.write_text(
        build_field_doc(field_frames, display_unit_label=display_unit_label, amount_divisor=amount_divisor),
        encoding="utf-8",
    )
    print(f"已生成整理结果: {output_dir}")
    print(f"展示单位编码: {display_unit_code or '未识别'}")
    print(f"展示单位文本: {display_unit_label}")
    print(f"金额换算除数: {amount_divisor:g}")


if __name__ == "__main__":
    main()

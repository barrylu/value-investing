#!/usr/bin/env python3

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


BASE_DIR = Path("/Users/luzuoguan/ai/value-investing/年报/长江电力-600900/萝卜投研-财务页下载")
RAW_DIR = BASE_DIR / "raw"
OUTPUT_DIR = BASE_DIR / "整理"
CSV_DIR = OUTPUT_DIR / "csv"
XLSX_PATH = OUTPUT_DIR / "长江电力-Datayes财务整理-2002至2025Q3.xlsx"
FIELD_DOC_PATH = OUTPUT_DIR / "Datayes-字段对照说明.md"

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


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def make_standard_frame(payload: dict[str, Any], source_name: str) -> tuple[pd.DataFrame, pd.DataFrame]:
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
            "公式": style.get("formula"),
        }
        values = item.get("data") or []
        for idx, period in enumerate(periods):
            row[period] = values[idx] if idx < len(values) else None
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
        row[period] = values[idx] if idx < len(values) else None
    records.append(row)

    for child in node.get("childMenus") or []:
        flatten_main_composition_node(
            parent_menu=parent_menu,
            dimension=dimension,
            node=child,
            periods=periods,
            records=records,
            path_prefix=current_path,
            depth=depth + 1,
        )


def make_main_composition_frame(payload: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
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
            group_row[period] = values[idx] if idx < len(values) else None
        records.append(group_row)

        for node in group.get("childMenus") or []:
            flatten_main_composition_node(
                parent_menu=parent_menu,
                dimension=node.get("menu", ""),
                node=node,
                periods=periods,
                records=records,
            )

    return pd.DataFrame(records), pd.DataFrame(fields)


def build_field_doc(field_frames: list[pd.DataFrame]) -> str:
    merged = pd.concat(field_frames, ignore_index=True).drop_duplicates()
    lines = [
        "# Datayes 字段对照说明",
        "",
        "说明：",
        "",
        "- 本文件基于 `萝卜投研-财务页下载/raw/` 下的原始 JSON 自动整理",
        "- 标准财务主表的列来自 `dataRow[].fdmtItemStyle`",
        "- `主营构成` 的层级字段来自 `parentMenu / childMenus` 结构",
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
        lines.append("| 字段代码 | 字段名称 | 展示名称 | 层级 | 单位 | 公式 |")
        lines.append("| --- | --- | --- | ---: | --- | --- |")
        for _, row in group.iterrows():
            formula = row["公式"] if pd.notna(row["公式"]) and row["公式"] else ""
            lines.append(
                f"| {row['字段代码'] or ''} | {row['字段名称'] or ''} | {row['展示名称'] or ''} | "
                f"{'' if pd.isna(row['层级']) else int(row['层级'])} | {row['单位说明'] or ''} | {formula} |"
            )
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CSV_DIR.mkdir(parents=True, exist_ok=True)

    field_frames: list[pd.DataFrame] = []
    output_frames: list[tuple[str, pd.DataFrame]] = []

    for item in STANDARD_FILES:
        payload = load_json(RAW_DIR / item.filename)
        frame, fields = make_standard_frame(payload, item.sheet_name)
        output_frames.append((item.sheet_name, frame))
        field_frames.append(fields)
        frame.to_csv(CSV_DIR / f"{item.sheet_name}.csv", index=False, encoding="utf-8-sig")

    mc_payload = load_json(RAW_DIR / "main_composition_full_periods.json")
    mc_frame, mc_fields = make_main_composition_frame(mc_payload)
    output_frames.append(("主营构成", mc_frame))
    field_frames.append(mc_fields)
    mc_frame.to_csv(CSV_DIR / "主营构成.csv", index=False, encoding="utf-8-sig")

    all_fields = pd.concat(field_frames, ignore_index=True).drop_duplicates()
    output_frames.append(("字段说明", all_fields))
    all_fields.to_csv(CSV_DIR / "字段说明.csv", index=False, encoding="utf-8-sig")

    with pd.ExcelWriter(XLSX_PATH, engine="openpyxl") as writer:
        for sheet_name, frame in output_frames:
            frame.to_excel(writer, sheet_name=sheet_name[:31], index=False)

    FIELD_DOC_PATH.write_text(build_field_doc(field_frames), encoding="utf-8")
    print(f"已生成整理结果: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()

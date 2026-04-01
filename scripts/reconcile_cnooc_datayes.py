#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path

import pandas as pd


BASE_DIR = Path("/Users/luzuoguan/ai/value-investing")
COMPANY_DIR = BASE_DIR / "年报" / "中国海油-600938"
SOURCE_WORKBOOK = COMPANY_DIR / "中国海油-2022至2024-财务报表与附注明细.xlsx"
OUTPUT_WORKBOOK = COMPANY_DIR / "中国海油-2022至2024-财务报表与附注明细-已对账.xlsx"
REPORT_MD = COMPANY_DIR / "Datayes对账结果.md"


def load_workbook_sheets() -> dict[str, pd.DataFrame]:
    excel = pd.ExcelFile(SOURCE_WORKBOOK)
    return {name: pd.read_excel(SOURCE_WORKBOOK, sheet_name=name) for name in excel.sheet_names}


def build_summary(validated_df: pd.DataFrame) -> pd.DataFrame:
    return (
        validated_df.groupby(["年份", "报表类别", "校验状态"])
        .size()
        .reset_index(name="条目数")
        .sort_values(["年份", "报表类别", "校验状态"])
        .reset_index(drop=True)
    )


def write_workbook(sheets: dict[str, pd.DataFrame], validated_df: pd.DataFrame, summary_df: pd.DataFrame) -> None:
    diff_df = validated_df[validated_df["校验状态"] != "PDF一致"].copy()
    with pd.ExcelWriter(OUTPUT_WORKBOOK, engine="openpyxl") as writer:
        for name, frame in sheets.items():
            frame.to_excel(writer, sheet_name=name[:31], index=False)
        summary_df.to_excel(writer, sheet_name="Datayes校验汇总", index=False)
        validated_df.to_excel(writer, sheet_name="Datayes主表对账明细", index=False)
        diff_df.to_excel(writer, sheet_name="Datayes重点差异", index=False)


def write_report(validated_df: pd.DataFrame, summary_df: pd.DataFrame) -> None:
    lines = ["# 中国海油 Datayes 对账结果", ""]
    lines.append(f"- 来源工作簿：`{SOURCE_WORKBOOK.name}`")
    lines.append(f"- 对账增强工作簿：`{OUTPUT_WORKBOOK.name}`")
    lines.append("- 对账范围：`2022-2024` 年报的合并利润表、合并资产负债表、合并现金流量表")
    lines.append("- 口径说明：Datayes 使用 `亿元`；PDF 主表原值为 `百万元`，已先换算后再比")
    lines.append("")
    lines.append("## 年度汇总")
    lines.append("")
    for year in sorted(summary_df["年份"].dropna().astype(int).unique()):
        yearly = summary_df[summary_df["年份"] == year]
        parts = [
            f"{row['报表类别']} {row['校验状态']} {int(row['条目数'])} 项"
            for _, row in yearly.iterrows()
        ]
        lines.append(f"- {year}：{'；'.join(parts)}")
    lines.append("")
    lines.append("## 重点差异")
    lines.append("")
    focus = validated_df[validated_df["校验状态"] != "PDF一致"].head(40)
    if focus.empty:
        lines.append("- 未发现需要额外说明的重点差异。")
    else:
        for _, row in focus.iterrows():
            lines.append(
                f"- {int(row['年份'])} {row['报表类别']} `{row['项目']}`：状态={row['校验状态']}；"
                f"PDF当前值(亿元)={row['PDF当前值_亿元']}；Datayes当前值(亿元)={row['当前值']}；来源页码={row['来源页码']}。"
            )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    sheets = load_workbook_sheets()
    validated_df = sheets.get("主表汇总", pd.DataFrame())
    if validated_df.empty:
        raise SystemExit("源工作簿缺少 `主表汇总`，无法生成对账结果。")
    summary_df = build_summary(validated_df)
    write_workbook(sheets, validated_df, summary_df)
    write_report(validated_df, summary_df)
    print(f"已生成：{OUTPUT_WORKBOOK}")
    print(f"已生成：{REPORT_MD}")


if __name__ == "__main__":
    main()

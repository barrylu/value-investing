#!/usr/bin/env python3

from __future__ import annotations

import math
import re
from pathlib import Path

import pandas as pd


BASE_DIR = Path("/Users/luzuoguan/ai/value-investing")
COMPANY_DIR = BASE_DIR / "年报" / "长江电力-600900"
SOURCE_WORKBOOK = COMPANY_DIR / "长江电力-2003至2024-财务报表与附注明细.xlsx"
OUTPUT_WORKBOOK = COMPANY_DIR / "长江电力-2003至2024-财务报表与附注明细-已对账.xlsx"
REPORT_MD = COMPANY_DIR / "Datayes对账结果.md"
DATAYES_CSV_DIR = COMPANY_DIR / "萝卜投研-财务页下载" / "整理" / "csv"

STATEMENT_CONFIG = {
    "利润表.csv": {"pdf_name": "合并利润表", "kind": "利润表"},
    "资产负债表.csv": {"pdf_name": "合并资产负债表", "kind": "资产负债表"},
    "现金流量表.csv": {"pdf_name": "合并现金流量表", "kind": "现金流量表"},
}

IGNORE_DISPLAY_NAMES = {
    "资产",
    "负债",
    "所有者权益(或股东权益)",
    "负债和所有者权益(或股东权益)",
    "经营活动产生的现金流量",
    "投资活动产生的现金流量",
    "筹资活动产生的现金流量",
    "汇率变动对现金及现金等价物的影响",
    "现金及现金等价物",
    "每股收益",
}

ALIAS_MAP = {
    "应收票据及应收账款": ["应收账款"],
    "应收票据及应收账款:应收票据": ["应收票据"],
    "应收票据及应收账款:应收账款": ["应收账款"],
    "应收票据及应收账款:应收款项融资": ["应收款项融资"],
    "其他应收款(合计)": ["其他应收款"],
    "其他应收款(合计):应收利息": ["应收利息"],
    "其他应收款(合计):应收股利": ["应收股利"],
    "其他应收款(合计):其他应收款": ["其他应收款"],
    "固定资产(合计)": ["固定资产"],
    "固定资产(合计):固定资产": ["固定资产"],
    "固定资产(合计):固定资产清理": ["固定资产清理"],
    "在建工程(合计)": ["在建工程"],
    "在建工程(合计):在建工程": ["在建工程"],
    "在建工程(合计):工程物资": ["工程物资"],
    "应付票据及应付账款": ["应付账款"],
    "应付票据及应付账款:应付票据": ["应付票据"],
    "应付票据及应付账款:应付账款": ["应付账款"],
    "其他应付款(合计)": ["其他应付款"],
    "其他应付款(合计):应付利息": ["应付利息"],
    "其他应付款(合计):应付股利": ["应付股利"],
    "其他应付款(合计):其他应付款": ["其他应付款"],
    "归属于母公司所有者权益合计": ["归属于母公司所有者权益", "归属于母公司股东权益"],
    "所有者权益合计": ["所有者权益合计", "所有者权益"],
    "负债和所有者权益总计": ["负债和所有者权益总计"],
    "归属于母公司所有者的净利润": ["归属于母公司所有者的净利润", "归属于母公司股东的净利润"],
    "归属于母公司所有者的综合收益总额": ["归属于母公司所有者的综合收益总额", "归属于母公司所有者的综"],
    "归属于少数股东的综合收益总额": ["归属于少数股东的综合收益总额", "归属于少数股东的综合收"],
    "少数股东损益": ["少数股东损益"],
    "持续经营净利润": ["持续经营净利润"],
    "终止经营净利润": ["终止经营净利润"],
    "每股收益-基本": ["基本每股收益", "每股收益(元/股)"],
    "每股收益-稀释": ["稀释每股收益"],
    "其中:对联营企业和合营企业的投资收益": ["对联营企业和合营企业的投资收益", "对联营企业和合营企"],
    "其中:利息费用": ["利息费用"],
    "其中:利息收入": ["利息收入"],
    "支付给职工以及为职工支付的现金": ["支付给职工以及为职工支付的现金", "支付给职工及为职工支付的现金"],
    "处置固定资产、无形资产和其他长期资产收回的现金净额": ["处置固定资产、无形资产和其他长期资产收回的现金净额", "处置固定资产、无形资产和其他长"],
    "购建固定资产、无形资产和其他长期资产支付的现金": ["购建固定资产、无形资产和其他长期资产支付的现金", "购建固定资产、无形资产和其他长"],
    "取得子公司及其他营业单位支付的现金净额": ["取得子公司及其他营业单位支付的现金净额", "取得子公司及其他营业单位支付的"],
    "分配股利、利润或偿付利息支付的现金": ["分配股利、利润或偿付利息支付的现金", "分配股利、利润或偿付利息支付的"],
    "其中:子公司吸收少数股东投资收到的现金": ["子公司吸收少数股东投资收到的现金"],
    "其中:子公司支付给少数股东的股利、利润": ["子公司支付给少数股东的股利、利润"],
}


def normalize_text(text: object) -> str:
    value = str(text or "")
    value = value.replace("：", ":").replace("（", "(").replace("）", ")")
    value = value.replace("“", "").replace("”", "").replace("—", "-").replace("－", "-")
    value = value.replace(" ", "")
    return re.sub(r"\s+", "", value)


def parse_number(value: object) -> float | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    text = str(value).strip()
    if not text or text in {"nan", "None", "-", "－"}:
        return None
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return None


def values_close(left: float | None, right: float | None) -> bool:
    if left is None or right is None:
        return False
    return abs(left - right) <= max(1.0, abs(right) * 1e-6)


def annual_columns(frame: pd.DataFrame) -> list[str]:
    return [col for col in frame.columns if re.fullmatch(r"20\d{2}年报", str(col))]


def datayes_aliases(display_name: str) -> list[str]:
    aliases = [display_name]
    aliases.extend(ALIAS_MAP.get(display_name, []))

    stripped = display_name.strip()
    stripped = stripped.replace("  ", " ")
    if stripped.startswith("其中:"):
        aliases.append(stripped.replace("其中:", "", 1))
    if stripped.startswith("减:"):
        aliases.append(stripped.replace("减:", "", 1))
    if stripped.startswith("加:"):
        aliases.append(stripped.replace("加:", "", 1))
    if "所有者" in stripped:
        aliases.append(stripped.replace("所有者", "股东"))
    if "股东" in stripped:
        aliases.append(stripped.replace("股东", "所有者"))
    if "以及为" in stripped:
        aliases.append(stripped.replace("以及为", "及为"))
    return sorted({normalize_text(alias) for alias in aliases if alias}, key=len, reverse=True)


def row_match_score(row: pd.Series, aliases: list[str], target_value: float | None, value_column: str) -> tuple[int, bool]:
    text_pool = "||".join(
        normalize_text(row.get(column, "")) for column in ("项目", "原始行", "标准项目") if column in row.index
    )
    value = parse_number(row.get(value_column))
    value_hit = values_close(value, target_value)

    if "被合并方实现的净利润为" in text_pool:
        return (0 if not value_hit else 10), value_hit

    best = 0
    for alias in aliases:
        if not alias:
            continue
        if text_pool == alias:
            best = max(best, 120)
        elif text_pool.endswith(alias):
            best = max(best, 110)
        elif alias in text_pool:
            best = max(best, 90 + min(len(alias), 20))
        elif text_pool and len(text_pool) >= 6 and text_pool in alias:
            best = max(best, 60)

    if best == 0 and value_hit:
        best = 80
    elif best > 0 and value_hit:
        best += 80
    return best, value_hit


def pick_match(frame: pd.DataFrame, display_name: str, target_value: float | None, value_column: str) -> pd.Series | None:
    aliases = datayes_aliases(display_name)
    ranked: list[tuple[int, int, pd.Series]] = []
    for idx, row in frame.iterrows():
        score, _ = row_match_score(row, aliases, target_value, value_column)
        if score <= 0:
            continue
        ranked.append((score, idx, row))
    if not ranked:
        return None
    ranked.sort(key=lambda item: (-item[0], len(normalize_text(item[2].get("项目", ""))), item[1]))
    return ranked[0][2]


def load_pdf_sheets() -> tuple[dict[str, pd.DataFrame], pd.ExcelFile]:
    excel = pd.ExcelFile(SOURCE_WORKBOOK)
    sheets = {name: pd.read_excel(SOURCE_WORKBOOK, sheet_name=name) for name in excel.sheet_names}
    return sheets, excel


def filter_consolidated(sheet: pd.DataFrame, report_name: str) -> pd.DataFrame:
    data = sheet.copy()
    if "报表名称" in data.columns:
        data = data[data["报表名称"] == report_name]
    return data.reset_index(drop=True)


def classify_status(
    current_match: pd.Series | None,
    next_match: pd.Series | None,
    datayes_value: float | None,
) -> tuple[str, float | None, str]:
    current_value = parse_number(current_match.get("值1")) if current_match is not None else None
    next_value = parse_number(next_match.get("值2")) if next_match is not None else None

    if values_close(current_value, datayes_value):
        return "与当年PDF一致", current_value, ""
    if values_close(next_value, datayes_value):
        return "与后续年报重述值一致", next_value, "Datayes 更接近后续年报比较口径，疑似年报重述。"
    if current_match is None and next_match is None:
        return "PDF未定位到，已用Datayes补充", datayes_value, "原始主表未稳定命中该行，使用 Datayes 补齐标准化项。"
    if current_match is None and next_match is not None:
        return "仅在后续年报比较数定位到", next_value or datayes_value, "当年主表未稳定命中，后续年报比较数可定位。"
    if current_match is not None and datayes_value is not None and current_value is not None:
        return "与Datayes存在差异，保留PDF原值", current_value, "PDF 与 Datayes 不一致，保留 PDF 原值并提示复核。"
    return "待复核", current_value or next_value or datayes_value, "未形成稳定匹配。"


def build_reconciliation(sheets: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    records: list[dict] = []

    for csv_name, config in STATEMENT_CONFIG.items():
        datayes_frame = pd.read_csv(DATAYES_CSV_DIR / csv_name)
        for period in annual_columns(datayes_frame):
            year = int(period[:4])
            if year < 2016 or year > 2024:
                continue
            current_sheet = filter_consolidated(sheets[f"{year}主表"], config["pdf_name"])
            next_sheet = None
            if year < 2024 and f"{year + 1}主表" in sheets:
                next_sheet = filter_consolidated(sheets[f"{year + 1}主表"], config["pdf_name"])

            for _, row in datayes_frame.iterrows():
                datayes_value = parse_number(row.get(period))
                if datayes_value is None:
                    continue

                display_name = str(row["展示名称"]).strip()
                if "特殊项目" in display_name or "差错金额" in display_name or display_name in IGNORE_DISPLAY_NAMES:
                    continue

                current_match = pick_match(current_sheet, display_name, datayes_value, "值1")
                next_match = pick_match(next_sheet, display_name, datayes_value, "值2") if next_sheet is not None else None
                status, chosen_value, note = classify_status(current_match, next_match, datayes_value)

                records.append(
                    {
                        "年份": year,
                        "报表类别": config["kind"],
                        "标准项目": display_name,
                        "Datayes字段代码": row["字段代码"],
                        "Datayes值": datayes_value,
                        "PDF当年值": parse_number(current_match.get("值1")) if current_match is not None else None,
                        "PDF后续年报比较值": parse_number(next_match.get("值2")) if next_match is not None else None,
                        "校验后值": chosen_value,
                        "校验状态": status,
                        "PDF匹配项目": current_match.get("项目") if current_match is not None else "",
                        "PDF匹配页码": current_match.get("页码") if current_match is not None else "",
                        "后续年报匹配项目": next_match.get("项目") if next_match is not None else "",
                        "后续年报匹配页码": next_match.get("页码") if next_match is not None else "",
                        "说明": note,
                    }
                )

    detailed = pd.DataFrame(records).sort_values(["年份", "报表类别", "标准项目"]).reset_index(drop=True)
    summary = (
        detailed.groupby(["年份", "校验状态"])
        .size()
        .reset_index(name="条目数")
        .sort_values(["年份", "条目数"], ascending=[True, False])
        .reset_index(drop=True)
    )
    return detailed, summary


def write_reconciled_workbook(sheets: dict[str, pd.DataFrame], detailed: pd.DataFrame, summary: pd.DataFrame) -> None:
    with pd.ExcelWriter(OUTPUT_WORKBOOK, engine="openpyxl") as writer:
        for name, frame in sheets.items():
            frame.to_excel(writer, sheet_name=name[:31], index=False)
        summary.to_excel(writer, sheet_name="Datayes校验汇总", index=False)
        detailed.to_excel(writer, sheet_name="主表标准化汇总", index=False)
        for year in sorted(detailed["年份"].unique()):
            yearly = detailed[detailed["年份"] == year]
            yearly.to_excel(writer, sheet_name=f"{year}主表标准化", index=False)


def write_report(detailed: pd.DataFrame, summary: pd.DataFrame) -> None:
    lines = ["# Datayes 对账结果", ""]
    lines.append(f"- 来源工作簿：`{SOURCE_WORKBOOK.name}`")
    lines.append(f"- 对账增强工作簿：`{OUTPUT_WORKBOOK.name}`")
    lines.append("- 对账范围：`2016-2024` 年报的合并利润表、合并资产负债表、合并现金流量表")
    lines.append("- 说明：Datayes 年度时序可能采用后续年报重述口径，因此报告将“与后续年报重述值一致”单列。")
    lines.append("")
    lines.append("## 年度汇总")
    lines.append("")
    for year in sorted(summary["年份"].unique()):
        sub = summary[summary["年份"] == year]
        parts = [f"{row['校验状态']} {int(row['条目数'])} 项" for _, row in sub.iterrows()]
        lines.append(f"- {year}：{'；'.join(parts)}")
    lines.append("")
    lines.append("## 重点说明")
    lines.append("")

    focus = detailed[detailed["校验状态"].isin(["PDF未定位到，已用Datayes补充", "与后续年报重述值一致", "与Datayes存在差异，保留PDF原值"])].head(40)
    if focus.empty:
        lines.append("- 未发现需要额外说明的重点差异。")
    else:
        for _, row in focus.iterrows():
            lines.append(
                f"- {int(row['年份'])} {row['报表类别']} `{row['标准项目']}`：{row['校验状态']}；PDF当年值={row['PDF当年值']}；后续比较值={row['PDF后续年报比较值']}；Datayes值={row['Datayes值']}。{row['说明']}"
            )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    sheets, _ = load_pdf_sheets()
    detailed, summary = build_reconciliation(sheets)
    write_reconciled_workbook(sheets, detailed, summary)
    write_report(detailed, summary)
    print(f"已生成：{OUTPUT_WORKBOOK}")
    print(f"已生成：{REPORT_MD}")


if __name__ == "__main__":
    main()

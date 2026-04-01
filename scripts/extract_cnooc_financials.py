#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


BASE_DIR = Path("/Users/luzuoguan/ai/value-investing")
COMPANY_DIR = BASE_DIR / "年报" / "中国海油-600938"
METADATA_PATH = COMPANY_DIR / "metadata.json"
MARKDOWN_DIR = COMPANY_DIR / "知识库" / "年报全文"
OUTPUT_XLSX = COMPANY_DIR / "中国海油-2022至2024-财务报表与附注明细.xlsx"
VERIFY_MD = COMPANY_DIR / "财务报表抽取核对说明.md"
VALIDATION_MD = COMPANY_DIR / "财务报表校验说明.md"
REFERENCE_CSV_DIR = COMPANY_DIR / "萝卜投研-财务页下载" / "整理" / "csv"

ANNUAL_TITLE_RE = re.compile(r"((?:19|20)\d{2})年年度报告")
PAGE_HEADER_RE = re.compile(r"^## 第 (\d+) 页$")
NUMERIC_VALUE_RE = re.compile(r"^[\(\-－–—]?\d[\d,]*(?:\.\d+)?\)?$")
NOTE_REF_RE = re.compile(r"^（[一二三四五六七八九十]+）\d+$")

STATEMENT_TITLES = {
    "合并资产负债表": "资产负债表",
    "合并利润表": "利润表",
    "合并现金流量表": "现金流量表",
}
STOP_TITLES = {
    "公司资产负债表",
    "公司利润表",
    "公司现金流量表",
    "合并股东权益变动表",
    "公司股东权益变动表",
}
IGNORE_LINES = {
    "人民币百万元",
    "项目",
    "附注",
    "首席执行官：周心怀",
    "首席财务官：穆秀平",
    "首席财务官：王欣",
    "首席财务官：谢尉志",
    "财务部总经理：王宇凡",
    "财务部总经理：王欣",
    "附注为财务报表的组成部分",
}
REFERENCE_SPECS = (
    ("利润表.csv", "利润表", "利润表"),
    ("资产负债表.csv", "资产负债表", "资产负债表"),
    ("现金流量表.csv", "现金流量表", "现金流量表"),
)
DATAYES_LONG_SPECS = (
    ("财务摘要.csv", "Datayes财务摘要"),
    ("关键指标.csv", "Datayes关键指标"),
)

ALIAS_MAP = {
    "应收票据及应收账款": ["应收账款", "应收票据及应收账款"],
    "应收票据及应收账款:应收票据": ["应收票据"],
    "应收票据及应收账款:应收账款": ["应收账款"],
    "应收票据及应收账款:应收款项融资": ["应收款项融资"],
    "其他应收款(合计)": ["其他应收款"],
    "其他应收款(合计):其他应收款": ["其他应收款"],
    "固定资产(合计)": ["固定资产"],
    "在建工程(合计)": ["在建工程"],
    "应付票据及应付账款": ["应付账款"],
    "应付票据及应付账款:应付账款": ["应付账款"],
    "归属于母公司所有者权益合计": ["归属于母公司股东权益", "归属于母公司所有者权益"],
    "股东权益合计": ["所有者权益合计", "股东权益合计"],
    "负债和股东权益总计": ["负债和股东权益总计", "负债和所有者权益总计"],
    "归属于母公司股东的净利润": ["归属于母公司所有者的净利润", "归属于母公司股东的净利润"],
    "营业总收入": ["营业收入", "营业总收入"],
    "营业总成本": ["营业总成本"],
    "资产总计": ["资产总计"],
    "销售商品、提供劳务收到的现金": ["销售商品、提供服务收到的现金"],
    "购买商品、接受劳务支付的现金": ["购买商品、接受服务支付的现金"],
    "处置固定资产、无形资产和其他长期资产收回的现金净额": ["处置固定资产、无形资产和其他长期资产收回的现金净额"],
    "购建固定资产、无形资产和其他长期资产支付的现金": ["购建固定资产、无形资产和其他长期资产支付的现金"],
    "加:期初现金及现金等价物余额": ["年初现金及现金等价物余额", "加:年初现金及现金等价物余额"],
    "期末现金及现金等价物余额": ["年末现金及现金等价物余额", "期末现金及现金等价物余额"],
    "现金及现金等价物净增加额": ["现金及现金等价物净增加额", "现金及现金等价物净减少额"],
}


@dataclass(frozen=True)
class ReportRecord:
    year: int
    title: str
    markdown_path: Path
    pdf_file: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="抽取中国海油年报主表并与 Datayes 对比")
    parser.add_argument("--years", nargs="*", type=int, help="仅处理指定年份")
    return parser.parse_args()


def normalize_label(text: str) -> str:
    value = str(text or "").strip()
    replacements = {
        "：": ":",
        "（": "",
        "）": "",
        "(": "",
        ")": "",
        "“": "",
        "”": "",
        " ": "",
        "\u3000": "",
        "\t": "",
        "\n": "",
        "\r": "",
        ",": "",
        "，": "",
        ".": "",
        "。": "",
        "-": "",
        "－": "",
    }
    for old, new in replacements.items():
        value = value.replace(old, new)
    return value


def looks_like_value(text: str) -> bool:
    stripped = str(text or "").strip()
    if stripped in {"-", "－", "—", "–", "–", "－", "–", "–"}:
        return True
    return bool(NUMERIC_VALUE_RE.fullmatch(stripped))


def parse_numeric_value(text: str) -> float | pd.NA:
    stripped = str(text or "").strip().replace("－", "-").replace("—", "-").replace("–", "-")
    if stripped in {"", "-", "None"}:
        return pd.NA
    negative = stripped.startswith("(") and stripped.endswith(")")
    stripped = stripped.strip("()")
    try:
        value = float(stripped.replace(",", ""))
    except ValueError:
        return pd.NA
    return -value if negative else value


def load_reports(selected_years: set[int] | None) -> list[ReportRecord]:
    records = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    reports: list[ReportRecord] = []
    for item in records:
        if item.get("kind") != "年报":
            continue
        title = str(item.get("title", "")).strip()
        matched = ANNUAL_TITLE_RE.search(title)
        if not matched:
            continue
        year = int(matched.group(1))
        if selected_years and year not in selected_years:
            continue
        matches = sorted(MARKDOWN_DIR.glob(f"{year}-*.md"))
        if not matches:
            raise FileNotFoundError(f"未找到 {year} 年年报全文 Markdown")
        reports.append(
            ReportRecord(
                year=year,
                title=title,
                markdown_path=matches[0],
                pdf_file=str(item.get("file", "")),
            )
        )
    return sorted(reports, key=lambda item: item.year)


def split_markdown_pages(markdown_path: Path) -> list[dict]:
    pages: list[dict] = []
    current_page = 0
    current_lines: list[str] = []
    for line in markdown_path.read_text(encoding="utf-8").splitlines():
        matched = PAGE_HEADER_RE.match(line.strip())
        if matched:
            if current_page:
                pages.append({"page_no": current_page, "lines": current_lines[:]})
            current_page = int(matched.group(1))
            current_lines = []
            continue
        if current_page:
            current_lines.append(line.rstrip())
    if current_page:
        pages.append({"page_no": current_page, "lines": current_lines[:]})
    return pages


def collect_statement_lines(pages: list[dict]) -> dict[str, list[tuple[int, str]]]:
    grouped: dict[str, list[tuple[int, str]]] = {title: [] for title in STATEMENT_TITLES}
    current_title: str | None = None
    for page in pages:
        for raw_line in page["lines"]:
            line = raw_line.strip()
            if not line:
                continue
            if line in STATEMENT_TITLES:
                current_title = line
                continue
            if line in STOP_TITLES:
                current_title = None
                continue
            if current_title:
                grouped[current_title].append((page["page_no"], line))
    return grouped


def should_skip_statement_line(text: str) -> bool:
    if not text:
        return True
    if text in IGNORE_LINES:
        return True
    if text.startswith("- 页码标记：") or text.startswith("- 文本字符数：") or text.startswith("- 行数：") or text.startswith("- 提取方式："):
        return True
    if re.fullmatch(r"- \d+ -", text):
        return True
    if re.fullmatch(r"\d{4}年\d{1,2}月\d{1,2}日", text):
        return True
    if re.fullmatch(r"第\d+页至第\d+页的财务报表由下列负责人签署：", text):
        return True
    return False


def parse_statement_rows(year: int, statement_title: str, rows_with_pages: list[tuple[int, str]]) -> list[dict]:
    parsed_rows: list[dict] = []
    cleaned = [(page_no, text) for page_no, text in rows_with_pages if not should_skip_statement_line(text)]
    current_group = ""
    label_parts: list[str] = []
    note_ref = ""
    value_parts: list[str] = []
    label_page_no = pd.NA

    def flush_row() -> None:
        nonlocal label_parts, note_ref, value_parts, label_page_no
        if not label_parts or len(value_parts) < 2:
            label_parts = []
            note_ref = ""
            value_parts = []
            label_page_no = pd.NA
            return
        label = "".join(label_parts)
        current_value_million = parse_numeric_value(value_parts[0])
        previous_value_million = parse_numeric_value(value_parts[1])
        parsed_rows.append(
            {
                "年份": year,
                "报表名称": statement_title,
                "报表类别": STATEMENT_TITLES[statement_title],
                "页码": label_page_no,
                "分组": current_group,
                "项目": label,
                "附注": note_ref,
                "当前值_百万元": current_value_million,
                "上年值_百万元": previous_value_million,
                "当前值_亿元": float(current_value_million) / 100 if not pd.isna(current_value_million) else pd.NA,
                "上年值_亿元": float(previous_value_million) / 100 if not pd.isna(previous_value_million) else pd.NA,
                "原始行": " | ".join(filter(None, [label, note_ref, value_parts[0], value_parts[1]])),
            }
        )
        label_parts = []
        note_ref = ""
        value_parts = []
        label_page_no = pd.NA

    for page_no, text in cleaned:
        if text.endswith("："):
            flush_row()
            current_group = text.rstrip("：")
            continue
        if NOTE_REF_RE.fullmatch(text):
            if label_parts and not value_parts:
                note_ref = text
            continue
        if looks_like_value(text):
            if not label_parts:
                continue
            value_parts.append(text)
            if len(value_parts) >= 2:
                flush_row()
            continue
        if value_parts:
            flush_row()
        if not label_parts:
            label_page_no = page_no
        label_parts.append(text)

    flush_row()
    return parsed_rows


def build_directory_sheet(verification: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(verification)[["年份", "年报标题", "Markdown文件", "PDF文件", "页数", "主表页命中", "主表行数", "状态"]]


def load_reference_main_rows(years: list[int]) -> pd.DataFrame:
    rows: list[dict] = []
    for csv_name, statement_kind, statement_label in REFERENCE_SPECS:
        csv_path = REFERENCE_CSV_DIR / csv_name
        if not csv_path.exists():
            continue
        df = pd.read_csv(csv_path)
        for _, item in df.iterrows():
            unit_code = pd.to_numeric(item.get("单位代码"), errors="coerce")
            if unit_code != 0:
                continue
            display_name = str(item.get("展示名称", "")).strip()
            if not display_name or display_name == "nan":
                continue
            for year in years:
                current_col = f"{year}年报"
                previous_col = f"{year - 1}年报"
                if current_col not in df.columns:
                    continue
                current_value = pd.to_numeric(item.get(current_col), errors="coerce")
                if pd.isna(current_value):
                    continue
                previous_value = pd.to_numeric(item.get(previous_col), errors="coerce") if previous_col in df.columns else pd.NA
                rows.append(
                    {
                        "年份": year,
                        "报表类别": statement_kind,
                        "字段代码": str(item.get("字段代码", "")),
                        "项目": display_name,
                        "项目_norm": normalize_label(display_name),
                        "当前参考值_亿元": float(current_value),
                        "上年参考值_亿元": float(previous_value) if not pd.isna(previous_value) else pd.NA,
                        "Datayes来源表": statement_label,
                    }
                )
    return pd.DataFrame(rows)


def datayes_aliases(display_name: str) -> list[str]:
    aliases = [display_name]
    aliases.extend(ALIAS_MAP.get(display_name, []))
    stripped = display_name.strip()
    if stripped.startswith("其中:"):
        aliases.append(stripped.replace("其中:", "", 1))
    if "所有者" in stripped:
        aliases.append(stripped.replace("所有者", "股东"))
    if "股东" in stripped:
        aliases.append(stripped.replace("股东", "所有者"))
    return sorted({normalize_label(alias) for alias in aliases if alias}, key=len, reverse=True)


def select_best_statement_candidate(candidates: pd.DataFrame, ref_row: pd.Series) -> pd.Series | None:
    if candidates.empty:
        return None
    aliases = datayes_aliases(str(ref_row["项目"]))
    enriched = candidates.copy()
    enriched["命中分"] = 0
    for alias in aliases:
        enriched.loc[enriched["项目_norm"] == alias, "命中分"] = enriched["命中分"].clip(lower=120)
        contains_mask = enriched["项目_norm"].map(lambda value: alias in value or value in alias)
        enriched.loc[contains_mask, "命中分"] = enriched["命中分"].clip(lower=90)
    enriched = enriched[enriched["命中分"] > 0]
    if enriched.empty:
        return None
    enriched["当前差值"] = (enriched["当前值_亿元"] - ref_row["当前参考值_亿元"]).abs().fillna(10**30)
    if pd.isna(ref_row["上年参考值_亿元"]):
        enriched["上年差值"] = 0.0
    else:
        enriched["上年差值"] = (enriched["上年值_亿元"] - ref_row["上年参考值_亿元"]).abs().fillna(10**30)
    enriched["名称长度差"] = (enriched["项目_norm"].str.len() - len(ref_row["项目_norm"])).abs()
    enriched = enriched.sort_values(
        by=["命中分", "当前差值", "上年差值", "名称长度差", "页码"],
        ascending=[False, True, True, True, True],
    )
    return enriched.iloc[0]


def build_validated_main_table(statement_rows: list[dict], years: list[int]) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw_df = pd.DataFrame(statement_rows).copy()
    if raw_df.empty:
        return pd.DataFrame(), pd.DataFrame()
    raw_df["项目_norm"] = raw_df["项目"].fillna("").map(normalize_label)
    reference_df = load_reference_main_rows(years)
    validated_rows: list[dict] = []

    for _, ref_row in reference_df.iterrows():
        candidates = raw_df[
            (raw_df["年份"] == ref_row["年份"]) &
            (raw_df["报表类别"] == ref_row["报表类别"])
        ]
        best = select_best_statement_candidate(candidates, ref_row)
        status = "参考补齐"
        page_no = pd.NA
        raw_line = ""
        pdf_item = ""
        pdf_current_yi = pd.NA
        pdf_previous_yi = pd.NA
        pdf_current_million = pd.NA
        pdf_previous_million = pd.NA

        if best is not None:
            page_no = best["页码"]
            raw_line = best["原始行"]
            pdf_item = best["项目"]
            pdf_current_yi = best["当前值_亿元"]
            pdf_previous_yi = best["上年值_亿元"]
            pdf_current_million = best["当前值_百万元"]
            pdf_previous_million = best["上年值_百万元"]
            current_match = pd.notna(pdf_current_yi) and abs(pdf_current_yi - ref_row["当前参考值_亿元"]) < 0.02
            previous_match = pd.isna(ref_row["上年参考值_亿元"]) or (
                pd.notna(pdf_previous_yi) and abs(pdf_previous_yi - ref_row["上年参考值_亿元"]) < 0.02
            )
            status = "PDF一致" if current_match and previous_match else "参考纠正"

        validated_rows.append(
            {
                "年份": ref_row["年份"],
                "报表类别": ref_row["报表类别"],
                "字段代码": ref_row["字段代码"],
                "项目": ref_row["项目"],
                "当前值": ref_row["当前参考值_亿元"],
                "上年值": ref_row["上年参考值_亿元"],
                "校验状态": status,
                "PDF项目": pdf_item,
                "PDF当前值_亿元": pdf_current_yi,
                "PDF上年值_亿元": pdf_previous_yi,
                "PDF当前值_百万元": pdf_current_million,
                "PDF上年值_百万元": pdf_previous_million,
                "来源页码": page_no,
                "来源原始行": raw_line,
            }
        )

    validated_df = pd.DataFrame(validated_rows)
    diff_df = validated_df[validated_df["校验状态"] != "PDF一致"].copy()
    return validated_df, diff_df


def build_datayes_long_sheet(csv_name: str, sheet_name: str, years: list[int]) -> pd.DataFrame:
    csv_path = REFERENCE_CSV_DIR / csv_name
    if not csv_path.exists():
        return pd.DataFrame()
    df = pd.read_csv(csv_path)
    rows: list[dict] = []
    for _, item in df.iterrows():
        for year in years:
            current_col = f"{year}年报"
            previous_col = f"{year - 1}年报"
            if current_col not in df.columns:
                continue
            current_value = pd.to_numeric(item.get(current_col), errors="coerce")
            if pd.isna(current_value):
                continue
            previous_value = pd.to_numeric(item.get(previous_col), errors="coerce") if previous_col in df.columns else pd.NA
            rows.append(
                {
                    "年份": year,
                    "来源Sheet": sheet_name,
                    "字段代码": str(item.get("字段代码", "")),
                    "字段名称": str(item.get("字段名称", "")),
                    "展示名称": str(item.get("展示名称", "")),
                    "层级": item.get("层级", pd.NA),
                    "单位说明": str(item.get("单位说明", "")),
                    "展示口径": str(item.get("展示口径", "")),
                    "当前值": float(current_value),
                    "上年值": float(previous_value) if not pd.isna(previous_value) else pd.NA,
                }
            )
    return pd.DataFrame(rows)


def build_main_composition_sheet(years: list[int]) -> pd.DataFrame:
    csv_path = REFERENCE_CSV_DIR / "主营构成.csv"
    if not csv_path.exists():
        return pd.DataFrame()
    df = pd.read_csv(csv_path)
    rows: list[dict] = []
    for _, item in df.iterrows():
        for year in years:
            current_col = f"{year}年报"
            previous_col = f"{year - 1}年报"
            if current_col not in df.columns:
                continue
            current_value = pd.to_numeric(item.get(current_col), errors="coerce")
            if pd.isna(current_value):
                continue
            previous_value = pd.to_numeric(item.get(previous_col), errors="coerce") if previous_col in df.columns else pd.NA
            rows.append(
                {
                    "年份": year,
                    "一级项目": str(item.get("一级项目", "")),
                    "维度": str(item.get("维度", "")),
                    "路径": str(item.get("路径", "")),
                    "当前节点": str(item.get("当前节点", "")),
                    "展示口径": str(item.get("展示口径", "")),
                    "当前值": float(current_value),
                    "上年值": float(previous_value) if not pd.isna(previous_value) else pd.NA,
                }
            )
    return pd.DataFrame(rows)


def write_outputs(verification: list[dict], statement_rows: list[dict]) -> pd.DataFrame:
    statement_df = pd.DataFrame(statement_rows)
    directory_df = build_directory_sheet(verification)
    years = sorted(directory_df["年份"].astype(int).tolist())
    validated_main_df, diff_main_df = build_validated_main_table(statement_rows, years)
    datayes_sheets = {
        sheet_name: build_datayes_long_sheet(csv_name, sheet_name, years)
        for csv_name, sheet_name in DATAYES_LONG_SPECS
    }
    datayes_sheets["Datayes主营构成"] = build_main_composition_sheet(years)

    with pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl") as writer:
        directory_df.to_excel(writer, sheet_name="目录", index=False)
        validated_main_df.to_excel(writer, sheet_name="主表汇总", index=False)
        diff_main_df.to_excel(writer, sheet_name="主表差异明细", index=False)
        statement_df.to_excel(writer, sheet_name="主表原始汇总", index=False)
        for sheet_name, datayes_df in datayes_sheets.items():
            datayes_df.to_excel(writer, sheet_name=sheet_name[:31], index=False)
        for year in years:
            yearly_statement = validated_main_df[validated_main_df["年份"] == year]
            yearly_statement.to_excel(writer, sheet_name=f"{year}主表", index=False)
    return validated_main_df


def write_verification_markdown(verification: list[dict]) -> None:
    lines = ["# 中国海油财务报表抽取核对说明", ""]
    lines.append(f"- 输出工作簿：`{OUTPUT_XLSX.name}`")
    lines.append("- 主表抽取来源：`知识库/年报全文/*.md` 中的合并资产负债表、合并利润表、合并现金流量表")
    lines.append("- PDF 主表单位：`百万元`；后续与 Datayes 对比时已换算为 `亿元`")
    lines.append("")
    lines.append("## 年度结果")
    lines.append("")
    for item in verification:
        lines.append(
            f"- {item['年份']}：页数 {item['页数']}，主表页 {item['主表页命中']}，主表行 {item['主表行数']}，状态：{item['状态']}"
        )
    VERIFY_MD.write_text("\n".join(lines), encoding="utf-8")


def write_validation_markdown(validated_main_df: pd.DataFrame) -> None:
    lines = ["# 中国海油主表校验说明", ""]
    lines.append("- 对比来源：`萝卜投研-财务页下载/整理/csv` 下按 `亿元` 口径整理后的标准化年报主表数据")
    lines.append("- 校验方式：PDF 主表原值 `百万元` 先换算为 `亿元`，再与 Datayes 年报列对比")
    lines.append("")
    lines.append("## 校验统计")
    lines.append("")
    if validated_main_df.empty:
        lines.append("- 无可用校验结果。")
    else:
        summary = (
            validated_main_df.groupby(["报表类别", "校验状态"])
            .size()
            .reset_index(name="条数")
            .sort_values(["报表类别", "校验状态"])
        )
        for _, row in summary.iterrows():
            lines.append(f"- {row['报表类别']} | {row['校验状态']} | {int(row['条数'])} 条")
    VALIDATION_MD.write_text("\n".join(lines), encoding="utf-8")


def process_report(report: ReportRecord) -> tuple[list[dict], dict]:
    pages = split_markdown_pages(report.markdown_path)
    grouped = collect_statement_lines(pages)
    statement_rows: list[dict] = []
    page_hits: list[str] = []
    for title, statement_kind in STATEMENT_TITLES.items():
        rows = parse_statement_rows(report.year, title, grouped.get(title, []))
        statement_rows.extend(rows)
        if rows:
            pages_hit = sorted({row["页码"] for row in rows})
            page_hits.append(f"{statement_kind}:{','.join(str(page) for page in pages_hit)}")
    verification = {
        "年份": report.year,
        "年报标题": report.title,
        "Markdown文件": report.markdown_path.name,
        "PDF文件": report.pdf_file,
        "页数": len(pages),
        "主表页命中": " | ".join(page_hits),
        "主表行数": len(statement_rows),
        "状态": "成功" if statement_rows else "需复核",
    }
    return statement_rows, verification


def main() -> None:
    args = parse_args()
    selected_years = set(args.years) if args.years else {2022, 2023, 2024}
    reports = load_reports(selected_years)
    if not reports:
        raise SystemExit("未找到可处理的中国海油年报记录。")

    all_statement_rows: list[dict] = []
    verification_rows: list[dict] = []
    for report in reports:
        statement_rows, verification = process_report(report)
        all_statement_rows.extend(statement_rows)
        verification_rows.append(verification)
        print(f"[{report.year}] 主表 {len(statement_rows)} 行")

    validated_main_df = write_outputs(verification_rows, all_statement_rows)
    write_verification_markdown(verification_rows)
    write_validation_markdown(validated_main_df)
    print(f"已生成：{OUTPUT_XLSX}")
    print(f"已生成：{VERIFY_MD}")
    print(f"已生成：{VALIDATION_MD}")


if __name__ == "__main__":
    main()

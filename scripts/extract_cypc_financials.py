#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from pypdf import PdfReader


BASE_DIR = Path("/Users/luzuoguan/ai/value-investing")
COMPANY_DIR = BASE_DIR / "年报" / "长江电力-600900"
METADATA_PATH = COMPANY_DIR / "metadata.json"
OUTPUT_XLSX = COMPANY_DIR / "长江电力-2003至2024-财务报表与附注明细.xlsx"
VERIFY_MD = COMPANY_DIR / "财务报表抽取核对说明.md"
REFERENCE_CSV_DIR = COMPANY_DIR / "萝卜投研-财务页下载" / "整理" / "csv"
VALIDATION_MD = COMPANY_DIR / "财务报表校验说明.md"

ANNUAL_TITLE_RE = re.compile(r"((?:19|20)\d{2})年年度报告")
ANNUAL_COLUMN_RE = re.compile(r"^(\d{4})年报$")
NOTE_HEADER_RE = re.compile(r"^(?:注释\s*)?(\d+)\s*[、\.\．]\s*(.+?)\s*$")
SUBSECTION_RE = re.compile(r"^(?:\(\d+\)|（\d+）|[一二三四五六七八九十]+、|\d+\.)")
NUMERIC_TOKEN_RE = re.compile(r"-?\d{1,3}(?:,\d{3})+\.\d{2,4}|-?\d+\.\d{2,4}|—|--|－")

STATEMENT_TITLE_ALIASES = {
    "合并资产负债表": "合并资产负债表",
    "资产负债表": "资产负债表",
    "母公司资产负债表": "母公司资产负债表",
    "合并利润表": "合并利润表",
    "利润表": "利润表",
    "母公司利润表": "母公司利润表",
    "合并利润及利润分配表": "合并利润表",
    "利润及利润分配表": "利润表",
    "母公司利润及利润分配表": "母公司利润表",
    "合并现金流量表": "合并现金流量表",
    "现金流量表": "现金流量表",
    "母公司现金流量表": "母公司现金流量表",
}
STATEMENT_STOP_TITLES = {
    "合并所有者权益变动表",
    "母公司所有者权益变动表",
    "合并股东权益变动表",
    "母公司股东权益变动表",
    "所有者权益变动表",
    "股东权益变动表",
}
NOTE_SECTION_MARKERS = (
    "合并财务报表项目注释",
    "财务报表项目注释",
    "会计报表主要项目注释",
    "财务报表附注",
    "会计报表附注",
    "报表附注",
)
PAGE_ARTIFACT_PATTERNS = (
    re.compile(r"^\d+\s*/\s*\d+$"),
    re.compile(r"^第\d+页$"),
    re.compile(r"^\d+\s*年年报\s*第\d+页$"),
)
REFERENCE_SPECS = (
    ("利润表.csv", "利润表", ("合并利润表", "利润表")),
    ("资产负债表.csv", "资产负债表", ("合并资产负债表", "资产负债表")),
    ("现金流量表.csv", "现金流量表", ("合并现金流量表", "现金流量表")),
)
DATAYES_LONG_SPECS = (
    ("财务摘要.csv", "Datayes财务摘要"),
    ("关键指标.csv", "Datayes关键指标"),
)
FOCUS_NOTE_CATEGORY_RULES = {
    "应收类": (
        "应收账款",
        "其他应收款",
        "应收票据",
        "应收票据及应收账款",
        "应收利息",
        "应收股利",
        "长期应收款",
        "应收补贴款",
    ),
    "资产类": (
        "固定资产",
        "在建工程",
        "工程物资",
        "无形资产",
        "长期待摊费用",
        "使用权资产",
        "商誉",
    ),
    "借款类": (
        "短期借款",
        "长期借款",
        "一年内到期的长期借款",
        "长期应付款",
    ),
    "税项类": (
        "应交税费",
        "应交税金",
        "企业所得税",
        "个人所得税",
        "所得税",
        "递延所得税",
        "税金及附加",
        "营业税金及附加",
        "流转税及附加税费",
        "增值税",
        "房产税",
        "土地使用税",
        "教育费附加",
    ),
}


@dataclass
class ReportRecord:
    year: int
    title: str
    pdf_path: Path


@dataclass
class PageBundle:
    page_no: int
    lines: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="抽取长江电力年报中的财务报表与附注明细")
    parser.add_argument(
        "--years",
        nargs="*",
        type=int,
        help="仅处理指定年份，例如 --years 2024 2014",
    )
    return parser.parse_args()


def load_reports(selected_years: set[int] | None) -> list[ReportRecord]:
    records = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    reports: list[ReportRecord] = []
    for item in records:
        if item.get("kind") != "年报":
            continue
        title = item.get("title", "")
        matched = ANNUAL_TITLE_RE.search(title)
        if not matched:
            continue
        year = int(matched.group(1))
        if selected_years and year not in selected_years:
            continue
        pdf_path = COMPANY_DIR / item["file"]
        if not pdf_path.exists():
            raise FileNotFoundError(f"缺少年报 PDF：{pdf_path}")
        reports.append(ReportRecord(year=year, title=title, pdf_path=pdf_path))
    return sorted(reports, key=lambda item: item.year)


def normalize_line(text: str) -> str:
    text = text.replace("\u3000", " ")
    text = text.replace("\t", " ")
    return text.rstrip()


def normalized_key(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def is_page_artifact(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    if stripped.startswith("中国长江电力股份有限公司"):
        return True
    if stripped.startswith("编制单位"):
        return True
    if stripped.startswith("公司负责人："):
        return True
    for pattern in PAGE_ARTIFACT_PATTERNS:
        if pattern.match(stripped):
            return True
    return False


def split_columns(line: str) -> list[str]:
    return [part.strip() for part in re.split(r"\s{2,}", line.strip()) if part.strip()]


def extract_numeric_tokens(text: str) -> list[str]:
    return NUMERIC_TOKEN_RE.findall(text)


def numeric_token_to_float(token: str) -> float | pd.NA:
    compact = str(token).strip()
    if compact in {"", "—", "--", "－"}:
        return pd.NA
    try:
        return float(compact.replace(",", ""))
    except ValueError:
        return pd.NA


def looks_like_note_ref(value: str) -> bool:
    compact = value.strip()
    return bool(compact) and bool(re.fullmatch(r"[一二三四五六七八九十0-9]+", compact))


def clean_fragment(text: str) -> str:
    return re.sub(r"\s+", "", text).strip()


def normalize_label(text: str) -> str:
    text = clean_fragment(str(text or ""))
    replacements = {
        ":": "：",
        "(": "",
        ")": "",
        "（": "",
        "）": "",
        "-": "",
        "－": "",
        "“": "",
        "”": "",
        "、": "",
        ",": "",
        "，": "",
        ".": "",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def is_report_page_line(line: str) -> bool:
    compact = clean_fragment(line)
    return bool(re.search(r"\d{4}年年度报告第\d+页", compact))


def is_value_cell(value: str) -> bool:
    compact = str(value or "").strip()
    if not compact:
        return False
    return bool(re.fullmatch(r"[-—－0-9,\.%]+", compact))


def is_age_or_period_text(value: str) -> bool:
    compact = clean_fragment(value)
    return bool(compact) and any(marker in compact for marker in ("年以内", "年以上", "月以内", "账龄", "年末", "年初", "期末", "期初"))


def read_pages(pdf_path: Path) -> list[PageBundle]:
    reader = PdfReader(str(pdf_path))
    bundles: list[PageBundle] = []
    for idx, page in enumerate(reader.pages, start=1):
        text = page.extract_text(extraction_mode="layout") or ""
        lines = [normalize_line(line) for line in text.splitlines()]
        bundles.append(PageBundle(page_no=idx, lines=lines))
    return bundles


def line_is_statement_title(line: str) -> str | None:
    key = normalized_key(line)
    for title, canonical in STATEMENT_TITLE_ALIASES.items():
        if key == normalized_key(title):
            return canonical
    return None


def detect_financial_statement_start(pages: list[PageBundle]) -> int:
    for bundle in pages:
        page_text = "".join(bundle.lines)
        has_statement = any(line_is_statement_title(line) for line in bundle.lines[:40])
        if has_statement and "编制单位" in page_text and "单位" in page_text:
            return bundle.page_no
    return 1


def collect_statement_lines(
    pages: list[PageBundle],
    financial_start_page: int,
    notes_start_page: int,
) -> dict[str, list[tuple[int, str]]]:
    grouped: dict[str, list[tuple[int, str]]] = {}
    current_title: str | None = None

    for bundle in pages:
        if bundle.page_no < financial_start_page or bundle.page_no >= notes_start_page:
            continue

        for raw_line in bundle.lines:
            stripped = raw_line.strip()
            if normalized_key(stripped) in {normalized_key(title) for title in STATEMENT_STOP_TITLES}:
                current_title = None
                continue

            matched = line_is_statement_title(stripped)
            if matched:
                current_title = matched
                grouped.setdefault(current_title, [])
                continue

            if current_title:
                grouped.setdefault(current_title, []).append((bundle.page_no, raw_line))
    return grouped


def statement_group_name(statement_title: str) -> str:
    if "资产负债表" in statement_title:
        return "资产负债表"
    if "现金流量表" in statement_title:
        return "现金流量表"
    return "利润表"


def is_statement_header_row(columns: list[str]) -> bool:
    if not columns:
        return False
    joined = "".join(columns)
    return "项目" in joined and any(
        marker in joined for marker in ("期末余额", "期初余额", "本期发生额", "上期发生额", "年度", "12月31日")
    )


def parse_statement_pages(year: int, statement_title: str, lines_with_pages: list[tuple[int, str]]) -> list[dict]:
    rows: list[dict] = []
    pending_fragments: list[str] = []
    current_section = ""

    for page_no, raw_line in lines_with_pages:
        line = raw_line.strip()
        if is_page_artifact(raw_line):
            continue
        if any(marker in line for marker in ("单位：", "单位:", "币种：", "币种:")):
            continue
        if line.startswith("编制单位") or "主管会计工作负责人" in line:
            continue
        if re.fullmatch(r"(?:\d{4}年)?\s*\d+\s*[—-]\s*\d+\s*月", clean_fragment(line)):
            continue

        columns = split_columns(raw_line)
        if not columns:
            continue
        if is_statement_header_row(columns):
            continue

        item_text = clean_fragment(columns[0])
        if not item_text:
            continue

        if item_text.endswith("：") and len(columns) == 1:
            current_section = item_text.rstrip("：")
            rows.append(
                {
                    "年份": year,
                    "报表名称": statement_title,
                    "报表类别": statement_group_name(statement_title),
                    "页码": page_no,
                    "分组": current_section,
                    "项目": current_section,
                    "附注": "",
                    "值1": "",
                    "值2": "",
                    "值3": "",
                    "值4": "",
                    "原始行": item_text,
                }
            )
            pending_fragments.clear()
            continue

        numeric_tokens = extract_numeric_tokens(raw_line)
        if len(columns) == 1 and not numeric_tokens:
            pending_fragments.append(item_text)
            continue

        if pending_fragments:
            item_text = clean_fragment("".join(pending_fragments) + item_text)
            pending_fragments.clear()

        note_ref = ""
        value_parts = columns[1:]
        if len(columns) >= 3 and looks_like_note_ref(columns[1]):
            note_ref = columns[1]
            value_parts = columns[2:]

        values: list[str] = []
        if value_parts:
            for part in value_parts:
                part_tokens = extract_numeric_tokens(part)
                if part_tokens and part not in part_tokens:
                    values.extend(part_tokens)
                else:
                    values.append(part.strip())
        else:
            values = numeric_tokens[:]

        if not values:
            pending_fragments.append(item_text)
            continue

        rows.append(
            {
                "年份": year,
                "报表名称": statement_title,
                "报表类别": statement_group_name(statement_title),
                "页码": page_no,
                "分组": current_section,
                "项目": item_text,
                "附注": note_ref,
                "值1": values[0] if len(values) > 0 else "",
                "值2": values[1] if len(values) > 1 else "",
                "值3": values[2] if len(values) > 2 else "",
                "值4": values[3] if len(values) > 3 else "",
                "原始行": line,
            }
        )
    return rows


def find_notes_start_page(
    pages: list[PageBundle],
    financial_start_page: int,
    fallback_page: int,
) -> int:
    for bundle in pages:
        if bundle.page_no <= financial_start_page:
            continue
        page_text = "".join(bundle.lines)
        if any(marker in page_text for marker in NOTE_SECTION_MARKERS):
            return bundle.page_no
    return fallback_page


def infer_note_line_type(columns: list[str]) -> str:
    if not columns:
        return "other"
    joined = "".join(columns)
    if any(marker in joined for marker in ("单位：", "币种：")):
        return "context"
    if "项目" in joined and any(marker in joined for marker in ("余额", "账面", "金额", "比例", "账龄", "本期", "上期", "期末", "期初")):
        return "table_header"
    if len(columns) >= 2:
        return "data_row"
    return "context"


def is_note_header(line: str) -> tuple[str, str] | None:
    matched = NOTE_HEADER_RE.match(line.strip())
    if not matched:
        return None
    title = matched.group(2).strip()
    if len(title) > 50:
        return None
    if any(stop in title for stop in ("财务报表项目注释", "会计报表主要项目注释")):
        return None
    return matched.group(1), title


def is_checkbox_line(columns: list[str], line: str) -> bool:
    joined = "".join(columns) if columns else line
    compact = joined.replace(" ", "")
    return compact in {"√适用□不适用", "□适用√不适用", "□适用□不适用", "√适用√不适用"}


def looks_like_prose_with_numbers(columns: list[str], line: str, line_type: str) -> bool:
    if len(line) < 30:
        return False
    if not any(punct in line for punct in "，。；："):
        return False
    if "如下" in line or "明细" in line or "截止" in line:
        return True
    if len(columns) <= 3 and ("公司" in line or "报告" in line or "批准" in line):
        return True
    return line_type == "context" and len(columns) <= 2


def parse_note_pages(year: int, pages: list[PageBundle], notes_start_page: int) -> list[dict]:
    rows: list[dict] = []
    current_note_no = ""
    current_note_title = ""
    current_subsection = ""
    current_table_header = ""

    for bundle in pages:
        if bundle.page_no < notes_start_page:
            continue

        for raw_line in bundle.lines:
            line = raw_line.strip()
            if is_page_artifact(raw_line):
                continue
            if not line:
                continue
            if is_report_page_line(line):
                continue

            header = is_note_header(line)
            if header:
                current_note_no, current_note_title = header
                current_subsection = ""
                current_table_header = ""
                continue

            if not current_note_no:
                continue

            if any(marker in line for marker in ("公司负责人：", "主管会计工作负责人")):
                continue

            if SUBSECTION_RE.match(line) and not extract_numeric_tokens(line):
                current_subsection = clean_fragment(line)
                current_table_header = ""
                continue

            columns = split_columns(raw_line)
            line_type = infer_note_line_type(columns)
            numeric_tokens = extract_numeric_tokens(raw_line)

            if is_checkbox_line(columns, line):
                continue
            if line_type == "context" and not numeric_tokens:
                continue
            if not columns and not numeric_tokens:
                continue
            if looks_like_prose_with_numbers(columns, line, line_type):
                continue

            if line_type == "table_header":
                current_table_header = clean_fragment(line)

            normalized_columns = columns[:] if columns else [line]
            if len(normalized_columns) == 1 and numeric_tokens:
                if normalized_columns[0] not in numeric_tokens:
                    pass
                else:
                    normalized_columns = numeric_tokens[:]

            rows.append(
                {
                    "年份": year,
                    "附注号": current_note_no,
                    "附注标题": current_note_title,
                    "子标题": current_subsection,
                    "表头": current_table_header,
                    "页码": bundle.page_no,
                    "行类型": line_type,
                    "原始行": line,
                    "列1": normalized_columns[0] if len(normalized_columns) > 0 else "",
                    "列2": normalized_columns[1] if len(normalized_columns) > 1 else "",
                    "列3": normalized_columns[2] if len(normalized_columns) > 2 else "",
                    "列4": normalized_columns[3] if len(normalized_columns) > 3 else "",
                    "列5": normalized_columns[4] if len(normalized_columns) > 4 else "",
                    "列6": normalized_columns[5] if len(normalized_columns) > 5 else "",
                    "数值抓取": " | ".join(numeric_tokens),
                }
            )
    return rows


def build_directory_sheet(verification: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(verification)[
        [
            "年份",
            "年报标题",
            "PDF文件",
            "页数",
            "主表页命中",
            "主表行数",
            "附注起始页",
            "附注行数",
            "状态",
        ]
    ]


def load_reference_main_rows(years: list[int]) -> pd.DataFrame:
    rows: list[dict] = []
    for csv_name, statement_kind, titles in REFERENCE_SPECS:
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
                        "当前参考值": float(current_value),
                        "上年参考值": float(previous_value) if not pd.isna(previous_value) else pd.NA,
                        "候选报表": " | ".join(titles),
                    }
                )
    return pd.DataFrame(rows)


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
                    "公式": str(item.get("公式", "")),
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
                    "层级深度": item.get("层级深度", pd.NA),
                    "当前节点": str(item.get("当前节点", "")),
                    "路径": str(item.get("路径", "")),
                    "apiKey": str(item.get("apiKey", "")),
                    "fullName": str(item.get("fullName", "")),
                    "当前值": float(current_value),
                    "上年值": float(previous_value) if not pd.isna(previous_value) else pd.NA,
                }
            )
    return pd.DataFrame(rows)


def classify_focus_note_category(title: str) -> str:
    normalized_title = normalize_label(title)
    for category, keywords in FOCUS_NOTE_CATEGORY_RULES.items():
        if any(normalize_label(keyword) in normalized_title for keyword in keywords):
            return category
    return ""


def infer_focus_item(columns: list[str]) -> str:
    compact_columns = [str(value).strip() for value in columns if str(value).strip()]
    if not compact_columns:
        return ""

    label_parts: list[str] = []
    index = 0
    while index < len(compact_columns):
        value = compact_columns[index]
        if is_value_cell(value):
            if index == 0 and len(compact_columns) > 1 and is_age_or_period_text(compact_columns[1]):
                label_parts.extend([value, compact_columns[1]])
                index += 2
            break
        label_parts.append(value)
        index += 1
    if not label_parts:
        label_parts.append(compact_columns[0])
    return "".join(label_parts[:3]).strip()


def should_assign_current_previous(header_text: str) -> bool:
    compact = clean_fragment(header_text)
    paired_markers = (
        ("期末", "期初"),
        ("年末", "年初"),
        ("本期", "上期"),
        ("期末余额", "期初余额"),
        ("年末余额", "年初余额"),
        ("期末账面余额", "期初账面余额"),
        ("年末账面余额", "年初账面余额"),
    )
    return any(left in compact and right in compact for left, right in paired_markers)


def build_focus_note_table(note_rows: list[dict]) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    note_df = pd.DataFrame(note_rows).copy()
    if note_df.empty:
        return pd.DataFrame(), {}

    focus_rows: list[dict] = []
    for _, row in note_df.iterrows():
        category = classify_focus_note_category(str(row.get("附注标题", "")))
        if not category:
            continue

        tokens = [token.strip() for token in str(row.get("数值抓取", "")).split("|") if token.strip()]
        numeric_values = [numeric_token_to_float(token) for token in tokens]
        if not numeric_values or all(pd.isna(value) for value in numeric_values):
            continue

        column_values = [row.get(f"列{i}", "") for i in range(1, 7)]
        item = infer_focus_item(column_values)
        if not item:
            continue
        if is_report_page_line(str(row.get("原始行", ""))):
            continue

        header_text = str(row.get("表头", ""))
        standardized = {
            "年份": row.get("年份"),
            "分类": category,
            "附注号": row.get("附注号"),
            "附注标题": row.get("附注标题"),
            "子标题": row.get("子标题"),
            "表头": header_text,
            "页码": row.get("页码"),
            "项目": item,
            "值1": numeric_values[0] if len(numeric_values) > 0 else pd.NA,
            "值2": numeric_values[1] if len(numeric_values) > 1 else pd.NA,
            "值3": numeric_values[2] if len(numeric_values) > 2 else pd.NA,
            "值4": numeric_values[3] if len(numeric_values) > 3 else pd.NA,
            "值5": numeric_values[4] if len(numeric_values) > 4 else pd.NA,
            "值6": numeric_values[5] if len(numeric_values) > 5 else pd.NA,
            "原始行": row.get("原始行"),
        }
        if should_assign_current_previous(header_text):
            standardized["当前值"] = standardized["值1"]
            standardized["上年值"] = standardized["值2"]
        else:
            standardized["当前值"] = pd.NA
            standardized["上年值"] = pd.NA
        focus_rows.append(standardized)

    focus_df = pd.DataFrame(focus_rows)
    if focus_df.empty:
        return focus_df, {}

    focus_df = focus_df.sort_values(["年份", "分类", "附注标题", "页码", "项目"]).reset_index(drop=True)
    category_sheets = {
        category: focus_df[focus_df["分类"] == category].reset_index(drop=True)
        for category in sorted(focus_df["分类"].dropna().unique())
    }
    return focus_df, category_sheets


def select_best_statement_candidate(candidates: pd.DataFrame, ref_row: pd.Series) -> pd.Series | None:
    if candidates.empty:
        return None

    ref_current = ref_row["当前参考值"]
    ref_previous = ref_row["上年参考值"]
    enriched = candidates.copy()
    enriched["精确命中"] = enriched["项目_norm"] == ref_row["项目_norm"]
    enriched["包含命中"] = enriched["项目_norm"].apply(
        lambda value: ref_row["项目_norm"] in value or value in ref_row["项目_norm"]
    )
    enriched = enriched[enriched["精确命中"] | enriched["包含命中"]]
    if enriched.empty:
        return None

    enriched["当前差值"] = (enriched["值1_num"] - ref_current).abs()
    enriched["当前差值"] = enriched["当前差值"].fillna(10**30)
    if pd.isna(ref_previous):
        enriched["上年差值"] = 0.0
    else:
        enriched["上年差值"] = (enriched["值2_num"] - ref_previous).abs()
        enriched["上年差值"] = enriched["上年差值"].fillna(10**30)
    enriched["名称长度差"] = (enriched["项目_norm"].str.len() - len(ref_row["项目_norm"])).abs()
    enriched = enriched.sort_values(
        by=["精确命中", "当前差值", "上年差值", "名称长度差", "页码"],
        ascending=[False, True, True, True, True],
    )
    return enriched.iloc[0]


def build_validated_main_table(statement_rows: list[dict], years: list[int]) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw_df = pd.DataFrame(statement_rows).copy()
    if raw_df.empty:
        return pd.DataFrame(), pd.DataFrame()

    raw_df["项目_norm"] = raw_df["项目"].fillna("").map(normalize_label)
    raw_df["值1_num"] = pd.to_numeric(raw_df["值1"].astype(str).str.replace(",", ""), errors="coerce")
    raw_df["值2_num"] = pd.to_numeric(raw_df["值2"].astype(str).str.replace(",", ""), errors="coerce")

    reference_df = load_reference_main_rows(years)
    validated_rows: list[dict] = []

    for _, ref_row in reference_df.iterrows():
        _, _, titles = next(spec for spec in REFERENCE_SPECS if spec[1] == ref_row["报表类别"])
        candidates = raw_df[
            (raw_df["年份"] == ref_row["年份"]) &
            (raw_df["报表名称"].isin(titles))
        ]
        best = select_best_statement_candidate(candidates, ref_row)

        current_status = "参考补齐"
        page_no = pd.NA
        raw_line = ""
        pdf_item = ""
        pdf_current = pd.NA
        pdf_previous = pd.NA

        if best is not None:
            page_no = best["页码"]
            raw_line = best["原始行"]
            pdf_item = best["项目"]
            pdf_current = best["值1_num"]
            pdf_previous = best["值2_num"]
            current_match = pd.notna(pdf_current) and abs(pdf_current - ref_row["当前参考值"]) < 1
            previous_match = pd.isna(ref_row["上年参考值"]) or (
                pd.notna(pdf_previous) and abs(pdf_previous - ref_row["上年参考值"]) < 1
            )
            if current_match and previous_match:
                current_status = "PDF一致"
            else:
                current_status = "参考纠正"

        validated_rows.append(
            {
                "年份": ref_row["年份"],
                "报表类别": ref_row["报表类别"],
                "字段代码": ref_row["字段代码"],
                "项目": ref_row["项目"],
                "当前值": ref_row["当前参考值"],
                "上年值": ref_row["上年参考值"],
                "校验状态": current_status,
                "PDF项目": pdf_item,
                "PDF当前值": pdf_current,
                "PDF上年值": pdf_previous,
                "来源页码": page_no,
                "来源原始行": raw_line,
            }
        )

    validated_df = pd.DataFrame(validated_rows)
    diff_df = validated_df[validated_df["校验状态"] != "PDF一致"].copy()
    return validated_df, diff_df


def write_outputs(
    verification: list[dict],
    statement_rows: list[dict],
    note_rows: list[dict],
) -> None:
    statement_df = pd.DataFrame(statement_rows)
    note_df = pd.DataFrame(note_rows)
    directory_df = build_directory_sheet(verification)
    years = sorted(directory_df["年份"].astype(int).tolist())
    validated_main_df, diff_main_df = build_validated_main_table(statement_rows, years)
    focus_note_df, focus_note_sheets = build_focus_note_table(note_rows)
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
        note_df.to_excel(writer, sheet_name="附注明细汇总", index=False)
        focus_note_df.to_excel(writer, sheet_name="附注重点明细汇总", index=False)

        for sheet_name, datayes_df in datayes_sheets.items():
            datayes_df.to_excel(writer, sheet_name=sheet_name, index=False)

        focus_sheet_names = {
            "应收类": "附注应收类",
            "资产类": "附注资产类",
            "借款类": "附注借款类",
            "税项类": "附注税项类",
        }
        for category, category_df in focus_note_sheets.items():
            category_df.to_excel(writer, sheet_name=focus_sheet_names.get(category, category[:31]), index=False)

        for year in years:
            yearly_statement = validated_main_df[validated_main_df["年份"] == year]
            yearly_note = note_df[note_df["年份"] == year]
            yearly_statement.to_excel(writer, sheet_name=f"{year}主表", index=False)
            yearly_note.to_excel(writer, sheet_name=f"{year}附注", index=False)


def write_verification_markdown(verification: list[dict]) -> None:
    lines = ["# 长江电力财务报表抽取核对说明", ""]
    lines.append(f"- 输出工作簿：`{OUTPUT_XLSX.name}`")
    lines.append("- 主表抽取范围：资产负债表、利润表、现金流量表（含合并/母公司/历史利润及利润分配表别名）")
    lines.append("- 附注抽取范围：`财务报表项目注释 / 会计报表主要项目注释` 后的表格式明细行")
    lines.append("- 说明：个别早期年报存在列合并、数字黏连、表头换行，工作簿已保留原始行文本与页码供复核。")
    lines.append("")
    lines.append("## 年度结果")
    lines.append("")
    for item in verification:
        lines.append(
            f"- {item['年份']}：页数 {item['页数']}，主表页 {item['主表页命中']}，主表行 {item['主表行数']}，附注起始页 {item['附注起始页']}，附注行 {item['附注行数']}，状态：{item['状态']}"
        )
    VERIFY_MD.write_text("\n".join(lines), encoding="utf-8")


def write_validation_markdown(validated_main_df: pd.DataFrame) -> None:
    lines = ["# 长江电力主表校验说明", ""]
    lines.append("- 对比来源：`萝卜投研-财务页下载/整理/csv` 下的标准化年报主表数据")
    lines.append("- 校验范围：`利润表 / 资产负债表 / 现金流量表` 年报口径")
    lines.append("- 说明：`主表汇总` 和各年 `YYYY主表` 已按参考数据完成校正；`主表原始汇总` 保留 PDF 直接抽取结果。")
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


def process_report(report: ReportRecord) -> tuple[list[dict], list[dict], dict]:
    pages = read_pages(report.pdf_path)
    financial_start_page = detect_financial_statement_start(pages)
    notes_start_page = find_notes_start_page(
        pages,
        financial_start_page=financial_start_page,
        fallback_page=len(pages) + 1,
    )
    statement_pages = collect_statement_lines(pages, financial_start_page, notes_start_page)

    statement_rows: list[dict] = []
    for title in sorted(statement_pages.keys()):
        statement_rows.extend(parse_statement_pages(report.year, title, statement_pages[title]))

    note_rows = parse_note_pages(report.year, pages, notes_start_page=notes_start_page)

    verification = {
        "年份": report.year,
        "年报标题": report.title,
        "PDF文件": report.pdf_path.name,
        "页数": len(pages),
        "主表页命中": ", ".join(
            f"{title}:{','.join(str(page_no) for page_no in sorted({page_no for page_no, _ in bundles}))}"
            for title, bundles in sorted(statement_pages.items())
        ),
        "主表行数": len(statement_rows),
        "附注起始页": notes_start_page,
        "附注行数": len(note_rows),
        "状态": "成功" if statement_rows and note_rows else "需复核",
    }
    return statement_rows, note_rows, verification


def main() -> None:
    args = parse_args()
    selected_years = set(args.years) if args.years else None
    reports = load_reports(selected_years)
    if not reports:
        raise SystemExit("未找到可处理的年报记录。")

    all_statement_rows: list[dict] = []
    all_note_rows: list[dict] = []
    verification_rows: list[dict] = []

    for report in reports:
        statement_rows, note_rows, verification = process_report(report)
        all_statement_rows.extend(statement_rows)
        all_note_rows.extend(note_rows)
        verification_rows.append(verification)
        print(
            f"[{report.year}] 主表 {len(statement_rows)} 行，附注 {len(note_rows)} 行，附注起始页 {verification['附注起始页']}"
        )

    write_outputs(verification_rows, all_statement_rows, all_note_rows)
    write_verification_markdown(verification_rows)
    validated_main_df, _ = build_validated_main_table(all_statement_rows, sorted(item["年份"] for item in verification_rows))
    write_validation_markdown(validated_main_df)

    print(f"已生成：{OUTPUT_XLSX}")
    print(f"已生成：{VERIFY_MD}")
    print(f"已生成：{VALIDATION_MD}")


if __name__ == "__main__":
    main()

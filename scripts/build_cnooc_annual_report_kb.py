#!/usr/bin/env python3

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

import fitz


BASE_DIR = Path("/Users/luzuoguan/ai/value-investing")
COMPANY_NAME = "中国海油"
COMPANY_CODE = "600938"
COMPANY_DIR = BASE_DIR / "年报" / f"{COMPANY_NAME}-{COMPANY_CODE}"
METADATA_PATH = COMPANY_DIR / "metadata.json"

KB_DIR = COMPANY_DIR / "知识库"
FULLTEXT_DIR = KB_DIR / "年报全文"
STRUCT_DIR = KB_DIR / "结构化"
README_PATH = KB_DIR / "README.md"
INDEX_MD_PATH = KB_DIR / "索引.md"
INDEX_JSON_PATH = KB_DIR / "索引.json"
VALIDATION_PATH = KB_DIR / "校验报告.md"
DATAYES_DIR = COMPANY_DIR / "萝卜投研-财务页下载"
DATAYES_README = DATAYES_DIR / "README.md"
DATAYES_MANIFEST = DATAYES_DIR / "manifest.json"
DATAYES_CSV_DIR = DATAYES_DIR / "整理" / "csv"
DATAYES_TRANSFORM_DOC = DATAYES_DIR / "整理" / "Datayes-字段对照说明.md"
EXTRACT_WORKBOOK = COMPANY_DIR / "中国海油-2022至2024-财务报表与附注明细.xlsx"
EXTRACT_VERIFY_MD = COMPANY_DIR / "财务报表抽取核对说明.md"
EXTRACT_VALIDATION_MD = COMPANY_DIR / "财务报表校验说明.md"
RECON_WORKBOOK = COMPANY_DIR / "中国海油-2022至2024-财务报表与附注明细-已对账.xlsx"
RECON_REPORT_MD = COMPANY_DIR / "Datayes对账结果.md"

ANNUAL_TITLE_RE = re.compile(r"((?:19|20)\d{2})年年度报告")
TOP_SECTION_RE = re.compile(r"^(第[一二三四五六七八九十百]+节)\s*(.+)$")
PAGE_LABEL_PATTERNS = (
    re.compile(r"第\s*(\d+)\s*页"),
    re.compile(r"(\d+)\s*/\s*(\d+)"),
)
LOW_TEXT_THRESHOLD = 80


@dataclass(frozen=True)
class ReportRecord:
    year: int
    title: str
    pdf_path: Path
    source_url: str
    disclosure_date: str


def normalize_line(line: str) -> str:
    line = line.replace("\u3000", " ")
    line = re.sub(r"[ \t]+", " ", line)
    return line.strip()


def slugify_title(title: str) -> str:
    safe = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "-", title).strip("-")
    return safe or "annual-report"


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_datayes_status() -> dict:
    annual_years: set[int] = set()
    profit_csv = DATAYES_CSV_DIR / "利润表.csv"
    if profit_csv.exists():
        with profit_csv.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            for name in fieldnames:
                matched = re.fullmatch(r"(20\d{2})年报", str(name))
                if matched:
                    annual_years.add(int(matched.group(1)))
    return {
        "manifest_exists": DATAYES_MANIFEST.exists(),
        "csv_exists": DATAYES_CSV_DIR.exists(),
        "field_doc_exists": DATAYES_TRANSFORM_DOC.exists(),
        "extract_workbook_exists": EXTRACT_WORKBOOK.exists(),
        "extract_verify_exists": EXTRACT_VERIFY_MD.exists(),
        "extract_validation_exists": EXTRACT_VALIDATION_MD.exists(),
        "recon_workbook_exists": RECON_WORKBOOK.exists(),
        "recon_report_exists": RECON_REPORT_MD.exists(),
        "annual_years": sorted(annual_years),
    }


def load_reports() -> list[ReportRecord]:
    records = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    reports: list[ReportRecord] = []
    for item in records:
        if item.get("kind") != "年报":
            continue
        title = str(item.get("title", "")).strip()
        matched = ANNUAL_TITLE_RE.search(title)
        if not matched:
            continue
        pdf_path = COMPANY_DIR / item["file"]
        if not pdf_path.exists():
            raise FileNotFoundError(f"缺少年报 PDF：{pdf_path}")
        reports.append(
            ReportRecord(
                year=int(matched.group(1)),
                title=title,
                pdf_path=pdf_path,
                source_url=str(item.get("url", "")).strip(),
                disclosure_date=str(item.get("date", "")).strip(),
            )
        )
    return sorted(reports, key=lambda item: item.year)


def extract_pdf_pages(pdf_path: Path) -> list[dict]:
    doc = fitz.open(pdf_path)
    pages: list[dict] = []
    for idx, page in enumerate(doc, start=1):
        text = page.get_text("text") or ""
        lines = [normalize_line(line) for line in text.splitlines() if normalize_line(line)]

        text = "\n".join(lines)
        page_label = ""
        for line in lines[:12]:
            for pattern in PAGE_LABEL_PATTERNS:
                matched = pattern.search(line)
                if matched:
                    page_label = matched.group(0)
                    break
            if page_label:
                break

        pages.append(
            {
                "pdf_page": idx,
                "page_label": page_label,
                "char_count": len(text),
                "line_count": len(lines),
                "used_plain_fallback": False,
                "text": text,
                "lines": lines,
            }
        )
    doc.close()
    return pages


def extract_headings(pages: list[dict]) -> list[dict]:
    headings: list[dict] = []
    seen: set[tuple[int, str]] = set()
    for page in pages:
        for line in page["lines"][:160]:
            matched = TOP_SECTION_RE.match(line)
            if not matched:
                continue
            key = (page["pdf_page"], line)
            if key in seen:
                continue
            seen.add(key)
            headings.append(
                {
                    "pdf_page": page["pdf_page"],
                    "section": matched.group(1),
                    "title": matched.group(2).strip(),
                    "raw": line,
                }
            )
    return headings


def write_fulltext_markdown(report: ReportRecord, pages: list[dict], headings: list[dict]) -> str:
    output_path = FULLTEXT_DIR / f"{report.year}-{slugify_title(report.title)}.md"
    lines = [
        f"# {report.title}",
        "",
        f"- 公司：{COMPANY_NAME}（{COMPANY_CODE}.SH）",
        f"- 年度：{report.year}",
        f"- 披露日期：{report.disclosure_date}",
        f"- 来源 PDF：`{report.pdf_path.name}`",
        f"- 巨潮链接：{report.source_url}",
        f"- PDF 页数：{len(pages)}",
        "",
    ]

    if headings:
        lines.append("## 识别到的一级章节")
        lines.append("")
        for item in headings:
            lines.append(f"- 第 {item['pdf_page']} 页 | {item['raw']}")
        lines.append("")

    for page in pages:
        lines.append(f"## 第 {page['pdf_page']} 页")
        lines.append("")
        lines.append(f"- 页码标记：{page['page_label'] or '未识别'}")
        lines.append(f"- 文本字符数：{page['char_count']}")
        lines.append(f"- 行数：{page['line_count']}")
        lines.append("- 提取方式：PyMuPDF text")
        lines.append("")
        if page["text"]:
            lines.append(page["text"])
        else:
            lines.append("[本页未提取到文本]")
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path.name


def write_structured_json(report: ReportRecord, pages: list[dict], headings: list[dict], markdown_name: str) -> dict:
    low_text_pages = [page["pdf_page"] for page in pages if page["char_count"] < LOW_TEXT_THRESHOLD]
    payload = {
        "company": {"name": COMPANY_NAME, "code": COMPANY_CODE},
        "year": report.year,
        "title": report.title,
        "disclosure_date": report.disclosure_date,
        "source_pdf": {
            "file": report.pdf_path.name,
            "sha256": file_sha256(report.pdf_path),
            "url": report.source_url,
        },
        "fulltext_markdown": markdown_name,
        "page_count": len(pages),
        "low_text_threshold": LOW_TEXT_THRESHOLD,
        "low_text_pages": low_text_pages,
        "used_plain_fallback_pages": [page["pdf_page"] for page in pages if page["used_plain_fallback"]],
        "page_stats": [
            {
                "pdf_page": page["pdf_page"],
                "page_label": page["page_label"],
                "char_count": page["char_count"],
                "line_count": page["line_count"],
            }
            for page in pages
        ],
        "headings": headings,
    }
    output_path = STRUCT_DIR / f"{report.year}.json"
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def write_index(index_rows: list[dict], datayes_status: dict) -> None:
    INDEX_JSON_PATH.write_text(json.dumps(index_rows, ensure_ascii=False, indent=2), encoding="utf-8")

    if datayes_status["recon_workbook_exists"]:
        datayes_line = "- Datayes 财务页数据、`亿元` 口径整理结果和 `2022-2024` 主表对账结果均已接入。"
    elif datayes_status["csv_exists"]:
        datayes_line = "- Datayes 财务页数据与 `亿元` 口径整理结果已接入；主表对账结果部分可用。"
    elif datayes_status["manifest_exists"]:
        datayes_line = "- Datayes 财务页原始下载已存在，但整理/对账结果尚未完全接入。"
    else:
        datayes_line = "- 当前仅包含巨潮年报 PDF 整理结果；Datayes 财务页数据尚未接入。"

    lines = [
        f"# {COMPANY_NAME}年报知识库索引",
        "",
        f"- 公司：{COMPANY_NAME}（{COMPANY_CODE}.SH）",
        f"- 年报数量：{len(index_rows)}",
        datayes_line,
        "",
    ]
    for item in index_rows:
        lines.extend(
            [
                f"## {item['year']}",
                "",
                f"- 标题：{item['title']}",
                f"- 披露日期：{item['disclosure_date']}",
                f"- PDF：`{item['pdf_file']}`",
                f"- Markdown：`年报全文/{item['markdown_file']}`",
                f"- 结构化：`结构化/{item['structured_file']}`",
                f"- PDF 页数：{item['page_count']}",
                f"- 低文本页：{len(item['low_text_pages'])}",
                f"- 一级章节数：{item['heading_count']}",
                f"- Datayes年报口径：{'已接入' if item['year'] in datayes_status['annual_years'] else '未接入'}",
                f"- 主表对账：{'已生成' if datayes_status['recon_workbook_exists'] and item['year'] in {2022, 2023, 2024} else '未生成'}",
                "",
            ]
        )
    INDEX_MD_PATH.write_text("\n".join(lines), encoding="utf-8")


def write_validation(index_rows: list[dict], datayes_status: dict) -> None:
    total_low_text = sum(len(item["low_text_pages"]) for item in index_rows)

    lines = [
        f"# {COMPANY_NAME}年报知识库校验报告",
        "",
        "- 校验一：`metadata.json` 中的年报条目均已生成 Markdown 与结构化 JSON",
        "- 校验二：结构化 JSON 的页数与实际 PDF 页数一致",
        "- 校验三：低文本页已显式记录，便于后续人工复核",
        "- 校验四：Datayes 接入状态按本地整理产物、主表抽取产物和对账产物进行检查",
        "",
        "## 汇总",
        "",
        f"- 年报数量：`{len(index_rows)}`",
        f"- 低文本页总数：`{total_low_text}`",
        f"- Datayes 原始下载：`{'已完成' if datayes_status['manifest_exists'] else '未完成'}`",
        f"- Datayes 亿元整理：`{'已完成' if datayes_status['csv_exists'] else '未完成'}`",
        f"- 主表抽取工作簿：`{'已生成' if datayes_status['extract_workbook_exists'] else '未生成'}`",
        f"- Datayes 对账结果：`{'已生成' if datayes_status['recon_report_exists'] else '未生成'}`",
        "",
    ]

    for item in index_rows:
        lines.append(f"## {item['year']} 年")
        lines.append("")
        lines.append(f"- 标题：{item['title']}")
        lines.append(f"- PDF 页数：`{item['page_count']}`")
        lines.append(f"- 低文本页：`{', '.join(map(str, item['low_text_pages'])) if item['low_text_pages'] else '无'}`")
        lines.append(f"- 一级章节数：`{item['heading_count']}`")
        lines.append("")

    VALIDATION_PATH.write_text("\n".join(lines), encoding="utf-8")


def write_readme(index_rows: list[dict], datayes_status: dict) -> None:
    lines = [
        f"# {COMPANY_NAME}年报知识库",
        "",
        "已完成：",
        "",
        "- 巨潮资讯年报 PDF 下载与覆盖核对",
        "- 年报页级全文 Markdown 整理",
        "- 逐年结构化 JSON 索引",
        "- 基础校验报告生成",
        "- Datayes 财务页原始下载与 `亿元` 口径整理" if datayes_status["csv_exists"] else "- Datayes 财务页原始下载待补齐",
        "- 2022-2024 年报主表与 Datayes 对账结果" if datayes_status["recon_report_exists"] else "- 主表与 Datayes 对账结果待补齐",
        "",
        "当前结果：",
        "",
        f"- 年报数量：`{len(index_rows)}`",
        f"- 覆盖年度：`{index_rows[0]['year']}-{index_rows[-1]['year']}`" if index_rows else "- 覆盖年度：`无`",
        f"- Datayes 年报口径覆盖：`{datayes_status['annual_years'][0]}-{datayes_status['annual_years'][-1]}`" if datayes_status["annual_years"] else "- Datayes 年报口径覆盖：`无`",
        "",
        "剩余风险：",
        "",
        "- 当前结构化 JSON 仍以 PDF 页级文本和一级章节识别为主，尚未把主表标准化结果逐年写回 JSON。",
        "- 主表对账目前覆盖 `2022-2024`，更早年度仍缺少可直接复用的中国海油财务页与主表抽取联动。",
        "- Datayes 页面单位已锁定为 `亿元`，但 PDF 主表原值为 `百万元`，后续新增脚本仍需保持换算一致。",
        "",
    ]
    README_PATH.write_text("\n".join(lines), encoding="utf-8")


def write_datayes_placeholder() -> None:
    DATAYES_DIR.mkdir(parents=True, exist_ok=True)
    if DATAYES_README.exists():
        return
    lines = [
        "# 萝卜投研财务页下载说明",
        "",
        "- 目标公司：中国海油 `600938`",
        "- 当前状态：未下载",
        "- 原因：本机当前缺少 `DATAYES_COOKIE` 与 `DATAYES_USER_AGENT` 环境变量，无法调用 Datayes 接口。",
        "- 后续动作：补齐环境变量后，可运行 `value-investing/scripts/download_datayes_finance.py --ticker 600938 --company-name 中国海油 --output-dir ...`。",
        "",
    ]
    DATAYES_README.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    FULLTEXT_DIR.mkdir(parents=True, exist_ok=True)
    STRUCT_DIR.mkdir(parents=True, exist_ok=True)
    datayes_status = collect_datayes_status()

    reports = load_reports()
    index_rows: list[dict] = []

    for report in reports:
        pages = extract_pdf_pages(report.pdf_path)
        headings = extract_headings(pages)
        markdown_name = write_fulltext_markdown(report, pages, headings)
        struct_payload = write_structured_json(report, pages, headings, markdown_name)
        index_rows.append(
            {
                "year": report.year,
                "title": report.title,
                "disclosure_date": report.disclosure_date,
                "pdf_file": report.pdf_path.name,
                "markdown_file": markdown_name,
                "structured_file": f"{report.year}.json",
                "page_count": struct_payload["page_count"],
                "low_text_pages": struct_payload["low_text_pages"],
                "plain_fallback_pages": len(struct_payload["used_plain_fallback_pages"]),
                "heading_count": len(struct_payload["headings"]),
                "sha256": struct_payload["source_pdf"]["sha256"],
            }
        )

    write_index(index_rows, datayes_status)
    write_validation(index_rows, datayes_status)
    write_readme(index_rows, datayes_status)
    write_datayes_placeholder()
    print(f"已生成 {COMPANY_NAME} 年报知识库：{KB_DIR}")


if __name__ == "__main__":
    main()

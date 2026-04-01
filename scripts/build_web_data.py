#!/usr/bin/env python3
"""
将 value-investing 项目中散落的 CSV / JSON 数据预处理为前端 Web 应用可直接读取的 JSON 文件。

输出目录: web-app/public/data/
输出结构:
  companies.json          — 公司列表元信息
  {slug}/ratios.json      — 财务比率（年度 + 全期间）
  {slug}/profile.json     — 公司基本信息
  {slug}/valuation.json   — 估值模型数据
  {slug}/notes.json       — 研究笔记索引
  buffett/index.json      — 巴菲特文集目录
  buffett/quotes.json     — 金句索引
  buffett/themes.json     — 主题索引
  peers/comparison.json   — 同行对比数据
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEB_DATA_DIR = PROJECT_ROOT / "web-app" / "public" / "data"

COMPANY_DIRS = [
    PROJECT_ROOT / "年报" / "长江电力-600900",
    PROJECT_ROOT / "年报" / "中国海油-600938",
]


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_csv_to_dicts(path: Path) -> list[dict]:
    """Read a CSV file and return list of dicts."""
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return [row for row in reader]


def clean_numeric(value: str | None) -> float | None:
    """Convert string to float, return None for empty/invalid."""
    if value is None or value.strip() == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def parse_slug(company_dir: Path) -> str:
    """Extract slug like '长江电力-600900' from path."""
    return company_dir.name


def parse_company_name(slug: str) -> str:
    """Extract company name from slug."""
    return slug.rsplit("-", 1)[0] if "-" in slug else slug


def parse_ticker(slug: str) -> str:
    """Extract ticker from slug."""
    return slug.rsplit("-", 1)[1] if "-" in slug else ""


def build_company_profile(company_dir: Path, slug: str) -> dict:
    """Build company profile from AKShare stock_profile.csv and metadata.json."""
    profile = {
        "slug": slug,
        "name": parse_company_name(slug),
        "ticker": parse_ticker(slug),
        "industry": "",
        "listDate": "",
        "totalShares": None,
        "circulatingShares": None,
        "marketCap": None,
    }

    # Read AKShare profile
    akshare_profile = company_dir / "AKShare-财务数据" / "raw" / "stock_profile.csv"
    if akshare_profile.exists():
        rows = read_csv_to_dicts(akshare_profile)
        kv = {row.get("item", ""): row.get("value", "") for row in rows}
        profile["industry"] = kv.get("行业", "")
        profile["listDate"] = kv.get("上市时间", "")
        profile["totalShares"] = clean_numeric(kv.get("总股本"))
        profile["circulatingShares"] = clean_numeric(kv.get("流通股"))
        profile["marketCap"] = clean_numeric(kv.get("总市值"))

    # Read metadata for annual report info
    metadata_path = company_dir / "metadata.json"
    if metadata_path.exists():
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        profile["annualReports"] = [
            {"year": int(re.search(r"(\d{4})年", item.get("title", "")).group(1)) if re.search(r"(\d{4})年", item.get("title", "")) else None,
             "title": item.get("title", ""),
             "date": item.get("date", ""),
             "kind": item.get("kind", "")}
            for item in metadata
        ]

    return profile


def build_ratios_data(company_dir: Path) -> dict:
    """Build financial ratios data from CSV files."""
    ratios_dir = company_dir / "萝卜投研-财务页下载" / "整理" / "ratios"

    annual_path = ratios_dir / "财务比率-年度.csv"
    full_path = ratios_dir / "财务比率-全期间.csv"

    annual_rows = read_csv_to_dicts(annual_path)
    full_rows = read_csv_to_dicts(full_path)

    def process_rows(rows: list[dict]) -> list[dict]:
        processed = []
        for row in rows:
            entry = {}
            for key, value in row.items():
                entry[key] = clean_numeric(value) if key != "期间" else value
            processed.append(entry)
        return processed

    return {
        "annual": process_rows(annual_rows),
        "full": process_rows(full_rows),
    }


def build_valuation_data(company_dir: Path) -> dict | None:
    """Build valuation data from markdown report."""
    valuation_dir = company_dir / "萝卜投研-财务页下载" / "整理" / "valuation"
    if not valuation_dir.exists():
        return None

    valuation_files = list(valuation_dir.glob("估值报告-*.md"))
    if not valuation_files:
        return None

    report_path = valuation_files[0]
    content = report_path.read_text(encoding="utf-8")

    # Extract key values from markdown
    result = {"reportFile": report_path.name, "raw": content}

    # Try to parse structured data
    patterns = {
        "baseFCF": r"FCF 基期（亿元）：`([^`]+)`",
        "explicitPV": r"显式预测期现值（亿元）：`([^`]+)`",
        "terminalPV": r"终值现值（亿元）：`([^`]+)`",
        "equityValue": r"DCF 股权价值（亿元）：`([^`]+)`",
        "sharesOutstanding": r"估算总股本（亿股）：`([^`]+)`",
        "intrinsicValuePerShare": r"DCF 每股内在价值（元）：`([^`]+)`",
        "growthRate": r"未来增长率：`([^`]+)`",
        "discountRate": r"折现率：`([^`]+)`",
        "terminalGrowthRate": r"永续增长率：`([^`]+)`",
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, content)
        if match:
            val = match.group(1).replace("%", "").replace(",", "")
            result[key] = clean_numeric(val) if key not in ("growthRate", "discountRate", "terminalGrowthRate") else val

    return result


def build_notes_index(company_dir: Path) -> list[dict]:
    """Build research notes index for a company."""
    slug = parse_slug(company_dir)
    name = parse_company_name(slug)
    notes_dir = PROJECT_ROOT / "研究笔记" / slug

    if not notes_dir.exists():
        return []

    notes = []
    for md_file in sorted(notes_dir.glob("*.md")):
        content = md_file.read_text(encoding="utf-8")
        # Extract title from first heading
        title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        title = title_match.group(1) if title_match else md_file.stem

        notes.append({
            "file": md_file.name,
            "title": title,
            "size": md_file.stat().st_size,
            "preview": content[:500],
        })

    return notes


def build_buffett_data() -> dict:
    """Build Buffett collection data."""
    buffett_dir = PROJECT_ROOT / "巴菲特文集"
    result = {"categories": [], "quotes": [], "themes": [], "timeline": None}

    # Build category listing
    categories = [
        {"id": "letters", "name": "致股东信", "dir": "致股东信"},
        {"id": "meetings", "name": "股东大会", "dir": "股东大会"},
        {"id": "partner", "name": "合伙人信", "dir": "合伙人信"},
        {"id": "early", "name": "早期文章", "dir": "早期文章"},
    ]

    for cat in categories:
        cat_dir = buffett_dir / cat["dir"]
        if not cat_dir.exists():
            continue
        files = sorted(cat_dir.glob("*.md"))
        items = []
        for f in files:
            year_match = re.search(r"(\d{4})", f.stem)
            items.append({
                "file": f"{cat['dir']}/{f.name}",
                "name": f.stem,
                "year": int(year_match.group(1)) if year_match else None,
                "size": f.stat().st_size,
            })
        cat["items"] = items
        cat["count"] = len(items)

    result["categories"] = categories

    # Parse quotes
    quotes_path = buffett_dir / "金句索引.md"
    if quotes_path.exists():
        content = quotes_path.read_text(encoding="utf-8")
        quote_blocks = re.findall(
            r"\*\*\[(\d{4})\]\*\*\s+(.+?)\n\n\*— (.+?)\*",
            content, re.DOTALL
        )
        for year, text, source in quote_blocks:
            result["quotes"].append({
                "year": int(year),
                "text": text.strip()[:300],
                "source": source.strip(),
            })

    # Parse themes
    themes_dir = buffett_dir / "主题索引"
    if themes_dir.exists():
        for theme_file in sorted(themes_dir.glob("*.md")):
            if theme_file.name == "README.md":
                continue
            content = theme_file.read_text(encoding="utf-8")
            # Count entries
            entry_count = len(re.findall(r"^###\s", content, re.MULTILINE))
            preview_match = re.search(r"^>\s+(.+)$", content, re.MULTILINE)
            result["themes"].append({
                "id": theme_file.stem,
                "name": theme_file.stem,
                "file": f"主题索引/{theme_file.name}",
                "entryCount": entry_count,
                "preview": preview_match.group(1) if preview_match else "",
            })

    # Parse timeline
    timeline_path = buffett_dir / "投资风格演进.md"
    if timeline_path.exists():
        result["timeline"] = timeline_path.read_text(encoding="utf-8")

    return result


def build_peers_data() -> dict | None:
    """Build peer comparison data."""
    peers_dir = PROJECT_ROOT / "研究笔记" / "同行对比"
    md_files = list(peers_dir.glob("同行对比-*.md"))
    if not md_files:
        return None

    result = {"comparisons": []}
    for md_file in md_files:
        content = md_file.read_text(encoding="utf-8")
        result["comparisons"].append({
            "name": md_file.stem,
            "content": content,
        })

    # Also try to load the xlsx-based data
    xlsx_csv_equiv = peers_dir / "同行对比-已接入样本.md"
    if xlsx_csv_equiv.exists():
        content = xlsx_csv_equiv.read_text(encoding="utf-8")
        # Parse markdown table
        tables = re.findall(r"\|.+\|(?:\n\|.+\|)+", content)
        result["markdownTables"] = tables

    return result


def build_main_composition(company_dir: Path) -> list[dict] | None:
    """Build main business composition data."""
    csv_path = company_dir / "萝卜投研-财务页下载" / "整理" / "csv" / "主营构成.csv"
    if not csv_path.exists():
        return None

    rows = read_csv_to_dicts(csv_path)
    # Filter to product-level revenue breakdown
    composition = []
    for row in rows:
        if row.get("一级项目") == "营业总收入" and row.get("维度") == "产品" and row.get("层级深度") == "2":
            item_name = row.get("当前节点", "")
            if "差额" in item_name:
                continue
            periods = {}
            for key, value in row.items():
                if re.match(r"\d{4}", key):
                    periods[key] = clean_numeric(value)
            composition.append({
                "segment": item_name,
                "periods": periods,
            })

    return composition if composition else None


def main():
    ensure_dir(WEB_DATA_DIR)

    companies_meta = []

    for company_dir in COMPANY_DIRS:
        slug = parse_slug(company_dir)
        print(f"处理: {slug}")

        company_data_dir = ensure_dir(WEB_DATA_DIR / slug)

        # Profile
        profile = build_company_profile(company_dir, slug)
        with open(company_data_dir / "profile.json", "w", encoding="utf-8") as f:
            json.dump(profile, f, ensure_ascii=False, indent=2)

        # Ratios
        ratios = build_ratios_data(company_dir)
        with open(company_data_dir / "ratios.json", "w", encoding="utf-8") as f:
            json.dump(ratios, f, ensure_ascii=False, indent=2)

        # Valuation
        valuation = build_valuation_data(company_dir)
        if valuation:
            with open(company_data_dir / "valuation.json", "w", encoding="utf-8") as f:
                json.dump(valuation, f, ensure_ascii=False, indent=2)

        # Notes
        notes = build_notes_index(company_dir)
        if notes:
            with open(company_data_dir / "notes.json", "w", encoding="utf-8") as f:
                json.dump(notes, f, ensure_ascii=False, indent=2)

        # Main composition
        composition = build_main_composition(company_dir)
        if composition:
            with open(company_data_dir / "composition.json", "w", encoding="utf-8") as f:
                json.dump(composition, f, ensure_ascii=False, indent=2)

        # Summary for company list
        latest_annual = ratios["annual"][-1] if ratios["annual"] else {}
        companies_meta.append({
            "slug": slug,
            "name": profile["name"],
            "ticker": profile["ticker"],
            "industry": profile["industry"],
            "latestPeriod": latest_annual.get("期间", ""),
            "latestRevenue": latest_annual.get("营收(亿元)"),
            "latestProfit": latest_annual.get("归母净利润(亿元)"),
            "latestROE": latest_annual.get("ROE(%)"),
            "latestDividendYield": latest_annual.get("股息率(%)"),
            "hasValuation": valuation is not None,
            "hasNotes": len(notes) > 0,
            "annualCount": len(ratios["annual"]),
        })

    # Companies list
    with open(WEB_DATA_DIR / "companies.json", "w", encoding="utf-8") as f:
        json.dump(companies_meta, f, ensure_ascii=False, indent=2)

    # Buffett data
    buffett_dir = ensure_dir(WEB_DATA_DIR / "buffett")
    buffett_data = build_buffett_data()
    with open(buffett_dir / "index.json", "w", encoding="utf-8") as f:
        json.dump(buffett_data["categories"], f, ensure_ascii=False, indent=2)
    with open(buffett_dir / "quotes.json", "w", encoding="utf-8") as f:
        json.dump(buffett_data["quotes"], f, ensure_ascii=False, indent=2)
    with open(buffett_dir / "themes.json", "w", encoding="utf-8") as f:
        json.dump(buffett_data["themes"], f, ensure_ascii=False, indent=2)
    if buffett_data["timeline"]:
        with open(buffett_dir / "timeline.json", "w", encoding="utf-8") as f:
            json.dump({"content": buffett_data["timeline"]}, f, ensure_ascii=False, indent=2)

    # Peers comparison
    peers_data = build_peers_data()
    if peers_data:
        peers_dir = ensure_dir(WEB_DATA_DIR / "peers")
        with open(peers_dir / "comparison.json", "w", encoding="utf-8") as f:
            json.dump(peers_data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 数据预处理完成，输出目录: {WEB_DATA_DIR}")
    print(f"   公司数量: {len(companies_meta)}")
    for c in companies_meta:
        print(f"   - {c['name']} ({c['ticker']}): {c['annualCount']} 年年报")


if __name__ == "__main__":
    main()

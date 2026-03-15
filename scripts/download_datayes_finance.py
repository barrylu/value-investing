#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
)


@dataclass(frozen=True)
class JsonDownload:
    slug: str
    path_template: str
    params: dict[str, Any]


@dataclass(frozen=True)
class BinaryDownload:
    slug: str
    path_template: str
    params: dict[str, Any]


def build_session(cookie: str, user_agent: str) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-cn",
            "Connection": "keep-alive",
            "Origin": "https://robo.datayes.com",
            "Referer": "https://robo.datayes.com/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
            "User-Agent": user_agent,
            "sec-ch-ua": '"Not(A:Brand";v="8", "Chromium";v="144", "Google Chrome";v="144"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
            "Cookie": cookie,
        }
    )
    return session


def request_json(session: requests.Session, url: str, params: dict[str, Any]) -> dict[str, Any]:
    response = session.get(url, params=params, timeout=60)
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != 1:
        raise RuntimeError(f"接口返回失败: {url} -> {payload}")
    return payload


def download_binary(session: requests.Session, url: str, params: dict[str, Any], target_path: Path) -> dict[str, Any]:
    response = session.get(url, params=params, timeout=120)
    response.raise_for_status()
    if response.headers.get("Content-Type", "").startswith("application/json"):
        try:
            payload = response.json()
        except Exception:
            payload = {"raw_text": response.text[:500]}
        raise RuntimeError(f"导出接口未返回文件: {url} -> {payload}")

    target_path.write_bytes(response.content)
    return {
        "content_disposition": response.headers.get("Content-Disposition", ""),
        "content_type": response.headers.get("Content-Type", ""),
        "bytes": len(response.content),
    }


def json_downloads() -> list[JsonDownload]:
    full_period_params = {
        "reportPeriodType": "A,CQ3,S1,Q1",
        "duration": "ACCUMULATE",
        "includeLatest": "true",
        "period": "30",
        "displaySort": "left",
    }

    return [
        JsonDownload(
            slug="financial_summary_full_periods",
            path_template="raw/financial_summary_full_periods.json",
            params={"reportType": "SUMMARY", **full_period_params},
        ),
        JsonDownload(
            slug="balance_sheet_full_periods",
            path_template="raw/balance_sheet_full_periods.json",
            params={"reportType": "BS", **full_period_params},
        ),
        JsonDownload(
            slug="income_statement_full_periods",
            path_template="raw/income_statement_full_periods.json",
            params={"reportType": "IS", **full_period_params},
        ),
        JsonDownload(
            slug="cashflow_full_periods",
            path_template="raw/cashflow_full_periods.json",
            params={"reportType": "CF", **full_period_params},
        ),
        JsonDownload(
            slug="key_finance_indicators_full_periods",
            path_template="raw/key_finance_indicators_full_periods.json",
            params={
                "reportType": "MZ",
                "ticker": "600900",
                **full_period_params,
            },
        ),
        JsonDownload(
            slug="main_composition_full_periods",
            path_template="raw/main_composition_full_periods.json",
            params={
                "reportName": "MC",
                "reportType": "A,S1",
                "period": "30",
                "includeLatest": "true",
                "duration": "accumulate",
                "isHideEmptyData": "true",
                "unit": "3",
                "decimalPoint": "2",
                "order": "left",
                "isStd": "true",
            },
        ),
    ]


def binary_downloads() -> list[BinaryDownload]:
    full_period_export = {
        "reportPeriodType": "A,CQ3,S1,Q1",
        "duration": "ACCUMULATE",
        "includeLatest": "true",
        "period": "30",
        "displaySort": "left",
        "isHideEmptyData": "true",
        "unit": "3",
        "decimalPoint": "2",
    }
    return [
        BinaryDownload(
            slug="balance_sheet_excel",
            path_template="excel/长江电力-资产负债表-全期间.xls",
            params={"reportType": "BS", **full_period_export},
        ),
        BinaryDownload(
            slug="income_statement_excel",
            path_template="excel/长江电力-利润表-全期间.xls",
            params={"reportType": "IS", **full_period_export},
        ),
        BinaryDownload(
            slug="cashflow_excel",
            path_template="excel/长江电力-现金流量表-全期间.xls",
            params={"reportType": "CF", **full_period_export},
        ),
        BinaryDownload(
            slug="financial_summary_excel",
            path_template="excel/长江电力-财务摘要-全期间.xls",
            params={"reportType": "SUMMARY", **full_period_export},
        ),
        BinaryDownload(
            slug="main_composition_excel",
            path_template="excel/长江电力-主营构成表-全期间.xls",
            params={
                "reportName": "MC",
                "reportType": "A,S1",
                "period": "30",
                "includeLatest": "true",
                "duration": "accumulate",
                "isHideEmptyData": "true",
                "unit": "3",
                "decimalPoint": "2",
                "order": "left",
                "isStd": "true",
            },
        ),
    ]


def write_manifest(output_dir: Path, records: list[dict[str, Any]]) -> None:
    (output_dir / "manifest.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_readme(output_dir: Path, records: list[dict[str, Any]]) -> None:
    lines = [
        "# 萝卜投研财务页下载说明",
        "",
        "说明：",
        "",
        "- 本目录内容来自长江电力 `600900` 的萝卜投研财务页接口下载",
        "- 下载时使用了临时登录态，但本目录**不保存**任何 Cookie 或令牌",
        "- `raw/` 为原始 JSON 响应，`excel/` 为页面可导出的表格文件",
        "- 主财务接口当前可回溯到 `2002年报/2003季报`，主营构成当前可回溯到 `2007年报/2008半年报` 左右，取决于页面本身提供范围",
        "",
        "下载文件：",
        "",
    ]
    for item in records:
        lines.append(f"- `{item['path']}`: `{item['slug']}`")
    lines.append("")
    (output_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="下载萝卜投研财务页数据")
    parser.add_argument("--ticker", default="600900")
    parser.add_argument(
        "--output-dir",
        default="/Users/luzuoguan/ai/value-investing/年报/长江电力-600900/萝卜投研-财务页下载",
    )
    args = parser.parse_args()

    cookie = os.environ.get("DATAYES_COOKIE", "").strip()
    if not cookie:
        raise SystemExit("缺少 DATAYES_COOKIE 环境变量")

    user_agent = os.environ.get("DATAYES_USER_AGENT", DEFAULT_USER_AGENT).strip() or DEFAULT_USER_AGENT
    output_dir = Path(args.output_dir)
    raw_dir = output_dir / "raw"
    excel_dir = output_dir / "excel"
    raw_dir.mkdir(parents=True, exist_ok=True)
    excel_dir.mkdir(parents=True, exist_ok=True)

    session = build_session(cookie=cookie, user_agent=user_agent)
    ticker = args.ticker

    records: list[dict[str, Any]] = []

    cards_base = f"https://gw.datayes.com/rrp_adventure/fdmtNew/{ticker}"
    cards_excel_base = f"https://gw.datayes.com/rrp_adventure/fdmtNew/excel/{ticker}"
    main_comp_base = f"https://gw.datayes.com/rrp_adventure/web/mainComposition/{ticker}"
    main_comp_excel_base = f"https://gw.datayes.com/rrp_adventure/web/mainComposition/excel/{ticker}"

    for item in json_downloads():
        target = output_dir / item.path_template
        target.parent.mkdir(parents=True, exist_ok=True)
        base_url = main_comp_base if item.slug == "main_composition_full_periods" else cards_base
        payload = request_json(session, base_url, item.params)
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        records.append(
            {
                "slug": item.slug,
                "kind": "json",
                "url": base_url,
                "params": item.params,
                "path": str(target.relative_to(output_dir)),
            }
        )

    for item in binary_downloads():
        target = output_dir / item.path_template
        target.parent.mkdir(parents=True, exist_ok=True)
        base_url = main_comp_excel_base if item.slug == "main_composition_excel" else cards_excel_base
        meta = download_binary(session, base_url, item.params, target)
        records.append(
            {
                "slug": item.slug,
                "kind": "excel",
                "url": base_url,
                "params": item.params,
                "path": str(target.relative_to(output_dir)),
                **meta,
            }
        )

    write_manifest(output_dir, records)
    write_readme(output_dir, records)
    print(f"已下载 {len(records)} 个文件到: {output_dir}")


if __name__ == "__main__":
    main()

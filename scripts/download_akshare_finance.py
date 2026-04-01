#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable

import pandas as pd

from value_investing_common import ensure_directory, project_root


try:
    import akshare as ak
except ImportError as exc:  # pragma: no cover
    raise SystemExit("缺少 akshare，请先在项目虚拟环境中安装 akshare") from exc


DataLoader = Callable[[], pd.DataFrame]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="下载 AKShare 财务数据，作为 Datayes 的备份/补充数据源")
    parser.add_argument("--ticker", default="600900")
    parser.add_argument("--company-name", default="长江电力")
    parser.add_argument("--industry-name", default="", help="可选，若提供则额外下载行业成分股")
    parser.add_argument(
        "--output-dir",
        default="",
        help="输出目录，默认写入 年报/<公司>-<代码>/AKShare-财务数据",
    )
    return parser.parse_args()


def safe_download(name: str, loader: DataLoader) -> tuple[pd.DataFrame | None, str | None]:
    try:
        return loader(), None
    except Exception as exc:  # pragma: no cover
        return None, str(exc)


def main() -> None:
    args = parse_args()
    output_dir = (
        Path(args.output_dir).resolve()
        if args.output_dir
        else project_root() / "年报" / f"{args.company_name}-{args.ticker}" / "AKShare-财务数据"
    )
    raw_dir = ensure_directory(output_dir / "raw")
    summary_dir = ensure_directory(output_dir / "整理")

    tasks: list[tuple[str, str, DataLoader]] = [
        ("利润表", "profit_statement.csv", lambda: ak.stock_financial_report_sina(stock=args.ticker, symbol="利润表")),
        ("资产负债表", "balance_sheet.csv", lambda: ak.stock_financial_report_sina(stock=args.ticker, symbol="资产负债表")),
        ("现金流量表", "cashflow_statement.csv", lambda: ak.stock_financial_report_sina(stock=args.ticker, symbol="现金流量表")),
        ("财务分析指标", "analysis_indicators.csv", lambda: ak.stock_financial_analysis_indicator(symbol=args.ticker)),
        ("个股基础信息", "stock_profile.csv", lambda: ak.stock_individual_info_em(symbol=args.ticker)),
    ]

    if args.industry_name:
        tasks.append(
            (
                "行业成分股",
                "industry_constituents.csv",
                lambda: ak.stock_board_industry_cons_em(symbol=args.industry_name),
            )
        )

    manifest: list[dict[str, object]] = []
    success_frames: dict[str, pd.DataFrame] = {}

    for display_name, filename, loader in tasks:
        frame, error = safe_download(display_name, loader)
        target = raw_dir / filename
        if frame is None:
            manifest.append(
                {
                    "name": display_name,
                    "path": str(target.relative_to(output_dir)),
                    "status": "failed",
                    "error": error,
                }
            )
            continue

        frame.to_csv(target, index=False, encoding="utf-8-sig")
        success_frames[display_name] = frame
        manifest.append(
            {
                "name": display_name,
                "path": str(target.relative_to(output_dir)),
                "status": "ok",
                "rows": int(len(frame)),
                "columns": list(frame.columns),
            }
        )

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    overview_rows = []
    for item in manifest:
        overview_rows.append(
            {
                "数据集": item["name"],
                "状态": item["status"],
                "行数": item.get("rows", "-"),
                "文件": item["path"],
            }
        )
    overview_df = pd.DataFrame(overview_rows)
    overview_df.to_excel(summary_dir / f"{args.company_name}-AKShare下载概览.xlsx", index=False)

    lines = [
        f"# {args.company_name} AKShare 财务数据说明",
        "",
        "说明：",
        "",
        f"- 股票代码：`{args.ticker}`",
        "- 数据源：AKShare 聚合接口（Sina / 东方财富等）",
        "- 目录说明：`raw/` 保存原始导出结果，`整理/` 保存概览工作簿",
        "",
        "下载结果：",
        "",
    ]
    for item in manifest:
        if item["status"] == "ok":
            lines.append(f"- ✅ {item['name']}：`{item['path']}`，共 `{item.get('rows', 0)}` 行")
        else:
            lines.append(f"- ⚠️ {item['name']}：下载失败，原因 `{item.get('error', 'unknown')}`")

    if success_frames:
        lines.extend([
            "",
            "可直接用于后续开发的优先数据：",
            "",
            "- `raw/analysis_indicators.csv`：财务分析指标，可作为 Datayes 指标备份",
            "- `raw/industry_constituents.csv`：若已下载，可用于同行对比样本池",
            "- 三大报表 CSV：可继续加工为统一字段口径",
            "",
        ])

    (output_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")

    print(f"已生成：{output_dir}")
    print(f"成功数据集：{sum(1 for item in manifest if item['status'] == 'ok')} / {len(manifest)}")


if __name__ == "__main__":
    main()

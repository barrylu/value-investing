#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from value_investing_common import dataframe_to_markdown, ensure_directory, project_root


try:  # pragma: no cover
    import plotly.graph_objects as go
except ImportError:  # pragma: no cover
    go = None


DEFAULT_METRICS = [
    "营收(亿元)",
    "归母净利润(亿元)",
    "ROE(%)",
    "ROIC(%)",
    "毛利率(%)",
    "净利率(%)",
    "资产负债率(%)",
    "经营现金流/净利润",
    "自由现金流(亿元)",
    "股息率(%)",
    "债务/EBITDA",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="基于年度比率结果做同行对比")
    parser.add_argument(
        "--company-dir",
        nargs="+",
        required=True,
        help="公司年报目录，例如 年报/长江电力-600900 年报/中国海油-600938",
    )
    parser.add_argument("--group-name", default="同行对比")
    parser.add_argument("--output-dir", default="", help="输出目录，默认写入 研究笔记/同行对比")
    return parser.parse_args()


def infer_company_name(company_dir: Path) -> str:
    if "-" in company_dir.name:
        return company_dir.name.rsplit("-", 1)[0]
    return company_dir.name


def load_latest_ratio_row(company_dir: Path) -> pd.Series:
    ratio_path = company_dir / "萝卜投研-财务页下载" / "整理" / "ratios" / "财务比率-年度.csv"
    if not ratio_path.exists():
        raise FileNotFoundError(f"缺少比率文件：{ratio_path}。请先运行 compute_financial_ratios.py")
    frame = pd.read_csv(ratio_path)
    if frame.empty:
        raise ValueError(f"比率文件为空：{ratio_path}")
    return frame.iloc[-1]


def rank_dataframe(frame: pd.DataFrame, metrics: list[str]) -> pd.DataFrame:
    ranking = frame[["公司", "期间"]].copy()
    for metric in metrics:
        ascending = metric in {"资产负债率(%)", "债务/EBITDA"}
        ranking[f"{metric}-排名"] = frame[metric].rank(ascending=ascending, method="min")
    return ranking


def build_radar_chart(frame: pd.DataFrame, metrics: list[str], output_path: Path) -> None:
    if go is None:
        return

    normalized = frame[["公司"] + metrics].copy()
    for metric in metrics:
        values = pd.to_numeric(normalized[metric], errors="coerce")
        if metric in {"资产负债率(%)", "债务/EBITDA"}:
            max_value = values.max()
            normalized[metric] = 1 - values / max_value if max_value else 0
        else:
            max_value = values.max()
            normalized[metric] = values / max_value if max_value else 0

    figure = go.Figure()
    categories = metrics + [metrics[0]]
    for _, row in normalized.iterrows():
        values = [row[metric] for metric in metrics]
        values.append(values[0])
        figure.add_trace(
            go.Scatterpolar(
                r=values,
                theta=categories,
                fill="toself",
                name=row["公司"],
            )
        )

    figure.update_layout(
        title="同行核心指标雷达图（已做同组归一化）",
        polar={"radialaxis": {"visible": True, "range": [0, 1]}},
        showlegend=True,
        template="plotly_white",
    )
    figure.write_html(output_path, include_plotlyjs="cdn", full_html=True)


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve() if args.output_dir else ensure_directory(project_root() / "研究笔记" / "同行对比")
    ensure_directory(output_dir)

    records: list[dict[str, object]] = []
    for raw_path in args.company_dir:
        company_dir = Path(raw_path).resolve()
        latest = load_latest_ratio_row(company_dir)
        record = {"公司": infer_company_name(company_dir), "期间": latest["期间"]}
        for metric in DEFAULT_METRICS:
            record[metric] = latest.get(metric)
        records.append(record)

    comparison_df = pd.DataFrame(records).sort_values(by=["ROE(%)", "ROIC(%)"], ascending=False).reset_index(drop=True)
    ranking_df = rank_dataframe(comparison_df, DEFAULT_METRICS)

    report_name = f"同行对比-{args.group_name}.md"
    report_path = output_dir / report_name
    workbook_path = output_dir / f"同行对比-{args.group_name}.xlsx"
    radar_path = output_dir / f"同行对比-{args.group_name}.html"

    with pd.ExcelWriter(workbook_path, engine="openpyxl") as writer:
        comparison_df.to_excel(writer, sheet_name="最新指标", index=False)
        ranking_df.to_excel(writer, sheet_name="排名", index=False)

    build_radar_chart(comparison_df, ["ROE(%)", "ROIC(%)", "毛利率(%)", "净利率(%)", "股息率(%)", "经营现金流/净利润"], radar_path)

    lines = [
        f"# {args.group_name} 同行对比",
        "",
        "## 最新年度核心指标",
        "",
        dataframe_to_markdown(comparison_df, digits=2),
        "",
        "## 指标排名",
        "",
        dataframe_to_markdown(ranking_df, digits=0),
        "",
        "## 读表提示",
        "",
        "- `资产负债率` 与 `债务/EBITDA` 排名按数值越低越靠前。",
        "- 其余指标默认按数值越高越靠前。",
        "- 若已安装 Plotly，还会附带一份归一化雷达图 HTML。",
        "",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"已生成：{report_path}")
    print(f"已生成：{workbook_path}")
    if radar_path.exists():
        print(f"已生成：{radar_path}")


if __name__ == "__main__":
    main()

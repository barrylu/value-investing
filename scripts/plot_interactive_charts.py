#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from value_investing_common import company_name_from_slug, company_slug_from_datayes_base, data_output_dir_for_base, ensure_directory


try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
except ImportError as exc:  # pragma: no cover
    raise SystemExit("缺少 plotly，请先在项目虚拟环境中安装 plotly 和 kaleido") from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="基于年度财务比率输出交互式 Plotly 图表")
    parser.add_argument(
        "--base-dir",
        default=str(
            Path(__file__).resolve().parents[1]
            / "年报"
            / "长江电力-600900"
            / "萝卜投研-财务页下载"
        ),
        help="Datayes 下载目录或其整理目录",
    )
    parser.add_argument("--company-name", default="", help="公司名称，默认从目录名推断")
    parser.add_argument("--output-dir", default="", help="输出目录，默认写入 整理/charts/interactive")
    return parser.parse_args()


def load_annual_ratios(base_dir: str | Path) -> pd.DataFrame:
    path = data_output_dir_for_base(base_dir) / "ratios" / "财务比率-年度.csv"
    if not path.exists():
        raise FileNotFoundError(f"缺少年度比率文件：{path}。请先运行 scripts/compute_financial_ratios.py")
    frame = pd.read_csv(path)
    if frame.empty:
        raise ValueError("年度比率文件为空")
    return frame


def add_line(fig: go.Figure, x, y, *, row: int, col: int, name: str, color: str) -> None:
    fig.add_trace(
        go.Scatter(x=x, y=y, mode="lines+markers", name=name, line={"color": color, "width": 2.4}),
        row=row,
        col=col,
    )


def main() -> None:
    args = parse_args()
    slug = company_slug_from_datayes_base(args.base_dir)
    company_name = args.company_name or company_name_from_slug(slug)

    annual = load_annual_ratios(args.base_dir)
    years = annual["期间"].astype(str).str.slice(0, 4)

    fig = make_subplots(
        rows=3,
        cols=2,
        subplot_titles=(
            "营收与归母净利润",
            "经营现金流、资本开支与自由现金流",
            "ROE / ROA / ROIC",
            "资产负债率与债务/EBITDA",
            "毛利率 / 净利率 / 股息率",
            "每股指标",
        ),
        specs=[[{"secondary_y": True}, {"secondary_y": False}], [{"secondary_y": False}, {"secondary_y": True}], [{"secondary_y": False}, {"secondary_y": False}]],
        vertical_spacing=0.12,
        horizontal_spacing=0.08,
    )

    fig.add_trace(
        go.Bar(x=years, y=annual["营收(亿元)"], name="营收", marker_color="#4C78A8"),
        row=1,
        col=1,
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(x=years, y=annual["归母净利润(亿元)"], mode="lines+markers", name="归母净利润", line={"color": "#E45756", "width": 2.4}),
        row=1,
        col=1,
        secondary_y=True,
    )

    fig.add_trace(go.Bar(x=years, y=annual["经营现金流(亿元)"], name="经营现金流", marker_color="#59A14F"), row=1, col=2)
    fig.add_trace(go.Bar(x=years, y=annual["资本开支(亿元)"], name="资本开支", marker_color="#F28E2B"), row=1, col=2)
    add_line(fig, years, annual["自由现金流(亿元)"], row=1, col=2, name="自由现金流", color="#E15759")

    add_line(fig, years, annual["ROE(%)"], row=2, col=1, name="ROE", color="#E15759")
    add_line(fig, years, annual["ROA(%)"], row=2, col=1, name="ROA", color="#4E79A7")
    add_line(fig, years, annual["ROIC(%)"], row=2, col=1, name="ROIC", color="#59A14F")

    add_line(fig, years, annual["资产负债率(%)"], row=2, col=2, name="资产负债率", color="#9C755F")
    fig.add_trace(
        go.Scatter(x=years, y=annual["债务/EBITDA"], mode="lines+markers", name="债务/EBITDA", line={"color": "#76B7B2", "width": 2.4}),
        row=2,
        col=2,
        secondary_y=True,
    )

    add_line(fig, years, annual["毛利率(%)"], row=3, col=1, name="毛利率", color="#4C78A8")
    add_line(fig, years, annual["净利率(%)"], row=3, col=1, name="净利率", color="#E15759")
    add_line(fig, years, annual["股息率(%)"], row=3, col=1, name="股息率", color="#59A14F")

    add_line(fig, years, annual["每股收益"], row=3, col=2, name="每股收益", color="#4C78A8")
    add_line(fig, years, annual["每股净资产"], row=3, col=2, name="每股净资产", color="#F28E2B")
    add_line(fig, years, annual["每股自由现金流"], row=3, col=2, name="每股自由现金流", color="#E15759")

    fig.update_layout(
        height=1150,
        title=f"{company_name} 财务分析交互式仪表盘",
        template="plotly_white",
        hovermode="x unified",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "left", "x": 0},
        margin={"l": 60, "r": 60, "t": 90, "b": 50},
    )

    fig.update_yaxes(title_text="营收（亿元）", row=1, col=1, secondary_y=False)
    fig.update_yaxes(title_text="归母净利润（亿元）", row=1, col=1, secondary_y=True)
    fig.update_yaxes(title_text="金额（亿元）", row=1, col=2)
    fig.update_yaxes(title_text="比例（%）", row=2, col=1)
    fig.update_yaxes(title_text="资产负债率（%）", row=2, col=2, secondary_y=False)
    fig.update_yaxes(title_text="倍数", row=2, col=2, secondary_y=True)
    fig.update_yaxes(title_text="比例（%）", row=3, col=1)
    fig.update_yaxes(title_text="每股金额（元）", row=3, col=2)

    output_dir = Path(args.output_dir).resolve() if args.output_dir else ensure_directory(data_output_dir_for_base(args.base_dir) / "charts" / "interactive")
    ensure_directory(output_dir)
    output_path = output_dir / f"{company_name}-交互式财务仪表盘.html"
    fig.write_html(output_path, include_plotlyjs="cdn", full_html=True)

    print(f"已生成：{output_path}")


if __name__ == "__main__":
    main()

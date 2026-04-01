#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from value_investing_common import (
    company_name_from_slug,
    company_slug_from_datayes_base,
    data_output_dir_for_base,
    dataframe_to_markdown,
    ensure_directory,
    format_number,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="基于年度财务比率结果生成估值模型")
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
    parser.add_argument("--growth-rate", type=float, default=0.05, help="未来 1-N 年自由现金流年化增长率")
    parser.add_argument("--discount-rate", type=float, default=0.10, help="折现率")
    parser.add_argument("--terminal-growth-rate", type=float, default=0.02, help="永续增长率")
    parser.add_argument("--forecast-years", type=int, default=10, help="显式预测年数")
    parser.add_argument(
        "--fcf-base",
        choices=["latest", "avg3", "median3"],
        default="avg3",
        help="自由现金流基期取值方式",
    )
    parser.add_argument("--current-price", type=float, default=None, help="当前股价，可选")
    parser.add_argument("--pe-range", default="", help="相对估值用 PE 区间，例如 12,15,18")
    parser.add_argument("--pb-range", default="", help="相对估值用 PB 区间，例如 1.2,1.5,1.8")
    parser.add_argument("--output-dir", default="", help="输出目录，默认写入 整理/valuation")
    return parser.parse_args()


def load_annual_ratios(base_dir: str | Path) -> pd.DataFrame:
    path = data_output_dir_for_base(base_dir) / "ratios" / "财务比率-年度.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"缺少年度比率文件：{path}。请先运行 scripts/compute_financial_ratios.py"
        )
    frame = pd.read_csv(path)
    if frame.empty:
        raise ValueError("年度比率文件为空，无法生成估值结果")
    return frame


def parse_range(raw: str) -> list[float]:
    if not raw.strip():
        return []
    values = [float(item.strip()) for item in raw.split(",") if item.strip()]
    return sorted(values)


def pick_base_fcf(series: pd.Series, mode: str) -> float:
    valid = series.dropna()
    if valid.empty:
        raise ValueError("没有可用于估值的自由现金流数据")
    if mode == "latest":
        return float(valid.iloc[-1])
    tail = valid.tail(3)
    if mode == "median3":
        return float(tail.median())
    return float(tail.mean())


def build_dcf_forecast(base_fcf: float, growth_rate: float, discount_rate: float, terminal_growth_rate: float, forecast_years: int) -> tuple[pd.DataFrame, float, float]:
    rows: list[dict[str, float]] = []
    for year in range(1, forecast_years + 1):
        projected_fcf = base_fcf * ((1 + growth_rate) ** year)
        discount_factor = 1 / ((1 + discount_rate) ** year)
        present_value = projected_fcf * discount_factor
        rows.append(
            {
                "预测年": year,
                "自由现金流(亿元)": projected_fcf,
                "折现因子": discount_factor,
                "现值(亿元)": present_value,
            }
        )
    last_fcf = rows[-1]["自由现金流(亿元)"]
    terminal_value = last_fcf * (1 + terminal_growth_rate) / (discount_rate - terminal_growth_rate)
    terminal_present_value = terminal_value / ((1 + discount_rate) ** forecast_years)
    return pd.DataFrame(rows), terminal_value, terminal_present_value


def build_sensitivity_matrix(base_fcf: float, discount_rate: float, growth_rate: float, terminal_growth_rate: float, forecast_years: int, shares_outstanding: float | None) -> pd.DataFrame:
    discount_candidates = [discount_rate - 0.02, discount_rate - 0.01, discount_rate, discount_rate + 0.01, discount_rate + 0.02]
    growth_candidates = [growth_rate - 0.02, growth_rate - 0.01, growth_rate, growth_rate + 0.01, growth_rate + 0.02]

    safe_discounts = [value for value in discount_candidates if value > terminal_growth_rate + 0.005]
    safe_growths = growth_candidates

    rows: list[dict[str, float | str]] = []
    for discount in safe_discounts:
        row: dict[str, float | str] = {"折现率\\增长率": f"{discount:.1%}"}
        for growth in safe_growths:
            _, _, terminal_pv = build_dcf_forecast(base_fcf, growth, discount, terminal_growth_rate, forecast_years)
            forecast_df, _, _ = build_dcf_forecast(base_fcf, growth, discount, terminal_growth_rate, forecast_years)
            equity_value = float(forecast_df["现值(亿元)"].sum() + terminal_pv)
            row[f"{growth:.1%}"] = equity_value / shares_outstanding if shares_outstanding else equity_value
        rows.append(row)
    return pd.DataFrame(rows)


def build_relative_valuation(latest_row: pd.Series, pe_range: list[float], pb_range: list[float]) -> pd.DataFrame:
    records: list[dict[str, float | str]] = []
    eps = latest_row.get("每股收益")
    bps = latest_row.get("每股净资产")

    if pe_range and pd.notna(eps):
        for multiple in pe_range:
            records.append(
                {
                    "方法": "PE",
                    "倍数": multiple,
                    "基础值": float(eps),
                    "估算每股价值": float(eps) * multiple,
                }
            )

    if pb_range and pd.notna(bps):
        for multiple in pb_range:
            records.append(
                {
                    "方法": "PB",
                    "倍数": multiple,
                    "基础值": float(bps),
                    "估算每股价值": float(bps) * multiple,
                }
            )

    return pd.DataFrame(records)


def main() -> None:
    args = parse_args()
    slug = company_slug_from_datayes_base(args.base_dir)
    company_name = args.company_name or company_name_from_slug(slug)

    if args.discount_rate <= args.terminal_growth_rate:
        raise SystemExit("折现率必须大于永续增长率")

    annual_ratios = load_annual_ratios(args.base_dir)
    latest_row = annual_ratios.iloc[-1]
    base_fcf = pick_base_fcf(annual_ratios["自由现金流(亿元)"], args.fcf_base)
    shares_outstanding = latest_row.get("估算总股本(亿股)")
    shares_outstanding = float(shares_outstanding) if pd.notna(shares_outstanding) and shares_outstanding else None

    forecast_df, terminal_value, terminal_pv = build_dcf_forecast(
        base_fcf,
        args.growth_rate,
        args.discount_rate,
        args.terminal_growth_rate,
        args.forecast_years,
    )
    explicit_value = float(forecast_df["现值(亿元)"].sum())
    total_equity_value = explicit_value + terminal_pv
    intrinsic_value_per_share = total_equity_value / shares_outstanding if shares_outstanding else None

    pe_range = parse_range(args.pe_range)
    pb_range = parse_range(args.pb_range)
    relative_df = build_relative_valuation(latest_row, pe_range, pb_range)
    sensitivity_df = build_sensitivity_matrix(
        base_fcf,
        args.discount_rate,
        args.growth_rate,
        args.terminal_growth_rate,
        args.forecast_years,
        shares_outstanding,
    )

    output_dir = Path(args.output_dir).resolve() if args.output_dir else ensure_directory(data_output_dir_for_base(args.base_dir) / "valuation")
    ensure_directory(output_dir)

    latest_period = str(latest_row["期间"])
    report_path = output_dir / f"估值报告-{company_name}-{latest_period}.md"
    workbook_path = output_dir / f"估值敏感性矩阵-{company_name}-{latest_period}.xlsx"

    summary_df = pd.DataFrame(
        [
            {"项目": "估值基期", "数值": latest_period},
            {"项目": "FCF 基期(亿元)", "数值": base_fcf},
            {"项目": "显式预测期现值(亿元)", "数值": explicit_value},
            {"项目": "终值现值(亿元)", "数值": terminal_pv},
            {"项目": "DCF 股权价值(亿元)", "数值": total_equity_value},
            {"项目": "估算总股本(亿股)", "数值": shares_outstanding},
            {"项目": "DCF 每股内在价值(元)", "数值": intrinsic_value_per_share},
        ]
    )

    with pd.ExcelWriter(workbook_path, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="估值摘要", index=False)
        forecast_df.to_excel(writer, sheet_name="DCF预测", index=False)
        sensitivity_df.to_excel(writer, sheet_name="敏感性矩阵", index=False)
        if not relative_df.empty:
            relative_df.to_excel(writer, sheet_name="相对估值", index=False)

    latest_snapshot = annual_ratios.tail(5)[
        [
            "期间",
            "营收(亿元)",
            "归母净利润(亿元)",
            "自由现金流(亿元)",
            "ROE(%)",
            "ROIC(%)",
            "资产负债率(%)",
            "股息率(%)",
        ]
    ].copy()

    lines = [
        f"# {company_name} 估值报告",
        "",
        "## 估值假设",
        "",
        f"- 基期口径：`{latest_period}`",
        f"- FCF 基期取值方式：`{args.fcf_base}`",
        f"- 未来增长率：`{args.growth_rate:.2%}`",
        f"- 折现率：`{args.discount_rate:.2%}`",
        f"- 永续增长率：`{args.terminal_growth_rate:.2%}`",
        f"- 显式预测期：`{args.forecast_years}` 年",
        "",
        "## 最近五年经营快照",
        "",
        dataframe_to_markdown(latest_snapshot, digits=2),
        "",
        "## DCF 结果",
        "",
        f"- FCF 基期（亿元）：`{format_number(base_fcf)}`",
        f"- 显式预测期现值（亿元）：`{format_number(explicit_value)}`",
        f"- 终值现值（亿元）：`{format_number(terminal_pv)}`",
        f"- DCF 股权价值（亿元）：`{format_number(total_equity_value)}`",
        f"- 估算总股本（亿股）：`{format_number(shares_outstanding)}`" if shares_outstanding else "- 估算总股本：`无法可靠推断`",
        f"- DCF 每股内在价值（元）：`{format_number(intrinsic_value_per_share)}`" if intrinsic_value_per_share else "- DCF 每股内在价值：`无法计算`",
    ]

    if args.current_price and intrinsic_value_per_share:
        margin = intrinsic_value_per_share / args.current_price - 1
        lines.append(f"- 相对当前价格 `{args.current_price:.2f}` 的安全边际：`{margin:.2%}`")

    lines.extend([
        "",
        "## DCF 预测明细",
        "",
        dataframe_to_markdown(forecast_df, digits=2),
        "",
    ])

    if not relative_df.empty:
        lines.extend(
            [
                "## 相对估值区间",
                "",
                dataframe_to_markdown(relative_df, digits=2),
                "",
            ]
        )
    else:
        lines.extend(
            [
                "## 相对估值区间",
                "",
                "- 未提供 `--pe-range` / `--pb-range` 参数，本次仅输出 DCF 框架。",
                "",
            ]
        )

    lines.extend(
        [
            "## 敏感性分析",
            "",
            "下表默认展示 `折现率 × 增长率` 组合下的每股估值（若无法估算股本，则为总股权价值，单位亿元）。",
            "",
            dataframe_to_markdown(sensitivity_df, digits=2),
            "",
            "## 使用建议",
            "",
            "- 先把 DCF 当作范围估值工具，而不是点估值工具。",
            "- 对于重资产、高分红公司，建议和股息率、ROIC、资产负债率一起看。",
            "- 若后续补入市场价格历史，可在本脚本基础上继续接 PE/PB 百分位模型。",
            "",
        ]
    )

    report_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"已生成：{report_path}")
    print(f"已生成：{workbook_path}")
    if intrinsic_value_per_share is not None:
        print(f"DCF 每股内在价值：{intrinsic_value_per_share:.2f} 元")


if __name__ == "__main__":
    main()

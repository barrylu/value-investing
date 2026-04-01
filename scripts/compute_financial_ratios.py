#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import pandas as pd

from value_investing_common import (
    company_name_from_slug,
    company_slug_from_datayes_base,
    csv_dir_for_base,
    data_output_dir_for_base,
    dataframe_to_markdown,
    divide_series,
    ensure_directory,
    filter_periods,
    format_number,
    load_statement,
    pct_change,
    rolling_average,
    series_from_candidates,
    sort_periods,
)

YI = 100_000_000.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="基于 Datayes 标准化 CSV 计算财务比率")
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
    parser.add_argument("--min-year", type=int, default=None)
    parser.add_argument("--max-year", type=int, default=None)
    parser.add_argument(
        "--output-dir",
        default="",
        help="输出目录，默认写入 萝卜投研-财务页下载/整理/ratios",
    )
    return parser.parse_args()


def configure_matplotlib() -> None:
    preferred_fonts = [
        "PingFang SC",
        "Hiragino Sans GB",
        "Microsoft YaHei",
        "SimHei",
        "Arial Unicode MS",
        "Noto Sans CJK SC",
    ]
    installed = {font.name for font in fm.fontManager.ttflist}
    for font_name in preferred_fonts:
        if font_name in installed:
            matplotlib.rcParams["font.sans-serif"] = [font_name]
            break
    matplotlib.rcParams["axes.unicode_minus"] = False


def infer_money_divisor_to_yi(revenue_series: pd.Series) -> float:
    valid = revenue_series.dropna().abs()
    if valid.empty:
        return YI
    return YI if float(valid.median()) > 1_000_000 else 1.0


def build_ratio_frame(periods: list[str], summary: pd.DataFrame, balance: pd.DataFrame, cashflow: pd.DataFrame, indicators: pd.DataFrame) -> pd.DataFrame:
    revenue = series_from_candidates(summary, periods, code_candidates=["tRevenue", "revenue"])
    cogs = series_from_candidates(summary, periods, code_candidates=["COGS"])
    operating_profit = series_from_candidates(summary, periods, code_candidates=["operateProfit"])
    net_profit = series_from_candidates(summary, periods, code_candidates=["NIncomeAttrP", "NIncome"])
    ebit = series_from_candidates(summary, periods, code_candidates=["EBIT"])
    ebitda = series_from_candidates(summary, periods, code_candidates=["EBITDA"])
    total_assets = series_from_candidates(balance, periods, code_candidates=["tAssets"])
    total_liabilities = series_from_candidates(balance, periods, code_candidates=["tLiab"])
    equity = series_from_candidates(balance, periods, code_candidates=["tEquityAttrP", "tShEquity"])
    cash = series_from_candidates(balance, periods, code_candidates=["cashCEquiv"])
    current_assets = series_from_candidates(balance, periods, code_candidates=["tCa"])
    inventories = series_from_candidates(balance, periods, code_candidates=["inventories"])
    short_borrowings = series_from_candidates(balance, periods, code_candidates=["stBorr"])
    long_borrowings = series_from_candidates(balance, periods, code_candidates=["ltBorr"])
    bonds_payable = series_from_candidates(balance, periods, code_candidates=["bondPayable"], contains_names=["应付债券"])

    ocf = series_from_candidates(cashflow, periods, code_candidates=["NCFOperateA"])
    capex = series_from_candidates(cashflow, periods, code_candidates=["purFixAssetsOth"])

    eps = series_from_candidates(indicators, periods, code_candidates=["basicEps", "eps"])
    bps = series_from_candidates(indicators, periods, code_candidates=["nAssetPs"])
    ocf_ps = series_from_candidates(indicators, periods, code_candidates=["nCFOperAPs"])
    fcff_ps = series_from_candidates(indicators, periods, code_candidates=["fcffPs"])
    fcfe_ps = series_from_candidates(indicators, periods, code_candidates=["fcfePs"])

    money_divisor_to_yi = infer_money_divisor_to_yi(revenue)
    shares_divisor_to_yi = money_divisor_to_yi

    gross_margin_pct = divide_series(revenue - cogs, revenue, scale=100.0)
    operating_margin_pct = divide_series(operating_profit, revenue, scale=100.0)
    net_margin_pct = divide_series(net_profit, revenue, scale=100.0)

    average_assets = rolling_average(total_assets).fillna(total_assets)
    average_equity = rolling_average(equity).fillna(equity)
    asset_turnover = divide_series(revenue, average_assets)
    equity_multiplier = divide_series(average_assets, average_equity)
    dupont_roe_pct = (net_margin_pct / 100.0) * asset_turnover * equity_multiplier * 100.0

    debt_ratio_pct = divide_series(total_liabilities, total_assets, scale=100.0)
    current_ratio = series_from_candidates(summary, periods, code_candidates=["currentRatio"])
    quick_ratio = series_from_candidates(summary, periods, code_candidates=["quickRatio"])

    interest_expense = series_from_candidates(
        load_statement_cache_profit,
        periods,
        code_candidates=["intExpFinanExp", "intExp"],
        contains_names=["利息费用"],
    )

    interest_bearing_debt = short_borrowings.fillna(0) + long_borrowings.fillna(0) + bonds_payable.fillna(0)
    debt_to_ebitda = divide_series(interest_bearing_debt, ebitda)
    interest_coverage = divide_series(ebit, interest_expense)

    fcf = ocf - capex
    depreciation_amortization = ebitda - ebit
    ocf_to_net_profit = divide_series(ocf, net_profit)
    fcf_margin_pct = divide_series(fcf, revenue, scale=100.0)
    capex_to_revenue_pct = divide_series(capex, revenue, scale=100.0)
    capex_to_da = divide_series(capex, depreciation_amortization)

    revenue_growth_pct = pct_change(revenue)
    net_profit_growth_pct = pct_change(net_profit)
    ocf_growth_pct = pct_change(ocf)

    roe_pct = series_from_candidates(summary, periods, code_candidates=["ROE", "ROEW"])
    roa_pct = series_from_candidates(summary, periods, code_candidates=["ROA"])
    roic_pct = series_from_candidates(summary, periods, code_candidates=["ROIC"])
    div_yield_pct = series_from_candidates(summary, periods, code_candidates=["divRatio"])

    shares_from_bps = divide_series(equity, bps)
    shares_from_eps = divide_series(net_profit, eps)
    shares_est = pd.concat([shares_from_bps, shares_from_eps], axis=1).mean(axis=1, skipna=True)
    fallback_fcf_ps = divide_series(fcf, shares_est)
    fcf_ps = fcfe_ps.fillna(fcff_ps).fillna(fallback_fcf_ps)

    ratio_frame = pd.DataFrame(
        {
            "期间": periods,
            "营收(亿元)": revenue / money_divisor_to_yi,
            "营业成本(亿元)": cogs / money_divisor_to_yi,
            "营业利润(亿元)": operating_profit / money_divisor_to_yi,
            "归母净利润(亿元)": net_profit / money_divisor_to_yi,
            "总资产(亿元)": total_assets / money_divisor_to_yi,
            "总负债(亿元)": total_liabilities / money_divisor_to_yi,
            "归母权益(亿元)": equity / money_divisor_to_yi,
            "货币资金(亿元)": cash / money_divisor_to_yi,
            "有息负债(亿元)": interest_bearing_debt / money_divisor_to_yi,
            "经营现金流(亿元)": ocf / money_divisor_to_yi,
            "资本开支(亿元)": capex / money_divisor_to_yi,
            "自由现金流(亿元)": fcf / money_divisor_to_yi,
            "毛利率(%)": gross_margin_pct,
            "营业利润率(%)": operating_margin_pct,
            "净利率(%)": net_margin_pct,
            "ROE(%)": roe_pct,
            "ROA(%)": roa_pct,
            "ROIC(%)": roic_pct,
            "杜邦ROE(%)": dupont_roe_pct,
            "资产周转率": asset_turnover,
            "权益乘数": equity_multiplier,
            "资产负债率(%)": debt_ratio_pct,
            "流动比率": current_ratio,
            "速动比率": quick_ratio,
            "债务/EBITDA": debt_to_ebitda,
            "利息保障倍数": interest_coverage,
            "经营现金流/净利润": ocf_to_net_profit,
            "FCF利润率(%)": fcf_margin_pct,
            "资本开支/营收(%)": capex_to_revenue_pct,
            "资本开支/折旧摊销": capex_to_da,
            "营收同比(%)": revenue_growth_pct,
            "归母净利润同比(%)": net_profit_growth_pct,
            "经营现金流同比(%)": ocf_growth_pct,
            "每股收益": eps,
            "每股净资产": bps,
            "每股经营现金流": ocf_ps,
            "每股自由现金流": fcf_ps,
            "股息率(%)": div_yield_pct,
            "估算总股本(亿股)": shares_est / shares_divisor_to_yi,
        }
    )
    return ratio_frame


def style_axis(ax: plt.Axes, title: str, ylabel: str) -> None:
    ax.set_title(title, fontsize=13, pad=12)
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", linestyle="--", alpha=0.25)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def save_chart(fig: plt.Figure, path: Path) -> None:
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def clean_plot_series(values: pd.Series, *, max_abs: float | None = None) -> pd.Series:
    series = pd.to_numeric(values, errors="coerce").replace([float("inf"), float("-inf")], pd.NA)
    if max_abs is not None:
        series = series.where(series.abs() <= max_abs)
    return series


def build_ratio_charts(company_name: str, annual_frame: pd.DataFrame, output_dir: Path) -> list[str]:
    configure_matplotlib()
    ensure_directory(output_dir)
    years = [str(period)[:4] for period in annual_frame["期间"]]
    files: list[str] = []

    fig, ax1 = plt.subplots(figsize=(11, 5))
    revenue = clean_plot_series(annual_frame["营收(亿元)"], max_abs=1_000_000)
    profit = clean_plot_series(annual_frame["归母净利润(亿元)"], max_abs=1_000_000)
    bars = ax1.bar(years, revenue, color="#4C78A8", alpha=0.9)
    style_axis(ax1, f"{company_name}年度营收与归母净利润", "营收（亿元）")
    ax2 = ax1.twinx()
    ax2.plot(years, profit, color="#E45756", marker="o", linewidth=2.2)
    ax2.set_ylabel("归母净利润（亿元）", color="#E45756")
    ax2.tick_params(axis="y", labelcolor="#E45756")
    for rect, value in zip(bars, revenue):
        if pd.notna(value):
            ax1.text(rect.get_x() + rect.get_width() / 2, rect.get_height() + 2, f"{value:.0f}", ha="center", va="bottom", fontsize=8)
    chart_name = "01-年度营收与归母净利润.png"
    save_chart(fig, output_dir / chart_name)
    files.append(chart_name)

    fig, ax = plt.subplots(figsize=(11, 5))
    ocf = clean_plot_series(annual_frame["经营现金流(亿元)"], max_abs=1_000_000)
    capex = clean_plot_series(annual_frame["资本开支(亿元)"], max_abs=1_000_000)
    fcf = clean_plot_series(annual_frame["自由现金流(亿元)"], max_abs=1_000_000)
    x = range(len(years))
    width = 0.28
    ax.bar([item - width for item in x], ocf, width=width, color="#59A14F", label="经营现金流")
    ax.bar(x, capex, width=width, color="#F28E2B", label="资本开支")
    ax.bar([item + width for item in x], fcf, width=width, color="#E15759", label="自由现金流")
    ax.set_xticks(list(x))
    ax.set_xticklabels(years)
    style_axis(ax, "年度经营现金流、资本开支与自由现金流", "金额（亿元）")
    ax.legend(frameon=False, ncol=3)
    chart_name = "02-年度现金流与资本开支.png"
    save_chart(fig, output_dir / chart_name)
    files.append(chart_name)

    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(years, clean_plot_series(annual_frame["ROE(%)"], max_abs=100), marker="o", linewidth=2.2, label="ROE")
    ax.plot(years, clean_plot_series(annual_frame["ROA(%)"], max_abs=100), marker="o", linewidth=2.2, label="ROA")
    ax.plot(years, clean_plot_series(annual_frame["ROIC(%)"], max_abs=100), marker="o", linewidth=2.2, label="ROIC")
    style_axis(ax, "年度回报率指标", "比例（%）")
    ax.legend(frameon=False, ncol=3)
    chart_name = "03-年度回报率指标.png"
    save_chart(fig, output_dir / chart_name)
    files.append(chart_name)

    fig, ax1 = plt.subplots(figsize=(11, 5))
    ax1.plot(years, clean_plot_series(annual_frame["资产负债率(%)"], max_abs=100), marker="o", linewidth=2.2, color="#4E79A7", label="资产负债率")
    style_axis(ax1, "年度杠杆与偿债指标", "资产负债率（%）")
    ax2 = ax1.twinx()
    ax2.plot(years, clean_plot_series(annual_frame["债务/EBITDA"], max_abs=20), marker="s", linewidth=2.0, color="#9C755F", label="债务/EBITDA")
    ax2.plot(years, clean_plot_series(annual_frame["流动比率"], max_abs=10), marker="^", linewidth=2.0, color="#76B7B2", label="流动比率")
    ax2.set_ylabel("倍数")
    lines = ax1.get_lines() + ax2.get_lines()
    labels = [line.get_label() for line in lines]
    ax1.legend(lines, labels, frameon=False, ncol=3)
    chart_name = "04-年度杠杆与偿债指标.png"
    save_chart(fig, output_dir / chart_name)
    files.append(chart_name)

    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(years, clean_plot_series(annual_frame["毛利率(%)"], max_abs=100), marker="o", linewidth=2.2, label="毛利率")
    ax.plot(years, clean_plot_series(annual_frame["净利率(%)"], max_abs=100), marker="o", linewidth=2.2, label="净利率")
    ax.plot(years, clean_plot_series(annual_frame["股息率(%)"], max_abs=20), marker="o", linewidth=2.2, label="股息率")
    style_axis(ax, "年度利润率与股息率", "比例（%）")
    ax.legend(frameon=False, ncol=3)
    chart_name = "05-年度利润率与股息率.png"
    save_chart(fig, output_dir / chart_name)
    files.append(chart_name)

    return files


def write_readme(company_name: str, output_dir: Path, annual_frame: pd.DataFrame, chart_files: list[str]) -> None:
    preview = annual_frame.tail(8)[
        [
            "期间",
            "营收(亿元)",
            "归母净利润(亿元)",
            "ROE(%)",
            "ROIC(%)",
            "资产负债率(%)",
            "经营现金流/净利润",
            "股息率(%)",
        ]
    ].copy()
    readme_lines = [
        f"# {company_name} 财务比率说明",
        "",
        "说明：",
        "",
        f"- 输入目录：`{csv_dir_for_base(args_cache.base_dir)}`",
        "- 口径：优先基于 Datayes 标准化 CSV 自行计算；少数已存在的标准指标（如 ROE、ROA、ROIC、股息率）直接复用财务摘要/关键指标字段",
        "- 金额类输出统一换算为 `亿元`，每股类保持 `元/股`",
        "",
        "输出文件：",
        "",
        "- `财务比率-全期间.csv`：包含年报 + 中报/季报的全期间结果",
        "- `财务比率-年度.csv`：仅保留年度口径，适合长期研究与估值输入",
        "- `财务比率分析.xlsx`：便于在 Excel 中继续加工",
        "- `charts/*.png`：年度趋势图",
        "",
        "年度核心字段预览：",
        "",
        dataframe_to_markdown(preview, digits=2),
        "",
        "已生成图表：",
        "",
    ]
    for chart_name in chart_files:
        readme_lines.append(f"- `{chart_name}`")
    readme_lines.append("")
    (output_dir / "README.md").write_text("\n".join(readme_lines), encoding="utf-8")


load_statement_cache_profit: pd.DataFrame
args_cache: argparse.Namespace


def main() -> None:
    global load_statement_cache_profit, args_cache
    args = parse_args()
    args_cache = args

    slug = company_slug_from_datayes_base(args.base_dir)
    company_name = args.company_name or company_name_from_slug(slug)
    output_dir = Path(args.output_dir).resolve() if args.output_dir else data_output_dir_for_base(args.base_dir) / "ratios"
    chart_dir = ensure_directory(output_dir / "charts")

    summary = load_statement(args.base_dir, "财务摘要")
    balance = load_statement(args.base_dir, "资产负债表")
    cashflow = load_statement(args.base_dir, "现金流量表")
    indicators = load_statement(args.base_dir, "关键指标")
    load_statement_cache_profit = load_statement(args.base_dir, "利润表")

    full_periods = filter_periods(sort_periods(summary.columns), min_year=args.min_year, max_year=args.max_year)
    annual_periods = filter_periods(sort_periods(summary.columns, annual_only=True), min_year=args.min_year, max_year=args.max_year)
    if not full_periods:
        raise SystemExit("未找到可计算的期间列")

    full_frame = build_ratio_frame(full_periods, summary, balance, cashflow, indicators)
    annual_frame = build_ratio_frame(annual_periods, summary, balance, cashflow, indicators)

    ensure_directory(output_dir)
    full_csv_path = output_dir / "财务比率-全期间.csv"
    annual_csv_path = output_dir / "财务比率-年度.csv"
    xlsx_path = output_dir / "财务比率分析.xlsx"

    full_frame.to_csv(full_csv_path, index=False, encoding="utf-8-sig")
    annual_frame.to_csv(annual_csv_path, index=False, encoding="utf-8-sig")
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        annual_frame.to_excel(writer, sheet_name="年度比率", index=False)
        full_frame.to_excel(writer, sheet_name="全期间比率", index=False)

    chart_files = build_ratio_charts(company_name, annual_frame, chart_dir)
    write_readme(company_name, output_dir, annual_frame, chart_files)

    latest = annual_frame.iloc[-1]
    print(f"已生成目录：{output_dir}")
    print(
        "最新年度摘要："
        f"营收={format_number(latest['营收(亿元)'])}亿元，"
        f"归母净利润={format_number(latest['归母净利润(亿元)'])}亿元，"
        f"ROE={format_number(latest['ROE(%)'])}%，"
        f"自由现金流={format_number(latest['自由现金流(亿元)'])}亿元。"
    )


if __name__ == "__main__":
    main()

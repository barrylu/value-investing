#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path

import matplotlib
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import pandas as pd


BASE_DIR = Path("/Users/luzuoguan/ai/value-investing/年报/长江电力-600900/萝卜投研-财务页下载/整理")
CSV_DIR = BASE_DIR / "csv"
CHART_DIR = BASE_DIR / "charts"
README_PATH = CHART_DIR / "README.md"


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


def load_csv(name: str) -> pd.DataFrame:
    return pd.read_csv(CSV_DIR / f"{name}.csv")


def annual_columns(frame: pd.DataFrame) -> list[str]:
    cols = [col for col in frame.columns if isinstance(col, str) and col.endswith("年报")]
    return sorted(cols, key=lambda item: int(item[:4]))


def annual_years(cols: list[str]) -> list[str]:
    return [col[:4] for col in cols]


def get_row(frame: pd.DataFrame, code: str) -> pd.Series:
    matched = frame.loc[frame["字段代码"] == code]
    if matched.empty:
        raise KeyError(f"未找到字段代码: {code}")
    return matched.iloc[0]


def get_main_row(frame: pd.DataFrame, top: str, dimension: str, depth: int, node: str) -> pd.Series:
    matched = frame.loc[
        (frame["一级项目"] == top)
        & (frame["维度"] == dimension)
        & (frame["层级深度"] == depth)
        & (frame["当前节点"] == node)
    ]
    if matched.empty:
        raise KeyError(f"未找到主营构成项目: {top}/{dimension}/{node}")
    return matched.iloc[0]


def money_to_yi(values: pd.Series) -> pd.Series:
    return values.astype(float) / 1e8


def ratio_to_pct(values: pd.Series) -> pd.Series:
    series = values.astype(float)
    if series.max() <= 1.5:
        return series * 100
    return series


def style_axis(ax: plt.Axes, title: str, ylabel: str) -> None:
    ax.set_title(title, fontsize=13, pad=12)
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def save_figure(fig: plt.Figure, filename: str) -> None:
    path = CHART_DIR / filename
    fig.tight_layout()
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def plot_revenue_profit(summary: pd.DataFrame, cols: list[str], years: list[str]) -> str:
    revenue = money_to_yi(get_row(summary, "tRevenue")[cols])
    profit = money_to_yi(get_row(summary, "NIncomeAttrP")[cols])

    fig, ax1 = plt.subplots(figsize=(11, 5))
    bars = ax1.bar(years, revenue, color="#4C78A8", alpha=0.88, label="营收")
    ax1.set_ylabel("营收（亿元）", color="#4C78A8")
    ax1.tick_params(axis="y", labelcolor="#4C78A8")
    style_axis(ax1, "长江电力年度营收与归母净利润", "营收（亿元）")

    ax2 = ax1.twinx()
    ax2.plot(years, profit, color="#E45756", marker="o", linewidth=2.2, label="归母净利润")
    ax2.set_ylabel("归母净利润（亿元）", color="#E45756")
    ax2.tick_params(axis="y", labelcolor="#E45756")
    ax2.spines["top"].set_visible(False)

    for rect, value in zip(bars, revenue):
        ax1.text(rect.get_x() + rect.get_width() / 2, rect.get_height() + 3, f"{value:.0f}", ha="center", va="bottom", fontsize=8)
    for x, y in zip(years, profit):
        ax2.text(x, y + 3, f"{y:.0f}", ha="center", va="bottom", fontsize=8, color="#E45756")

    save_figure(fig, "01-年度营收与归母净利润.png")
    return "01-年度营收与归母净利润.png"


def plot_cashflow_capex(summary: pd.DataFrame, cols: list[str], years: list[str]) -> str:
    ocf = money_to_yi(get_row(summary, "NCFOperateANotes")[cols])
    capex = money_to_yi(get_row(summary, "purFixAssetsOth")[cols])

    fig, ax = plt.subplots(figsize=(11, 5))
    x = range(len(years))
    width = 0.38
    ax.bar([i - width / 2 for i in x], ocf, width=width, color="#59A14F", label="经营现金流净额")
    ax.bar([i + width / 2 for i in x], capex, width=width, color="#F28E2B", label="资本开支")
    ax.set_xticks(list(x))
    ax.set_xticklabels(years)
    style_axis(ax, "年度经营现金流与资本开支", "金额（亿元）")
    ax.legend(frameon=False, ncol=2)

    save_figure(fig, "02-年度经营现金流与资本开支.png")
    return "02-年度经营现金流与资本开支.png"


def plot_balance_structure(summary: pd.DataFrame, cols: list[str], years: list[str]) -> str:
    liabilities = money_to_yi(get_row(summary, "TLiab")[cols])
    equity = money_to_yi(get_row(summary, "TEquityAttrP")[cols])
    assets = money_to_yi(get_row(summary, "TAssets")[cols])

    fig, ax = plt.subplots(figsize=(11, 5))
    ax.bar(years, liabilities, color="#9C755F", label="负债合计")
    ax.bar(years, equity, bottom=liabilities, color="#76B7B2", label="归母权益")
    ax.plot(years, assets, color="#4E79A7", linewidth=2.2, marker="o", label="资产总计")
    style_axis(ax, "年度资产负债结构", "金额（亿元）")
    ax.legend(frameon=False, ncol=3)

    save_figure(fig, "03-年度资产负债结构.png")
    return "03-年度资产负债结构.png"


def plot_profitability(summary: pd.DataFrame, cols: list[str], years: list[str]) -> str:
    roe = ratio_to_pct(get_row(summary, "ROE")[cols])
    gross_margin = ratio_to_pct(get_row(summary, "grossMARgin")[cols])
    net_margin = ratio_to_pct(get_row(summary, "npMARgin")[cols])
    debt_ratio = ratio_to_pct(get_row(summary, "asseTLiabRatio")[cols])

    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(years, roe, marker="o", linewidth=2.2, label="ROE")
    ax.plot(years, gross_margin, marker="o", linewidth=2.2, label="毛利率")
    ax.plot(years, net_margin, marker="o", linewidth=2.2, label="净利率")
    ax.plot(years, debt_ratio, marker="o", linewidth=2.2, label="资产负债率")
    style_axis(ax, "年度盈利能力与杠杆指标", "比例（%）")
    ax.legend(frameon=False, ncol=4)

    save_figure(fig, "04-年度盈利能力与杠杆指标.png")
    return "04-年度盈利能力与杠杆指标.png"


def plot_per_share(indicators: pd.DataFrame, cols: list[str], years: list[str]) -> str:
    eps = get_row(indicators, "basicEps")[cols].astype(float)
    nav_ps = get_row(indicators, "nAssetPs")[cols].astype(float)
    ocf_ps = get_row(indicators, "nCFOperAPs")[cols].astype(float)

    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(years, eps, marker="o", linewidth=2.2, label="每股收益")
    ax.plot(years, nav_ps, marker="o", linewidth=2.2, label="每股净资产")
    ax.plot(years, ocf_ps, marker="o", linewidth=2.2, label="每股经营现金流")
    style_axis(ax, "年度每股指标", "每股金额（元）")
    ax.legend(frameon=False, ncol=3)

    save_figure(fig, "05-年度每股指标.png")
    return "05-年度每股指标.png"


def plot_main_composition(main_comp: pd.DataFrame, cols: list[str], years: list[str]) -> str:
    hydro_revenue = money_to_yi(get_main_row(main_comp, "营业总收入", "行业", 2, "境内水电行业")[cols])
    other_revenue = money_to_yi(get_main_row(main_comp, "营业总收入", "行业", 2, "其他行业")[cols])
    hydro_margin = ratio_to_pct(get_main_row(main_comp, "毛利率", "行业", 2, "境内水电行业")[cols])
    overall_margin = ratio_to_pct(get_main_row(main_comp, "毛利率", "汇总", 0, "毛利率")[cols])

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 8), height_ratios=[2, 1.5])
    ax1.bar(years, hydro_revenue, color="#4C78A8", label="境内水电行业")
    ax1.bar(years, other_revenue, bottom=hydro_revenue, color="#B07AA1", label="其他行业")
    style_axis(ax1, "年度主营收入构成", "收入（亿元）")
    ax1.legend(frameon=False, ncol=2)

    ax2.plot(years, hydro_margin, marker="o", linewidth=2.2, label="境内水电行业毛利率")
    ax2.plot(years, overall_margin, marker="o", linewidth=2.2, label="整体毛利率")
    style_axis(ax2, "年度主营毛利率对比", "毛利率（%）")
    ax2.legend(frameon=False, ncol=2)

    save_figure(fig, "06-年度主营构成与毛利率.png")
    return "06-年度主营构成与毛利率.png"


def write_readme(files: list[str]) -> None:
    summary = load_csv("财务摘要")
    summary_years = annual_years(annual_columns(summary))
    main_comp = load_csv("主营构成")
    main_years = sorted([col[:4] for col in main_comp.columns if col.endswith("年报")], key=int)
    lines = [
        "# 长江电力 Datayes 图表说明",
        "",
        "图表口径：",
        "",
        "- 数据来源：`整理/csv/` 下由 Datayes 原始接口整理出的 CSV",
        f"- 主财务图表年度范围：`{summary_years[0]}-{summary_years[-1]}`",
        f"- 主营构成图表年度范围：`{main_years[0]}-{main_years[-1]}`",
        "- 金额类图表统一换算为 `亿元`",
        "",
        "生成图表：",
        "",
    ]
    for item in files:
        lines.append(f"- `{item}`")
    lines.append("")
    README_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    configure_matplotlib()
    CHART_DIR.mkdir(parents=True, exist_ok=True)

    summary = load_csv("财务摘要")
    indicators = load_csv("关键指标")
    main_comp = load_csv("主营构成")
    cols = annual_columns(summary)
    years = annual_years(cols)

    files = [
        plot_revenue_profit(summary, cols, years),
        plot_cashflow_capex(summary, cols, years),
        plot_balance_structure(summary, cols, years),
        plot_profitability(summary, cols, years),
        plot_per_share(indicators, annual_columns(indicators), annual_years(annual_columns(indicators))),
        plot_main_composition(main_comp, [col for col in main_comp.columns if col.endswith("年报")], [col[:4] for col in main_comp.columns if col.endswith("年报")]),
    ]
    write_readme(files)
    print(f"已生成 {len(files)} 张图表到: {CHART_DIR}")


if __name__ == "__main__":
    main()

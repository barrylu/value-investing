# 中国海油 AKShare 财务数据说明

说明：

- 股票代码：`600938`
- 数据源：AKShare 聚合接口（Sina / 东方财富等）
- 目录说明：`raw/` 保存原始导出结果，`整理/` 保存概览工作簿

下载结果：

- ✅ 利润表：`raw/profit_statement.csv`，共 `23` 行
- ✅ 资产负债表：`raw/balance_sheet.csv`，共 `21` 行
- ✅ 现金流量表：`raw/cashflow_statement.csv`，共 `23` 行
- ✅ 财务分析指标：`raw/analysis_indicators.csv`，共 `0` 行
- ✅ 个股基础信息：`raw/stock_profile.csv`，共 `8` 行
- ✅ 行业成分股：`raw/industry_constituents.csv`，共 `50` 行

可直接用于后续开发的优先数据：

- `raw/analysis_indicators.csv`：财务分析指标，可作为 Datayes 指标备份
- `raw/industry_constituents.csv`：若已下载，可用于同行对比样本池
- 三大报表 CSV：可继续加工为统一字段口径

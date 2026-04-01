# 萝卜投研财务页下载说明

说明：

- 本目录内容来自中国海油 `600938` 的萝卜投研财务页接口下载
- 下载使用已登录的内置浏览器会话完成，然后经本地临时接收服务落盘
- 下载过程中未把浏览器登录态写入仓库文件
- `raw/` 为原始 JSON 响应，`excel/` 为页面可导出的表格文件
- 本次导出展示单位固定为：`亿元`（参数 `unit=4`）
- 当前页面可见的全期间范围到 `2018年报` 为止；这已是本次页面返回的最早区间

下载文件：

- `raw/financial_summary_full_periods.json`: `financial_summary_full_periods`，区间 `2025三季报 -> 2018年报`，共 `22` 列
- `raw/balance_sheet_full_periods.json`: `balance_sheet_full_periods`，区间 `2025三季报 -> 2018年报`，共 `20` 列
- `raw/income_statement_full_periods.json`: `income_statement_full_periods`，区间 `2025三季报 -> 2018年报`，共 `22` 列
- `raw/cashflow_full_periods.json`: `cashflow_full_periods`，区间 `2025三季报 -> 2018年报`，共 `22` 列
- `raw/key_finance_indicators_full_periods.json`: `key_finance_indicators_full_periods`，区间 `2025三季报 -> 2018年报`，共 `20` 列
- `raw/main_composition_full_periods.json`: `main_composition_full_periods`，区间 `2025半年报 -> 2018年报`，共 `12` 列
- `excel/中国海油-资产负债表-全期间.xls`: `balance_sheet_excel`
- `excel/中国海油-利润表-全期间.xls`: `income_statement_excel`
- `excel/中国海油-现金流量表-全期间.xls`: `cashflow_excel`
- `excel/中国海油-财务摘要-全期间.xls`: `financial_summary_excel`
- `excel/中国海油-主营构成表-全期间.xls`: `main_composition_excel`

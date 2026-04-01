# 价值投资资料整理与学习

面向初学者的公司研究资料库：年报、资讯与学习笔记，配合 AI Agent 提升效率。

## 目录结构

```
value-investing/
├── README.md                 # 本说明
├── AI-AGENT-使用指南.md      # 如何用 AI Agent 辅助研究
├── 年报/                     # 公司年报 PDF/链接 与 摘要笔记
│   └── [公司代码或简称]/
├── 资讯/                     # 新闻、研报、公告等
│   ├── 按公司/
│   └── 按主题/
├── 研究笔记/                 # 你的分析与思考
│   └── [公司代码或简称]/
└── 模板与清单/               # 研究清单、模板
```

## 使用方式

1. **年报**：把下载的年报 PDF 或官方链接放到 `年报/[公司]/`，用 AI 帮你做摘要、提炼关键数据。
2. **资讯**：在 `资讯/` 下按公司或主题整理新闻/研报链接或摘录，让 AI 做要点归纳、与年报交叉验证。
3. **研究笔记**：在 `研究笔记/[公司]/` 写你的理解，用 AI 做结构化整理、查漏补缺、生成简单估值框架。

详细工作流与提示词示例见 **AI-AGENT-使用指南.md**。

## Python 环境

项目已提供独立虚拟环境方案，推荐在 `value-investing/.venv` 中安装和运行数据分析工具，避免影响系统 Python。

使用说明与示例见 **Python-虚拟环境使用指南.md**。

## 已搭建的基础分析工具

`scripts/` 下目前已经补齐以下基础工具：

- `compute_financial_ratios.py`：基于 Datayes 标准化 CSV 计算财务比率、输出 Excel 和年度趋势图
- `build_valuation_model.py`：读取年度比率结果，生成 DCF 估值报告和敏感性矩阵
- `download_akshare_finance.py`：用 AKShare 下载免费财务数据，作为 Datayes 的备份/补充来源
- `plot_interactive_charts.py`：把年度财务比率结果输出为交互式 HTML 仪表盘
- `compare_peers.py`：读取多个公司的年度比率结果，生成同行横向对比表

典型使用顺序：

1. 先准备好 `年报/[公司]/萝卜投研-财务页下载/整理/csv/`
2. 运行 `compute_financial_ratios.py`
3. 再运行 `build_valuation_model.py` 或 `plot_interactive_charts.py`
4. 需要数据备份时运行 `download_akshare_finance.py`
5. 需要横向对比时运行 `compare_peers.py`

# Python 虚拟环境使用指南

本项目的 Python 虚拟环境位于 `value-investing/.venv`。

## 1. 激活环境

在项目目录下执行：

```bash
cd /Users/luzuoguan/WorkBuddy/Claw/value-investing
source .venv/bin/activate
```

激活后，终端前面通常会出现 `(.venv)`。

## 2. 已安装的常用包

本环境用于资料整理、数据处理、研究分析与基础开发，当前常用包包括：

```text
pandas
numpy
matplotlib
openpyxl
requests
plotly
kaleido
akshare
jupyter
pytest
ruff
black
```

## 3. 常用命令

查看 Python 和 pip：

```bash
python --version
pip --version
```

启动 Jupyter：

```bash
jupyter notebook
```

格式化代码：

```bash
black .
```

检查代码风格：

```bash
ruff check .
```

退出虚拟环境：

```bash
deactivate
```

## 4. 使用示例

### 示例 1：读取 CSV 并查看前几行

```python
import pandas as pd

df = pd.read_csv("data.csv")
print(df.head())
```

### 示例 2：读取 Excel 并计算简单指标

```python
import pandas as pd

df = pd.read_excel("财务数据.xlsx")
df["ROE"] = df["净利润"] / df["净资产"]
print(df[["年份", "ROE"]])
```

### 示例 3：画一个简单趋势图

```python
import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_excel("财务数据.xlsx")
plt.plot(df["年份"], df["营收"])
plt.title("营收趋势")
plt.xlabel("年份")
plt.ylabel("营收")
plt.show()
```

### 示例 4：用 requests 拉取网页

```python
import requests

resp = requests.get("https://www.example.com", timeout=10)
print(resp.status_code)
print(resp.text[:200])
```

## 5. 推荐工作流

1. 进入项目目录并激活 `.venv`
2. 准备好 `年报/[公司]/萝卜投研-财务页下载/整理/csv/` 数据
3. 先运行 `scripts/compute_financial_ratios.py` 生成年度比率
4. 再运行 `scripts/build_valuation_model.py` 或 `scripts/plot_interactive_charts.py`
5. 需要免费备份数据源时运行 `scripts/download_akshare_finance.py`
6. 写完脚本后用 `ruff check .` 和 `black .` 做基础整理
7. 需要退出时执行 `deactivate`

## 6. 不想手动激活时

也可以直接使用虚拟环境里的命令：

```bash
/Users/luzuoguan/WorkBuddy/Claw/value-investing/.venv/bin/python script.py
/Users/luzuoguan/WorkBuddy/Claw/value-investing/.venv/bin/jupyter notebook
```

# web-app 手机访问说明

## 目标
让 `web-app/` 能作为纯静态站点在手机浏览器访问。

## 已完成
- 页面移动端适配：顶部栏、抽屉导航、表格横向滚动、图表手机高度优化
- 保持纯静态结构：直接读取 `web-app/data/` 下的 JSON
- 适合用任意静态文件服务器托管

## 本地启动（推荐）
在仓库根目录执行：

```bash
cd /projects/value-investing
python3 -m http.server 8000 --directory web-app
```

然后在电脑浏览器打开：

```text
http://127.0.0.1:8000
```

## 手机访问
前提：手机和这台机器在同一网络，且 8000 端口可访问。

先查看这台机器 IP：

```bash
hostname -I
```

假设 IP 是 `192.168.1.20`，那手机访问：

```text
http://192.168.1.20:8000
```

## 如果要长期运行
可考虑：
- Nginx / Caddy 反向代理
- Docker 静态站点
- OpenClaw Gateway 挂静态资源

## 数据更新
如果年报/研究笔记变了，重新生成前端 JSON：

```bash
cd /projects/value-investing
python3 scripts/build_web_data.py
```

## 当前已知限制
- 巴菲特原文阅读仍依赖仓库内 Markdown 文件直读；不同部署目录下可能需要再调一次路径
- 研究笔记弹窗当前优先展示摘要，不是完整 markdown 原文
- 若要做公网手机访问，还需要域名/反向代理/鉴权

#!/usr/bin/env python3
"""
巴菲特文集 - 金句提取 + 投资风格演进时间线
"""
import os, re, sys

sys.stdout = open(sys.stdout.fileno(), mode='w', buffering=1)

BASE = '/Users/luzuoguan/WorkBuddy/Claw/value-investing/巴菲特文集'

# ========== 1. 金句提取 ==========
# 经典金句的关键特征：短小精悍、包含哲理性表述
QUOTE_PATTERNS = [
    # 直接引用的经典概念
    r'别人贪婪.{0,10}恐惧',
    r'别人恐惧.{0,10}贪婪',
    r'市场先生',
    r'安全边际',
    r'能力圈',
    r'护城河',
    r'时间是.{0,15}朋友',
    r'时间是.{0,15}敌人',
    r'价格是你付出的.{0,20}价值是你得到的',
    r'第一条规则.{0,20}不要亏钱',
    r'不要亏钱',
    r'潮水退去',
    r'裸泳',
    r'一英尺的栏',
    r'打卡',
    r'20个打孔位',
    r'复利',
    r'滚雪球',
    r'湿的雪.{0,10}长的坡',
    r'用合理的价格买入优秀',
    r'用便宜的价格买入平庸',
    r'永远不要做空美国',
    r'我最喜欢的持股期限是永远',
    r'集中投资',
    r'分散.{0,10}无知的保护',
    r'退潮',
]

# 金句判断辅助：含有哲理性转折、对比、总结的短句
WISDOM_MARKERS = [
    '最重要的', '最大的', '最好的', '最坏的', '永远',
    '从不', '第一条', '第二条', '关键是', '秘诀',
    '本质', '核心', '真正的', '唯一', '根本',
]

def extract_quotes(base_dir):
    """Extract notable quotes from all files."""
    quotes = []
    
    scan_dirs = ['致股东信', '股东大会', '合伙人信', '早期文章']
    for dirname in scan_dirs:
        dirpath = os.path.join(base_dir, dirname)
        if not os.path.isdir(dirpath):
            continue
        
        for filename in sorted(os.listdir(dirpath)):
            if not filename.endswith('.md'):
                continue
            filepath = os.path.join(dirpath, filename)
            year = re.search(r'(\d{4})', filename)
            year = year.group(1) if year else '?'
            
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
            
            for para in paragraphs:
                if len(para) < 15 or len(para) > 500:
                    continue
                
                score = 0
                matched = []
                
                # Check quote patterns
                for pattern in QUOTE_PATTERNS:
                    if re.search(pattern, para):
                        score += 3
                        matched.append(pattern[:20])
                
                # Check wisdom markers
                for marker in WISDOM_MARKERS:
                    if marker in para:
                        score += 1
                
                # Bonus for shorter, punchier statements
                if 15 < len(para) < 150:
                    score += 2
                elif 150 < len(para) < 300:
                    score += 1
                
                if score >= 3:
                    quotes.append({
                        'year': year,
                        'source': f"{dirname}/{filename}",
                        'text': para,
                        'score': score,
                    })
    
    # Sort by score, deduplicate
    quotes.sort(key=lambda x: -x['score'])
    seen = set()
    unique = []
    for q in quotes:
        key = q['text'][:80]
        if key not in seen:
            seen.add(key)
            unique.append(q)
    
    return unique[:150]  # Top 150 quotes


def write_quotes(quotes, base_dir):
    """Write quotes index."""
    filepath = os.path.join(base_dir, '金句索引.md')
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write("# 💎 巴菲特金句索引\n\n")
        f.write("> 从72年致股东信和股东大会中提取的经典语录\n\n")
        f.write(f"共收录 {len(quotes)} 条金句\n\n")
        f.write("---\n\n")
        
        # Group by decade
        decades = {}
        for q in quotes:
            try:
                decade = f"{int(q['year'])//10*10}s"
            except:
                decade = "其他"
            if decade not in decades:
                decades[decade] = []
            decades[decade].append(q)
        
        for decade in sorted(decades.keys()):
            f.write(f"## {decade}\n\n")
            # Sort by year within decade
            for q in sorted(decades[decade], key=lambda x: x['year']):
                text = q['text']
                if len(text) > 400:
                    text = text[:400] + "..."
                f.write(f"**[{q['year']}]** {text}\n\n")
                f.write(f"*— {q['source']}*\n\n")
                f.write("---\n\n")
    
    return filepath


# ========== 2. 投资风格演进时间线 ==========
def build_timeline(base_dir):
    """Build investment style evolution timeline."""
    
    timeline = [
        {
            'period': '1950-1956',
            'title': '格雷厄姆门徒：纯粹的"捡烟蒂"',
            'events': [
                '1950: 进入哥伦比亚商学院，师从格雷厄姆',
                '1951: 发表第一篇投资分析——GEICO保险',
                '1951-1954: 做经纪人，学习格雷厄姆的"净营运资本法"',
                '1954-1956: 加入格雷厄姆纽曼公司，实践deep value investing',
            ],
            'style': '寻找价格低于净营运资本的股票（"烟蒂股"），纯统计学方法',
            'key_concepts': ['净营运资本', '清算价值', '统计学低估'],
        },
        {
            'period': '1957-1969',
            'title': '合伙人时代：从格雷厄姆到费雪的过渡',
            'events': [
                '1957: 创立巴菲特合伙基金',
                '1958-1962: 三类投资法——低估类、套利类、控制类',
                '1962: 开始收购登普斯特（控制类投资的典范）',
                '1963: 著名的美国运通"色拉油丑闻"投资',
                '1965: 收购伯克希尔·哈撒韦（后来承认是个错误）',
                '1967: 收购国民赔偿保险公司（保险帝国的起点）',
                '1969: 关闭合伙基金，13年年化30.4%',
            ],
            'style': '从纯统计学低估向"特殊情况"和"控制权"投资扩展',
            'key_concepts': ['低估类（格雷厄姆式）', '套利类', '控制类', '特殊情况投资'],
        },
        {
            'period': '1970-1982',
            'title': '伯克希尔早期：芒格影响初现',
            'events': [
                '1970: 开始通过伯克希尔经营',
                '1971-1972: 收购喜诗糖果（3倍账面价值！格雷厄姆不会买）',
                '1973: 股市暴跌中大量买入华盛顿邮报',
                '1976: 重新大量买入GEICO保险（危机中的好公司）',
                '1977-1982: 开始在年报中系统性阐述投资理念',
            ],
            'style': '开始愿意为优质企业支付合理溢价，芒格的影响逐渐显现',
            'key_concepts': ['品牌护城河', '消费者垄断', '经济商誉 vs 会计商誉'],
        },
        {
            'period': '1983-1998',
            'title': '黄金时代："好公司合理价格"成熟期',
            'events': [
                '1983: 收购内布拉斯加家具城（B夫人的故事）',
                '1985: 收购斯科特-费策公司',
                '1986-1988: 阐述"所有者盈余"概念',
                '1988: 开始大举买入可口可乐（1.02亿美元→后来价值百亿）',
                '1991: 投资所罗门兄弟遭遇危机',
                '1993: 收购鞋业公司Dexter（后来承认是最大的错误之一）',
                '1996: 发行B类股，使普通投资者也能持有伯克希尔',
                '1998: 收购通用再保险（220亿美元）',
            ],
            'style': '"用合理的价格买入优秀的企业，远好于用便宜的价格买入平庸的企业"',
            'key_concepts': ['所有者盈余', '浮存金杠杆', '经济特许权', '透视盈余'],
        },
        {
            'period': '1999-2008',
            'title': '坚守与反思：泡沫中的清醒者',
            'events': [
                '1999: 互联网泡沫中坚持不买科技股，被市场嘲笑',
                '2000: 泡沫破裂验证了他的判断',
                '2002: 大举买入中石油（后来大赚）',
                '2003: 开始警告衍生品是"金融大规模杀伤性武器"',
                '2006: 承诺将99%的财富捐赠',
                '2008: "别人恐惧时我贪婪"——金融危机中大举投资高盛、GE等',
                '2008: 收购比亚迪股份',
            ],
            'style': '强调能力圈边界，对衍生品和杠杆持批评态度，危机中逆势出手',
            'key_concepts': ['能力圈', '衍生品风险', '逆向投资', '危机投资'],
        },
        {
            'period': '2009-2022',
            'title': '大象级收购与回归买入整个企业',
            'events': [
                '2009: 收购北伯灵顿铁路（BNSF），340亿美元',
                '2010: 将账面价值改为内在价值的度量标准讨论',
                '2011: 开始回购伯克希尔股票',
                '2013: 与3G资本合作收购亨氏',
                '2015: 收购精密铸件（Precision Castparts），370亿美元',
                '2016: 开始买入苹果股票（后来成为最大持仓）',
                '2020: 新冠危机，航空股割肉离场',
                '2020: 买入日本五大商社',
                '2022: 收购Alleghany保险，116亿美元',
            ],
            'style': '倾向于收购整个企业而非买入部分股票，回购成为重要资本配置手段',
            'key_concepts': ['大象级收购', '股票回购', '永久持有', '铁路/能源基础设施'],
        },
    ]
    
    filepath = os.path.join(base_dir, '投资风格演进.md')
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write("# 🎯 巴菲特投资风格演进时间线\n\n")
        f.write('> 从"捡烟蒂"到"好公司合理价格"——72年投资哲学的进化\n\n')
        f.write("---\n\n")
        
        for era in timeline:
            f.write(f"## {era['period']}：{era['title']}\n\n")
            f.write(f"**投资风格：** {era['style']}\n\n")
            
            f.write("**关键事件：**\n\n")
            for event in era['events']:
                f.write(f"- {event}\n")
            f.write("\n")
            
            f.write(f"**核心概念：** {' | '.join(era['key_concepts'])}\n\n")
            f.write("---\n\n")
        
        # Summary evolution chart
        f.write("## 📊 风格演变总结\n\n")
        f.write("| 时期 | 估值方法 | 投资对象 | 持有期限 | 集中度 |\n")
        f.write("|------|---------|---------|---------|--------|\n")
        f.write("| 1950s | 净营运资本 < 股价 | 统计学低估股 | 短-中期 | 分散 |\n")
        f.write("| 1960s | 低估+套利+控制 | 多类型混合 | 中期 | 适度集中 |\n")
        f.write("| 1970s | 账面价值+盈利能力 | 优质消费品牌 | 长期 | 集中 |\n")
        f.write("| 1980-90s | 所有者盈余折现 | 经济特许权企业 | 永久持有 | 高度集中 |\n")
        f.write("| 2000s | 内在价值+护城河 | 危机中的优质企业 | 永久持有 | 高度集中 |\n")
        f.write("| 2010-20s | 整体收购+回购 | 基础设施+科技龙头 | 永久持有 | 超大仓位 |\n\n")
        
        f.write("## 🔑 永恒不变的原则\n\n")
        f.write("尽管方法在进化，以下原则从未改变：\n\n")
        f.write("1. **安全边际** — 始终要求价格低于价值\n")
        f.write("2. **能力圈** — 只做自己能理解的投资\n")
        f.write("3. **长期视角** — 以企业主而非股票交易者的心态投资\n")
        f.write("4. **管理层品质** — 诚信和能力缺一不可\n")
        f.write("5. **独立思考** — 不受市场情绪影响\n")
        f.write("6. **耐心** — 宁可错过也不犯错\n")
    
    return filepath


def format_size(filepath):
    size = os.path.getsize(filepath)
    return f"{size//1024}KB" if size >= 1024 else f"{size}B"


def list_md_files(dirpath):
    if not os.path.isdir(dirpath):
        return []
    return sorted([f for f in os.listdir(dirpath) if f.endswith('.md')])


def extract_years(files):
    years = []
    for filename in files:
        stem = filename[:-3]
        if stem.isdigit():
            years.append(int(stem))
    return sorted(years)


def rebuild_main_readme(base_dir, quote_count):
    lines = [
        "# 📚 巴菲特文集 · 总目录",
        "",
        "> **巴菲特 1950-2022 致股东信 + 股东大会实录**",
        "> 约440万字 | 覆盖72年投资智慧",
        "> 本文集由 WorkBuddy 从原始 Word 文档自动拆分生成",
        "",
        "---",
        "",
    ]

    categories = [
        ('前言.md', '📖 前言', True),
        ('生平', '👤 巴菲特生平', False),
        ('早期文章', '📝 早期文章 (1951-1953)', False),
        ('合伙人信', '💼 巴菲特合伙人信 (1957-1969)', False),
        ('致股东信', '📮 致股东信 (1965-2022)', False),
        ('股东大会', '🎤 股东大会实录 (1986-2023)', False),
        ('附录', '📊 附录', False),
    ]

    for path, title, is_file in categories:
        full = os.path.join(base_dir, path)
        if is_file:
            if os.path.isfile(full):
                lines.append(f"## {title}")
                lines.append(f"- [{os.path.basename(path)}]({path})")
                lines.append("")
            continue

        files = list_md_files(full)
        if not files:
            continue

        lines.append(f"## {title}")
        lines.append("")
        for filename in files:
            rel = f"{path}/{filename}"
            name = filename[:-3]
            lines.append(f"- [{name}]({rel}) ({format_size(os.path.join(full, filename))})")
        lines.append("")

    theme_dir = os.path.join(base_dir, '主题索引')
    theme_files = [f for f in list_md_files(theme_dir) if f != 'README.md']
    if theme_files:
        lines.append("## 🧠 主题索引")
        lines.append("")
        lines.append("按9大投资主题分类的智慧提取：")
        lines.append("")
        for filename in theme_files:
            name = filename[:-3]
            lines.append(f"- [{name}](主题索引/{filename})")
        lines.append("")

    quote_path = os.path.join(base_dir, '金句索引.md')
    if os.path.isfile(quote_path):
        lines.append("## 💎 金句索引")
        lines.append("")
        lines.append(f"- [巴菲特金句索引](金句索引.md) — {quote_count}条经典语录")
        lines.append("")

    timeline_path = os.path.join(base_dir, '投资风格演进.md')
    if os.path.isfile(timeline_path):
        lines.append("## 🎯 投资风格演进")
        lines.append("")
        lines.append("- [投资风格演进时间线](投资风格演进.md) — 从\"捡烟蒂\"到\"好公司合理价格\"")
        lines.append("")

    total_files = 0
    for _, _, files in os.walk(base_dir):
        total_files += len([f for f in files if f.endswith('.md')])

    letter_files = list_md_files(os.path.join(base_dir, '致股东信'))
    meeting_files = list_md_files(os.path.join(base_dir, '股东大会'))
    partnership_files = list_md_files(os.path.join(base_dir, '合伙人信'))

    letter_years = extract_years(letter_files)
    meeting_years = extract_years(meeting_files)

    lines.append("---")
    lines.append("")
    lines.append(f"**共 {total_files} 个文件**")
    lines.append("")
    lines.append("### 📊 统计")
    if letter_years:
        lines.append(f"- 致股东信: {len(letter_files)} 篇 ({min(letter_years)}-{max(letter_years)})")
    if meeting_years:
        lines.append(f"- 股东大会: {len(meeting_files)} 篇 ({min(meeting_years)}-{max(meeting_years)})")
    if partnership_files:
        lines.append(f"- 合伙人信: {len(partnership_files)} 篇 (1957-1969)")

    readme_path = os.path.join(base_dir, 'README.md')
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    return readme_path, total_files


def main():
    print("=== 金句提取 ===")
    quotes = extract_quotes(BASE)
    qpath = write_quotes(quotes, BASE)
    print(f"✓ 金句索引: {len(quotes)} 条 → {qpath}")
    
    print("\n=== 投资风格演进时间线 ===")
    tpath = build_timeline(BASE)
    print(f"✓ 时间线 → {tpath}")
    
    print("\n更新总目录...")
    readme_path, total_files = rebuild_main_readme(BASE, len(quotes))
    print(f"✓ 总目录已更新: {readme_path}")
    print(f"✓ 当前 Markdown 文件数: {total_files}")
    
    print("\n✅ 全部完成!")


if __name__ == '__main__':
    main()

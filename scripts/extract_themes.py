#!/usr/bin/env python3
"""
巴菲特文集 - 主题化知识提取
从拆分后的Markdown文件中按投资主题提取关键段落
"""
import os, re, sys

sys.stdout = open(sys.stdout.fileno(), mode='w', buffering=1)

BASE = '/Users/luzuoguan/WorkBuddy/Claw/value-investing/巴菲特文集'
OUTPUT = os.path.join(BASE, '主题索引')
os.makedirs(OUTPUT, exist_ok=True)

# ========== 主题定义 ==========
THEMES = {
    '估值与安全边际': {
        'keywords': [
            '内在价值', '安全边际', '所有者盈余', '透视盈余', '账面价值',
            '市盈率', '市净率', '折现', '现金流折现', '估值', '低估',
            '价值远超', '合理价格', '出价', '买入价格', '买贵了',
            'intrinsic value', '每股价值', '每股账面', '清算价值',
            '资产价值', '盈利能力', '收益率', '回报率',
        ],
        'description': '巴菲特对企业估值的方法论：内在价值、安全边际、所有者盈余等核心概念'
    },
    '护城河与竞争优势': {
        'keywords': [
            '护城河', '竞争优势', '特许经营权', '经济特许权', '品牌',
            '定价权', '垄断', '转换成本', '网络效应', '规模经济',
            '进入壁垒', '不可替代', '经济商誉', '商誉',
            '持久竞争', '长期竞争', '宽阔的护城河', '经济城堡',
            'franchise', '消费者垄断', '收费桥梁',
        ],
        'description': '企业持久竞争优势的来源与识别'
    },
    '保险与浮存金': {
        'keywords': [
            '浮存金', '保险', '承保', '保费', '理赔', '再保险',
            'GEICO', '国民赔偿', 'General Re', '通用再保险',
            '承保利润', '承保亏损', '综合比率', '保险业务',
            '灾难保险', '超级巨灾', '保险浮存', 'float',
        ],
        'description': '伯克希尔的核心引擎——保险业务与浮存金'
    },
    '资本配置': {
        'keywords': [
            '资本配置', '资本分配', '再投资', '留存收益', '股票回购',
            '回购', '分红', '股息', '收购', '并购', '多元化',
            '现金储备', '现金', '配置资本', '分配资本',
            '每一美元', '留存利润', '资本支出', '自由现金',
        ],
        'description': '如何明智地配置资本：回购、收购、分红、留存'
    },
    '管理层评估': {
        'keywords': [
            '管理层', '经理人', 'CEO', '诚信', '正直', '能力',
            '薪酬', '期权', '激励', '代理人', '制度性迫力',
            '官僚', '帝国建设', '股东利益', '管理能力',
            '我们的经理', '优秀的管理', '信任', '授权',
        ],
        'description': '如何评估和选择管理层'
    },
    '市场观与投资心理': {
        'keywords': [
            '市场先生', 'Mr. Market', '恐惧', '贪婪', '别人恐惧',
            '别人贪婪', '市场波动', '市场情绪', '投机', '赌博',
            '从众', '羊群', '非理性', '泡沫', '恐慌', '狂热',
            '耐心', '纪律', '逆向', '独立思考', '长期',
            '短期', '择时', '预测', '宏观经济',
        ],
        'description': '巴菲特对市场波动、投资心理和投机行为的看法'
    },
    '投资错误与教训': {
        'keywords': [
            '错误', '教训', '失败', '亏损', '愚蠢', '蠢事',
            '后悔', '不该', '错失', '代价高昂', '损失',
            '最大的错误', '犯了错', '吸取教训', '自我批评',
        ],
        'description': '巴菲特坦诚分享的投资失误和深刻教训'
    },
    '行业分析方法': {
        'keywords': [
            '行业', '产业', '周期', '商业模式', '竞争格局',
            '需求', '供给', '定价', '成本结构', '利润率',
            '行业前景', '行业特征', '商品型', '差异化',
            '资本密集', '轻资产', '重资产',
        ],
        'description': '如何分析行业特征和竞争格局'
    },
    '芒格智慧': {
        'keywords': [
            '芒格', '查理', 'Charlie', 'Munger',
        ],
        'description': '查理·芒格的独立观点和智慧语录',
        'filter': lambda text: any(k in text for k in ['芒格：', '芒格:', 'Charlie:', '查理：']),
    },
}


def scan_file(filepath, filename):
    """Scan a file and extract relevant paragraphs for each theme."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Split into paragraphs
    paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
    
    # Determine year and type from path
    year = re.search(r'(\d{4})', filename)
    year = year.group(1) if year else '?'
    
    parent_dir = os.path.basename(os.path.dirname(filepath))
    
    results = {}
    
    for theme_name, theme_config in THEMES.items():
        hits = []
        keywords = theme_config['keywords']
        custom_filter = theme_config.get('filter', None)
        
        for para in paragraphs:
            if len(para) < 30:  # skip very short paragraphs
                continue
            
            # Check keywords
            matched_kws = [kw for kw in keywords if kw.lower() in para.lower()]
            
            # For 芒格智慧, also apply custom filter
            if theme_name == '芒格智慧':
                if custom_filter and custom_filter(para):
                    matched_kws.append('_speaker_')
                elif not matched_kws:
                    continue
            
            if matched_kws:
                # Score by number of keyword matches and paragraph quality
                score = len(matched_kws)
                if len(para) > 200:
                    score += 1  # prefer longer, more substantive paragraphs
                hits.append((score, para, matched_kws))
        
        if hits:
            # Sort by score descending, take top entries
            hits.sort(key=lambda x: -x[0])
            results[theme_name] = [(para, kws) for _, para, kws in hits[:15]]
    
    return year, parent_dir, results


def main():
    print("扫描所有文件...")
    
    # Collect all results by theme
    theme_results = {name: [] for name in THEMES}
    
    # Scan all markdown files
    scan_dirs = ['致股东信', '股东大会', '合伙人信', '早期文章']
    total_files = 0
    
    for dirname in scan_dirs:
        dirpath = os.path.join(BASE, dirname)
        if not os.path.isdir(dirpath):
            continue
        
        files = sorted([f for f in os.listdir(dirpath) if f.endswith('.md')])
        for filename in files:
            filepath = os.path.join(dirpath, filename)
            year, parent, results = scan_file(filepath, filename)
            total_files += 1
            
            for theme_name, hits in results.items():
                for para, kws in hits:
                    theme_results[theme_name].append({
                        'year': year,
                        'source': f"{parent}/{filename}",
                        'text': para,
                        'keywords': kws,
                    })
            
            if total_files % 20 == 0:
                print(f"  已扫描 {total_files} 个文件...")
    
    print(f"扫描完成: {total_files} 个文件")
    
    # Write theme files
    print("\n生成主题索引文件...")
    
    for theme_name, config in THEMES.items():
        entries = theme_results[theme_name]
        if not entries:
            continue
        
        # Sort by year
        entries.sort(key=lambda x: x['year'])
        
        # Deduplicate similar paragraphs (keep unique ones)
        seen = set()
        unique_entries = []
        for e in entries:
            # Use first 100 chars as dedup key
            key = e['text'][:100]
            if key not in seen:
                seen.add(key)
                unique_entries.append(e)
        
        # Limit to top entries per theme with balanced decade coverage
        if len(unique_entries) > 80:
            # Group by decade and sample evenly
            by_decade = {}
            for e in unique_entries:
                try:
                    decade = f"{int(e['year'])//10*10}s"
                except:
                    decade = "other"
                by_decade.setdefault(decade, []).append(e)
            
            per_decade = max(10, 80 // max(len(by_decade), 1))
            balanced = []
            for decade in sorted(by_decade.keys()):
                balanced.extend(by_decade[decade][:per_decade])
            
            # If still under 80, fill from remaining
            if len(balanced) < 80:
                used = set(id(e) for e in balanced)
                for e in unique_entries:
                    if id(e) not in used and len(balanced) < 80:
                        balanced.append(e)
            
            unique_entries = sorted(balanced, key=lambda x: x['year'])[:80]
        
        filepath = os.path.join(OUTPUT, f"{theme_name}.md")
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"# {theme_name}\n\n")
            f.write(f"> {config['description']}\n\n")
            f.write(f"共收录 {len(unique_entries)} 条相关段落\n\n")
            f.write("---\n\n")
            
            current_decade = None
            for e in unique_entries:
                year = e['year']
                try:
                    decade = f"{int(year)//10*10}s"
                except:
                    decade = "其他"
                
                if decade != current_decade:
                    current_decade = decade
                    f.write(f"\n## {decade}\n\n")
                
                # Truncate very long paragraphs
                text = e['text']
                if len(text) > 800:
                    text = text[:800] + "..."
                
                f.write(f"### [{year}] {e['source']}\n\n")
                f.write(f"{text}\n\n")
                f.write(f"*关键词: {', '.join(e['keywords'][:5])}*\n\n")
                f.write("---\n\n")
        
        print(f"  ✓ {theme_name}: {len(unique_entries)} 条")
    
    # Generate theme index
    index_path = os.path.join(OUTPUT, 'README.md')
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write("# 🧠 巴菲特投资智慧 · 主题索引\n\n")
        f.write("> 从72年致股东信和股东大会实录中提取的核心投资主题\n\n")
        f.write("---\n\n")
        
        for theme_name, config in THEMES.items():
            count = len(theme_results.get(theme_name, []))
            emoji_map = {
                '估值与安全边际': '💰',
                '护城河与竞争优势': '🏰',
                '保险与浮存金': '🛡️',
                '资本配置': '♟️',
                '管理层评估': '👔',
                '市场观与投资心理': '🧘',
                '投资错误与教训': '⚠️',
                '行业分析方法': '🔬',
                '芒格智慧': '🦉',
            }
            emoji = emoji_map.get(theme_name, '📌')
            f.write(f"### {emoji} [{theme_name}]({theme_name}.md)\n")
            f.write(f"{config['description']}\n")
            f.write(f"*{count} 条相关段落*\n\n")
    
    print(f"\n✅ 主题索引已生成: {index_path}")
    print("=== 主题提取完成 ===")


if __name__ == '__main__':
    main()

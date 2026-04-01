#!/usr/bin/env python3
"""
巴菲特文集拆分 - 使用缓存数据快速处理
"""
import re, os, pickle, sys

sys.stdout = open(sys.stdout.fileno(), mode='w', buffering=1)

CACHE = '/Users/luzuoguan/WorkBuddy/Claw/value-investing/.cache/paragraphs.pkl'
OUTPUT = '/Users/luzuoguan/WorkBuddy/Claw/value-investing/巴菲特文集'

print("加载缓存...")
with open(CACHE, 'rb') as f:
    paras = pickle.load(f)
print(f"共 {len(paras)} 段落")

# ========== 1. 识别所有章节 ==========
print("识别章节...")

sections = []

for i, (text, style) in enumerate(paras):
    text = text.strip()
    if not text:
        continue
    
    # 致股东信: "巴菲特致股东的信 YYYY" / "巴菲特给股东的信 YYYY"
    m = re.match(r'^巴菲特[致给]股东的信\s*(\d{4})', text)
    if m:
        sections.append({'type': '致股东信', 'year': int(m.group(1)), 'idx': i, 'title': text})
        continue
    
    # 股东大会: "伯克希尔股东大会实录 YYYY" or "问答 YYYY"
    m = re.match(r'^伯克希尔股东大会(?:实录|问答)\s*(\d{4})', text)
    if m:
        sections.append({'type': '股东大会', 'year': int(m.group(1)), 'idx': i, 'title': text})
        continue
    
    # 早期BH信: "伯克希尔.哈撒韦公司 1969年"
    m = re.match(r'^伯克希尔[.·]哈撒韦公司\s*(\d{4})\s*年', text)
    if m:
        sections.append({'type': '致股东信', 'year': int(m.group(1)), 'idx': i, 'title': text})
        continue

# 合伙人信 (para 230-3700 range)
for i, (text, style) in enumerate(paras):
    if i < 230 or i > 3700:
        continue
    text = text.strip()
    m = re.match(r'^(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})?\s*日?\s*$', text)
    if m:
        year = int(m.group(1))
        if 1957 <= year <= 1970:
            sections.append({'type': '合伙人信', 'year': year, 'idx': i, 'title': f'巴菲特合伙人信 {text.strip()}'})

# 早期文章
for i, (text, style) in enumerate(paras):
    if i > 250:
        break
    text = text.strip()
    if '我最看好的股票' in text and 'GEICO' in text:
        sections.append({'type': '早期文章', 'year': 1951, 'idx': i, 'title': '我最看好的股票：GEICO保险 (1951)'})
    if i == 183 and '1953' in text:
        sections.append({'type': '早期文章', 'year': 1953, 'idx': i, 'title': '西部保险公司分析 (1953)'})

# Sort and deduplicate
sections.sort(key=lambda x: x['idx'])
deduped = []
for s in sections:
    if deduped and deduped[-1]['year'] == s['year'] and deduped[-1]['type'] == s['type'] and s['idx'] - deduped[-1]['idx'] < 50:
        continue
    deduped.append(s)
sections = deduped

print(f"识别到 {len(sections)} 个章节")

# Count by type
from collections import Counter
type_counts = Counter(s['type'] for s in sections)
for t, c in type_counts.most_common():
    print(f"  {t}: {c}")

# ========== 2. 特殊章节定位 ==========
bio_start = None
appendix_start = None
for i, (text, style) in enumerate(paras):
    t = text.strip()
    if '巴菲特 40 岁' in t or ('1930-1970' in t and '年' in t):
        if bio_start is None:
            bio_start = i
    if '道指百年走势' in t and i > 90000:
        if appendix_start is None:
            appendix_start = i

print(f"生平起始: para {bio_start}")
print(f"附录起始: para {appendix_start}")

# ========== 3. 写入文件 ==========
print("\n开始写入文件...")

def extract_text(start, end):
    lines = []
    for i in range(start, min(end, len(paras))):
        text = paras[i][0].strip()
        if text:
            lines.append(text)
    return '\n\n'.join(lines)

def write_md(filepath, title, content):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(f"# {title}\n\n{content}\n")

# 前言
first_section = min(s['idx'] for s in sections) if sections else len(paras)
if bio_start:
    preamble_end = bio_start
else:
    preamble_end = first_section
write_md(f"{OUTPUT}/前言.md", "前言", extract_text(0, preamble_end))
print("  ✓ 前言")

# 生平
if bio_start:
    bio_end = 129  # first early article
    write_md(f"{OUTPUT}/生平/巴菲特生平_1930-1970.md", "巴菲特生平 (1930-1970)", extract_text(bio_start, bio_end))
    print("  ✓ 生平")

# 附录
if appendix_start:
    write_md(f"{OUTPUT}/附录/道指百年走势.md", "道指百年走势", extract_text(appendix_start, len(paras)))
    print("  ✓ 附录")

# 主要章节
written_files = {}  # track written files to handle append
count = 0
for idx, section in enumerate(sections):
    # Determine end
    if idx + 1 < len(sections):
        end = sections[idx + 1]['idx']
    else:
        end = appendix_start if appendix_start else len(paras)
    
    type_dir = section['type']
    year = section['year']
    
    if type_dir == '合伙人信':
        # Multiple per year - use date in filename
        date_str = paras[section['idx']][0].strip()
        safe = re.sub(r'[\s/\\]', '', date_str)
        filename = f"{year}_{safe}.md"
    else:
        filename = f"{year}.md"
    
    filepath = f"{OUTPUT}/{type_dir}/{filename}"
    
    content = extract_text(section['idx'], end)
    if not content.strip():
        continue
    
    if filepath in written_files:
        # Append to existing file
        with open(filepath, 'a', encoding='utf-8') as f:
            f.write(f"\n\n---\n\n# {section['title']}\n\n{content}\n")
    else:
        write_md(filepath, section['title'], content)
        written_files[filepath] = True
    
    count += 1
    if count % 20 == 0:
        print(f"  已写入 {count} 个章节...")

print(f"  共写入 {count} 个章节文件")

# ========== 4. 生成目录 ==========
print("\n生成总目录...")

index = []
index.append("# 📚 巴菲特文集 · 总目录")
index.append("")
index.append("> **巴菲特 1950-2022 致股东信 + 股东大会实录**")
index.append("> 约440万字 | 覆盖72年投资智慧")
index.append("> 本文集由 WorkBuddy 从原始 Word 文档自动拆分生成")
index.append("")
index.append("---")
index.append("")

categories = [
    ('前言.md', '📖 前言', True),
    ('生平', '👤 巴菲特生平', False),
    ('早期文章', '📝 早期文章 (1951-1953)', False),
    ('合伙人信', '💼 巴菲特合伙人信 (1957-1969)', False),
    ('致股东信', '📮 致股东信 (1965-2022)', False),
    ('股东大会', '🎤 股东大会实录 (1986-2023)', False),
    ('附录', '📊 附录', False),
]

total_files = 0
for path, title, is_file in categories:
    full = f"{OUTPUT}/{path}"
    
    if is_file:
        if os.path.exists(full):
            index.append(f"## {title}")
            index.append(f"- [{os.path.basename(path)}]({path})")
            index.append("")
            total_files += 1
        continue
    
    if not os.path.isdir(full):
        continue
    
    files = sorted([f for f in os.listdir(full) if f.endswith('.md')])
    if not files:
        continue
    
    index.append(f"## {title}")
    index.append("")
    
    for f in files:
        name = f.replace('.md', '')
        rel = f"{path}/{f}"
        # Get file size for reference
        fsize = os.path.getsize(f"{full}/{f}")
        size_str = f"{fsize//1024}KB" if fsize > 1024 else f"{fsize}B"
        index.append(f"- [{name}]({rel}) ({size_str})")
    
    index.append("")
    total_files += len(files)

index.append("---")
index.append("")
index.append(f"**共 {total_files} 个文件**")
index.append("")

# Year coverage stats
letter_years = sorted(set(s['year'] for s in sections if s['type'] == '致股东信'))
meeting_years = sorted(set(s['year'] for s in sections if s['type'] == '股东大会'))
partner_years = sorted(set(s['year'] for s in sections if s['type'] == '合伙人信'))

index.append("### 📊 统计")
index.append(f"- 致股东信: {len(letter_years)} 篇 ({min(letter_years)}-{max(letter_years)})")
index.append(f"- 股东大会: {len(meeting_years)} 篇 ({min(meeting_years)}-{max(meeting_years)})")
index.append(f"- 合伙人信: {len(partner_years)} 篇 ({min(partner_years)}-{max(partner_years)})")
index.append("")

readme_path = f"{OUTPUT}/README.md"
with open(readme_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(index))

print(f"✅ 总目录已生成: {readme_path}")
print(f"✅ 共 {total_files} 个 Markdown 文件")
print("\n=== 拆分完成 ===")

#!/usr/bin/env python3
"""
巴菲特文集质量检查脚本
生成覆盖率、串档、统计不一致与常见 OCR 噪声报告
"""
import os
import re
from pathlib import Path

BASE = Path('/Users/luzuoguan/WorkBuddy/Claw/value-investing/巴菲特文集')
REPORT = BASE / '质量检查报告.md'


def list_years(dirpath: Path):
    years = []
    if not dirpath.is_dir():
        return years
    for p in sorted(dirpath.glob('*.md')):
        if p.stem.isdigit():
            years.append(int(p.stem))
    return years


def read_text(path: Path):
    return path.read_text(encoding='utf-8') if path.exists() else ''


def extract_readme_stats(readme_text: str):
    stats = {}
    m = re.search(r'\*\*共\s+(\d+)\s+个文件\*\*', readme_text)
    if m:
        stats['total_files'] = int(m.group(1))
    m = re.search(r'- 致股东信:\s*(\d+)\s*篇', readme_text)
    if m:
        stats['letters'] = int(m.group(1))
    m = re.search(r'- 股东大会:\s*(\d+)\s*篇', readme_text)
    if m:
        stats['meetings'] = int(m.group(1))
    m = re.search(r'- 合伙人信:\s*(\d+)\s*篇', readme_text)
    if m:
        stats['partnership'] = int(m.group(1))
    return stats


def find_header_leaks(meeting_dir: Path):
    leaks = []
    pattern = re.compile(r'巴菲特[致给]股东的信\s*(\d{4})')
    for p in sorted(meeting_dir.glob('*.md')):
        text = read_text(p)
        for match in pattern.finditer(text):
            year = match.group(1)
            line_no = text[:match.start()].count('\n') + 1
            leaks.append((p.name, year, line_no))
            break
    return leaks


def count_ocr_noise(paths):
    patterns = {
        'A I': re.compile(r'\bA I\b'),
        'K ilpatrick': re.compile(r'K ilpatrick'),
        '异常空格英文': re.compile(r'[A-Za-z]\s{1,}[A-Za-z]{1,}'),
    }
    counts = {k: 0 for k in patterns}
    samples = []
    for path in paths:
        text = read_text(path)
        for name, pattern in patterns.items():
            hits = list(pattern.finditer(text))
            counts[name] += len(hits)
            if hits and len(samples) < 10:
                m = hits[0]
                snippet = text[max(0, m.start()-20):m.end()+20].replace('\n', ' ')
                samples.append((path.relative_to(BASE).as_posix(), name, snippet))
    return counts, samples


def main():
    readme = read_text(BASE / 'README.md')
    letters = list_years(BASE / '致股东信')
    meetings = list_years(BASE / '股东大会')
    partnership_files = sorted((BASE / '合伙人信').glob('*.md')) if (BASE / '合伙人信').is_dir() else []
    all_md_files = sorted(BASE.rglob('*.md'))

    expected_letters = list(range(1965, 2023))
    expected_meetings = list(range(1986, 2024))
    missing_letters = [y for y in expected_letters if y not in letters]
    missing_meetings = [y for y in expected_meetings if y not in meetings]

    leaks = find_header_leaks(BASE / '股东大会')
    readme_stats = extract_readme_stats(readme)
    actual_stats = {
        'total_files': len(all_md_files),
        'letters': len(letters),
        'meetings': len(meetings),
        'partnership': len(partnership_files),
    }

    noise_counts, noise_samples = count_ocr_noise([
        BASE / '前言.md',
        BASE / '生平' / '巴菲特生平_1930-1970.md',
        BASE / '金句索引.md',
    ])

    lines = [
        '# 巴菲特文集质量检查报告',
        '',
        '## 总览',
        '',
        f'- 当前 Markdown 文件数: **{actual_stats["total_files"]}**',
        f'- 致股东信文件数: **{actual_stats["letters"]}**',
        f'- 股东大会文件数: **{actual_stats["meetings"]}**',
        f'- 合伙人信文件数: **{actual_stats["partnership"]}**',
        '',
        '## 发现的问题',
        '',
    ]

    if missing_letters:
        lines.append(f'1. **致股东信缺失年份**：{missing_letters}')
    else:
        lines.append('1. **致股东信缺失年份**：未发现')

    if missing_meetings:
        lines.append(f'2. **股东大会缺失年份**：{missing_meetings}')
    else:
        lines.append('2. **股东大会缺失年份**：未发现')

    if leaks:
        leak_desc = '；'.join([f'{name} 第{line_no}行混入 {year} 年致股东信标题' for name, year, line_no in leaks])
        lines.append(f'3. **股东大会文件串档**：{leak_desc}')
    else:
        lines.append('3. **股东大会文件串档**：未发现')

    stat_issues = []
    for key, label in [('total_files', '总文件数'), ('letters', '致股东信'), ('meetings', '股东大会'), ('partnership', '合伙人信')]:
        if readme_stats.get(key) is not None and readme_stats.get(key) != actual_stats[key]:
            stat_issues.append(f'{label} README={readme_stats.get(key)} / 实际={actual_stats[key]}')
    if stat_issues:
        lines.append('4. **README 统计不一致**：' + '；'.join(stat_issues))
    else:
        lines.append('4. **README 统计不一致**：未发现')

    noise_issue = '；'.join([f'{k}={v}' for k, v in noise_counts.items() if v]) or '未发现明显 OCR 噪声'
    lines.append(f'5. **介绍/索引文本噪声**：{noise_issue}')

    lines.extend([
        '',
        '## OCR/排版样例',
        '',
    ])
    if noise_samples:
        for rel, kind, snippet in noise_samples:
            lines.append(f'- `{rel}` [{kind}]：{snippet}')
    else:
        lines.append('- 未发现')

    lines.extend([
        '',
        '## 建议处理顺序',
        '',
        '1. 先修复章节识别规则并重跑拆分，解决缺失年份与串档问题。',
        '2. 再重建 README、主题索引和金句索引，保证统计与目录一致。',
        '3. 最后针对前言、生平、金句索引做文本清洗，处理 OCR/空格噪声与截断句。',
        '',
    ])

    REPORT.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(str(REPORT))


if __name__ == '__main__':
    main()

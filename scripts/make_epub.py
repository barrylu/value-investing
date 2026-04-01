#!/usr/bin/env python3
"""
将巴菲特文集 Markdown 文件转为 EPUB 电子书
用法: python make_epub.py <input.md> [output.epub]
"""
import sys
import re
import markdown
from pathlib import Path
from ebooklib import epub

def md_to_epub(md_path, epub_path=None):
    md_path = Path(md_path)
    if epub_path is None:
        epub_path = md_path.with_suffix('.epub')
    else:
        epub_path = Path(epub_path)
    
    text = md_path.read_text('utf-8')
    
    # 提取书名
    h1_match = re.match(r'^#\s+(.+)', text, re.MULTILINE)
    book_title = h1_match.group(1).strip() if h1_match else md_path.stem
    
    # 创建 EPUB
    book = epub.EpubBook()
    book.set_identifier(f'buffett-letter-{md_path.stem}')
    book.set_title(book_title)
    book.set_language('zh-CN')
    book.add_author('沃伦·巴菲特 (Warren Buffett)')
    
    # CSS 样式
    css = epub.EpubItem(
        uid='style',
        file_name='style/default.css',
        media_type='text/css',
        content='''
body {
    font-family: "PingFang SC", "Microsoft YaHei", "Noto Sans SC", serif;
    line-height: 1.9;
    color: #2c2c2c;
    margin: 1em;
}
h1 {
    font-size: 1.6em;
    color: #1a1a2e;
    margin: 1.5em 0 0.5em;
    border-bottom: 2px solid #4a6fa5;
    padding-bottom: 0.3em;
}
h2 {
    font-size: 1.3em;
    color: #16213e;
    margin: 1.2em 0 0.4em;
}
h3 {
    font-size: 1.1em;
    color: #333;
    margin: 0.8em 0 0.3em;
}
p {
    margin: 0.6em 0;
    text-indent: 2em;
}
blockquote {
    border-left: 3px solid #4a6fa5;
    padding-left: 1em;
    color: #555;
    font-style: italic;
    margin: 1em 0;
}
table {
    border-collapse: collapse;
    width: 100%;
    margin: 1em 0;
    font-size: 0.9em;
}
th, td {
    border: 1px solid #ddd;
    padding: 0.4em 0.6em;
    text-align: left;
}
th { background: #f5f5f5; font-weight: bold; }
hr { border: none; border-top: 1px solid #ccc; margin: 1.5em 0; }
'''.encode('utf-8')
    )
    book.add_item(css)
    
    # 按段落分章节（致股东信通常无 ## 标题，按主题段落分）
    # 先找所有 "小标题行"：纯文本行，较短，前后有空行
    lines = text.split('\n')
    
    # 尝试按自然段落标题分割
    sections = []
    current_title = book_title
    current_content = []
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        # 跳过一级标题（书名）
        if line.startswith('# ') and i < 5:
            continue
        # 检测是否为小节标题
        # 1. ## 标题
        if line.startswith('## '):
            if current_content:
                sections.append((current_title, '\n'.join(current_content)))
            current_title = stripped.lstrip('#').strip()
            current_content = []
            continue
        
        current_content.append(line)
    
    if current_content:
        sections.append((current_title, '\n'.join(current_content)))
    
    # 如果只有一个大章节，按行数拆分（每约 150 行一章）
    if len(sections) <= 1:
        full_text = sections[0][1] if sections else text
        all_lines = full_text.split('\n')
        chunk_size = 150
        sections = []
        for i in range(0, len(all_lines), chunk_size):
            chunk = all_lines[i:i + chunk_size]
            title = f'{book_title}' if i == 0 else f'续篇 ({i // chunk_size + 1})'
            sections.append((title, '\n'.join(chunk)))
    
    # 转换为 EPUB 章节
    chapters = []
    spine = ['nav']
    toc = []
    
    for idx, (title, content) in enumerate(sections):
        html_content = markdown.markdown(content, extensions=['tables'])
        
        ch = epub.EpubHtml(
            title=title,
            file_name=f'ch_{idx:03d}.xhtml',
            lang='zh-CN'
        )
        ch.content = f'''<html><head><link rel="stylesheet" href="style/default.css"/></head>
<body>
<h1>{title}</h1>
{html_content}
</body></html>'''
        ch.add_item(css)
        book.add_item(ch)
        chapters.append(ch)
        spine.append(ch)
        toc.append(ch)
    
    book.toc = toc
    book.spine = spine
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    
    epub.write_epub(str(epub_path), book, {})
    
    size_kb = epub_path.stat().st_size / 1024
    print(f'✅ EPUB 生成完成: {epub_path}')
    print(f'   书名: {book_title}')
    print(f'   章节数: {len(chapters)}')
    print(f'   文件大小: {size_kb:.1f} KB')
    return str(epub_path)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('用法: python make_epub.py <input.md> [output.epub]')
        sys.exit(1)
    
    md_file = sys.argv[1]
    out_file = sys.argv[2] if len(sys.argv) > 2 else None
    md_to_epub(md_file, out_file)

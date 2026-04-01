import fs from 'fs';
import path from 'path';
import { marked } from 'marked';
import EPub from 'epub-gen-memory';

const mdFile = process.argv[2];
if (!mdFile) {
  console.error('Usage: node make_epub.mjs <markdown-file> [output.epub]');
  process.exit(1);
}

const outputFile = process.argv[3] || mdFile.replace(/\.md$/, '.epub');
const mdContent = fs.readFileSync(mdFile, 'utf-8');

// 把 Markdown 按 ## 二级标题拆分成章节
const lines = mdContent.split('\n');
const chapters = [];
let currentTitle = '';
let currentLines = [];

// 提取一级标题作为书名
let bookTitle = '巴菲特致股东的信';
const h1Match = mdContent.match(/^#\s+(.+)/m);
if (h1Match) {
  bookTitle = h1Match[1].trim();
}

function flushChapter() {
  if (currentLines.length > 0) {
    const md = currentLines.join('\n');
    const html = marked.parse(md);
    chapters.push({
      title: currentTitle || '引言',
      data: html,
    });
  }
}

for (const line of lines) {
  // 跳过和一级标题重复的纯文本行
  if (line.startsWith('## ') || line.startsWith('# ')) {
    flushChapter();
    currentTitle = line.replace(/^#+\s*/, '').trim();
    currentLines = [];
  } else {
    currentLines.push(line);
  }
}
flushChapter();

// 如果没拆出多章节，就按段落分几个大章节
if (chapters.length <= 1) {
  const fullHtml = marked.parse(mdContent);
  // 按约 5000 字拆分
  const paras = fullHtml.split('</p>');
  const chunkSize = Math.ceil(paras.length / Math.max(1, Math.floor(paras.length / 30)));
  const newChapters = [];
  for (let i = 0; i < paras.length; i += chunkSize) {
    const chunk = paras.slice(i, i + chunkSize).join('</p>') + '</p>';
    newChapters.push({
      title: i === 0 ? bookTitle : `续 (${Math.floor(i / chunkSize) + 1})`,
      data: chunk,
    });
  }
  chapters.length = 0;
  chapters.push(...newChapters);
}

const options = {
  title: bookTitle,
  author: '沃伦·巴菲特 (Warren Buffett)',
  publisher: '巴菲特文集',
  lang: 'zh-CN',
  content: chapters,
  css: `
    body { font-family: "PingFang SC", "Microsoft YaHei", serif; line-height: 1.8; color: #333; }
    h1 { font-size: 1.6em; margin: 1em 0 0.5em; color: #1a1a2e; }
    h2 { font-size: 1.3em; margin: 0.8em 0 0.4em; color: #16213e; }
    h3 { font-size: 1.1em; margin: 0.6em 0 0.3em; }
    p { margin: 0.5em 0; text-indent: 2em; }
    blockquote { border-left: 3px solid #4a6fa5; padding-left: 1em; color: #555; font-style: italic; }
  `,
};

const epubBuffer = await new EPub(options).genEpub();
fs.writeFileSync(outputFile, epubBuffer);
console.log(`✅ EPUB 生成完成: ${outputFile}`);
console.log(`   书名: ${bookTitle}`);
console.log(`   章节数: ${chapters.length}`);
console.log(`   文件大小: ${(epubBuffer.length / 1024).toFixed(1)} KB`);

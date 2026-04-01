# Cursor Markdown 自动预览配置说明

## 目标

在 Cursor 中实现下面这套行为：

- 打开新的 `.md` 文件时，自动打开预览
- 不使用“`.md` 默认直接走预览编辑器”的方式，避免 `Unable to retrieve document from URI` 这类报错
- 不使用左右分栏，适合小屏幕
- 已经打开过的 Markdown 标签之间来回切换时，不要再次强制切回预览
- 左侧单击打开新文件时，不要覆盖旧标签

## 背景

实践中发现，直接把 `.md` 绑定到：

```json
"workbench.editorAssociations": {
  "*.md": "vscode.markdown.preview.editor"
}
```

在当前 Cursor 版本下不稳定，容易出现：

- `Unable to retrieve document from URI`
- `Assertion Failed: Argument is 'undefined' or 'null'`

因此最终采用的是：

- `.md` 先按普通 Markdown 文本打开
- 再自动调用预览命令

## 当前生效方案

### 1. 安装的扩展

- `yzhang.markdown-all-in-one`
- `matt-rudge.auto-open-preview-panel`

其中真正负责“自动打开预览”的是：

- `matt-rudge.auto-open-preview-panel`

`Markdown All in One` 目前只是保留安装，不负责自动侧边预览。

### 2. 当前 `settings.json`

用户设置文件路径：

- macOS: `~/Library/Application Support/Cursor/User/settings.json`

当前建议配置如下：

```json
{
  "window.commandCenter": true,
  "remote.SSH.remotePlatform": {
    "barry": "linux"
  },
  "keyboard.dispatch": "keyCode",
  "git.openRepositoryInParentFolders": "always",
  "workbench.editor.enablePreview": false,
  "workbench.editor.enablePreviewFromCodeNavigation": false,
  "workbench.editor.enablePreviewFromQuickOpen": false,
  "workbench.editor.editorActionsLocation": "default",
  "workbench.editorAssociations": {
    "*.xlsx": "default"
  },
  "markdown.extension.preview.autoShowPreviewToSide": false,
  "autoOpenPreviewPanel.openPreviewToTheSide": false,
  "autoOpenPreviewPanel.languages": "markdown",
  "files.associations": {
    "*.md": "markdown"
  }
}
```

### 3. 这组配置分别解决什么问题

- `workbench.editor.enablePreview: false`
  关闭 Cursor 的“预览标签”机制，避免左侧点新文件时覆盖旧标签。

- `workbench.editor.enablePreviewFromCodeNavigation: false`
  避免通过代码跳转时使用预览标签。

- `workbench.editor.enablePreviewFromQuickOpen: false`
  避免通过 `Cmd+P` 打开文件时使用预览标签。

- `markdown.extension.preview.autoShowPreviewToSide: false`
  禁用 `Markdown All in One` 的自动侧边预览，避免和小屏需求冲突。

- `autoOpenPreviewPanel.openPreviewToTheSide: false`
  自动打开预览，但不是左右分栏。

- `autoOpenPreviewPanel.languages: "markdown"`
  只对 Markdown 生效。

- `files.associations -> "*.md": "markdown"`
  确保 `.md` 先按普通 Markdown 文本打开，而不是直接绑定到预览编辑器。

## 本地热修补

### 1. 为什么需要热修补

`matt-rudge.auto-open-preview-panel` 原版扩展虽然能自动打开预览，但有两个问题：

1. 后面打开的新 Markdown 文件不一定会正确切到对应预览
2. 如果简单改成“切到任何 Markdown 标签都自动预览”，又会导致无法回到纯文本模式

所以最终做了一个本地热修补。

### 2. 修补后的行为

- 新打开一个 `.md` 文件时：自动打开该文件的预览
- 已经打开的 `.md` 文件之间切换：不再重复强制切换成预览
- 文件关闭后，再次重新打开时：会再次自动预览

### 3. 修补文件路径

- `~/.cursor/extensions/matt-rudge.auto-open-preview-panel-0.0.6-universal/out/extension.js`

当前修补后的核心逻辑是：

```js
const previewedDocs = new Set();

function openPreview(doc) {
  vscode.commands.executeCommand(`${doc.languageId}.${previewCommand}`, doc.uri)
    .then(() => { }, (e) => console.error(e));
}

function maybeOpenPreview(doc) {
  let languages = refreshSettings();
  const docKey = doc.uri.toString();
  if (extensionEnabled && languages.includes(doc.languageId) && !previewedDocs.has(docKey)) {
    previewedDocs.add(docKey);
    openPreview(doc);
  }
}

if (vscode.window.activeTextEditor) {
  maybeOpenPreview(vscode.window.activeTextEditor.document);
}

vscode.workspace.onDidOpenTextDocument((doc) => {
  maybeOpenPreview(doc);
});

vscode.workspace.onDidCloseTextDocument((doc) => {
  previewedDocs.delete(doc.uri.toString());
});
```

## 日常使用效果

现在的实际体验应当是：

1. 左侧点击一个新的 `.md` 文件
2. 文件先正常作为文本编辑器打开
3. Cursor 自动再打开这个文件的预览
4. 顶部标签不会因为“预览标签”机制被覆盖
5. 回到已经打开过的 Markdown 文件时，不会再次被强制切成预览

## 注意事项

- 这个方案不是 Cursor 原生完整支持的路径，而是“设置 + 扩展 + 本地热修补”的组合方案。
- 如果 `matt-rudge.auto-open-preview-panel` 扩展升级，`out/extension.js` 的本地改动可能会被覆盖。
- 如果覆盖后行为退化，优先重新检查上面的热修补文件。
- 如果未来 Cursor 官方修复了“`.md` 默认预览编辑器”这条链路，可以重新评估是否回到官方方式。

## 若以后失效，优先检查

1. `settings.json` 里是否仍然保留上面的配置
2. 扩展 `matt-rudge.auto-open-preview-panel` 是否还在
3. `~/.cursor/extensions/.../out/extension.js` 是否被升级覆盖
4. 修改后是否执行过 `Developer: Reload Window`

## 最终结论

对当前这台机器和当前 Cursor 版本，最稳的 Markdown 自动预览方案不是：

- `.md` 默认直接绑定预览编辑器

而是：

- 普通 Markdown 文本打开
- 自动触发预览
- 关闭预览标签覆盖行为
- 对自动预览扩展做本地热修补

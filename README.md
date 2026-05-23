# 悟空飞书导出 Markdown 工具

![https://asiaassets.gokuscraper.com/images/2026/04/22/b90fd68e1c4b09ed.webp](https://asiaassets.gokuscraper.com/images/2026/04/22/b90fd68e1c4b09ed.webp)

这是一个飞书文档导出工具，支持导出Markdown格式，并进行数据分析。

## 核心优势

- 免登录免配置，可以直接在线使用
- 直接用浏览器导出，下载 ZIP（含 `.md` + 图片资源目录）
- 可以 对 Markdown 做基础统计、标题预览、链接导出、高频中文关键词分析

**中文** | [English](README_EN.md)

---

## 在线使用

[https://feishu66.streamlit.app/](https://feishu66.streamlit.app/)

## 功能概览

### 0导出

- 输入飞书/Lark 文档 URL
- 调用 CLI 执行导出（子进程方式，避免部分环境直接 import 报错）
- 页面实时显示命令行日志
- 导出完成后提供 ZIP 下载（包含 Markdown 与资源目录）
- 导出结束后自动清理临时目录（含 `finally` 兜底）

### 1分析

- 支持三种输入来源：
  1. 最近一次导出的 Markdown（自动缓存）
  2. 上传 `.md` 文件
  3. 直接粘贴 Markdown 文本
- 统计指标：总字数、总行数、标题数、代码块数、链接数、图片数
- 可导出链接列表（`.txt`）
- 高频关键词仅统计中文词，分词使用 `CoreNatureDictionary.txt`

---

## 运行方式

### 方式一：直接启动 Streamlit

```bash
streamlit run streamlit_app.py
```

### 方式二：使用启动脚本（自动打开浏览器）

```bash
python start_ui.py
```

默认地址：<http://localhost:8501>

---

## 环境要求

- Python 3.11+
- 已安装项目依赖（见 `pyproject.toml`）

建议先在项目根目录执行：

```bash
pip install -e .
```

如需浏览器导出能力，请确保安装 Playwright 及浏览器内核：

```bash
pip install playwright
playwright install chromium
```

---

## 目录与关键文件

- `streamlit_app.py`：主界面与业务逻辑
- `start_ui.py`：一键启动脚本
- `CoreNatureDictionary.txt`：中文分词词典（高频关键词分析使用）
- `framework_settings.json`：页面输入配置缓存

---

## 使用说明

1. 打开页面后进入 `0导出`
2. 填入飞书/Lark 文档链接，点击“开始导出”
3. 导出完成后点击“点击下载到本地（含图片文件夹）”
4. 切换到 `1分析`
   - 可直接点“开始分析”（自动用最近导出的 md）
   - 或上传/粘贴 Markdown 再分析

---

# 公众号和交流群

![交流群](https://asiaassets.gokuscraper.com/%E6%82%9F%E7%A9%BA%E7%88%AC%E8%99%AB%E5%85%AC%E4%BC%97%E5%8F%B7.jpg)

## 官方网站

https://gokuscraper.com

在线体验工具，或了解更多数据分析能力。

如有定制化数据分析或工具需求，欢迎交流。



## 常见问题

### 1) 提示找不到 `feishu_docx.main`

应用会自动回退到 `feishu_docx.cli.main`。如果仍失败，请确认虚拟环境和依赖安装正常。

### 2) 为什么下载是 ZIP 而不是单个 md？

因为 Markdown 会引用同名资源目录（图片/附件）。ZIP 能保证解压后路径完整可用。

### 3) 高频关键词为什么是中文词？

分析逻辑已限定中文词，并基于 `CoreNatureDictionary.txt` 分词，更适合中文内容场景。

---

## 备注

本工具基于现有 `feishu-docx` 能力进行 Streamlit UI 封装，重点是“简单可用、可视化、可下载、可分析”。

## 免责声明

本项目为数据分析与可视化工具，仅处理公开数据用于研究分析。

本项目与任何第三方平台无关联或授权关系。

禁止用于任何违法或侵犯他人权益的用途，使用者需自行承担全部责任。

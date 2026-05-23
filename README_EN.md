# Goku Feishu Markdown Downloader 

[中文](README.md) | **English**

This is a lightweight Streamlit app focused on two scenarios: **Feishu/Lark document export + Markdown analysis**.

- `0 Export`: Browser-based export without app login, then download a ZIP package (`.md` + images/attachments folder)
- `1 Analyze`: Basic Markdown stats, heading preview, link export, and high-frequency Chinese keyword analysis

---

## Online Demo

[https://feishu66.streamlit.app/](https://feishu66.streamlit.app/)

## Features

### 0 Export

- Input a Feishu/Lark document URL
- Run CLI export via subprocess (avoids import issues in some runtime environments)
- Stream command-line logs in real time on the page
- Provide ZIP download after export (Markdown + assets folder)
- Auto-clean temporary directories after completion (with `finally` safeguard)

### 1 Analyze

- Supports three input sources:
  1. Most recently exported Markdown (auto-cached)
  2. Upload an `.md` file
  3. Paste Markdown text directly
- Metrics: total characters, total lines, heading count, code block count, link count, image count
- Export all extracted links as `.txt`
- High-frequency keywords are Chinese-only, tokenized using `CoreNatureDictionary.txt`

---

## Run

### Option 1: Start Streamlit directly

```bash
streamlit run streamlit_app.py
```

### Option 2: Use startup script (opens browser automatically)

```bash
python start_ui.py
```

Default URL: [http://localhost:8501](http://localhost:8501)

---

## Requirements

- Python 3.11+
- Project dependencies installed (see `pyproject.toml`)

Recommended in project root:

```bash
pip install -e .
```

For browser export capability, install Playwright and browser binaries:

```bash
pip install playwright
playwright install chromium
```

---

## Key Files

- `streamlit_app.py`: Main UI and business logic
- `start_ui.py`: One-click startup script
- `CoreNatureDictionary.txt`: Chinese token dictionary (used for keyword analysis)
- `framework_settings.json`: Cached page input settings

---

## How to Use

1. Open the app and go to `0 Export`
2. Paste a Feishu/Lark document link and click “Start Export”
3. After completion, click download (ZIP includes images/assets folder)
4. Switch to `1 Analyze`
   - Click analyze directly to use the latest exported Markdown
   - Or upload/paste Markdown, then analyze

---

## FAQ

### 1) `feishu_docx.main` not found

The app will automatically fall back to `feishu_docx.cli.main`. If it still fails, check your Python environment and dependency installation.

### 2) Why ZIP instead of a single `.md` file?

Because Markdown usually references an assets directory (images/attachments). ZIP keeps paths intact after extraction.

### 3) Why are high-frequency keywords Chinese only?

Current analysis logic is intentionally restricted to Chinese tokens and uses `CoreNatureDictionary.txt`, which is optimized for Chinese content.

---

## Notes

This UI wraps existing `feishu-docx` capabilities and focuses on being simple, visual, downloadable, and analysis-friendly.

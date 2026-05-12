import base64
import json
import os
import subprocess
import sys
import shutil
import tempfile
import threading
import time
import io
import zipfile
import re
import mimetypes
from collections import Counter
from functools import lru_cache
from importlib.util import find_spec
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import streamlit as st

# --- 基础配置 ---
SETTINGS_FILE = "framework_settings.json"
APP_DIR = Path(__file__).resolve().parent
CORE_DICT_PATH = APP_DIR / "CoreNatureDictionary.txt"


def resolve_asset_path(file_name: str) -> str:
    candidates = [APP_DIR / file_name, Path.cwd() / file_name]
    for p in candidates:
        if p.exists(): return str(p)
    return file_name


def image_to_data_uri(path: str) -> str:
    try:
        file_path = Path(path)
        if not file_path.exists():
            return ""
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if not mime_type:
            mime_type = "image/png"
        data = file_path.read_bytes()
        encoded = base64.b64encode(data).decode("utf-8")
        return f"data:{mime_type};base64,{encoded}"
    except Exception:
        return ""


# --- 核心工具 (保留：设置管理与文件操作) ---
def load_settings() -> Dict[str, Any]:
    if not os.path.exists(SETTINGS_FILE):
        return {"mode": "免登录导出", "target_input": ""}
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"mode": "免登录导出", "target_input": ""}


def save_settings(mode: str, target_input: str) -> None:
    data = {
        "mode": mode,
        "target_input": target_input,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# --- 状态初始化 ---
def init_state():
    settings = load_settings()
    defaults = {
        "mode": settings.get("mode", "免登录导出"),
        "target_input": settings.get("target_input", ""),
        "last_export_md_text": "",
        "last_export_md_name": "",
        "chromium_ready": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def ensure_playwright_chromium() -> tuple[bool, str]:
    """确保 Playwright Chromium 已安装。"""
    if st.session_state.get("chromium_ready"):
        return True, ""

    install_cmd = [sys.executable, "-m", "playwright", "install", "chromium"]
    completed = subprocess.run(
        install_cmd,
        capture_output=True,
        text=True,
        cwd=str(APP_DIR),
        check=False,
    )

    output = (completed.stdout or "")
    if completed.stderr:
        output = f"{output}\n{completed.stderr}".strip()

    if completed.returncode == 0:
        st.session_state["chromium_ready"] = True
        return True, output
    return False, output


def run_export_browser_with_live_log(url: str) -> tuple[int, str, str, Path]:
    output_dir = Path(tempfile.mkdtemp(prefix="feishu_export_"))
    os.makedirs(output_dir, exist_ok=True)
    module_name = "feishu_docx.main" if find_spec("feishu_docx.main") else "feishu_docx.cli.main"
    command = [
        sys.executable,
        "-W", "ignore",  # 添加这一行，屏蔽报警
        "-m",
        module_name,
        "export-browser",
        url,
        "-o",
        str(output_dir),
    ]

    status_placeholder = st.empty()
    log_placeholder = st.empty()
    status_placeholder.info("正在检查浏览器环境，请稍候...")

    chromium_ok, chromium_log = ensure_playwright_chromium()
    if chromium_log:
        log_placeholder.code(chromium_log, language="bash")
    if not chromium_ok:
        status_placeholder.error("Chromium 安装失败，无法继续导出")
        install_cmd_text = f"{sys.executable} -m playwright install chromium"
        return -1, install_cmd_text, chromium_log or "Chromium 安装失败", output_dir

    status_placeholder.info("正在执行导出命令，请稍候...")

    with tempfile.NamedTemporaryFile(mode="w+", encoding="utf-8", delete=False) as tmp:
        log_path = tmp.name

    result_holder: dict[str, Any] = {}

    def _worker() -> None:
        with open(log_path, "w", encoding="utf-8", buffering=1) as log_file:
            try:
                completed = subprocess.run(
                    command,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    text=True,
                    cwd=str(APP_DIR),
                    check=False,
                )
                result_holder["returncode"] = completed.returncode
            except Exception as e:
                result_holder["returncode"] = -1
                with open(log_path, "a", encoding="utf-8") as fallback_log:
                    fallback_log.write(f"执行异常: {e}\n")

    worker = threading.Thread(target=_worker, daemon=True)
    worker.start()

    cursor = 0
    content = ""
    while worker.is_alive():
        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as reader:
                reader.seek(cursor)
                chunk = reader.read()
                if chunk:
                    content += chunk
                    cursor = reader.tell()
                    log_placeholder.code(content or "等待输出中...", language="bash")
        except Exception:
            pass
        time.sleep(0.2)

    worker.join(timeout=1)

    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as reader:
            content = reader.read()
    except Exception:
        content = content or ""

    if not content:
        content = "(无输出)"
    log_placeholder.code(content, language="bash")

    return_code = int(result_holder.get("returncode", -1))
    if return_code == 0:
        status_placeholder.success("导出完成")
    else:
        status_placeholder.error("导出失败，请查看下方日志")

    return return_code, " ".join(command), content, output_dir


def pick_exported_markdown(output_dir: Path) -> Path | None:
    files = sorted(output_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def build_export_zip_bytes(output_dir: Path, markdown_file: Path) -> tuple[str, bytes]:
    zip_name = f"{markdown_file.stem}.zip"
    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(markdown_file, arcname=markdown_file.name)

        assets_dir = output_dir / markdown_file.stem
        if assets_dir.exists() and assets_dir.is_dir():
            for file_path in assets_dir.rglob("*"):
                if file_path.is_file():
                    zf.write(file_path, arcname=str(file_path.relative_to(output_dir)))

    return zip_name, buffer.getvalue()


@lru_cache(maxsize=1)
def load_core_dictionary() -> tuple[set[str], int]:
    """加载 CoreNatureDictionary 词库，仅保留中文词。"""
    if not CORE_DICT_PATH.exists():
        return set(), 0

    words: set[str] = set()
    max_len = 0
    try:
        with open(CORE_DICT_PATH, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                term = line.split("\t", 1)[0].strip()
                if len(term) < 2:
                    continue
                if not re.fullmatch(r"[\u4e00-\u9fff]+", term):
                    continue
                words.add(term)
                if len(term) > max_len:
                    max_len = len(term)
    except Exception:
        return set(), 0

    return words, max_len


def tokenize_chinese_with_core_dict(text: str) -> list[str]:
    """使用 CoreNatureDictionary 做最大正向匹配分词。"""
    words, max_len = load_core_dictionary()
    if not words or max_len <= 0:
        return re.findall(r"[\u4e00-\u9fff]{2,}", text)

    tokens: list[str] = []
    chinese_chunks = re.findall(r"[\u4e00-\u9fff]+", text)

    for chunk in chinese_chunks:
        i = 0
        n = len(chunk)
        while i < n:
            upper = min(n, i + max_len)
            matched = ""
            for j in range(upper, i, -1):
                candidate = chunk[i:j]
                if candidate in words:
                    matched = candidate
                    break

            if matched:
                tokens.append(matched)
                i += len(matched)
            else:
                # 词库未命中时退化为双字切分，尽量保留语义
                if i + 2 <= n:
                    tokens.append(chunk[i:i + 2])
                    i += 2
                else:
                    i += 1

    return [t for t in tokens if len(t) >= 2]


def analyze_markdown_text(md_text: str) -> dict[str, Any]:
    lines = md_text.splitlines()
    non_empty_lines = [line for line in lines if line.strip()]
    heading_lines = [line for line in lines if re.match(r"^\s{0,3}#{1,6}\s+", line)]

    image_count = len(re.findall(r"!\[[^\]]*\]\([^\)]+\)", md_text))
    raw_links = re.findall(r"(?<!!)\[[^\]]+\]\(([^\)]+)\)", md_text)
    links: list[str] = []
    seen: set[str] = set()
    for raw in raw_links:
        url = raw.strip()
        if " " in url:
            url = url.split(" ", 1)[0].strip()
        if not url:
            continue
        if url not in seen:
            seen.add(url)
            links.append(url)
    link_count = len(links)
    code_block_count = len(re.findall(r"```", md_text)) // 2

    # 高频关键词仅统计中文词（使用 CoreNatureDictionary 分词）
    tokens = tokenize_chinese_with_core_dict(md_text)
    stop_words = {
        "一个", "我们", "你们", "他们", "以及", "可以", "如果", "因为", "所以", "就是", "然后",
        "这个", "那个", "进行", "通过", "相关", "需要", "已经", "没有", "还是", "一下",
    }
    filtered = [t for t in tokens if t not in stop_words]
    top_keywords = Counter(filtered).most_common(15)

    return {
        "char_count": len(md_text),
        "line_count": len(lines),
        "non_empty_line_count": len(non_empty_lines),
        "heading_count": len(heading_lines),
        "image_count": image_count,
        "link_count": link_count,
        "links": links,
        "code_block_count": code_block_count,
        "headings": heading_lines[:20],
        "top_keywords": top_keywords,
    }


# --- 主程序 ---
def main():
    st.set_page_config(
        page_title="悟空飞书导出Markdowm工具（支持Lark）",
        page_icon=resolve_asset_path("logo.svg"),
        layout="wide"
    )
    init_state()

    # 标题区
    title_col1, title_col2, title_col3 = st.columns([1, 10, 5])
    with title_col1:
        st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
        st.image(resolve_asset_path("logo.svg"), width=42)
    with title_col2:
        st.markdown("<h1 style='margin: 0; margin-left: -22px;'>悟空飞书导出Markdowm工具(支持Lark)</h1>", unsafe_allow_html=True)
    with title_col3:
        right_col1, right_col2 = st.columns([3, 3])
        with right_col1:
            github_src = image_to_data_uri(resolve_asset_path("github-logo.png"))
            if github_src:
                st.markdown(
                    """
                    <div style="display:flex; flex-direction:column; align-items:center; width:140px; margin:0 auto;">
                        <img src="{src}" style="width:140px; height:auto; display:block;" />
                        <div style="margin-top:4px; text-align:center;">
                            <a href="https://github.com/gokuscraper/goku-feishu-markdown-scraper" target="_blank">本工具开源</a>
                        </div>
                    </div>
                    """.format(src=github_src),
                    unsafe_allow_html=True,
                )
            else:
                st.image(resolve_asset_path("github-logo.png"), width=140)
                st.markdown(
                    "<div style='text-align: center; margin-top: 4px;'><a href='https://github.com/gokuscraper/goku-feishu-markdown-scraper' target='_blank'>本工具开源</a></div>",
                    unsafe_allow_html=True,
                )
        with right_col2:
            gzh_src = image_to_data_uri(resolve_asset_path("gzh.jpg"))
            if gzh_src:
                st.markdown(
                    """
                    <div style="display:flex; flex-direction:column; align-items:center; width:140px; margin:0 auto;">
                        <img src="{src}" style="width:140px; height:auto; display:block;" />
                        <div style="margin-top:4px; text-align:center;">交流群</div>
                    </div>
                    """.format(src=gzh_src),
                    unsafe_allow_html=True,
                )
            else:
                st.image(resolve_asset_path("gzh.jpg"), width=140)
                st.markdown("<div style='text-align: center; margin-top: 4px;'>交流群</div>", unsafe_allow_html=True)
    st.caption("使用方法：填链接，点导出，耐心等，选下载，看分析。")

    st.divider()

    tabs = st.tabs(["0导出", "1分析"])

    with tabs[0]:
        st.session_state["target_input"] = st.text_input(
            "飞书文档 URL",
            value=st.session_state["target_input"],
            placeholder="https://xxx.feishu.cn/wiki/xxxx 或 https://xxx.larkoffice.com/docx/xxxx",
        )

        save_settings(st.session_state["mode"], st.session_state["target_input"])

        if st.button("开始导出", type="primary", use_container_width=True):
            url = st.session_state["target_input"].strip()

            if not url:
                st.warning("请先输入文档 URL")
            else:
                temp_output_dir: Path | None = None
                try:
                    code, command_text, _, temp_output_dir = run_export_browser_with_live_log(url)
                    st.caption(f"执行命令：{command_text}")
                    if code != 0:
                        st.info("导出失败。已自动尝试模块回退（feishu_docx.main -> feishu_docx.cli.main），请检查日志。")
                    else:
                        output_file = pick_exported_markdown(temp_output_dir)
                        if output_file and output_file.exists():
                            st.success(f"导出成功：{output_file.name}")
                            st.session_state["last_export_md_text"] = output_file.read_text(encoding="utf-8", errors="replace")
                            st.session_state["last_export_md_name"] = output_file.name
                            zip_name, zip_bytes = build_export_zip_bytes(temp_output_dir, output_file)
                            st.markdown(
                                """
                                <style>
                                div[data-testid="stDownloadButton"] button {
                                    background-color: #FFD54F !important;
                                    color: #111827 !important;
                                    border: 1px solid #E0A800 !important;
                                    font-weight: 700 !important;
                                }
                                div[data-testid="stDownloadButton"] button:hover {
                                    background-color: #FFCA28 !important;
                                    color: #111827 !important;
                                    border: 1px solid #D89C00 !important;
                                }
                                </style>
                                """,
                                unsafe_allow_html=True,
                            )
                            st.download_button(
                                "点击下载到本地（含图片文件夹）",
                                data=zip_bytes,
                                file_name=zip_name,
                                mime="application/zip",
                                use_container_width=True,
                            )
                        else:
                            st.warning("导出成功，但未找到 Markdown 文件。")
                finally:
                    if temp_output_dir is not None:
                        try:
                            shutil.rmtree(temp_output_dir, ignore_errors=True)
                        except Exception:
                            pass

    with tabs[1]:
        st.subheader("文字版 MD 分析")
        if st.session_state.get("last_export_md_text"):
            st.info(f"可直接分析最近导出文件：{st.session_state.get('last_export_md_name', '未命名.md')}")
        uploaded_md = st.file_uploader("上传 Markdown 文件（.md）", type=["md"]) 
        md_text = st.text_area("或直接粘贴 Markdown 内容", height=220, placeholder="# 粘贴你的 Markdown 内容")

        if st.button("开始分析", type="primary", use_container_width=True):
            final_text = md_text
            source_label = "手动粘贴"
            if uploaded_md is not None:
                final_text = uploaded_md.read().decode("utf-8", errors="replace")
                source_label = f"上传文件：{uploaded_md.name}"
            elif not final_text.strip() and st.session_state.get("last_export_md_text"):
                final_text = st.session_state.get("last_export_md_text", "")
                source_label = f"最近导出：{st.session_state.get('last_export_md_name', '未命名.md')}"

            if not final_text.strip():
                st.warning("请先上传 .md 文件、粘贴 Markdown 内容，或先去 0导出 执行一次导出")
            else:
                st.caption(f"分析来源：{source_label}")
                result = analyze_markdown_text(final_text)
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("总字数", result["char_count"])
                c2.metric("总行数", result["line_count"])
                c3.metric("标题数", result["heading_count"])
                c4.metric("代码块", result["code_block_count"])

                c5, c7 = st.columns([1, 1])
                c5.metric("链接数量", result["link_count"])
                c7.metric("图片数量", result["image_count"])

                if result["links"]:
                    link_text = "\n".join(result["links"])
                    st.download_button(
                        "下载链接列表(.txt)",
                        data=link_text.encode("utf-8"),
                        file_name="markdown_links.txt",
                        mime="text/plain",
                        use_container_width=False,
                        type="secondary",
                        key=f"export_links_{result['link_count']}_{len(result['links'])}",
                    )
                else:
                    st.caption("无可导出链接")

                st.markdown("#### 标题预览（前 20 条）")
                if result["headings"]:
                    st.code("\n".join(result["headings"]), language="markdown")
                else:
                    st.info("未识别到标题")

                st.markdown("#### 高频关键词（Top 15）")
                if result["top_keywords"]:
                    keyword_lines = [f"{word}: {count}" for word, count in result["top_keywords"]]
                    st.code("\n".join(keyword_lines), language="text")
                else:
                    st.info("未识别到有效关键词")

    st.divider()
    st.caption("Powered by 悟空爬虫 | 让数据不仅被看见，更被读懂。")


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""group-daily（WaytoAGI-EDU）公开版环境自检。

公开教育版默认采用「低风险离线素材模式」：
    1. 用户自行准备 story.json 或手动整理后的群聊素材；
    2. Skill 只负责摘要结构、HTML 渲染与 PNG 导出；
    3. 默认不要求、不鼓励接入微信数据库读取、解密或刷新链路。

检查项:
    1. macOS / Linux / Windows 基础平台提示；
    2. Python 依赖: Pillow（推荐/截图辅助）, openai-whisper 与 silk-python（可选语音）；
    3. Chrome / Chromium 浏览器（HTML → PNG 用，推荐）；
    4. assets/waytoagi-edu 教育版素材是否存在；
    5. examples/story_waytoagi_edu_demo.json 示例是否存在；
    6. vchat / wechat-decrypt 仅作为历史高级能力提示，不作为公开版必装项。
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
from pathlib import Path


ANSI_GREEN = "\033[32m"
ANSI_YELLOW = "\033[33m"
ANSI_RED = "\033[31m"
ANSI_DIM = "\033[2m"
ANSI_RESET = "\033[0m"

ROOT = Path(__file__).resolve().parents[1]


def ok(msg, detail=""):
    print(f"  {ANSI_GREEN}✅{ANSI_RESET} {msg}", end="")
    if detail:
        print(f"  {ANSI_DIM}{detail}{ANSI_RESET}")
    else:
        print()


def warn(msg, fix=""):
    print(f"  {ANSI_YELLOW}⚠️{ANSI_RESET}  {msg}")
    if fix:
        print(f"     {ANSI_DIM}建议: {fix}{ANSI_RESET}")


def fail(msg, fix=""):
    print(f"  {ANSI_RED}❌{ANSI_RESET} {msg}")
    if fix:
        print(f"     {ANSI_DIM}修复: {fix}{ANSI_RESET}")


def header(title):
    print(f"\n{ANSI_DIM}── {title} ─────────────{ANSI_RESET}")


def check_platform():
    header("平台")
    system = platform.system()
    if system == "Darwin":
        ok(f"macOS {platform.mac_ver()[0]}")
        return True
    warn(f"当前系统是 {system}", "核心 Python/HTML 逻辑可参考使用；PNG 截图路径可能需要按系统调整")
    return True


def check_python_deps():
    header("Python 依赖")
    required_ok = True
    try:
        import PIL  # noqa: F401
        ok("Pillow")
    except Exception as e:
        fail(f"Pillow 不可用：{type(e).__name__}: {e}", "python3 -m pip install Pillow")
        required_ok = False

    try:
        import whisper  # noqa: F401
        ok("openai-whisper（可选：语音转写）")
    except Exception as e:
        warn(f"openai-whisper 不可用（可选，不影响文字群日报）：{type(e).__name__}: {e}",
             "不需要语音功能可忽略；如需语音转写，建议在独立 Python venv 中安装")

    try:
        import pysilk  # noqa: F401
        ok("silk-python / pysilk（可选：语音解码）")
    except Exception as e:
        warn(f"silk-python / pysilk 不可用（可选）：{type(e).__name__}: {e}",
             "不需要语音功能可忽略")
    return required_ok


def check_browser():
    header("浏览器（HTML → PNG 推荐）")
    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    ]
    for p in candidates:
        if os.access(p, os.X_OK):
            ok("找到浏览器", detail=p)
            return True

    path_browser = shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("msedge")
    if path_browser:
        ok("在 PATH 中找到 Chrome/Chromium/Edge", detail=path_browser)
        return True

    warn("没找到 Chrome / Chromium / Edge", "仍可先生成 HTML；如需自动导出 PNG，请安装 Chrome 或改造截图脚本")
    return True


def check_assets():
    header("WaytoAGI-EDU 教育版素材")
    asset_dir = ROOT / "assets" / "waytoagi-edu"
    manifest = asset_dir / "manifest.json"
    if not manifest.exists():
        fail("缺少 assets/waytoagi-edu/manifest.json", "请确认教育版素材已随仓库 clone 完整")
        return False
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except Exception as e:
        fail(f"manifest.json 无法读取：{type(e).__name__}: {e}")
        return False

    needed = ["mascot_logo.png", "mascot_hero.png", "mascot_full.png", "sticker_sheet.png"]
    missing = [name for name in needed if not (asset_dir / name).exists()]
    sticker_count = len(list(asset_dir.glob("sticker_*.png")))
    if missing:
        fail("缺少关键素材: " + ", ".join(missing), "请重新拉取仓库或检查 assets/waytoagi-edu")
        return False
    ok("教育版 logo / hero / 全身吉祥物 / 表情包集合齐全", detail=f"stickers={sticker_count}")
    ok("配色清单已加载", detail=", ".join(data.get("palette", {}).keys()))
    return True


def check_examples():
    header("示例 story 与图片模板")
    story = ROOT / "examples" / "story_waytoagi_edu_demo.json"
    if story.exists():
        ok("示例 story.json 存在", detail=str(story.relative_to(ROOT)))
    else:
        warn("尚未发现 examples/story_waytoagi_edu_demo.json", "可参考 references/story-schema.md 手动创建")

    example_dir = ROOT / "assets" / "examples"
    examples = sorted(example_dir.glob("*.png")) if example_dir.exists() else []
    if examples:
        ok("确认版图片模板存在", detail=", ".join(p.name for p in examples))
    else:
        warn("尚未发现确认版图片模板", "不影响脚本运行，但 README 展示效果会变弱")
    return True


def check_bailian_cli():
    header("阿里云百炼 CLI（可选：自动生成 story.json）")
    bl = shutil.which("bl")
    if not bl:
        warn("未检测到 bl 命令", "如需从群聊素材自动生成 story.json，先运行 npm install -g bailian-cli")
        return True

    try:
        version = subprocess.run(
            [bl, "--version"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
        ok("检测到百炼 CLI", detail=version or bl)
    except Exception as e:
        warn(f"bl --version 执行失败：{type(e).__name__}: {e}", "确认 Node.js >= 22.12 且 bailian-cli 安装完整")
        return True

    try:
        status = subprocess.run(
            [bl, "auth", "status"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout
        data = json.loads(status)
        if data.get("authenticated"):
            ok("百炼认证已配置", detail="可运行 scripts/generate_story_with_bl.py")
        else:
            warn("bl 尚未登录", "运行 bl auth login --api-key sk-xxxxx")
    except Exception as e:
        warn(f"无法读取 bl auth status：{type(e).__name__}: {e}", "运行 bl auth status 手动确认")
    return True


def check_optional_wechat_stack():
    header("微信自动读取链路（历史高级能力，公开版默认不推荐）")
    vchat = shutil.which("vchat")
    if vchat:
        warn("检测到 vchat", f"{vchat}；请仅在明确授权、合规且接受平台风险时使用")
    else:
        ok("未检测到 vchat；公开教育版默认不依赖它")

    root = os.environ.get("VCHAT_DATA_DIR")
    if root:
        warn("设置了 VCHAT_DATA_DIR", "这属于高级/历史链路；公开版推荐改用离线 story.json")
    else:
        ok("未设置 VCHAT_DATA_DIR；符合低风险离线模式")
    return True


def check_env_vars():
    header("环境变量（可选）")
    gd_vault = os.environ.get("GROUP_DAILY_VAULT")
    if gd_vault:
        path = Path(os.path.expanduser(gd_vault))
        if path.exists():
            ok("GROUP_DAILY_VAULT", detail=str(path))
        else:
            warn(f"GROUP_DAILY_VAULT 指向不存在的目录: {path}", f"mkdir -p '{path}' 或修改环境变量")
    else:
        warn("GROUP_DAILY_VAULT 未设", "会按脚本默认值输出；也可显式设置为你的日报目录")


def main():
    print(f"{ANSI_DIM}group-daily（WaytoAGI-EDU）公开版环境自检{ANSI_RESET}")
    checks = [
        check_platform(),
        check_python_deps(),
        check_browser(),
        check_assets(),
        check_examples(),
        check_bailian_cli(),
        check_optional_wechat_stack(),
    ]
    check_env_vars()
    print()
    if all(checks):
        print(f"{ANSI_GREEN}✅ 公开版低风险离线流程已就绪：可用 story.json 生成 HTML / PNG。{ANSI_RESET}")
    else:
        print(f"{ANSI_RED}❌ 仍有必需项缺失，请按上方提示修复后重试。{ANSI_RESET}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()

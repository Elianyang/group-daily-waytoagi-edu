#!/usr/bin/env python3
"""主编排脚本：吃 story.json，生成 WaytoAGI-EDU 群日报。

默认流程：头像导出 → 品牌化 HTML → PNG 长图。
进阶流程：加 --site 后，同时生成可交互 Dashboard（每日总结 / 我的群友 / 聊天记录）。

用法（AI 准备好 story.json 后调用）:
    python3 make_daily.py \\
        --story /tmp/story.json \\
        --out-dir ~/Desktop

    python3 make_daily.py \\
        --story /tmp/story.json \\
        --chat-log /tmp/chat_history.txt \\
        --site \\
        --out-dir ~/Desktop

输出:
    ~/Desktop/群日报_<群名>_<日期>.html
    ~/Desktop/群日报_<群名>_<日期>.png
    ~/Desktop/群日报_<群名>_<日期>_dashboard.html   # 启用 --site 时
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent


def collect_wxids(story):
    """从 story 中收集需要头像的人物 → wxid 映射。

    story.timeline[].cast: [{name, wxid}] 或 story.timeline[].protagonists +
    story.timeline[].wxids 平行数组都支持。
    story.highlights[].name + .wxid 也收集。
    """
    mapping = {}

    for s in story.get("timeline", []):
        cast = s.get("cast")
        if cast:
            for c in cast:
                if c.get("wxid"):
                    mapping[c["wxid"]] = c["name"]
        else:
            names = s.get("protagonists", [])
            wxids = s.get("wxids", [])
            for n, w in zip(names, wxids):
                if w:
                    mapping[w] = n

    for hl in story.get("highlights", []):
        if hl.get("wxid"):
            mapping[hl["wxid"]] = hl["name"]

    return mapping


def normalize_protagonists(story):
    """把 timeline[].cast 形式归一化为 protagonists + wxids 平行数组"""
    for s in story.get("timeline", []):
        if "cast" in s and not s.get("protagonists"):
            cast = s["cast"]
            s["protagonists"] = [c["name"] for c in cast]
            s["wxids"] = [c.get("wxid", "") for c in cast]


def run(cmd, **kwargs):
    print(f"$ {' '.join(cmd)}", file=sys.stderr)
    subprocess.run(cmd, check=True, **kwargs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--story", required=True, help="story.json 路径")
    ap.add_argument("--out-dir", default="~/Desktop",
                    help="输出目录（默认桌面）")
    ap.add_argument("--name-suffix", default="",
                    help="文件名后缀，例如 _draft")
    ap.add_argument("--no-open", action="store_true",
                    help="生成后不自动打开")
    ap.add_argument("--png-height", type=int, default=26000,
                    help="PNG 截图高度上限，WaytoAGI-EDU 专属版默认 26000")
    ap.add_argument("--site", action="store_true",
                    help="同时生成互动 Dashboard：每日总结 / 我的群友 / 聊天记录")
    ap.add_argument("--chat-log", default="",
                    help="vchat 导出的聊天记录文本；启用 --site 时用于生成群友发言记录")
    ap.add_argument("--site-out", default="",
                    help="互动 Dashboard 输出路径；默认随日报文件生成 *_dashboard.html")
    args = ap.parse_args()

    story_path = os.path.expanduser(args.story)
    with open(story_path, encoding="utf-8") as f:
        story = json.load(f)

    normalize_protagonists(story)
    # 写回归一化后的 story（render_html.py 用 protagonists）
    norm_story_path = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    )
    json.dump(story, norm_story_path, ensure_ascii=False)
    norm_story_path.close()

    out_dir = Path(os.path.expanduser(args.out_dir))
    out_dir.mkdir(parents=True, exist_ok=True)
    group = story.get("group_name", "群")
    date = story.get("date", "未知日期")
    stem = f"群日报_{group}_{date}{args.name_suffix}"
    html_path = out_dir / f"{stem}.html"
    png_path = out_dir / f"{stem}.png"
    site_path = Path(os.path.expanduser(args.site_out)) if args.site_out else out_dir / f"{stem}_dashboard.html"

    # 1. 头像
    wxid_map = collect_wxids(story)
    avatars_path = tempfile.NamedTemporaryFile(
        suffix=".json", delete=False
    ).name
    if wxid_map:
        names_map_path = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        json.dump(wxid_map, names_map_path, ensure_ascii=False)
        names_map_path.close()

        run([
            sys.executable, str(SCRIPT_DIR / "extract_avatars.py"),
            "--names-map", names_map_path.name,
            "--out", avatars_path,
        ])
    else:
        # 空头像也得有文件
        with open(avatars_path, "w") as f:
            json.dump({}, f)

    # 2. HTML
    run([
        sys.executable, str(SCRIPT_DIR / "render_html.py"),
        "--story", norm_story_path.name,
        "--avatars", avatars_path,
        "--out", str(html_path),
    ])

    # 3. PNG
    try:
        run([
            sys.executable, str(SCRIPT_DIR / "html_to_png.py"),
            "--html", str(html_path),
            "--out", str(png_path),
            "--height", str(args.png_height),
        ])
    except subprocess.CalledProcessError as e:
        raise SystemExit(
            "PNG 导出失败，但 HTML 已生成，可先打开 HTML 预览或在普通终端重试截图命令。\n"
            f"HTML: {html_path}\n"
            f"PNG:  {png_path}\n"
            f"失败命令: {' '.join(e.cmd)}"
        )

    # 4. 互动 Dashboard（可选）
    if args.site:
        cmd = [
            sys.executable, str(SCRIPT_DIR / "build_site.py"),
            "--story", norm_story_path.name,
            "--out", str(site_path),
        ]
        if args.chat_log:
            cmd.extend(["--chat-log", os.path.expanduser(args.chat_log)])
        run(cmd)

    print(f"\n✅ 生成完成", file=sys.stderr)
    print(f"   HTML:      {html_path}", file=sys.stderr)
    print(f"   PNG:       {png_path}", file=sys.stderr)
    if args.site:
        print(f"   Dashboard: {site_path}", file=sys.stderr)

    if not args.no_open and sys.platform == "darwin":
        subprocess.run(["open", str(html_path)])
        subprocess.run(["open", str(png_path)])
        if args.site:
            subprocess.run(["open", str(site_path)])


if __name__ == "__main__":
    main()

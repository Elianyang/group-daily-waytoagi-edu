#!/usr/bin/env python3
"""用阿里云百炼 CLI 将手动群聊素材整理成 story.json。

公开版默认不读取微信数据库。这个脚本只处理用户主动提供的文本文件：

    python3 scripts/generate_story_with_bl.py \
      --chat input/chat_manual_demo.txt \
      --out output/story.json \
      --group "WaytoAGI-EDU 情报局" \
      --date 2026-06-11

依赖：
    npm install -g bailian-cli
    bl auth login --api-key sk-xxxxx
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


SYSTEM_PROMPT = """你是 WaytoAGI-EDU 教育社群的群日报主编。

任务：把用户提供的群聊素材整理成可被 scripts/make_daily.py 渲染的 story.json。

硬性要求：
- 只输出一个 JSON 对象，不要 Markdown，不要解释。
- 不要编造不存在的人名、观点、链接或数据；素材不足时宁可减少 timeline/highlights。
- 品牌必须写作 WaytoAGI-EDU。
- 风格是教育 AI 共创社群：温暖、故事化、有角色、有现场感，不写成会议纪要。
- 默认群名是 WaytoAGI-EDU 情报局。
- timeline 建议 3-6 条公开示例；真实素材丰富时可写 6-8 条。
- highlights 建议 3-6 人；真实素材丰富时可写 6-8 人。
- 每个 timeline 条目包含 no/time/badge/cast/theme/story/quotes/output。
- cast 使用 [{ "name": "显示名" }]；公开版不要写 wxid。
- stats 可以根据素材粗略估算：total_messages、unique_senders、total_chars、new_members。
- footer_quote 选择最能代表当天气质的一句话；没有合适原话时，用概括句并把 attr 写成“主编概括”。

输出 JSON 顶层字段：
group_name, date, time_range, lead_eyebrow, lead_title, opening,
timeline, highlights, sops, qas, stats, footer_quote, members, brand_stickers。
"""


def strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def extract_json(text: str) -> dict:
    clean = strip_ansi(text).strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", clean, re.S)
    if fence:
        clean = fence.group(1)
    else:
        start = clean.find("{")
        end = clean.rfind("}")
        if start >= 0 and end > start:
            clean = clean[start : end + 1]

    try:
        return json.loads(clean)
    except json.JSONDecodeError as e:
        raise SystemExit(
            "无法从 bl 输出中解析 JSON。请查看原始输出后重试。\n"
            f"JSON 错误: {e}\n\n原始输出前 2000 字:\n{text[:2000]}"
        )


def validate_story(story: dict) -> None:
    required = ["group_name", "date", "time_range", "lead_title", "opening", "timeline", "highlights", "stats"]
    missing = [k for k in required if k not in story]
    if missing:
        raise SystemExit("生成的 story.json 缺少必填字段: " + ", ".join(missing))
    if not isinstance(story.get("timeline"), list) or not story["timeline"]:
        raise SystemExit("生成的 story.json timeline 为空")
    if not isinstance(story.get("highlights"), list) or not story["highlights"]:
        raise SystemExit("生成的 story.json highlights 为空")


def build_user_prompt(args: argparse.Namespace, chat_text: str) -> str:
    return textwrap.dedent(
        f"""
        请根据以下群聊素材生成 story.json。

        群名：{args.group}
        日期：{args.date}
        时间范围：{args.time_range}

        公开版安全规则：
        - 这些素材由用户主动提供。
        - 不要输出任何手机号、邮箱、地址、账号、身份证、原始数据库路径。
        - 如果素材里出现明显隐私信息，请概括，不要逐字引用。

        群聊素材：
        {chat_text}
        """
    ).strip()


def run_bl(args: argparse.Namespace, user_prompt: str) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False) as f:
        json.dump(messages, f, ensure_ascii=False)
        messages_path = f.name

    cmd = [
        args.bl_bin,
        "text",
        "chat",
        "--model",
        args.model,
        "--messages-file",
        messages_path,
        "--output",
        "text",
        "--non-interactive",
        "--temperature",
        str(args.temperature),
        "--max-tokens",
        str(args.max_tokens),
    ]

    if args.dry_run:
        print(" ".join(cmd))
        print(f"\nmessages-file: {messages_path}")
        return ""

    env = os.environ.copy()
    env["NO_COLOR"] = "1"
    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
    except FileNotFoundError:
        raise SystemExit("未找到 bl 命令。请先运行 npm install -g bailian-cli")
    except subprocess.CalledProcessError as e:
        stderr = e.stderr or ""
        hint = ""
        if "Arrearage" in stderr or "overdue-payment" in stderr:
            hint = (
                "\n\n提示：百炼返回 Arrearage，通常表示当前阿里云百炼账号欠费、额度不可用，"
                "或 API Key 所属账号未处于正常服务状态。请到百炼控制台确认额度/账单，"
                "或换一个可用的 DASHSCOPE_API_KEY 后重试。"
            )
        raise SystemExit(
            "bl text chat 执行失败。\n"
            f"命令: {' '.join(cmd)}\n"
            f"stdout:\n{e.stdout}\n\nstderr:\n{stderr}"
            f"{hint}"
        )
    finally:
        if not args.keep_prompt:
            Path(messages_path).unlink(missing_ok=True)

    return result.stdout


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chat", required=True, help="用户主动提供的群聊文本路径")
    ap.add_argument("--out", default="output/story.json", help="输出 story.json 路径")
    ap.add_argument("--group", default="WaytoAGI-EDU 情报局", help="群名")
    ap.add_argument("--date", required=True, help="日期 YYYY-MM-DD")
    ap.add_argument("--time-range", default="当天", help="时间范围，例如 09:00 → 22:30")
    ap.add_argument("--model", default="qwen3.7-max", help="百炼模型 ID")
    ap.add_argument("--temperature", type=float, default=0.4)
    ap.add_argument("--max-tokens", type=int, default=6000)
    ap.add_argument("--bl-bin", default=os.environ.get("BL_BIN", "bl"))
    ap.add_argument("--dry-run", action="store_true", help="只打印 bl 命令和 prompt 文件，不发起请求")
    ap.add_argument("--keep-prompt", action="store_true", help="保留临时 messages-file，便于排错")
    args = ap.parse_args()

    chat_path = Path(args.chat).expanduser()
    if not chat_path.exists():
        raise SystemExit(f"群聊素材不存在: {chat_path}")

    chat_text = chat_path.read_text(encoding="utf-8").strip()
    if not chat_text:
        raise SystemExit(f"群聊素材为空: {chat_path}")

    user_prompt = build_user_prompt(args, chat_text)
    raw = run_bl(args, user_prompt)
    if args.dry_run:
        return

    story = extract_json(raw)
    validate_story(story)

    out_path = Path(args.out).expanduser()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(story, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"[ok] story.json 已生成: {out_path}", file=sys.stderr)
    print("[next] python3 scripts/make_daily.py --story " + str(out_path) + " --out-dir output --no-open", file=sys.stderr)


if __name__ == "__main__":
    main()

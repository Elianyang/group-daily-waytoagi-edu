#!/usr/bin/env python3
"""把 story.json + avatars.json 渲染成杂志风群日报 HTML。

用法:
    python3 render_html.py \\
        --story /tmp/story.json \\
        --avatars /tmp/avatars.json \\
        --out ~/Desktop/群日报.html

story.json 结构见 references/story-schema.md。
HTML 模板路径: ../assets/template.html
"""
import argparse
import html
import json
import os
import sys
from pathlib import Path

TEMPLATE_PATH = Path(__file__).parent.parent / "assets" / "template.html"
BRAND_DIR = Path(__file__).parent.parent / "assets" / "waytoagi-edu"
BRAND_MANIFEST_PATH = BRAND_DIR / "manifest.json"


def h(s):
    """HTML 转义"""
    return html.escape(str(s)) if isinstance(s, str) else str(s)


def avatar_img(name, avatars, size=44, cls="avatar"):
    """渲染头像 img 标签。没有头像时显示首字 placeholder。"""
    src = avatars.get(name, "")
    if src:
        return (f'<img class="{cls}" src="{src}" alt="{h(name)}" '
                f'style="width:{size}px;height:{size}px;" />')
    first = name[0] if name else "·"
    return (f'<span class="{cls} avatar-text" '
            f'style="width:{size}px;height:{size}px;">{h(first)}</span>')



def file_uri(path):
    """把本地资产转成 file:// URI，供 Chrome headless 稳定加载。"""
    return Path(path).resolve().as_uri()


def load_brand():
    """读取 WaytoAGI-EDU 品牌资产清单。"""
    if not BRAND_MANIFEST_PATH.exists():
        return {
            "mascot": "", "hero": "", "stickers": [],
            "watermark": "Co-Created with 进击中的丫丫老师"
        }
    with open(BRAND_MANIFEST_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data


def render_sticker_rail(brand, story):
    """渲染 4 张小鹿贴纸：默认按日期/群名稳定轮换，也可由 story.brand_stickers 指定 id。"""
    stickers = brand.get("stickers", [])
    if not stickers:
        return ""
    wanted = story.get("brand_stickers") or []
    chosen = []
    if wanted:
        by_id = {x.get("id"): x for x in stickers}
        chosen = [by_id[x] for x in wanted if x in by_id]
    if not chosen:
        seed = sum(ord(c) for c in (story.get("group_name", "") + story.get("date", "")))
        # 固定选 4 个：鼓励、发现、陪伴、完成感
        preferred = [1, 2, 5, 9, 10, 13, 14, 15]
        for k in range(4):
            chosen.append(stickers[preferred[(seed + k * 2) % len(preferred)]])
    chosen = chosen[:4]
    parts = ['<div class="brand-stickers">\n']
    for item in chosen:
        img = BRAND_DIR / item.get("file", "")
        if not img.exists():
            continue
        label = item.get("label", "WaytoAGI-EDU")
        parts.append(f'  <div class="brand-sticker"><img src="{file_uri(img)}" alt="{h(label)}"><span>{h(label)}</span></div>\n')
    parts.append('</div>\n')
    return "".join(parts)

def render_timeline(timeline, avatars):
    parts = ['<div class="section-divider">Stories · 时间故事线</div>\n']
    for s in timeline:
        protagonists = s.get("protagonists", [])
        cast_html = "".join(avatar_img(p, avatars, 36) for p in protagonists)
        cast_names = " / ".join(protagonists)
        parts.append(f"""
<div class="story">
  <div class="story-header">
    <div class="story-no">{h(s.get('no', ''))}</div>
    <div class="story-meta">
      <div class="story-time">{h(s.get('time', ''))}</div>
      <div class="story-badge">{h(s.get('badge', ''))}</div>
    </div>
  </div>
  <h2 class="story-theme">{h(s.get('theme', ''))}</h2>
  <div class="story-cast">
    <span class="cast-label">CAST</span>
    <span class="cast-avatars">{cast_html}</span>
    <span class="cast-names">{h(cast_names)}</span>
  </div>
  <p class="story-text">{h(s.get('story', ''))}</p>
""")
        quotes = s.get("quotes", [])
        if quotes:
            parts.append('  <div class="story-quotes">\n')
            for q in quotes:
                if isinstance(q, dict):
                    who = q["who"]
                    text = q["text"]
                    source = q.get("source", "")
                    duration_s = q.get("duration_s")
                else:
                    who, text = q[0], q[1]
                    source = ""
                    duration_s = None
                if source == "voice":
                    dur_str = f" {duration_s:.0f} 秒" if duration_s else ""
                    voice_badge = f' <span class="voice-badge">🎙 语音{dur_str}</span>'
                else:
                    voice_badge = ""
                parts.append(f"""    <div class="story-quote">
      <div class="quote-text">{h(text)}</div>
      <div class="quote-attr">— {h(who)}{voice_badge}</div>
    </div>
""")
            parts.append("  </div>\n")
        if s.get("output"):
            parts.append(f'  <div class="story-output">PRODUCED '
                         f'<b>{h(s["output"])}</b></div>\n')
        parts.append("</div>\n")
    return "".join(parts)


def render_highlights(highlights, avatars):
    if not highlights:
        return ""
    parts = ['<div class="section-divider">Cast · 今日高光</div>\n',
             '<div class="highlights">\n']
    for hl in highlights:
        name = hl["name"]
        src = avatars.get(name, "")
        avatar_html = (
            f'<img class="avatar hl-avatar" src="{src}" alt="{h(name)}" />'
            if src else
            f'<span class="avatar avatar-text hl-avatar">'
            f'{h(name[0] if name else "·")}</span>'
        )
        parts.append(f"""  <div class="hl">
    {avatar_html}
    <div class="hl-info">
      <div class="hl-name">{h(name)}</div>
      <div class="hl-tag">{h(hl.get('tag', ''))}</div>
      <div class="hl-desc">{h(hl.get('desc', ''))}</div>
    </div>
  </div>
""")
    parts.append("</div>\n")
    return "".join(parts)


def render_sops(sops):
    if not sops:
        return ""
    parts = ['<details open>\n  <summary>工作流 SOP · 群友实战</summary>\n'
             '  <div class="body">\n']
    for sop in sops:
        parts.append(f"""    <div class="sop-block">
      <div class="sop-title">{h(sop.get('title', ''))}</div>
      <div class="sop-meta">{h(sop.get('author', ''))} · {h(sop.get('time', ''))}</div>
      <ol class="sop-steps">
""")
        for step in sop.get("steps", []):
            parts.append(f'        <li class="sop-step">{h(step)}</li>\n')
        parts.append('      </ol>\n')
        if sop.get("output"):
            parts.append(f'      <div class="sop-out">{h(sop["output"])}</div>\n')
        parts.append('    </div>\n')
    parts.append('  </div>\n</details>\n')
    return "".join(parts)


def render_qas(qas):
    if not qas:
        return ""
    parts = [f'<details open>\n  <summary>Q&amp;A 沉淀 · {len(qas)} 问已答</summary>\n'
             '  <div class="body">\n']
    for qa in qas:
        parts.append(f'    <div class="qa-item">\n'
                     f'      <div class="qa-q">{h(qa.get("q", ""))}'
                     f'<span class="asker">— {h(qa.get("asker", ""))}</span></div>\n')
        for ans in qa.get("answers", []):
            if isinstance(ans, dict):
                who = ans["who"]
                text = ans["text"]
                source = ans.get("source", "")
                duration_s = ans.get("duration_s")
            else:
                who, text = ans[0], ans[1]
                source = ""
                duration_s = None
            voice_tag = ""
            if source == "voice":
                dur_str = f" {duration_s:.0f}s" if duration_s else ""
                voice_tag = f' <span class="voice-badge">🎙{dur_str}</span>'
            parts.append(f'      <div class="qa-a"><b>{h(who)}</b>{h(text)}{voice_tag}</div>\n')
        parts.append('    </div>\n')
    parts.append('  </div>\n</details>\n')
    return "".join(parts)


def render_colophon(story):
    stats = story.get("stats", {})
    quote = story.get("footer_quote", {})
    return f"""
<div class="colophon">
  <div class="colophon-stats">
    <div class="colophon-num"><div class="n">{stats.get('total_messages', '—')}</div><div class="l">Messages</div></div>
    <div class="colophon-num"><div class="n">{stats.get('unique_senders', '—')}</div><div class="l">People</div></div>
    <div class="colophon-num"><div class="n">{stats.get('total_chars', '—'):,}</div><div class="l">Characters</div></div>
    <div class="colophon-num"><div class="n">{len(story.get('timeline', []))}</div><div class="l">Stories</div></div>
    <div class="colophon-num"><div class="n">+{stats.get('new_members', 0)}</div><div class="l">Newcomer</div></div>
  </div>
  {f'<div class="colophon-quote">{h(quote.get("text", ""))}<span class="attr">— {h(quote.get("attr", ""))}</span></div>' if quote else ''}
  <div class="colophon-meta">
    {h(story.get('group_name', ''))} · {h(story.get('date', ''))} · {h(story.get('time_range', ''))}
  </div>
  <div class="brand-watermark">Co-Created with 进击中的丫丫老师</div>
  <div class="brand-watermark-ghost">Co-Created with 进击中的丫丫老师</div>
</div>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--story", required=True, help="story.json 路径")
    ap.add_argument("--avatars", required=True, help="avatars.json 路径")
    ap.add_argument("--out", required=True, help="输出 HTML 路径")
    args = ap.parse_args()

    with open(args.story, encoding="utf-8") as f:
        story = json.load(f)
    with open(args.avatars, encoding="utf-8") as f:
        avatars = json.load(f)

    if not TEMPLATE_PATH.exists():
        sys.exit(f"模板不存在: {TEMPLATE_PATH}")

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    brand = load_brand()

    # 处理开场首字下沉
    opening = story.get("opening", "")
    if opening:
        first_char = opening[0]
        opening_rest = opening[1:].replace("\n", "<br>")
        opening_html = (f'<span class="drop-cap">{h(first_char)}</span>'
                        f'{opening_rest}')
    else:
        opening_html = ""

    substitutions = {
        "{{TITLE}}": h(story.get("group_name", "群日报")),
        "{{DATE}}": h(story.get("date", "")),
        "{{GROUP_NAME}}": h(story.get("group_name", "")),
        "{{VOL}}": h(story.get("date", "").replace("-", ".")),
        "{{LEAD_EYEBROW}}": h(story.get("lead_eyebrow", "Today's Story · 今日故事")),
        "{{LEAD_TITLE}}": story.get("lead_title", "").replace("\n", "<br>"),
        "{{OPENING}}": opening_html,
        "{{TIMELINE}}": render_timeline(story.get("timeline", []), avatars),
        "{{HIGHLIGHTS}}": render_highlights(story.get("highlights", []), avatars),
        "{{APPENDIX_DIVIDER}}": ('<div class="section-divider">Appendix · '
                                 '可抄作业</div>\n'
                                 if (story.get("sops") or story.get("qas"))
                                 else ""),
        "{{SOPS}}": render_sops(story.get("sops", [])),
        "{{QAS}}": render_qas(story.get("qas", [])),
        "{{COLOPHON}}": render_colophon(story),
        "{{BRAND_MASCOT}}": file_uri(BRAND_DIR / brand.get("mascot", "mascot_logo.png")),
        "{{BRAND_HERO}}": file_uri(BRAND_DIR / brand.get("hero", "mascot_hero.png")),
        "{{STICKER_RAIL}}": render_sticker_rail(brand, story),
    }

    output = template
    for k, v in substitutions.items():
        output = output.replace(k, v)

    out_path = os.path.expanduser(args.out)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(output)
    print(f"✅ HTML 生成: {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()

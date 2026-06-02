#!/usr/bin/env python3
"""生成 WaytoAGI-EDU 互动群日报 Dashboard。

功能：
- 保留日报故事线，同时提供「每日总结 / 我的群友 / 聊天记录」三栏交互。
- 正文和人物卡中的人名可点击，跳转到该群友发言记录。
- 支持从 vchat 文本日志解析当天聊天记录；不上传、不外发，纯本地静态 HTML。

用法：
    python3 scripts/build_site.py \
        --story story.json \
        --chat-log chat_history.txt \
        --out dashboard.html
"""
import argparse
import collections
import hashlib
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRAND_DIR = ROOT / "assets" / "waytoagi-edu"
BRAND_MANIFEST = BRAND_DIR / "manifest.json"


def h(x):
    return html.escape("" if x is None else str(x))


def file_uri(path: Path) -> str:
    return path.resolve().as_uri()


def slug(name: str) -> str:
    raw = name or "unknown"
    digest = hashlib.md5(raw.encode("utf-8")).hexdigest()[:10]
    return f"p-{digest}"


def load_brand():
    if BRAND_MANIFEST.exists():
        return json.loads(BRAND_MANIFEST.read_text(encoding="utf-8"))
    return {"palette": {}, "mascot": "", "hero": "", "stickers": [], "watermark": "Co-Created with 进击中的丫丫老师"}


def parse_chat_log(path: str | None):
    if not path:
        return []
    p = Path(path).expanduser()
    if not p.exists():
        return []
    text = p.read_text(encoding="utf-8", errors="ignore")
    pattern = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\] ([^:]+): (.*?)(?=^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}\]|\Z)", re.M | re.S)
    rows = []
    for m in pattern.finditer(text):
        ts, sender, body = m.groups()
        rows.append({"time": ts, "sender": sender.strip(), "text": body.strip()})
    return rows


def story_people(story):
    people = collections.OrderedDict()
    def add(name, role="群友", desc=""):
        if not name:
            return
        people.setdefault(name, {"name": name, "tag": role, "desc": desc})
    for item in story.get("highlights", []):
        add(item.get("name"), item.get("tag", "今日高光"), item.get("desc", ""))
    for seg in story.get("timeline", []):
        cast = seg.get("cast") or []
        if cast:
            for c in cast:
                add(c.get("name"), seg.get("badge", "故事人物"), seg.get("theme", ""))
        for n in seg.get("protagonists", []):
            add(n, seg.get("badge", "故事人物"), seg.get("theme", ""))
        for q in seg.get("quotes", []):
            if isinstance(q, dict):
                add(q.get("who"), "被引用", q.get("text", "")[:80])
    for qa in story.get("qas", []):
        add(qa.get("asker"), "提问者", qa.get("q", ""))
        for ans in qa.get("answers", []):
            add(ans.get("who"), "回答者", ans.get("text", "")[:80])
    for m in story.get("members", []):
        add(m.get("name"), m.get("role") or m.get("tag") or "群友", m.get("intro") or m.get("desc") or "")
    return people


def merge_people_with_chat(story, messages):
    people = story_people(story)
    counts = collections.Counter(m["sender"] for m in messages)
    last_text = {}
    for m in messages:
        last_text[m["sender"]] = m["text"]
    for name, count in counts.most_common():
        people.setdefault(name, {"name": name, "tag": "活跃群友", "desc": f"当天发言 {count} 条。最近发言：{last_text.get(name, '')[:80]}"})
        people[name]["count"] = count
    for name in people:
        people[name].setdefault("count", counts.get(name, 0))
    return list(people.values())


def link_name(name):
    return f'<a class="person-link" href="#speaker-{slug(name)}" data-person="{h(name)}">{h(name)}</a>'


def render_quotes(quotes):
    if not quotes:
        return ""
    out = ['<div class="quote-list">']
    for q in quotes:
        if isinstance(q, dict):
            who, text = q.get("who", ""), q.get("text", "")
        else:
            who, text = q[0], q[1]
        out.append(f'<blockquote>“{h(text)}”<footer>— {link_name(who)}</footer></blockquote>')
    out.append('</div>')
    return "".join(out)


def render_timeline(story):
    parts = []
    for seg in story.get("timeline", []):
        names = []
        if seg.get("cast"):
            names = [c.get("name", "") for c in seg.get("cast", [])]
        else:
            names = seg.get("protagonists", [])
        chips = "".join(f'<span class="chip">{link_name(n)}</span>' for n in names if n)
        parts.append(f'''
        <article class="story-card" id="story-{h(seg.get('no',''))}">
          <div class="story-top"><span class="story-no">{h(seg.get('no',''))}</span><span>{h(seg.get('time',''))}</span><b>{h(seg.get('badge',''))}</b></div>
          <h3>{h(seg.get('theme',''))}</h3>
          <div class="chips">{chips}</div>
          <p>{h(seg.get('story',''))}</p>
          {render_quotes(seg.get('quotes', []))}
          {f'<div class="produced">✨ {h(seg.get("output"))}</div>' if seg.get('output') else ''}
        </article>''')
    return "\n".join(parts)


def render_member_cards(people):
    cards = []
    for p in people:
        name = p.get("name", "")
        first = name[:1] or "鹿"
        cards.append(f'''
        <article class="member-card" id="speaker-{slug(name)}" data-name="{h(name).lower()}" data-text="{h((p.get('tag','') + ' ' + p.get('desc','')).lower())}">
          <div class="avatar-bubble">{h(first)}</div>
          <div class="member-main">
            <h3>{h(name)}</h3>
            <div class="member-tag">{h(p.get('tag','群友'))} · 发言 {h(p.get('count',0))} 条</div>
            <p>{h(p.get('desc') or '暂未沉淀自我介绍；可在 story.members 中补充 intro 字段。')}</p>
            <a href="#records-{slug(name)}" class="mini-link">查看 TA 的发言记录 →</a>
          </div>
        </article>''')
    return "\n".join(cards)


def render_records(messages):
    by = collections.defaultdict(list)
    for m in messages:
        by[m["sender"]].append(m)
    sections = []
    for sender, rows in sorted(by.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        items = []
        for m in rows:
            items.append(f'<li><time>{h(m["time"][11:])}</time><span>{h(m["text"])}</span></li>')
        sections.append(f'''
        <section class="record-person" id="records-{slug(sender)}" data-person="{h(sender).lower()}">
          <h3>{link_name(sender)} <small>{len(rows)} 条</small></h3>
          <ol>{''.join(items)}</ol>
        </section>''')
    if not sections:
        return '<div class="empty">未提供 chat-log，因此这里仅展示日报故事线。传入 --chat-log 后会自动生成群友发言记录。</div>'
    return "\n".join(sections)


def render_highlights(story):
    out = []
    for item in story.get("highlights", []):
        out.append(f'<div class="highlight-pill">{link_name(item.get("name",""))}<span>{h(item.get("tag",""))}</span></div>')
    return "".join(out)


def render_site(story, messages, out_path: Path):
    brand = load_brand()
    palette = brand.get("palette", {})
    people = merge_people_with_chat(story, messages)
    mascot = BRAND_DIR / brand.get("mascot", "mascot_logo.png")
    hero = BRAND_DIR / brand.get("hero", "mascot_hero.png")
    stickers = brand.get("stickers", [])[:4]
    sticker_html = "".join(
        f'<img src="{file_uri(BRAND_DIR / s.get("file", ""))}" alt="{h(s.get("label","小鹿贴纸"))}">' 
        for s in stickers if (BRAND_DIR / s.get("file", "")).exists()
    )
    stats = story.get("stats", {})
    html_text = f'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{h(story.get('group_name','群日报'))} · {h(story.get('date',''))} · Interactive Daily</title>
<style>
:root {{
  --deep:{palette.get('deep_purple','#2B104C')}; --magic:{palette.get('magic_purple','#6E2EB8')};
  --gold:{palette.get('star_gold','#FFD84D')}; --cream:{palette.get('warm_cream','#FFF8E9')};
  --blue:{palette.get('edu_blue','#39B7FF')}; --pink:{palette.get('blush_pink','#FF8FA3')};
  --paper:#fffaf0; --soft:#fbf3fe; --ink:#241136;
}}
*{{box-sizing:border-box}} html{{scroll-behavior:smooth}} body{{margin:0;font-family:"HanziPen SC","Hannotate SC","Klee","Chalkboard SE","Marker Felt",-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:var(--ink);background:radial-gradient(circle at 18% 8%,#fff4bf 0 8%,transparent 22%),radial-gradient(circle at 86% 12%,#ffd9e7 0 7%,transparent 24%),linear-gradient(135deg,#fff8e9,#fbf3fe 48%,#f2e7ff)}}
a{{color:inherit}} .app{{display:grid;grid-template-columns:260px minmax(0,1fr);min-height:100vh}} .side{{position:sticky;top:0;height:100vh;padding:24px 18px;background:linear-gradient(180deg,var(--deep),#4b1680);color:white;overflow:auto}} .brand{{display:flex;gap:12px;align-items:center;margin-bottom:24px}} .brand img{{width:58px;height:58px;object-fit:contain;background:#fff;border-radius:18px;padding:6px;box-shadow:0 8px 24px #0004}} .brand h1{{font-size:21px;margin:0;line-height:1.05}} .brand small{{color:#ffe996}} .nav button{{width:100%;border:0;border-radius:18px;padding:13px 14px;margin:7px 0;text-align:left;background:#ffffff14;color:white;font-weight:800;cursor:pointer}} .nav button.active,.nav button:hover{{background:var(--gold);color:var(--deep)}} .date-card{{margin:20px 0;padding:14px;border-radius:18px;background:#ffffff12;border:1px solid #ffffff26}} .date-card b{{font-size:22px;color:var(--gold)}} .side-note{{font-size:12px;line-height:1.7;color:#f8eaffcc}} .main{{padding:28px;max-width:1180px;width:100%;margin:0 auto}} .hero{{position:relative;border-radius:34px;padding:32px;overflow:hidden;background:linear-gradient(135deg,#fffdf6,#f8ecff);box-shadow:0 22px 70px #4b168026;border:2px solid #fff}} .hero-bg{{position:absolute;right:-30px;top:-20px;width:260px;opacity:.16}} .eyebrow{{display:inline-flex;gap:8px;align-items:center;padding:8px 14px;border-radius:999px;background:#fff0c4;color:var(--deep);font-weight:900}} .hero h2{{font-size:42px;line-height:1.08;margin:18px 0 12px;color:var(--deep);white-space:pre-line}} .opening{{max-width:760px;font-size:17px;line-height:1.9}} .stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:20px}} .stat{{padding:14px;border-radius:20px;background:white;border:1px solid #eadcff}} .stat b{{display:block;font-size:24px;color:var(--magic)}} .stickers{{display:flex;gap:10px;flex-wrap:wrap;margin-top:18px}} .stickers img{{width:72px;height:72px;object-fit:contain;filter:drop-shadow(0 8px 14px #6e2eb833)}} .panel{{display:none;margin-top:24px}} .panel.active{{display:block}} .toolbar{{display:flex;gap:12px;margin:18px 0;position:sticky;top:0;z-index:2;background:#fff8e9dd;backdrop-filter:blur(12px);padding:12px;border-radius:18px}} input{{width:100%;padding:13px 16px;border:2px solid #e7d5ff;border-radius:16px;font-size:15px;background:white}} .story-card,.member-card,.record-person,.qa-card,.sop-card{{background:#fffef9;border:1px solid #eadcff;border-radius:26px;padding:22px;margin:16px 0;box-shadow:0 10px 32px #6e2eb812}} .story-top{{display:flex;gap:12px;align-items:center;color:var(--magic);font-weight:900}} .story-no{{font-size:34px;color:var(--gold);text-shadow:0 2px 0 var(--deep)}} h3{{margin:10px 0;color:var(--deep)}} .chips{{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0}} .chip,.person-link{{display:inline-flex;align-items:center;border-radius:999px;background:#f2e6ff;color:var(--magic);padding:3px 9px;font-weight:900;text-decoration:none}} .person-link:hover{{background:var(--gold);color:var(--deep)}} blockquote{{margin:10px 0;padding:13px 16px;border-left:5px solid var(--gold);background:#fff7df;border-radius:14px}} blockquote footer{{margin-top:6px;color:var(--magic);font-weight:800}} .produced{{margin-top:12px;padding:10px 13px;border-radius:15px;background:#ebf8ff;color:#075985;font-weight:800}} .highlight-row{{display:flex;gap:10px;flex-wrap:wrap;margin-top:14px}} .highlight-pill{{border-radius:999px;background:white;border:1px solid #eadcff;padding:8px 12px}} .highlight-pill span{{margin-left:8px;color:#8b5bb7}} .member-card{{display:flex;gap:15px;align-items:flex-start}} .avatar-bubble{{width:54px;height:54px;border-radius:20px;display:grid;place-items:center;background:linear-gradient(135deg,var(--gold),var(--pink));color:var(--deep);font-size:24px;font-weight:900;flex:none}} .member-tag{{color:var(--magic);font-weight:900}} .mini-link{{color:var(--magic);font-weight:900;text-decoration:none}} .record-person ol{{padding-left:0;list-style:none}} .record-person li{{display:grid;grid-template-columns:58px minmax(0,1fr);gap:12px;padding:9px 0;border-bottom:1px dashed #eadcff;line-height:1.65}} time{{color:var(--magic);font-weight:800}} .empty{{padding:24px;border-radius:22px;background:white}} .watermark{{text-align:center;margin:28px;color:#8b5bb7;font-weight:900;opacity:.65}} @media(max-width:760px){{.app{{grid-template-columns:1fr}}.side{{position:relative;height:auto}}.hero h2{{font-size:30px}}.stats{{grid-template-columns:repeat(2,1fr)}}.main{{padding:16px}}}}
</style>
</head>
<body>
<div class="app">
  <aside class="side">
    <div class="brand"><img src="{file_uri(mascot)}" alt="WaytoAGI-EDU"><div><h1>WaytoAGI-EDU</h1><small>Magic Daily</small></div></div>
    <nav class="nav">
      <button class="active" data-tab="daily">✨ 每日总结</button>
      <button data-tab="members">🦌 我的群友</button>
      <button data-tab="records">💬 聊天记录</button>
    </nav>
    <div class="date-card"><span>当前日期</span><br><b>{h(story.get('date',''))}</b><p>{h(story.get('time_range',''))}</p></div>
    <p class="side-note">本页面由本地聊天记录生成，仅用于提高回看效率。点击正文中的蓝色人名，可跳转到该群友卡片；在聊天记录区可继续查看 TA 当天发言。</p>
  </aside>
  <main class="main">
    <section class="hero">
      <img class="hero-bg" src="{file_uri(hero)}" alt="小鹿装饰">
      <div class="eyebrow">{h(story.get('lead_eyebrow','WaytoAGI-EDU · Magic Daily'))}</div>
      <h2>{h(story.get('lead_title','群日报'))}</h2>
      <p class="opening">{h(story.get('opening',''))}</p>
      <div class="stats"><div class="stat"><b>{h(stats.get('total_messages',len(messages)))}</b>消息</div><div class="stat"><b>{h(stats.get('unique_senders',len({m['sender'] for m in messages})))}</b>发言人</div><div class="stat"><b>{h(stats.get('total_chars','—'))}</b>有效字</div><div class="stat"><b>{h(stats.get('new_members',0))}</b>新成员</div></div>
      <div class="stickers">{sticker_html}</div>
      <div class="highlight-row">{render_highlights(story)}</div>
    </section>
    <section id="daily" class="panel active">
      {render_timeline(story)}
      {''.join(f'<article class="sop-card"><h3>可抄作业 · {h(x.get("title","SOP"))}</h3><p><b>{h(x.get("author",""))}</b> · {h(x.get("time",""))}</p><ol>' + ''.join(f'<li>{h(step)}</li>' for step in x.get('steps',[])) + f'</ol><div class="produced">{h(x.get("output",""))}</div></article>' for x in story.get('sops', []))}
      {''.join(f'<article class="qa-card"><h3>Q：{h(q.get("q",""))}</h3><p>提问者：{link_name(q.get("asker",""))}</p>' + ''.join(f'<blockquote>“{h(a.get("text",""))}”<footer>— {link_name(a.get("who",""))}</footer></blockquote>' for a in q.get('answers',[])) + '</article>' for q in story.get('qas', []))}
    </section>
    <section id="members" class="panel">
      <div class="toolbar"><input id="memberSearch" placeholder="搜索群友 / 角色 / 自我介绍，例如：吵爷、skill、前线记者"></div>
      {render_member_cards(people)}
    </section>
    <section id="records" class="panel">
      <div class="toolbar"><input id="recordSearch" placeholder="搜索聊天记录 / 人名 / 关键词"></div>
      {render_records(messages)}
    </section>
    <div class="watermark">{h(brand.get('watermark','Co-Created with 进击中的丫丫老师'))}</div>
  </main>
</div>
<script>
const buttons=[...document.querySelectorAll('.nav button')];
const panels=[...document.querySelectorAll('.panel')];
function showTab(id){{buttons.forEach(b=>b.classList.toggle('active',b.dataset.tab===id));panels.forEach(p=>p.classList.toggle('active',p.id===id));}}
buttons.forEach(b=>b.addEventListener('click',()=>showTab(b.dataset.tab)));
document.querySelectorAll('a[href^="#speaker-"]').forEach(a=>a.addEventListener('click',()=>showTab('members')));
document.querySelectorAll('a[href^="#records-"]').forEach(a=>a.addEventListener('click',()=>showTab('records')));
function bindSearch(inputId, selector){{const input=document.getElementById(inputId); if(!input) return; input.addEventListener('input',()=>{{const q=input.value.trim().toLowerCase(); document.querySelectorAll(selector).forEach(el=>{{el.style.display=(!q || (el.dataset.name||el.dataset.text||el.dataset.person||el.textContent).toLowerCase().includes(q))?'':'none';}})}})}}
bindSearch('memberSearch','.member-card'); bindSearch('recordSearch','.record-person');
</script>
</body></html>'''
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html_text, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--story", required=True)
    ap.add_argument("--chat-log")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    story = json.loads(Path(args.story).expanduser().read_text(encoding="utf-8"))
    messages = parse_chat_log(args.chat_log)
    render_site(story, messages, Path(args.out).expanduser())
    print(f"✅ 互动 Dashboard 生成: {Path(args.out).expanduser()}")


if __name__ == "__main__":
    main()

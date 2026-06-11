# Workshop 提交稿

提交入口：<https://github.com/modelstudioai/modelstudioai.github.io/issues/new?template=showcase.md&title=%E3%80%90%E6%A1%88%E4%BE%8B%E3%80%91>

## 我做了什么

我把原本面向微信群的 `group-daily` Skill 改造成了 `group-daily（WaytoAGI-EDU）` 教育版：它可以把用户主动提供的群聊素材整理成一份故事化群日报，并输出带 WaytoAGI-EDU 视觉体系的 HTML + PNG 长图。

这个版本强调低风险离线素材模式：公开仓库不包含微信群原始记录、数据库、缓存或私密素材；用户可以把自己有权处理的聊天片段放到 `input/`，再用百炼 CLI 生成 `story.json`，最后渲染成长图。

GitHub 仓库：<https://github.com/Elianyang/group-daily-waytoagi-edu>

## 使用的工具

- 阿里云百炼 CLI：`bl text chat`，用于把手动群聊素材结构化成 `story.json`
- Agent Skill：`group-daily（WaytoAGI-EDU）`，沉淀故事结构、品牌规范、日报工作流
- Python 渲染脚本：`scripts/make_daily.py`、`scripts/render_html.py`、`scripts/html_to_png.py`
- WaytoAGI-EDU 教育版视觉素材：紫金配色、小鹿吉祥物、贴纸体系

## 效果展示

仓库内置了可公开展示的示例素材和效果图：

- 示例素材：`input/chat_manual_demo.txt`
- 示例结构化日报：`examples/story_waytoagi_edu_demo.json`
- 效果图：`assets/examples/waytoagi-edu-daily-style-confirmed.png`

彩排验证：

- 环境自检已通过：`python3 scripts/check_env.py`
- 示例渲染已跑通：`python3 scripts/make_daily.py --story examples/story_waytoagi_edu_demo.json --out-dir output --name-suffix _smoke --no-open`
- 本地生成 PNG 尺寸：`900×4998`，约 `2MB`
- `scripts/generate_story_with_bl.py` 已接入 `bl text chat`；实际调用需要百炼账号/API Key 处于可用状态

本地复现命令：

```bash
git clone https://github.com/Elianyang/group-daily-waytoagi-edu.git
cd group-daily-waytoagi-edu
bash install.sh

python3 scripts/generate_story_with_bl.py \
  --chat input/chat_manual_demo.txt \
  --out output/story.json \
  --group "WaytoAGI-EDU 情报局" \
  --date 2026-06-11 \
  --time-range "09:18 → 20:10"

python3 scripts/make_daily.py \
  --story output/story.json \
  --out-dir output \
  --name-suffix _workshop \
  --no-open
```

## 踩坑记录（可选）

1. 群日报很容易写成会议纪要，所以我把 Skill 的核心约束改成“故事化群报”：保留角色、冲突、产出和当天最有共鸣的一句话。
2. 公开仓库不能依赖微信数据库读取，也不能上传原始聊天记录，所以我把默认入口改成手动素材 / 成员主动提交 / 少量截图等低风险输入。
3. 百炼 CLI 适合接在“素材 → 结构化 story.json”这一步；渲染和出图仍由本地 Python 完成，职责更清楚，也方便别人 fork 后复用。

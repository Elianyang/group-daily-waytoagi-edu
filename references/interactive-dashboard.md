# Interactive Dashboard · 互动群日报站点

`group-daily（WaytoAGI-EDU）` 除了生成适合转发的 PNG 长图，也支持生成一个纯本地、可交互的 HTML Dashboard，用来覆盖参考图中的三个真实场景：

1. **没时间守群，但不想错过每日重点**：打开「每日总结」，先看 AI 提炼的故事线、SOP、Q&A 和数据。
2. **某位群友发言很精彩，想继续追 TA 的发言**：点击正文中的蓝色人名，跳到「我的群友」卡片，再点「查看 TA 的发言记录」。
3. **忘记某位群友是做什么的**：进入「我的群友」，搜索姓名 / 标签 / 自我介绍，查看该成员的群内角色卡。

## 输出文件

启用 `--site` 后，`make_daily.py` 会额外输出：

```text
群日报_<群名>_<日期>_dashboard.html
```

这个文件是单文件静态页面，默认包含：

- 左侧导航：每日总结 / 我的群友 / 聊天记录
- 日期卡片：当前日报日期与时间范围
- 日报 Hero：标题、开场、统计、小鹿贴纸
- 每日总结：故事线、引用、SOP、Q&A
- 我的群友：群友卡片、角色标签、贡献描述、发言数量、搜索框
- 聊天记录：按发言人分组的当天记录、搜索框
- 人物跳转：日报正文中的人名可点击到成员卡片，成员卡片可跳到聊天记录

## 命令

```bash
python3 scripts/make_daily.py \
  --story /path/to/story.json \
  --chat-log /path/to/chat_history.txt \
  --site \
  --out-dir /path/to/output \
  --name-suffix _interactive \
  --no-open
```

只生成互动 Dashboard，也可以直接调用：

```bash
python3 scripts/build_site.py \
  --story /path/to/story.json \
  --chat-log /path/to/chat_history.txt \
  --out /path/to/dashboard.html
```

## 数据来源与隐私

- `--chat-log` 通常来自本机 `vchat history "WaytoAGI-EDU 情报局" --asc ... > chat_history.txt`。
- Dashboard 生成是纯本地文件处理，不上传、不外发。
- 不要把 `chat_history*.txt`、`.db`、`.sqlite` 或生成的私密站点提交到公开仓库。
- 仓库 `.gitignore` 已默认排除聊天日志、数据库和生成物。

## story.json 可选增强字段

```json
{
  "members": [
    {
      "name": "吵爷",
      "role": "诗意技术人",
      "intro": "WaytoAGI 社区早期成员，关注算法、AI 创作、音乐影像与诗歌。"
    }
  ],
  "brand_stickers": ["sticker_01", "sticker_05", "sticker_09", "sticker_13"]
}
```

- `members`：用于补充“我的群友”里的自我介绍 / 名片信息。
- `brand_stickers`：用于稳定指定小鹿贴纸；不填时按日期和群名自动轮换。

## 设计约束

- 品牌必须写作 `WaytoAGI-EDU`。
- 不能写成 `WAYTOAGI-EDU`，也不能拆成 `W A Y T O A G I - E D U`。
- 使用紫金魔法小鹿风格：暖米白、魔法紫、星星金、柔和圆点/纸感渐变。
- 不使用明显斜杠条纹背景。
- 字体优先手绘可爱感 fallback：`HanziPen SC`、`Hannotate SC`、`Klee`、`Chalkboard SE`、`Marker Felt`。

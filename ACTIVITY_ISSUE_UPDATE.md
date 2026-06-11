# 活动 Issue 补充更新

补充一个上台前彩排结果：

- 仓库地址：<https://github.com/Elianyang/group-daily-waytoagi-edu>
- 环境自检已通过：`python3 scripts/check_env.py`
- 示例渲染流程已跑通：`python3 scripts/make_daily.py --story examples/story_waytoagi_edu_demo.json --out-dir output --name-suffix _smoke --no-open`
- 本地成功生成 HTML + PNG，PNG 尺寸为 `900×4998`，约 `2MB`
- 已补充脚本容错：当 Chrome headless 在沙箱环境不可用时，会给出明确提示；当百炼 CLI 返回 `Arrearage` 时，会提示检查百炼账号额度/账单状态

这意味着作品现场至少有两条可演示路径：

1. **稳定演示路径**：直接使用 `examples/story_waytoagi_edu_demo.json` 生成 HTML + PNG。
2. **百炼 CLI 路径**：在百炼账号/API Key 可用时，用 `scripts/generate_story_with_bl.py` 从 `input/chat_manual_demo.txt` 生成 `story.json`，再渲染成长图。

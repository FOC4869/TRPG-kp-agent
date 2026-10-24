# 可分发 CoC 模组制作 skill

2026-10-23；用户已确认完整实施计划。当前独立 worktree 从干净 detached HEAD 建立 feat/coc-module-builder-skill。

## 目标与边界

交付 skills/coc-module-builder，可由 Skills CLI 安装，离开仓库和聊天上下文仍包含完整格式规范、原创模板、视觉生产流程与只读校验工具。默认整理内容、规划全量素材并制作首幕样本；无图片工具时如实记录未完成。保留现有内容包核心形状，视觉扩展独立版本化。

本轮不生成真实模组图片、不改现有模组、不接 HTTP/规则执行器/前端，不推送或发布，不复制出版物内容进 skill。

## 实施切片

1. 自包含入口、三份 reference、合法空集合模板与原创样例；检查内部链接和可移植性。
2. Python 独立校验器及锁文件：重复 YAML 键、出处/实体/素材引用、路径边界、哈希、解码/尺寸/透明通道；只读 JSON/文本报告与续做建议。
3. 临时目录故障与续做测试、本地 CLI 安装验证；同步 README/development/architecture/memory。

## 接口与决策

核心 0.1.0 内容格式保持原状；新增 visual_format_version: 0.1.0，不迁移已有模组。pending/failed/review 素材只存在 asset-plan；accepted 才进入索引。presentation 指向计划或已验收素材 ID，draft 校验允许未完成引用，--complete 要求所有计划通过验收。

校验器不代替主持、图片语义或视觉人工评审，不写回文件。续做以 source fingerprint、style version、prompt/reference fingerprint 和已登记文件哈希比较，已验收项不覆盖，失配给出 revise 而非静默 skip。

评审在本会话顺序执行：产品范围、架构/权限、代码、DX、QA；不委派子代理。回退为移除 skill 与相关文档段落，无数据迁移。

## 验证

已完成：

- 独立校验器 34 项离线测试通过，覆盖原创夹具的共享/默认背景、NPC 多状态、未知规则，以及 YAML、实体/锚点、越界路径、哈希、损坏图像、尺寸、透明通道、无工具、部分失败、重复运行和版本变更。
- Skills CLI 在临时目录成功发现并复制安装 coc-module-builder；核对 37 个分发文件的内容，安装副本在原仓库外通过相同 34 项测试。
- skill-creator 元信息检查通过；skill 内 Markdown 相对链接存在、没有个人绝对路径；git diff --check 通过。
- 修正依赖缺失时退出码为 2，与独立工具文档一致；只读校验没有修改测试夹具或生成真实模组素材。

只交付 skill、模板、校验器、原创测试与说明文档。后端和前端代码及依赖未改，不运行全量业务测试或浏览器 QA。未调用图片生成或游戏模型；画风、人物一致性、剧透、透明边缘和宽屏合成的人工验收尚未执行，后续使用真实首幕验证。runtime_compatible 继续为 false。未提交、推送或发布。

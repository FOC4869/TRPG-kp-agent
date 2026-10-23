# 游戏内结案弹窗

2026-10-23。用户要求简化为游戏页内结案弹窗：结束标题、一小段总结、返回首页；取消独立结案页和统计接口。

## 实现范围

- 在干净 design/frontend-ui 上新建 feat/investigation-ending-dialog，沿用现有游戏主题，单会话顺序完成，不分配子代理。
- 客户端展示 DTO 接收可选 ended 标志；结束时直接复用该轮 Keeper 最后的文字。初始化也兼容 ended，未来恢复结束会话时立即展示。缺少文本使用中性提示，不编造结局。
- 设置中增加“查看结案弹窗示例”，经既有异步 mock action 返回最后叙述及 ended；不从玩家自由文本猜测结束，不引入真实 HTTP、额外总结接口或模型调用。
- 结案后禁用发送、建议、重试和预览操作；清空未提交草稿。弹窗由原生 dialog 实现，标题和长总结内部滚动，背景遮罩。可用关闭/Escape 回看记录，但不会恢复行动；保留“查看结案”重新打开入口。
- 只设置“返回首页”主按钮，不展示奖励、评分、统计或追加素材。原有本地预览刷新重置约定不变。

## 文件与验证

types/game.ts、data/game-preview.ts、api/game.ts 定义结束投影与演示；GamePage/GameDrawer 接受结束状态；InvestigationEndingDialog.tsx 与 game.css 展示弹窗。docs/game-preview-api.md、README、development、architecture、memory 同步。

先检查 mock 完整回复/ended 标志/取消/结束文本，再 npm ci/lint/typecheck/build 和 diff 检查。按项目视觉验收约定检查桌面/窄屏、触发、关闭/Escape、重开、结束后禁止输入、返回首页。顺序 Product/Eng/Design/Code/DX/QA 自查；无后端改动不重复后端全量测试，无新依赖。回退前端与文档即可，无存储迁移。

## 验证结果

- npm ci、lint（零警告）、typecheck、build、git diff --check 通过。扩展 check-game-preview.mjs 并通过：显式结束标志、最终 Keeper 文本、无奖励事实、玩家“结束调查”文本不触发结束、初始化不持久化演示状态；原有上下文/取消等检查仍通过。
- 浏览器通过：设置演示 → 异步响应 → 自动弹窗；Escape 返回时输入框与建议均不存在，保留记录及“查看结案”；重开正常；“返回首页”确实进入首页并展示开始调查。
- 1440×900、390×844 和 1280×400 弹窗均在视口内，返回按钮可见。短屏总结区 clientHeight 67 / scrollHeight 106，内部滚动；桌面和窄屏正常排版。未新增生图或图片资源。
- 结果通过最小 ended 展示字段串接，不新增 HTTP、总结接口或模型调用。初始化 ended 分支已实现；当前 mock 初始化始终未结束，真实会话恢复需正式 API 接入后再验。
- 同会话顺序完成范围/边界/设计/代码/DX/QA 检查。无后端变更，未重复后端全量测试或真实模型评估；前端不替代后端终局写入限制。截图 output/qa/investigation-ending/dialog-1440.jpg（Git 忽略）。

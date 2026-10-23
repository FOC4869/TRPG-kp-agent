# Frontend

Vite + React + TypeScript，桌面优先的 CoC AI Keeper 首页、模组库／详情与调查员选择。
采用原创雨夜旧宅背景、HTML 标题、可交互导航与调查入口。继续调查置灰，本轮无存档功能。

```sh
npm ci
npm run dev
```

在本目录执行。开发地址为 http://127.0.0.1:5173，/api 代理到 http://127.0.0.1:8000。
后端启动、检查命令与工程边界见 [开发指南](../docs/development.md)。
`npm run build` 产物为 dist；正式部署需另外配置同源 /api 转发。前端不包含模型密钥或隐藏剧情数据。

首页与模组库可离线于后端浏览。“开始调查”和“模组库”进入 #/modules；每页最多 3 张卡片，左右翻页并展示所选模组公开详情。
目录目前来自 src/data/modules.ts 的示例记录：《岭下暗影》与 6 个明确标注待收录的条目，用于 3/3/1 分页预览。src/api/modules.ts 保留异步分页与取消边界，未接模组 HTTP；后续接入时替换读取适配，页面不补空卡。
“选择调查员”进入 #/investigators?module=<id>，展示十人照片墙、四类档案与确认弹窗；确认后进入 #/game?module=<id>&investigator=<id> 的开场预览，不创建后端游戏或存档。
人物资料位于 src/data/investigators.ts，全部为独立 UI 示例；照片使用新生成的 investigator-previews.webp 图集，未复制后端角色资产。列表摘要与详情分别由 src/api/investigators.ts 返回，类型位于 src/types/investigators.ts；未来换为真实请求时保留组件结构，见 [API 适配契约](../docs/investigator-api.md)。
设置提供减少动态效果（本次浏览内生效）及后端健康检查；默认尊重系统减少动态效果偏好。
主要布局检查尺寸为 1280×720、1440×900、1920×1080 和 2560×1080，短窗口支持纵向滚动。
素材见 [images/README.md](public/images/README.md)，生图仅作为环境背景，页面文字和按钮可选中、可聚焦、可操作。

验证：`npm ci`、`npm run lint`、`npm run typecheck`、`npm run build`。

游戏页通过 src/api/game.ts 获取独立 mock，背景/NPC 分层、长对话内部滚动，人物/物品/线索/记录使用侧边抽屉。未知行动说明预览范围；设置可查看固定检定样例。刷新重置进度。离线核对：`node scripts/check-game-preview.mjs`；正式 API 与素材授权边界见 ../docs/game-preview-api.md。

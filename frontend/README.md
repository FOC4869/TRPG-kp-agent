# Frontend

Vite + React + TypeScript，桌面优先的 CoC AI Keeper 首页。
采用原创雨夜旧宅背景、HTML 标题、可交互导航与调查入口。继续调查置灰，本轮无存档功能。

```sh
npm ci
npm run dev
```

在本目录执行。开发地址为 http://127.0.0.1:5173，/api 代理到 http://127.0.0.1:8000。
后端启动、检查命令与工程边界见 [开发指南](../docs/development.md)。
`npm run build` 产物为 dist；正式部署需另外配置同源 /api 转发。前端不包含模型密钥或隐藏剧情数据。

首页可离线于后端浏览。“开始调查”和“模组库”目前打开公开模组预览，尚未接游戏 HTTP。
设置提供减少动态效果（本次浏览内生效）及后端健康检查；默认尊重系统减少动态效果偏好。
主要布局检查尺寸为 1280×720、1440×900、1920×1080 和 2560×1080，短窗口支持纵向滚动。
素材见 [images/README.md](public/images/README.md)，生图仅作为环境背景，页面文字和按钮可选中、可聚焦、可操作。

验证：`npm ci`、`npm run lint`、`npm run typecheck`、`npm run build`。

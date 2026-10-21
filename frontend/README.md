# Frontend

Vite 官方 React + TypeScript 模板初始化，当前页面用于检查后端连接。

```sh
npm ci
npm run dev
```

在本目录执行。开发地址为 http://127.0.0.1:5173，/api 代理到 http://127.0.0.1:8000。
后端启动、检查命令与工程边界见 [开发指南](../docs/development.md)。
`npm run build` 产物为 dist；正式部署需另外配置同源 /api 转发。前端不包含模型密钥或隐藏剧情数据。

# 调查员选择：前端适配契约

2026-10-23。这是前端展示层草案，不代表已有后端 HTTP 路由；目前只有健康接口是真实 HTTP。

## 调用入口

`frontend/src/api/investigators.ts`：

| 方法 | 参数 | 返回 |
|---|---|---|
| listInvestigators | moduleId, signal: AbortSignal | InvestigatorCatalogue：module 的 id/title、items 摘要列表、适配层 source |
| getInvestigator | moduleId, id, signal: AbortSignal | InvestigatorDetail：某位调查员的展示详情 |

类型的唯一代码定义位于 frontend/src/types/investigators.ts。当前方法检查模组上下文，然后返回独立 mock 数据的副本；不读取 backend 目录、发起人物请求、创建实例或保存选项。

摘要包含 id、name、displayName、occupation、age（可空）、portrait.url；图集 crop 元数据 sprite 为假资源所需的可选展示字段，真实接口返回普通授权头像 URL 即可。
详情增加 overview、resources（HP/上限、SAN、MP/上限、幸运）、八属性、skills、background 段落、equipment、cash。未知量为 null，不等同于零；没有 SAN 上限字段。
source 是适配层元信息 mock/api，不要求未来服务器返回它。后端实际字段名与此草案不同时，在适配层映射，不把文件目录结构暴露给组件。

## 页面与请求生命周期

模组库的可用条目进入 `#/investigators?module=<id>`。无 module 或模组未开放时提示返回；不使用默认模组兜底。
列表与详情分别读取；组件卸载/模组或人物切换时取消前一个 AbortController。仅当请求未取消且详情 ID 与当前选择匹配时展示并启用确认。
列表/详情支持 loading、空、错误/重试。原生 AbortError 不呈现为用户错误。当前 mock 对不可用模组/未知人物分别抛出 InvestigatorRequestError 的 module-unavailable / investigator-unavailable。

## 后续 HTTP 接入

1. 先确认公开字段、可选人物与 moduleId 的关联、授权和头像访问策略，再确定实际 URL。
2. 将 api/investigators.ts 中的 mock 查询替换为带 AbortSignal 的 fetch；校验/转换响应，区分未找到、无权限、网络失败。不要把失败静默替换为示例角色。
3. API 返回授权摘要/详情，不返回 source、source_issues、后台文件路径、整个 YAML/Markdown、隐藏剧情或存档。不得把 backend/data/characters 整体复制到 public。
4. 创建游戏需要另行明确服务生命周期、模板版本快照、实例资源与状态；本页确认弹窗仅为 UI 预览，不代替后端创建。

当前假头像是独立生成的十人图集，人物数值和背景也为 UI 示意，不是后端原卡的同步副本。正式接入时移除示例来源提示及假资源，保留未知量与展示边界。

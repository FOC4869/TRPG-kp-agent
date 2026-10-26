# 项目约定

先读 README、docs/development.md 和最新测试报告。

- 产品代码只放在 backend/、frontend/，不再维护 versions/ 下的另一份产品。
- 只有一套 Agent：graph.py 的七阶段流程；web.py 是网页接入，models.py 是同一模型适配器。不要恢复另一套 Agent。
- 场景与人物从配置读取。模型不生成出目、资源变化、奖励或存档修改；确定计算由 campaign.py、tools.py、trpg/ 处理。
- 只传公开的当前位置、已发现线索、物品和允许的行动给模型与前端，不公开整个 data/ 或 saves/。
- 网页只用单进程单 worker；随机结果先保存，效果只提交一次，正文最后保存。恢复必须沿用原请求。
- 不自动迁移或清空玩家存档。测试使用独立临时存档，默认离线；真实 API 测试必须得到用户明确授权，不把密钥、存档或原始模型请求提交 Git。
- 改完运行代码执行后端 unittest、前端 lint/typecheck/build，以及相关 frontend/scripts 检查；真实调用不能替代确定性的失败分支测试。
- 改接口、配置格式或启动流程时同步 docs/development.md；不能把未实际运行的检查写成已通过。

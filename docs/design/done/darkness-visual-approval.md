# 岭下暗影素材验收及实体 ID 修正

2026-10-23，用户明确审阅通过现有素材并要求修复重复 ID 后提交、合并。

- 事件 `degenerate_origin` 与线索同名。事件改为 `investigate_degenerate_origin`；线索 ID 和事件 `clue: degenerate_origin` 不变。全仓检索未发现其他事件 ID 引用，正文锚点不变。
- 24 项生成素材全部 accepted；原始 9 项材料不变，索引共 33 项。保留美术偏差说明与默认 keeper_only，不实现公开展示授权。
- 内容版本升为 0.1.1；旧 manifest/计划/索引保存于模组 assets/visual-approval-history-v1.json。ID 修正未改变图像相关事实，复核已有图像后更新当前指纹，不重新生成或覆盖图片。
- 更新预览状态和标准 visual-validation.json，移除曾为重复 ID 绕行的扩展诊断结果，使用完整标准 --complete 校验。

验证：标准完整校验通过，24 项生成记录均可复用（skip），图像尺寸、真实透明通道、哈希、实体与出处引用通过；既有规则/地图/源文本疑点仍为 warnings，runtime_compatible 保持 false。补充回归核对事件/线索分离、引用保持及所有生产状态 accepted。

未改游戏运行时、前端或依赖，不重复业务全量测试、浏览器 QA 或真实模型调用。

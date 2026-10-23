# 校验、安装与续做

## 独立工具环境

需要 Python 3.12+、uv；脚本不导入后端，不需要 API key，不调用网络/模型。随附 scripts/requirements.txt 使用精确版本，scripts/validate_module.py.lock 将 PEP 723 脚本依赖锁定；uv 首次准备隔离环境可能下载依赖，不在模组目录安装项目。

从任意工作目录，以安装后的 skill 路径替换 SKILL_DIR：

    uv run --locked --script SKILL_DIR/scripts/validate_module.py MODULE_DIR --json
    uv run --locked --script SKILL_DIR/scripts/validate_module.py MODULE_DIR --complete
    uv run --locked --script SKILL_DIR/scripts/validate_module.py MODULE_DIR --resume --json

不使用 uv 时，在独立虚拟环境安装 scripts/requirements.txt，再用该环境的 python 运行脚本。测试使用同一个隔离解释器运行 tests/test_validate_module.py（见脚本 --self-test）；无模型测试。

脚本只读。退出码 0 表示所选校验模式通过；1 表示包存在错误；2 表示参数或依赖环境问题。默认 draft 允许未生成计划，但 warnings/progress 清楚报告缺项；--complete 把未验收/失配项转为错误。任何模式均不证明 runtime 可用，也不把 style.status 改 approved。JSON 格式固定：ok/errors/warnings/content_fingerprint/resume（按 ID 排序的 action/reasons/input_fingerprint）/progress。

## 自动检查范围

- 全部 .yaml/.yml 以 SafeLoader 读取并拒绝重复键/递归别名；必需文件/集合形状和版本；文件路径及符号链接不得越界。
- 实体 ID/出处锚点唯一且存在；入口、地点连接、父地点、模板、线索、物件、issue、选项、素材、presentation 引用可定位。
- source.document 原始字节哈希和 story 锚点移除后的文本保真；无实际来源的空模板不代表真实完成，模板仅用于初始化。
- 二进制素材文件存在、SHA-256、MIME 与实际解码格式；索引元数据尺寸与 alpha 通道准确；生成素材必须遵守 plan 规格。
- 透明立绘至少存在 alpha=0 和 alpha>0 的像素；全透明或完全不透明都失败。不会自动识别画在图片里的棋盘格或视觉错误。
- 当前计划/索引一致、状态/三次尝试上限、复用环、引用文件、风格版本/内容与输入指纹是否失配。

路径以 POSIX 相对格式登记，在 Windows 也用 /。非图片的 PDF/音视频只校验文件/哈希，不假装理解其内容；text/markdown 使用 content_ref。

## 续做建议

| action | 含义 |
|---|---|
| skip | accepted、文件/记录/当前指纹一致，复用其结果 |
| generate | planned 或 failed 且未耗尽次数，输入有效且有工具 |
| review | 存在候选，等待人工验收，不重新生图 |
| reuse | 复用项等待对应主项或将其登记，不另调用图片工具 |
| revise | 已验收项/输入记录不再匹配当前内容、风格、提示词、参考或文件；新建版本，不能覆盖旧图 |
| blocked | 无图片工具、输入文件不完整、状态无效或次数耗尽；报告原因 |

style.status 未 approved 时，later 项禁止生成，待生成项报告 blocked；已有验收项仍可报告 skip 或 revise，但 revise 也不授权继续生图。sample 可生成。样本有产物后停下来供用户选定。image_tool 状态由当前实际工具能力更新，不因上次 unavailable 而永远阻断；恢复工具后仅将真正待生成的 blocked_tool 项改 planned，再跑报告。失败次数不重置。

任何 errors 均须先处理，不能机械执行 resume。--resume 仅显示建议，不写 plan、不创建图片、不读取游戏数据库。

## 可重复验证

    uv run --locked --script SKILL_DIR/scripts/validate_module.py --self-test

测试夹具是原创短故事；图片为临时生成的几何测试像素，用于尺寸/通道/损坏测试，不冒充 AI 图片或视觉验收。覆盖共享背景、默认回退、NPC 两状态、无规则版本、无图片工具、部分失败、重复运行只读、内容/风格/提示词/参考变化、文件损坏、路径与引用错误。

发布前在临时项目目录运行本地安装，避免修改用户真实 agent 配置：

    npx skills add /absolute/path/to/source-repo --skill coc-module-builder --agent codex --yes

安装后确认 references、templates、scripts、锁文件和 tests 都在 skill 内，复制目录至仓库外仍可运行。远端发布后才使用 npx skills add FOC4869/TRPG-kp-agent --skill coc-module-builder；开发分支未发布不声称远端可安装。公开安装需要仓库可访问。

人工检查不计入自动通过：画风/身份、语义、剧透、时代准确性、真实界面合成；无图像工具时这些未执行。所有运行条件和剩余项写交付报告。

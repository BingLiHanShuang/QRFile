# Core Rules

## General
- 任务切换时优先使用 `/clear`，同一任务进入新阶段使用 `/compact`
- 长会话中主动使用 `/context` 观察 token 消耗
- 每次纠正 Claude 的错误后，让它自己更新 CLAUDE.md

## 上下文管理
- CLAUDE.md 只保留契约性内容，不放百科式文档
- 路径/语言相关规则放到对应的 rules 文件中
- 定期审查 `.claude/settings.json` 的 `allowedTools` 列表

## 会话管理
- 长任务开始前，先让 Claude 写 HANDOFF.md 记录当前进度
- 开新会话时，把 HANDOFF.md 路径发给新实例继续工作

## 验证铁律
- 任何代码修改后必须先通过 `pytest tests/ -v`
- Claude 说"完成了"不算完成，必须有测试通过才算
- 编解码闭环验证：encode 文件 → decode 图片 → diff 对比原始文件

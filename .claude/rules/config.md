# Config Rules

## 配置文件管理
- 编辑 `pyproject.toml` 前先备份
- `.env.example` 必须与实际使用的环境变量保持同步
- 不要在代码中硬编码环境变量值

## 依赖管理
- 添加新依赖时更新 `pyproject.toml` 的 `dependencies` 列表
- 同时更新 `requirements.txt`
- 使用 `pip install -e .` 验证可编辑安装正常

## 版本管理
- 遵循 SemVer：`pyproject.toml` 中的 version 字段
- 重大变更（如 QR 数据格式变化）需更新主版本号

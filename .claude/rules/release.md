# Release Rules

## 发布前检查
- [ ] `pytest tests/ -v` 全部通过
- [ ] 编解码闭环验证通过
- [ ] `qrcode --help` 和所有子命令 `--help` 正常
- [ ] `pip install -e .` 成功
- [ ] CHANGELOG 已更新

## 版本号
- 遵循 SemVer 规范
- 在 `pyproject.toml` 中更新 version

## 禁止操作
- 不要在主分支上直接提交
- 不要 force push
- 不要提交包含密钥的文件（检查 `.env`、credentials 等）

## Git 操作
- 提交前先 `git diff` 检查变更
- 提交信息使用中文描述变更原因

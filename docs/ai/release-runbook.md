# Release Runbook

## 发布前验证

1. **全量测试**
   ```
   pytest tests/ -v
   ```

2. **编解码闭环**
   ```
   echo "test content" > /tmp/test_in.txt
   qrcode encode /tmp/test_in.txt --output /tmp/qr_out
   qrcode decode /tmp/qr_out/test_in_qrcode.png --output /tmp/test_out.txt
   diff /tmp/test_in.txt /tmp/test_out.txt
   ```

3. **CLI 帮助菜单**
   ```
   qrcode --help
   qrcode encode --help
   qrcode decode --help
   qrcode convert --help
   qrcode camera --help
   ```

4. **可编辑安装**
   ```
   pip install -e .
   ```

5. **批量转换**
   ```
   mkdir -p /tmp/qr_batch
   echo "a" > /tmp/qr_batch/a.txt
   echo "b" > /tmp/qr_batch/b.txt
   qrcode convert --source /tmp/qr_batch
   ```

## 版本号更新

在 `pyproject.toml` 中更新 `version` 字段。

## 发布

1. 提交所有变更
2. 打 tag：`git tag v1.0.0`
3. 推送：`git push && git push --tags`

## 回滚

如果发布后发现严重问题：
1. `git revert <commit>` 回滚代码
2. 打新的 patch 版本号

## 紧急修复

1. 从 main 分支切出 hotfix 分支
2. 修复 + 测试
3. 合并回 main
4. 更新 patch 版本号

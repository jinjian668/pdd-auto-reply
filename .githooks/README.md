# Git Hooks

启用仓库级预提交检查：

```powershell
git config core.hooksPath .githooks
```

`pre-commit` 会调用 `tools/check_repo_safety.ps1`，阻止密钥、凭据、日志、客户隐私和数据库数据进入提交。

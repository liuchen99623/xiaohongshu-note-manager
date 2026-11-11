# 贡献指南

欢迎 Issue 和 Pull Request。

1. Fork 后从 `main` 新建分支。
2. 保持 Python 3.11+、标准库优先，不提交真实账号数据、Cookie、Token 或生成素材。
3. 修改行为时补充 `unittest`。
4. 本地执行：

```bash
python3 -m unittest discover -s tests -v
python3 scripts/secret_scan.py .
```

提交信息建议使用 `feat:`, `fix:`, `docs:`, `test:` 等前缀。

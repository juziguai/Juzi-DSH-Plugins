# 官方标准预设快照

`standard.patch.yml` 来自 MIT 许可的 `@deepseek-ai/dsh-web-app@0.2.1-rc.3` 包中的 `presets/standard.patch.yml`。此快照同时与 rc.2 对应文件一致。

- 上游：[DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness/tree/main/packages/web/app)
- 核对方式：从官方 npm 包提取源文件，统一 CRLF/LF 后逐字比较。
- 当前文件统一 LF 的 SHA-256：`0d398d2a6872a73a106cb3bd19303ecccf1637e1fcad4d0bf9d8a72d2c2c68f5`。

仅替换 persona 的 prefix 和新增预设标识，其余插件配置保留。更新上游快照后重新构建并验证；此目录不进入安装包。

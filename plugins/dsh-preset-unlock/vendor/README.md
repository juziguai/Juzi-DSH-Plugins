# 官方标准预设快照

`standard.patch.yml` 来自 MIT 许可的 `@deepseek-ai/dsh-web-app@0.2.2-rc.3` 包中的 `presets/standard.patch.yml`。

- 上游：[DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness/tree/main/packages/web/app)
- 核对方式：从官方 npm 包提取源文件，统一 CRLF/LF 后逐字比较。
- 当前文件统一 LF 的 SHA-256：`e40bb192ed3b835312c2acd2ccd64d3bc4b85f80a7bc95b132cb18fbee190b5d`。

仅替换 persona 的 prefix 和新增预设标识，其余插件配置保留。更新上游快照后重新构建并验证；此目录不进入安装包。

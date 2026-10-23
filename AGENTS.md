# 项目约定

- 本仓库维护 `plugins/` 下的独立 DSH 插件；不要修改旧仓库或已安装 profile 来完成源码整理。
- 修改前检查 Git 状态，保留用户已有修改。commit、push、发布需要各自明确授权。
- Ultra 维护入口为 `lib/client.js`；`archive/legacy-patches/` 不可作为构建脚本执行。
- 版本角标从模板与更新脚本生成 `lib/client.js`；不要只修改生成物。
- 搜索插件复用官方 MCP 客户端；保持 Python 独立 stdio 入口和工具名称稳定。新增配置需验证官方 schema。
- 常规验证运行 `npm test` 和 `git diff --check`。真实 API 冒烟、profile 切换和应用重启单独执行，不混入默认测试。
- 组件版本独立维护；根 `package.json` 是仓库版本源。文档、清单、运行入口与迁移说明必须一致。

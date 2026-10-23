# Juzi-DSH-Plugins

Juzi 自研 DeepSeek Harness（DSH）插件源仓库。各插件独立维护清单、接入配置和说明；根目录提供统一检查入口。

| 插件 | 能力 | 维护入口 |
|---|---|---|
| [dsh-ultra-effort](plugins/dsh-ultra-effort/README.md) | 模型选择与推理强度控件 | `lib/client.js` |
| [dsh-model-version-badge](plugins/dsh-model-version-badge/README.md) | 模型快照版本角标 | `build/client.template.js`、`build/update-versions.ps1` |
| [dsh-deepseek-tools](plugins/dsh-deepseek-tools/README.md) | 官方 Search / Fetch，复用 DSH MCP 桥接 | `lib/`、`server.py`、`usage_store.py` |

```text
plugins/       三个独立插件
scripts/       仓库检查与插件配置测试
deploy/        独立 MCP 接入样例
docs/          开发、安装与迁移说明
```

## 开发检查

需要 Node.js、Python 3；根目录检查不需要安装 npm 依赖。

```powershell
npm run check
npm test
```

`npm test` 运行清单/JS 语法检查、搜索插件路径与配置测试、Python 计数并发测试，不请求真实 API。
搜索服务运行时另需使用目标 Python 安装 `plugins/dsh-deepseek-tools/requirements.txt`。

安装、迁移、构建边界见 [开发指南](docs/development.md)。真实 API 冒烟会产生请求，需主动执行插件的 `smoke_test.py`。

## Git 与版本

保留复制来源的 Git 历史；仓库版本以根 `package.json` 为准，插件版本各自维护。
本地配置、密钥、运行数据、缓存和检查点不入库。上游许可证随原插件保留，不替其他组件推断授权。
提交、推送、发布分别执行，不由检查命令触发。用户可见变更记录在 [CHANGELOG.md](CHANGELOG.md)。

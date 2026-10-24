# Juzi-DSH-Plugins

Juzi 自研 DeepSeek Harness（DSH）插件源仓库。各插件独立维护清单、接入配置和说明；根目录提供统一检查入口。

| 插件 | 能力 | 维护入口 |
|---|---|---|
| [dsh-changes](plugins/dsh-changes/README.md) | 执行中实时查看轮次文件变更与差异 | `lib/` |
| [dsh-ultra-effort](plugins/dsh-ultra-effort/README.md) | 模型选择、推理强度动效与内置版本角标 | `src/`、`build/client.mjs` |
| [dsh-model-version-badge](plugins/dsh-model-version-badge/README.md) | 旧版独立角标，已由 Ultra 0.2.2 替代 | 冻结保留，供回退 |
| [dsh-deepseek-tools](plugins/dsh-deepseek-tools/README.md) | 官方 Search / Fetch，复用 DSH MCP 桥接 | `lib/`、`server.py`、`usage_store.py` |

```text
plugins/       变更、Ultra、搜索及冻结的旧角标包
scripts/       仓库检查与插件配置测试
deploy/        独立 MCP 接入样例
docs/          开发、安装与迁移说明
```

## 开发检查

需要 Node.js、Python 3；根目录检查不需要安装 npm 依赖。

```powershell
npm run client:build
npm run check
python -m pip install -r plugins/dsh-deepseek-tools/requirements.txt
npm test
```

`npm test` 检查构建漂移、清单/JS 语法、变更快照与生命周期、Ultra 单包标签与交互、搜索配置及 Python 计数并发与凭证边界，不请求真实 API。CI 另用官方 SlotCore 和 Cordis 验证插槽注册与 Host 激活契约。
搜索服务运行时另需使用目标 Python 安装 `plugins/dsh-deepseek-tools/requirements.txt`。

升级 Ultra 0.2.2 后先验证内置角标与动效，再停用旧 Model Version Badge；无须同时维护两个版本。迁移和回退步骤见 [合并迁移指南](docs/ultra-migration.md)。

安装、迁移、构建边界见 [开发指南](docs/development.md)。真实 API 冒烟会产生请求，需主动执行插件的 `smoke_test.py`。

## 插件市场

在 DSH「插件 → 发现 → 索引源」添加：

```text
https://raw.githubusercontent.com/juziguai/Juzi-DSH-Plugins/main/marketplace/index.json
```

「变更」0.1.0 安装并启用后，开启新一轮任务，从会话标题右侧或右栏添加页打开「变更」。需要本机 Git，不需要 Python 或 API Key；历史仅保留本次 Host 运行期间。

市场格式、接入前提和发布方法见 [市场指南](docs/marketplace.md)。安装者使用自己的专用 API Key，源码和索引不携带发布者凭证。

## Git 与版本

保留复制来源的 Git 历史；仓库版本以根 `package.json` 为准，插件版本各自维护。
本地配置、密钥、运行数据、缓存和检查点不入库。上游许可证随原插件保留，不替其他组件推断授权。
提交、推送、发布分别执行，不由检查命令触发。用户可见变更记录在 [CHANGELOG.md](CHANGELOG.md)。

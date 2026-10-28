# Juzi-DSH-Plugins

Juzi 自研 DeepSeek Harness（DSH）插件源仓库。各插件独立维护清单、接入配置和说明；根目录提供统一检查入口。

| 插件 | 能力 | 维护入口 |
|---|---|---|
| [dsh-quote-annotate](plugins/dsh-quote-annotate/README.md) | 选中文字、添加评论并引用到草稿，已发送引用可折叠查看 | `src/`、`lib/`、`build/client.mjs` |
| [dsh-changes](plugins/dsh-changes/README.md) | 执行中实时查看轮次文件变更与差异 | `lib/` |
| [dsh-ultra-effort](plugins/dsh-ultra-effort/README.md) | 模型选择、推理强度动效、内置角标与快速执行（实验） | `src/`、`lib/fast-*.js`、`build/client.mjs` |
| [dsh-model-version-badge](plugins/dsh-model-version-badge/README.md) | 旧版独立角标，已由 Ultra 0.2.2 替代 | 冻结保留，供回退 |
| [dsh-deepseek-tools](plugins/dsh-deepseek-tools/README.md) | 官方 Search / Fetch，复用 DSH MCP 桥接 | `lib/`、`server.py`、`usage_store.py` |
| [juzi-win-dsh](plugins/juzi-win-dsh/README.md) | Windows 窗口、截图、输入、窗口管理、剪贴板、应用启动与OCR找字 | `lib/`、`server.py`、`winapi.py` |
| [dsh-preset-unlock](plugins/dsh-preset-unlock/README.md) | 纯声明型 Agent 预设「解锁模式」，人格来自 Markdown | `prompts/persona.md`、`build/patch.mjs` |

```text
plugins/       文本引用、变更、Ultra、搜索、电脑控制、解锁模式预设及冻结的旧角标包
scripts/       仓库检查与插件配置测试
deploy/        独立 MCP 接入样例
docs/          开发、安装与迁移说明
```

## 开发检查

需要 Node.js、Python 3；根目录检查不需要安装 npm 依赖。

```powershell
npm run client:build
npm run preset:check
npm run check
python -m pip install -r plugins/dsh-deepseek-tools/requirements.txt
npm test
```

Ultra 快速执行的 Host/React 集成测试需先解析插件自身依赖，并提供官方测试运行时入口；完整依赖安装命令和环境变量见 [CI 检查配置](.github/workflows/verify.yml)。市场已发布版本以市场索引中的固定源码为准。

`npm test` 检查构建漂移、清单/JS语法、引用序列化/存储/交互、变更快照与生命周期、Ultra单包标签与交互、预设生成、搜索配置及Python计数并发与凭证边界，不请求真实API。CI另用官方SlotCore、Cordis和预设schema验证声明契约。电脑控制的Windows真机冒烟与隔离回归需单独运行其`smoke_test.py`、`regression_test.py`；包本身没有独立npm测试脚本。
Python 部分设置了 `PYTHON` 时严格使用该解释器，不能 `import mcp` 就报错；未设置时，依次尝试 Windows 的 `C:\Python314\python.exe` 和 PATH 中的 `python`，取能导入依赖的解释器。
搜索服务运行时另需使用目标 Python 安装 `plugins/dsh-deepseek-tools/requirements.txt`。

升级到 Ultra 0.2.2 或更新版本后先验证内置角标与动效，再停用旧 Model Version Badge；无须同时维护两个版本。迁移和回退步骤见 [合并迁移指南](docs/ultra-migration.md)。

安装、迁移、构建边界见 [开发指南](docs/development.md)。真实 API 冒烟会产生请求，需主动执行插件的 `smoke_test.py`。

## 插件市场

在 DSH「插件 → 发现 → 索引源」添加：

```text
https://raw.githubusercontent.com/juziguai/Juzi-DSH-Plugins/main/marketplace/index.json
```

「变更」0.1.3 安装并启用后，开启新一轮任务，从会话标题右侧或右栏添加页打开「变更」。文件在同一标题行下原位展开；顶部更多菜单提供自动换行、全部展开/折叠，旁侧可复制摘要。需要本机 Git，不需要 Python 或 API Key；历史仅保留本次 Host 运行期间。

「解锁模式」0.1.1 需要 DSH 0.2.1-rc.3 或更新版本；安装后手动选择预设，不自动修改默认预设或权限。卸载前保留旧会话需要的 `unlock` 声明，详见插件说明。

Ultra 0.3.0 需要 DSH 0.2.1-rc.3 或更新版本。闪电提供按会话保存的快速执行（实验），默认关闭、空闲时切换、下一轮生效；保持所选模型与推理强度，不代表服务商付费加速。

「文本引用与批注」0.1.1需要DSH 0.2.1-rc.3或更新版本。引用只进入草稿，不自动发送；支持悬停预览、评论、按会话保存和已发送引用折叠。原生chip的键盘接口边界及dock等价入口见[插件说明](plugins/dsh-quote-annotate/README.md)。

「电脑控制」1.1.2仅支持Windows，提供17个MCP工具；先准备Python与Pillow，OCR引擎、宿主审批及确认模式边界见[插件说明](plugins/juzi-win-dsh/README.md)。

市场名称、插件名称、分类与描述已适配 DSH 中文界面；已安装页的中文描述随对应插件更新生效。

市场格式、接入前提和发布方法见 [市场指南](docs/marketplace.md)。安装者使用自己的专用 API Key，源码和索引不携带发布者凭证。

## Git 与版本

保留复制来源的 Git 历史；仓库版本以根 `package.json` 为准，插件版本各自维护。
本地配置、密钥、运行数据、缓存和检查点不入库。上游许可证随原插件保留，不替其他组件推断授权。
提交、推送、发布分别执行，不由检查命令触发。用户可见变更记录在 [CHANGELOG.md](CHANGELOG.md)。

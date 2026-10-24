# 开发与接入

## 源码与构建

- Ultra：交互、样式、标签组件、版本数据位于 `plugins/dsh-ultra-effort/src/`；在仓库根运行 `npm run build` 生成 `lib/client.js`。构建无第三方依赖，默认验证会检查生成漂移。`archive/legacy-patches/` 不能重放。
- 更新模型版本：从 Ultra 目录运行 `powershell -NoProfile -File build/update-versions.ps1`，联网读取官方价格页后写 JSON 并构建。独立角标包冻结为旧版回退用途；新数据只维护 Ultra 一处。
- 搜索：`lib/index.js` 将 MCP 配置交给官方客户端；`lib/config.js` 按模块位置定位 Python。Python 文件保持同目录，独立 stdio 入口不依赖 DSH。
- 不自动安装、启动或重启真实 profile。静态检查通过不等于 DSH 界面或生产工具验收通过。

## 安装到 DSH

先选择目标 profile，并按宿主要求退出正在使用的实例。以下以 web 为例，在仓库根目录执行；只安装需要的插件。

```powershell
$repo = (Get-Location).Path.Replace('\', '/')
dsh plugin --profile web add "link:$repo/plugins/dsh-ultra-effort"
dsh plugin --profile web add "file:$repo/plugins/dsh-deepseek-tools"
```

核对目标 profile `package.json` 的 `dsh.profile.bundles` 包含需要加载的包名。
搜索插件复用宿主 `@deepseek-ai/dsh-mcp-client@0.2.1-rc.2`，不捆绑另一套 DSH 服务。升级宿主时重新核验 peer 版本与契约。
搜索插件推荐 `file:` 安装，由包管理器解析 peer；更新源码后需重新安装。UI 插件可使用 `link:`。搜索插件若改用 `link:`，必须先在插件目录解析好匹配 peer；仅链接包不能保证 ESM 依赖可解析。

搜索插件先安装 Python 依赖，再按需覆盖解释器：

```powershell
python -m pip install -r plugins/dsh-deepseek-tools/requirements.txt
```

```yaml
- id: juzi-deepseek-tools
  config:
    python: 'C:/Python314/python.exe'
```

如已有 `mcp-deepseek-tools` 条目，切换时停用旧条目，避免两个 `deepseek` 命名空间同时注册。Ultra 内置角标无需独立包或官方标签插槽注册；旧角标包的迁移见 [迁移指南](ultra-migration.md)。

## 从旧仓库迁移

旧目录 `Juzi-DeepSeek-Tools` 保持原样。新源码在本仓库 `plugins/`；原安装引用不会自动切换。
切换前备份 profile 清单与 patch，记录旧路径；逐个更新包路径和 bundle 配置，重启后验证插件界面/工具发现。
失败时恢复备份和旧路径，停止继续切换。不要删除旧目录，直到新路径完整验收。

## 验证分层

1. `npm test`：构建一致性、离线结构、语法、Ultra 单包标签与交互、插件参数和计数并发。
   设置 `DSH_SLOT_CORE_MODULE` 指向官方 `dsh-client-ui-slots/lib/index.js` 时，执行真实插槽注册共存测试；CI 必须执行。
2. 安装环境：验证官方 peer 可解析、MCP 握手及工具发现。
3. 真实 profile：模型切换、强度交互、版本角标、Search/Fetch；真实 API 测试主动执行，可能产生费用。

## Git 工作流

`git status --short` → 检查完整 diff 和新增文件 → `npm test` → `git diff --check`。
审核范围后再按用户授权暂存/提交；不直接 `git add .`。保留依赖锁文件，忽略运行时锁而非所有 `*.lock`。
根仓库版本与组件版本独立，不为目录搬迁机械升级所有插件。新组件必须包含清单、README、加载入口及可验证路径。

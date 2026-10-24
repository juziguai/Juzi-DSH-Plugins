/**
 * @juzi/dsh-preset-unlock — 纯声明型插件。
 *
 * 本包在运行时**不做任何事**：没有工具、没有路由、没有提示词段、没有客户端。
 * 它存在的唯一意义，是携带 `cordis.patch.yml` 这个 bundle 补丁层，
 * 由该补丁向 profile 插入一行 `@deepseek-ai/dsh-agent-preset`，
 * 从而在 DSH 的预设选择器里出现「解锁模式」。
 *
 * 之所以仍需要一个入口模块：DSH 的 bundle 约定与仓库检查器
 * （scripts/check.mjs）都要求补丁中存在指向本包自身的行，
 * 因此这里提供一个最小可加载的 Cordis 插件。
 *
 * 人格文本不在这里：真源是 `prompts/persona.md`，
 * 由 `build/patch.mjs` 在构建时嵌入 `cordis.patch.yml`。
 */

/** Cordis 插件名。 */
export const name = 'juzi-preset-unlock';

/**
 * 空实现：本插件没有任何生命周期行为。
 * 保留函数体是为了满足插件加载契约（模块需导出 apply）。
 */
export function apply() {}

#!/usr/bin/env node
/**
 * 由 persona.md + 官方 standard 预设清单，生成 cordis.patch.yml。
 *
 * 为什么用「文本锚点替换」而不是 YAML 解析：
 * 本仓库的检查流程不安装任何 npm 依赖（见根 README 的「开发检查」），
 * 因此不能引入 js-yaml / yaml。vendor/standard.patch.yml 是官方文件的
 * 逐字快照，结构稳定；这里对固定锚点做外科式替换，锚点缺失就直接报错，
 * 避免静默产出一份格式错误的补丁。
 *
 * 用法：
 *   node build/patch.mjs            # 生成 cordis.patch.yml
 *   node build/patch.mjs --check    # 只校验生成物是否与源一致（CI 用）
 */

import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const pkgRoot = join(here, '..');

const VENDOR = join(pkgRoot, 'vendor', 'standard.patch.yml');
const PERSONA = join(pkgRoot, 'prompts', 'persona.md');
const OUTPUT = join(pkgRoot, 'cordis.patch.yml');

/** 统一换行，避免 CRLF/LF 差异造成 --check 误报。 */
const readNormalized = (path) => readFileSync(path, 'utf8').replace(/\r\n/g, '\n');

/** 生成完整的 patch 文本。 */
function generate() {
  const vendor = readNormalized(VENDOR);
  const persona = readNormalized(PERSONA).replace(/\n+$/, '');
  if (!persona.trim()) throw new Error('persona.md 不能为空');
  const lines = vendor.split('\n');

  // ── 锚点 1：官方预设行只能出现一次 ──────────────────────────────────────
  const presetLines = lines.filter((line) => line === '    - id: preset-standard');
  if (presetLines.length !== 1) {
    throw new Error(`vendor 结构异常：期望 1 个 "    - id: preset-standard"，实际 ${presetLines.length} 个`);
  }

  // ── 锚点 2：plugins 列表起点只能出现一次 ────────────────────────────────
  const pluginsIndexes = [];
  lines.forEach((line, index) => {
    if (line === '        plugins:') pluginsIndexes.push(index);
  });
  if (pluginsIndexes.length !== 1) {
    throw new Error(`vendor 结构异常：期望 1 个 "        plugins:"，实际 ${pluginsIndexes.length} 个`);
  }
  const pluginsStart = pluginsIndexes[0];

  // ── 锚点 3：persona 的 prefix 行必须唯一且为单行写法 ────────────────────
  const prefixIndexes = [];
  for (let i = pluginsStart; i < lines.length; i += 1) {
    if (/^ {14}prefix: /.test(lines[i])) prefixIndexes.push(i);
  }
  if (prefixIndexes.length !== 1) {
    throw new Error(`vendor 结构异常：期望 1 处 persona prefix 行，实际 ${prefixIndexes.length} 处`);
  }
  const prefixIndex = prefixIndexes[0];

  // ── 组装：替换 persona 为块标量，其余插件行原样保留 ─────────────────────
  const pluginBlock = lines.slice(pluginsStart, prefixIndex);
  const personaBlock = [
    '              prefix: |-',
    ...persona.split('\n').map((line) => (line.length === 0 ? '' : `                ${line}`)),
  ];
  const tail = lines.slice(prefixIndex + 1);

  const header = [
    '# ⚠️ 本文件由 build/patch.mjs 生成，请勿手改。',
    '# 源：prompts/persona.md（人格真源） + vendor/standard.patch.yml（官方工具清单快照）',
    '# 重新生成：node build/patch.mjs',
    '- insert:',
    "    - id: juzi-preset-unlock",
    "      name: '@juzi/dsh-preset-unlock'",
    "    - id: preset-unlock",
    "      name: '@deepseek-ai/dsh-agent-preset'",
    '      config:',
    '        id: unlock',
    '        name: 解锁模式',
    '        order: 2',
  ];

  return [...header, ...pluginBlock, ...personaBlock, ...tail].join('\n').replace(/\n+$/, '') + '\n';
}

const generated = generate();

if (process.argv.includes('--check')) {
  if (!existsSync(OUTPUT)) {
    console.error('cordis.patch.yml 不存在，请先运行 node build/patch.mjs');
    process.exitCode = 1;
  } else if (readNormalized(OUTPUT) !== generated) {
    console.error('cordis.patch.yml 与源不一致，请重新运行 node build/patch.mjs');
    process.exitCode = 1;
  } else {
    console.log('OK cordis.patch.yml 与源一致');
  }
} else {
  writeFileSync(OUTPUT, generated);
  const pluginRows = (generated.match(/^ {10}- id: /gm) ?? []).length;
  const personaChars = readNormalized(PERSONA).replace(/\n+$/, '').length;
  console.log(`已生成 ${OUTPUT}（插件行 ${pluginRows} 个，persona ${personaChars} 字符，文件 ${generated.length} 字符）`);
}

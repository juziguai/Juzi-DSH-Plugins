import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const DEFAULT_PYTHON = 'C:\\Python314\\python.exe';

function resolvePython(config) {
  if (config.python !== undefined) {
    if (typeof config.python !== 'string' || !config.python.trim()) {
      throw new TypeError('juzi-win-dsh: python must be a non-empty executable path');
    }
    return config.python;
  }
  const fromEnv = process.env.JUZI_WIN_DSH_PYTHON;
  if (fromEnv && fromEnv.trim()) return fromEnv.trim();
  if (process.platform === 'win32' && existsSync(DEFAULT_PYTHON)) return DEFAULT_PYTHON;
  return 'python';
}

function resolveConfirmMode(config) {
  const mode = config.confirmMode ?? 'always';
  if (!['always', 'allowlist', 'off'].includes(mode)) {
    throw new TypeError('juzi-win-dsh: confirmMode must be always, allowlist or off');
  }
  return mode;
}

function resolveAllowlist(config) {
  const allowlist = config.allowlist ?? [];
  if (!Array.isArray(allowlist) || allowlist.some(item => typeof item !== 'string' || !item.trim())) {
    throw new TypeError('juzi-win-dsh: allowlist must be an array of non-empty process names');
  }
  return allowlist.map(item => item.trim());
}

export function createConfig(config = {}) {
  return {
    serverName: 'win',
    transport: 'stdio',
    command: resolvePython(config),
    args: [fileURLToPath(new URL('../server.py', import.meta.url))],
    cwd: fileURLToPath(new URL('../', import.meta.url)),
    env: {
      JUZI_WIN_DSH_CONFIRM_MODE: resolveConfirmMode(config),
      JUZI_WIN_DSH_ALLOWLIST: resolveAllowlist(config).join(';'),
      PYTHONIOENCODING: 'utf-8',
      PYTHONUTF8: '1',
    },
    toolCallTimeoutMs: 120000,
    failOnStartupError: true,
  };
}

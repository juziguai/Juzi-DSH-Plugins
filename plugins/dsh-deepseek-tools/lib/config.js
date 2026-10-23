import { fileURLToPath } from 'node:url';

export function createConfig(config = {}) {
  const python = config.python ?? 'python';
  if (typeof python !== 'string' || !python.trim()) {
    throw new TypeError('dsh-deepseek-tools: python must be a non-empty executable path');
  }
  return {
    serverName: 'deepseek',
    transport: 'stdio',
    command: python,
    args: [fileURLToPath(new URL('../server.py', import.meta.url))],
    cwd: fileURLToPath(new URL('../', import.meta.url)),
    toolCallTimeoutMs: 90000,
    failOnStartupError: true,
  };
}

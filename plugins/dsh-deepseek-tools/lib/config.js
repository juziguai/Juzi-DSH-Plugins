import { tmpdir } from 'node:os';
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
    // A package directory used as cwd stays locked by Windows for the process lifetime.
    cwd: tmpdir(),
    toolCallTimeoutMs: 90000,
    failOnStartupError: true,
  };
}

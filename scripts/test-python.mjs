import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));

function importsMcp(command) {
  const probe = spawnSync(command, ['-c', 'import mcp'], { stdio: 'ignore' });
  return !probe.error && probe.status === 0;
}

function resolvePython() {
  if (process.env.PYTHON) {
    return importsMcp(process.env.PYTHON) ? process.env.PYTHON : null;
  }
  const candidates = [];
  if (process.platform === 'win32') candidates.push('C:\\Python314\\python.exe');
  candidates.push('python');
  for (const candidate of candidates) {
    if ((candidate.includes('\\') || candidate.includes('/')) && !existsSync(candidate)) continue;
    if (importsMcp(candidate)) return candidate;
  }
  return null;
}

const python = resolvePython();
if (!python) {
  if (process.env.PYTHON) console.error(`[test-python] PYTHON 指向的解释器无法 import mcp：${process.env.PYTHON}`);
  else console.error('[test-python] 未找到已安装 requirements.txt 依赖的 Python 解释器。');
  console.error('  安装：python -m pip install -r plugins/dsh-deepseek-tools/requirements.txt');
  console.error('  或设置 PYTHON 指向已装依赖的解释器（如 C:\\Python314\\python.exe）。');
  process.exit(1);
}

console.log(`[test-python] interpreter: ${python}`);
for (const file of ['test_usage.py', 'test_security.py']) {
  const result = spawnSync(python, [`plugins/dsh-deepseek-tools/${file}`], {
    cwd: root, stdio: 'inherit',
  });
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status ?? 1);
}

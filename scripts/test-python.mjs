import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));
for (const file of ['test_usage.py', 'test_security.py']) {
  const result = spawnSync(process.env.PYTHON || 'python', [`plugins/dsh-deepseek-tools/${file}`], {
    cwd: root, stdio: 'inherit',
  });
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status ?? 1);
}

import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import { isAbsolute } from 'node:path';
import { createConfig } from '../plugins/dsh-deepseek-tools/lib/config.js';

test('service entry is absolute and independent of the host working directory', () => {
  const before = process.cwd();
  try {
    process.chdir(process.env.TEMP || '/tmp');
    const config = createConfig();
    assert(isAbsolute(config.args[0]));
    assert(existsSync(config.args[0]));
    assert(existsSync(config.cwd));
    assert.equal(config.serverName, 'deepseek');
    assert.equal(config.failOnStartupError, true);
  } finally { process.chdir(before); }
});

test('custom Python path retains spaces without shell quoting', () => {
  assert.equal(createConfig({ python: 'C:/Python Runtime/python.exe' }).command,
    'C:/Python Runtime/python.exe');
});

test('invalid Python settings fail before spawning', () => {
  for (const python of ['', '   ', 42, false]) {
    assert.throws(() => createConfig({ python }), /non-empty executable/);
  }
});

import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import { isAbsolute, dirname, relative } from 'node:path';
import { spawnSync } from 'node:child_process';
import { createConfig } from '../plugins/dsh-deepseek-tools/lib/config.js';

test('service entry is absolute and independent of the host working directory', () => {
  const before = process.cwd();
  try {
    process.chdir(process.env.TEMP || '/tmp');
    const config = createConfig();
    assert(isAbsolute(config.args[0]));
    assert(existsSync(config.args[0]));
    assert(existsSync(config.cwd));
    assert(isAbsolute(config.cwd));
    const offset = relative(dirname(config.args[0]), config.cwd);
    assert(offset.startsWith('..') || isAbsolute(offset), 'cwd must be outside the replaceable package');
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

test('Windows search MCP remains available while its package directory is replaced', {
  skip: process.platform !== 'win32', timeout: 30000,
}, () => {
  const python = process.env.PYTHON || (existsSync('C:/Python314/python.exe') ? 'C:/Python314/python.exe' : 'python');
  const config = createConfig({ python });
  const result = spawnSync(python, ['-c', String.raw`
import json, os, pathlib, shutil, subprocess, sys, tempfile
config = json.load(sys.stdin)
source = pathlib.Path(config['args'][0]).parent
with tempfile.TemporaryDirectory(prefix='juzi-search-update-') as scratch:
    root = pathlib.Path(scratch)
    package = root / 'plugin with spaces'
    shutil.copytree(source, package, ignore=shutil.ignore_patterns('__pycache__'))
    moved = root / 'replaced'
    configured_cwd = pathlib.Path(config['cwd'])
    if configured_cwd.is_relative_to(source):
        configured_cwd = package / configured_cwd.relative_to(source)
    for inside in (True, False):
        child = subprocess.Popen([sys.executable, str(package / 'server.py')],
            cwd=str(package) if inside else str(configured_cwd),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding='utf-8')
        def request(method, number, params=None):
            payload = {'jsonrpc':'2.0', 'id':number, 'method':method}
            if params is not None:
                payload['params'] = params
            child.stdin.write(json.dumps(payload)+'\n')
            child.stdin.flush()
            reply = json.loads(child.stdout.readline())
            assert 'error' not in reply, reply
            return reply['result']
        try:
            request('initialize', 1, {'protocolVersion':'2024-11-05',
                'capabilities':{}, 'clientInfo':{'name':'search-cwd-test','version':'1'}})
            tools = {tool['name'] for tool in request('tools/list', 2)['tools']}
            assert tools == {'DeepSeek-Search','DeepSeek-Fetch'}, tools
            if inside:
                try:
                    package.rename(moved)
                except OSError as error:
                    assert error.winerror in (5, 32), error
                else:
                    raise AssertionError('package cwd must reproduce the Windows directory lock')
            else:
                package.rename(moved)
                moved.rename(package)
                assert {tool['name'] for tool in request('tools/list', 3)['tools']} == tools
                assert request('ping', 4) == {}
        finally:
            child.communicate(timeout=5)
        assert child.returncode == 0, child.returncode
    sys.path.insert(0, str(package))
    import usage_store
    for key in ('DEEPSEEK_USAGE_PATH', 'CLAUDE_CONFIG_DIR'):
        os.environ.pop(key, None)
    before = usage_store.usage_path()
    os.chdir(config['cwd'])
    assert usage_store.usage_path() == before
    explicit = str(root / 'usage.json')
    os.environ['DEEPSEEK_USAGE_PATH'] = explicit
    assert usage_store.usage_path() == pathlib.Path(explicit)
print('old cwd locked; configured cwd permits replacement; MCP tools and usage paths preserved')
`], { input: JSON.stringify(config), encoding: 'utf8', timeout: 25000 });
  assert.equal(result.error, undefined);
  assert.equal(result.status, 0, result.stderr || result.stdout);
});

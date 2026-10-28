import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import { isAbsolute, dirname, relative } from 'node:path';
import { spawnSync } from 'node:child_process';
import { createConfig } from '../plugins/juzi-win-dsh/lib/config.js';

test('computer control starts by absolute path outside its package directory', () => {
  const config = createConfig();
  assert(isAbsolute(config.args[0]));
  assert(existsSync(config.args[0]));
  assert(isAbsolute(config.cwd));
  assert(existsSync(config.cwd));
  const offset = relative(dirname(config.args[0]), config.cwd);
  assert(offset.startsWith('..') || isAbsolute(offset));
  assert.equal(createConfig({ python: 'C:/Python Runtime/python.exe' }).command,
    'C:/Python Runtime/python.exe');
});

test('Windows running MCP permits package replacement with external cwd', {
  skip: process.platform !== 'win32', timeout: 30000,
}, () => {
  const config = createConfig();
  const run = spawnSync(config.command, ['-c', String.raw`
import json, pathlib, shutil, subprocess, sys, tempfile
config = json.load(sys.stdin)
with tempfile.TemporaryDirectory(prefix='juzi-update-') as scratch:
    root = pathlib.Path(scratch)
    package = root / 'plugin with spaces'
    shutil.copytree(pathlib.Path(config['args'][0]).parent, package,
                    ignore=shutil.ignore_patterns('__pycache__'))
    moved = root / 'replaced'
    for inside in (True, False):
        child = subprocess.Popen([sys.executable, str(package / 'server.py')],
            cwd=str(package) if inside else config['cwd'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding='utf-8')
        def request(method, number, params=None):
            child.stdin.write(json.dumps({'jsonrpc':'2.0','id':number,
                'method':method,'params':params if params is not None else {'protocolVersion':'2024-11-05',
                'capabilities':{},'clientInfo':{'name':'cwd-regression','version':'1'}}})+'\n')
            child.stdin.flush()
            reply = json.loads(child.stdout.readline())
            assert 'error' not in reply, reply
            return reply['result']
        try:
            request('initialize', 1)
            assert len(request('tools/list', 2)['tools']) == 17
            if inside:
                try:
                    package.rename(moved)
                except OSError as error:
                    assert error.winerror in (5, 32), error
                else:
                    raise AssertionError('old cwd no longer reproduces directory lock')
            else:
                package.rename(moved)
                moved.rename(package)
                assert len(request('tools/list', 3)['tools']) == 17
                result = request('tools/call', 4, {'name':'manage_window',
                    'arguments':{'action':'get_work_area'}})
                assert not result.get('isError'), result
                payload = json.loads(result['content'][0]['text'])
                assert payload['ok'], payload
        finally:
            child.communicate(timeout=5)
        assert child.returncode == 0, child.returncode
print('old cwd blocked; new cwd rename and MCP requests passed')
`], { input: JSON.stringify(config), encoding: 'utf8', timeout: 25000,
    env: { ...process.env, ...config.env } });
  assert.equal(run.error, undefined);
  assert.equal(run.status, 0, run.stderr || run.stdout);
});

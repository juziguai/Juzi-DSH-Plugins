/** Execute Git through the composed DSH subprocess capability, never a shell. */
export function capabilityGit(subprocess, lifetime, timeoutMs) {
  let executable;
  return async (args, { cwd, input, signal = lifetime, maxBytes = 8 * 1024 * 1024 } = {}) => {
    executable ??= subprocess.resolveExecutable('git', undefined, lifetime);
    const timeout = AbortSignal.timeout(timeoutMs);
    const combined = AbortSignal.any([lifetime, signal, timeout]);
    const handle = subprocess.spawn({
      argv: [await executable, '--no-pager', ...args], cwd, signal: combined, graceMs: 3000,
      env: { ...Object.fromEntries(Object.keys(process.env).filter(key => key.startsWith('GIT_')).map(key => [key, undefined])),
        GIT_CONFIG_COUNT: '0', GIT_TERMINAL_PROMPT: '0', GIT_OPTIONAL_LOCKS: '0', LC_ALL: 'C' },
      stdio: { stdin: input === undefined ? 'ignore' : { data: input }, stdout: { maxBytes }, stderr: { maxBytes: 16384 } },
    });
    const outcome = await handle.done;
    combined.throwIfAborted();
    const stdout = handle.collected.stdout.readFrom(0);
    if (stdout.lossy) throw new Error('Git output limit exceeded');
    return { code: outcome.exitCode, stdout: stdout.text, stderr: handle.collected.stderr.readFrom(0).text };
  };
}

export function checked(result, operation) {
  if (result.code !== 0) throw new Error(`${operation} failed (Git exit ${result.code})`);
  return result.stdout;
}

export function parseNumstat(text) {
  if (text && !text.endsWith('\0')) throw new Error('Incomplete Git file list');
  const parts = text.split('\0'); parts.pop();
  const rows = [];
  while (parts.length) {
    const line = parts.shift();
    const match = /^(-|\d+)\t(-|\d+)\t(.*)$/s.exec(line);
    if (!match) throw new Error('Invalid Git file statistics');
    let path = match[3], oldPath;
    if (!path) { oldPath = parts.shift(); path = parts.shift(); }
    if (path === undefined || oldPath === '') throw new Error('Incomplete Git rename');
    rows.push({ path, oldPath, binary: match[1] === '-', added: Number(match[1]) || 0, deleted: Number(match[2]) || 0 });
  }
  return rows;
}

export function parseHunks(patch) {
  const hunks = []; let current;
  for (const line of patch.split('\n')) {
    const header = /^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@/.exec(line);
    if (header) {
      current = { oldStart: +header[1], oldLines: header[2] === undefined ? 1 : +header[2],
        newStart: +header[3], newLines: header[4] === undefined ? 1 : +header[4], lines: [] };
      hunks.push(current);
    } else if (current && /^[ +\-]/.test(line)) current.lines.push(line);
  }
  return hunks;
}

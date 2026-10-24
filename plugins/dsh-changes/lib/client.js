window.__ModuleLoader__.load({
  id: '@juzi/dsh-changes',
  factory: require => {
    const React = require('react');
    const h = React.createElement;
    const ID = '@juzi/dsh-changes', KIND = 'juzi-changes';
    const CSS = `
.jc-page{--jc-text:var(--dsw-alias-label-primary,#202631);--jc-muted:var(--dsw-alias-label-secondary,#89909a);--jc-line:var(--dsw-alias-border-l2,#e9eaec);--jc-bg:var(--dsw-alias-bg-layer-1,#fff);--jc-accent:#3971df;--jc-green:#009b43;--jc-red:#e32636;display:flex;flex-direction:column;height:100%;min-height:0;min-width:0;overflow:hidden;color:var(--jc-text);background:var(--jc-bg);font-size:14px;line-height:1.5;font-family:inherit;container-type:inline-size}
.jc-page *{box-sizing:border-box}.jc-page svg,.jc-open svg,.jc-title svg{flex:none;vertical-align:middle}
.jc-toolbar{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:7px 10px;min-height:50px;flex:none;border-bottom:1px solid var(--jc-line)}
.jc-turn-group,.jc-tools{display:inline-flex;align-items:center;gap:4px;padding:3px;border:1px solid var(--jc-line);border-radius:24px;box-shadow:0 2px 7px #00000004;min-width:0}.jc-turn-group{gap:7px;padding-right:9px}.jc-turn{position:relative;display:inline-flex;align-items:center;min-width:0}.jc-turn>svg{position:absolute;right:6px;pointer-events:none;color:var(--jc-muted)}
.jc-select{appearance:none;min-width:78px;max-width:135px;border:0;border-radius:18px;background:transparent;color:inherit;padding:4px 23px 4px 9px;font:inherit;cursor:pointer;line-height:20px}.jc-count{display:inline-flex;align-items:center;gap:4px;white-space:nowrap;font-size:13px;font-weight:400;font-variant-numeric:tabular-nums}.jc-add{color:var(--jc-green)}.jc-del{color:var(--jc-red)}.jc-grow{flex:1;min-width:0}
.jc-button,.jc-open{display:inline-flex;align-items:center;justify-content:center;gap:6px;border:1px solid var(--jc-line);background:transparent;color:inherit;border-radius:8px;min-height:30px;padding:4px 8px;cursor:pointer;font:inherit;white-space:nowrap;flex:none}.jc-icon-button{width:28px;min-height:28px;padding:5px;border-color:transparent;color:var(--jc-muted)}.jc-tools>.jc-icon-button,.jc-tools>.jc-menu>.jc-icon-button{border-radius:50%}.jc-button:hover,.jc-open:hover,.jc-file-toggle:hover{background:color-mix(in srgb,currentColor 5%,transparent)}.jc-button[aria-expanded=true]{color:var(--jc-accent);background:color-mix(in srgb,var(--jc-accent) 7%,transparent)}.jc-button:disabled{opacity:.35;cursor:default}
.jc-open{font-size:12px;color:var(--jc-muted)}.jc-title{display:inline-flex;align-items:center;gap:7px;min-width:0}.jc-title svg{color:var(--jc-muted)}.jc-page button:focus-visible,.jc-page select:focus-visible,.jc-page [tabindex]:focus-visible,.jc-open:focus-visible{outline:2px solid var(--jc-accent);outline-offset:-2px}
.jc-menu{position:relative;display:inline-flex;flex:none}.jc-menu-panel{position:absolute;right:0;top:calc(100% + 5px);z-index:10;min-width:166px;padding:5px;border:1px solid var(--jc-line);border-radius:9px;background:var(--jc-bg);box-shadow:0 6px 24px #0000001a;color:var(--jc-text);font-size:12px}.jc-menu[data-above=true]>.jc-menu-panel{top:auto;bottom:calc(100% + 5px)}.jc-menu-item{display:grid;grid-template-columns:14px 1fr;gap:7px;align-items:center;width:100%;min-height:30px;border:0;border-radius:5px;padding:5px 7px;color:inherit;background:transparent;font:inherit;text-align:left;white-space:nowrap;cursor:pointer}.jc-menu-item:hover,.jc-menu-item:focus-visible{background:color-mix(in srgb,currentColor 6%,transparent)}.jc-menu-item:disabled{opacity:.4;cursor:default}
.jc-note{flex:none;max-height:100px;overflow:auto;padding:9px 12px;margin:0;font-size:12px;line-height:1.6;color:var(--jc-muted);background:color-mix(in srgb,#d99a31 9%,var(--jc-bg));overflow-wrap:anywhere}.jc-error{color:var(--dsw-alias-state-error-primary,var(--jc-red))}.jc-copy-feedback{flex:none;padding:6px 12px;font-size:11px;color:var(--jc-green);overflow-wrap:anywhere}.jc-copy-feedback.jc-error{color:var(--dsw-alias-state-error-primary,var(--jc-red))}
.jc-main{display:flex;flex-direction:column;flex:1;min-height:0}.jc-files{overflow:auto;flex:1;min-height:0;scrollbar-width:thin}.jc-entry{position:relative;border-bottom:1px solid var(--jc-line)}.jc-file-head{display:flex;align-items:center;gap:5px;min-height:42px;padding:4px 8px 4px 12px;background:var(--jc-bg)}.jc-entry[data-expanded=true]>.jc-file-head{position:sticky;top:0;z-index:2;border-bottom:1px solid var(--jc-line)}.jc-file-head:has(.jc-menu-panel){z-index:5}
.jc-file-toggle{display:flex;align-items:center;gap:8px;flex:1;min-width:0;border:0;border-radius:5px;padding:5px 0;color:inherit;background:transparent;font:inherit;text-align:left;cursor:pointer}.jc-file-icon{display:inline-flex;align-items:center;justify-content:center;flex:none;width:19px;height:23px;color:var(--jc-muted)}.jc-file-icon[data-type=code]{color:#b99520}.jc-file-icon[data-type=text]{color:#2caa50}
.jc-file-label{display:flex;align-items:baseline;flex:1;min-width:0;white-space:nowrap;font-weight:400}.jc-directory{flex:0 1 auto;min-width:0;max-width:60%;overflow:hidden;text-overflow:ellipsis;color:var(--jc-muted)}.jc-filename{flex:0 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis;color:var(--jc-text)}.jc-file-head .jc-count{flex:none;font-size:13px}.jc-file-kind{flex:none;font-size:11px;color:var(--jc-muted);white-space:nowrap}.jc-file-head .jc-icon-button{width:24px;min-height:26px;padding:3px}
.jc-diff-content{position:relative}.jc-diff-placeholder{min-height:64px}.jc-updating{position:absolute;right:8px;top:5px;z-index:1;padding:1px 5px;border-radius:4px;color:var(--jc-muted);background:var(--jc-bg);font-size:10px}.jc-diff-code{overflow:auto;min-height:0;font:12.5px/23px Consolas,"NSimSun","SimSun",monospace;tab-size:4;scrollbar-width:thin}.jc-context{padding:6px 8px;color:var(--jc-text);background:color-mix(in srgb,currentColor 5%,var(--jc-bg));font:13.5px/22px system-ui,sans-serif}
.jc-code-line{display:flex;min-width:max-content;white-space:pre;border-left:3px solid transparent}.jc-code-line.jc-plus{border-left-color:var(--jc-green);background:color-mix(in srgb,var(--jc-green) 9%,var(--jc-bg))}.jc-code-line.jc-minus{border-left-color:var(--jc-red);background:color-mix(in srgb,var(--jc-red) 7%,var(--jc-bg))}.jc-ln{width:35px;flex:none;text-align:right;padding-right:8px;font-size:11px;font-variant-numeric:tabular-nums;color:var(--jc-muted);user-select:none}.jc-sign{width:22px;flex:none;text-align:center;user-select:none}.jc-plus .jc-sign{color:var(--jc-green)}.jc-minus .jc-sign{color:var(--jc-red)}.jc-code{padding-right:14px}
.jc-diff-code[data-wrap=true] .jc-code-line{min-width:0}.jc-diff-code[data-wrap=true] .jc-code{flex:1;min-width:0;white-space:pre-wrap;overflow-wrap:anywhere}.jc-diff-message{padding:18px 12px;color:var(--jc-muted);font-size:12px;line-height:1.8}.jc-empty{max-width:300px;margin:0 auto;padding:36px 20px;text-align:center;color:var(--jc-muted);font-size:12px;line-height:1.8}.jc-empty>svg{display:block;margin:0 auto 12px;opacity:.55}.jc-empty strong{display:block;margin-bottom:6px;font-size:13px;font-weight:500;color:var(--jc-text)}
.jc-footer{display:flex;align-items:center;gap:6px;flex:none;min-height:29px;border-top:1px solid var(--jc-line);padding:4px 10px;color:var(--jc-muted);font-size:10px}.jc-footer-label{display:inline-flex;align-items:center;gap:5px}.jc-footer .jc-button{font-size:10px;min-height:22px;padding:2px 5px;border:0}.jc-sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap;border:0}
html[data-ds-dark-theme] .jc-page,body[data-ds-dark-theme] .jc-page{--jc-bg:var(--dsw-alias-bg-layer-1,#202329);--jc-accent:#80a6ff;--jc-green:#6ace91;--jc-red:#ff8e95}.jc-page ::selection{background:color-mix(in srgb,var(--jc-accent) 24%,transparent)}
@container(max-width:360px){.jc-toolbar{gap:5px;padding-inline:7px}.jc-turn-group{gap:3px;padding-right:6px}.jc-tools{gap:0}.jc-select{min-width:72px;padding-left:6px}.jc-file-head{gap:3px;padding-left:8px;padding-right:5px}.jc-file-toggle{gap:5px}.jc-file-head .jc-count{font-size:11px;gap:3px}.jc-file-head .jc-icon-button{width:23px}.jc-directory{max-width:45%}.jc-ln{width:31px}}
`;
    // Lucide 0.468.0 icon geometry; see LICENSE.LUCIDE (ISC / MIT).
    const iconNodes = {"file-diff":[["path",{"d":"M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"}],["path",{"d":"M9 10h6"}],["path",{"d":"M12 13V7"}],["path",{"d":"M9 17h6"}]],"file-code-2":[["path",{"d":"M4 22h14a2 2 0 0 0 2-2V7l-5-5H6a2 2 0 0 0-2 2v4"}],["path",{"d":"M14 2v4a2 2 0 0 0 2 2h4"}],["path",{"d":"m5 12-3 3 3 3"}],["path",{"d":"m9 18 3-3-3-3"}]],"file-text":[["path",{"d":"M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"}],["path",{"d":"M14 2v4a2 2 0 0 0 2 2h4"}],["path",{"d":"M10 9H8"}],["path",{"d":"M16 13H8"}],["path",{"d":"M16 17H8"}]],"file":[["path",{"d":"M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"}],["path",{"d":"M14 2v4a2 2 0 0 0 2 2h4"}]],"refresh-cw":[["path",{"d":"M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"}],["path",{"d":"M21 3v5h-5"}],["path",{"d":"M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"}],["path",{"d":"M8 16H3v5"}]],"chevron-down":[["path",{"d":"m6 9 6 6 6-6"}]],"external-link":[["path",{"d":"M15 3h6v6"}],["path",{"d":"M10 14 21 3"}],["path",{"d":"M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"}]],"info":[["circle",{"cx":"12","cy":"12","r":"10"}],["path",{"d":"M12 16v-4"}],["path",{"d":"M12 8h.01"}]]};
    iconNodes.copy = [['rect', { width: 14, height: 14, x: 8, y: 8, rx: 2, ry: 2 }], ['path', { d: 'M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2' }]];
    iconNodes.ellipsis = [['circle', { cx: 12, cy: 12, r: 1 }], ['circle', { cx: 19, cy: 12, r: 1 }], ['circle', { cx: 5, cy: 12, r: 1 }]];
    iconNodes.check = [['path', { d: 'M20 6 9 17l-5-5' }]];
    function Icon({ name = 'file-diff', size = 16, ...props }) {
      return h('svg', { width: size, height: size, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.7,
        strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': true, focusable: false, ...props },
        iconNodes[name].map(([tag, attributes], index) => h(tag, { ...attributes, key: index })));
    }
    const fileState = { added: '新增', deleted: '删除', renamed: '重命名', modified: '修改' };
    function fileParts(display) {
      const parts = display.replaceAll('\\', '/').split('/');
      return { name: parts.pop(), directory: parts.join('/') };
    }
    function FileIcon({ display }) {
      const extension = display.split('.').pop().toLowerCase();
      const type = /^(js|jsx|ts|tsx|mjs|cjs|py|go|rs|java|css|html|vue|sh|ps1|json|yml|yaml)$/.test(extension) ? 'code' : /^(md|txt|rst|log)$/.test(extension) ? 'text' : 'file';
      return h('span', { className: 'jc-file-icon', 'data-type': type }, h(Icon, { name: type === 'code' ? 'file-code-2' : type === 'text' ? 'file-text' : 'file', size: 19 }));
    }
    function FileLabel({ display }) {
      const { name, directory } = fileParts(display);
      return h('span', { className: 'jc-file-label' }, directory ? h('span', { className: 'jc-directory' }, directory + '/') : null, h('span', { className: 'jc-filename' }, name));
    }
    function Menu({ label, items }) {
      const [open, setOpen] = React.useState(false), [above, setAbove] = React.useState(false);
      const root = React.useRef(null), trigger = React.useRef(null);
      React.useEffect(() => {
        if (!open) return;
        const dismiss = event => { if (!root.current.contains(event.target)) setOpen(false); };
        document.addEventListener('pointerdown', dismiss);
        root.current.querySelector('[role^="menuitem"]')?.focus();
        return () => document.removeEventListener('pointerdown', dismiss);
      }, [open]);
      return h('span', { className: 'jc-menu', ref: root, 'data-above': above, onKeyDown: event => {
        if (event.key === 'Escape' && open) { event.stopPropagation(); setOpen(false); trigger.current.focus(); }
        if (open && ['ArrowDown', 'ArrowUp'].includes(event.key)) {
          event.preventDefault(); const buttons = [...root.current.querySelectorAll('[role^="menuitem"]:not(:disabled)')];
          const current = buttons.indexOf(document.activeElement), step = event.key === 'ArrowDown' ? 1 : -1;
          buttons[(current + step + buttons.length) % buttons.length]?.focus();
        }
      }, onBlur: event => { if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false); } },
        h('button', { className: 'jc-button jc-icon-button', ref: trigger, 'aria-label': label, title: label, 'aria-haspopup': 'menu', 'aria-expanded': open,
          onClick: () => { setAbove(trigger.current.getBoundingClientRect().bottom + 120 > root.current.closest('.jc-page').getBoundingClientRect().bottom); setOpen(value => !value); } }, h(Icon, { name: 'ellipsis' })),
        open ? h('div', { className: 'jc-menu-panel', role: 'menu', 'aria-label': label }, items.map(item => h('button', {
          key: item.label, className: 'jc-menu-item', role: item.checked === undefined ? 'menuitem' : 'menuitemcheckbox', 'aria-checked': item.checked, disabled: item.disabled,
          onClick: () => { setOpen(false); trigger.current.focus(); item.run(); },
        }, h('span', { 'aria-hidden': true }, item.checked ? h(Icon, { name: 'check', size: 14 }) : null), item.label))) : null);
    }
    const statusName = { starting: '正在建立轮次基线', running: '执行中 · 实时更新', finished: '已结束', interrupted: '已中断', error: '记录失败' };
    function formatSummary(summary, readError) {
      const quotePath = path => {
        const text = path.replaceAll('\r', '\\r').replaceAll('\n', '\\n');
        const fence = '`'.repeat(Math.max(0, ...(text.match(/`+/g) ?? []).map(run => run.length)) + 1);
        return fence + (text.startsWith('`') || text.endsWith('`') ? ' ' + text + ' ' : text) + fence;
      };
      const lines = [`## 第 ${summary.turn} 轮变更摘要`, '',
        `状态：${summary.status === 'running' ? '执行中（截至复制时）' : statusName[summary.status] ?? summary.status}`,
        `共 ${summary.total} 个文件；文本新增 ${summary.added} 行，删除 ${summary.deleted} 行。`, ''];
      if (readError) lines.push('读取提示：' + readError + '（以下为面板当前显示的记录）', '');
      if (summary.error) lines.push('快照未更新：' + summary.error + '（以下为面板保留的记录，可能不完整）', '');
      if (summary.warning) lines.push('记录提示：' + summary.warning, '');
      for (const file of summary.files) {
        const path = (file.oldDisplay ? quotePath(file.oldDisplay) + ' → ' : '') + quotePath(file.display);
        const detail = file.oversized ? '超限文件，未统计文本增删' : file.binary ? '二进制文件，未统计文本增删' : `+${file.added} / -${file.deleted}`;
        lines.push(`- ${fileState[file.status]} ${path}（${detail}）`);
      }
      if (!summary.total) lines.push(summary.error || summary.status === 'error' ? '暂无成功记录的文件明细。' : '无文件变更。');
      if (summary.total > summary.files.length) lines.push('', `仅列出前 ${summary.files.length} 个文件；总计包含全部 ${summary.total} 个文件。`);
      return lines.join('\n');
    }
    const counts = data => h('span', { className: 'jc-count', 'aria-label': `新增 ${data?.added ?? 0} 行，删除 ${data?.deleted ?? 0} 行` }, h('span', { className: 'jc-add' }, '+' + (data?.added ?? 0)), h('span', { className: 'jc-del' }, '-' + (data?.deleted ?? 0)));
    async function read(action, params, signal) {
      const response = await fetch('api/juzi.changes.' + action + '?' + new URLSearchParams(params), { signal, cache: 'no-store', credentials: 'same-origin' });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error ?? '读取变更失败');
      if (action === 'list' && !Array.isArray(data.turns) || action === 'turn' && (!Array.isArray(data.files) || !Number.isSafeInteger(data.revision)) ||
        action === 'diff' && (!['text', 'binary', 'oversized'].includes(data.kind) || data.kind === 'text' && !Array.isArray(data.hunks))) throw new Error('变更接口返回格式不正确，请刷新或检查插件版本');
      return data;
    }
    function Diff({ value, wrap }) {
      if (!value) return h('div', { className: 'jc-diff-message', role: 'status' }, '正在读取差异…');
      if (value.error) return h('div', { className: 'jc-note jc-error', role: 'alert' }, value.error);
      if (value.kind !== 'text') return h('div', { className: 'jc-diff-message' }, value.kind === 'binary' ? '二进制文件，不显示文本差异。' : '文件超过快照大小限制，不显示文本差异。');
      const rows = []; let count = 0, oldNext = 1, newNext = 1;
      for (const [index, hunk] of value.hunks.entries()) {
        const omitted = Math.max(0, hunk.oldStart - oldNext, hunk.newStart - newNext);
        if (omitted) rows.push(h('div', { className: 'jc-context', key: 'context:' + index }, `${omitted} 行未修改`));
        let old = hunk.oldStart, current = hunk.newStart;
        for (const line of hunk.lines) {
          if (++count > 5000) break;
          const sign = line[0], previousNumber = sign === '+' ? '' : old++, currentNumber = sign === '-' ? '' : current++;
          rows.push(h('div', { className: 'jc-code-line ' + (sign === '+' ? 'jc-plus' : sign === '-' ? 'jc-minus' : ''), key: index + ':' + count },
            h('span', { className: 'jc-ln', title: (sign === '-' ? '原文件第 ' + previousNumber : '当前文件第 ' + currentNumber) + ' 行' }, sign === '-' ? previousNumber : currentNumber),
            h('span', { className: 'jc-sign', 'aria-hidden': true }, sign), h('span', { className: 'jc-code' }, line.slice(1))));
        }
        oldNext = old; newNext = current;
        if (count > 5000) break;
      }
      if (count > 5000) rows.push(h('div', { className: 'jc-note', key: 'limit' }, '仅显示前 5,000 行差异。'));
      return rows.length ? h('div', { className: 'jc-diff-code', 'data-wrap': wrap, tabIndex: 0, 'aria-label': '文件差异内容' }, rows) : h('div', { className: 'jc-diff-message' }, '没有文本差异。');
    }
    function FileDiff({ file, sessionId, turn, revision, wrap, visible, generation, epochRef, entryRef, id }) {
      const content = React.useRef(null), retainedHeight = React.useRef(64);
      const [nearby, setNearby] = React.useState(false), [result, setResult] = React.useState(null);
      React.useEffect(() => {
        const observer = new IntersectionObserver(([entry]) => setNearby(entry.isIntersecting),
          { root: entryRef.current.parentElement, rootMargin: '160px 0px' });
        const resize = new ResizeObserver(([entry]) => {
          // Preserve the last visible height when evicting a body or hiding the tab.
          if (entry.contentRect.height > 0) retainedHeight.current = entry.contentRect.height;
        });
        observer.observe(entryRef.current); resize.observe(content.current);
        return () => { observer.disconnect(); resize.disconnect(); };
      }, []);
      const active = visible && nearby;
      React.useEffect(() => {
        if (!active) { setResult(null); return; }
        const controller = new AbortController(), epoch = epochRef.current;
        read('diff', { sessionId, turn: String(turn), revision: String(revision), file: file.id }, controller.signal)
          .then(value => { if (!controller.signal.aborted && epoch === epochRef.current) setResult({ revision, value }); },
            error => { if (!controller.signal.aborted && epoch === epochRef.current) setResult({ revision, value: { error: error.message } }); });
        return () => controller.abort();
      }, [sessionId, turn, revision, file.id, active, generation, epochRef]);
      return h('div', { className: 'jc-diff-content', ref: content, role: 'region', 'aria-label': file.display + ' 的差异', id, 'aria-busy': active && result?.revision !== revision,
          style: active && !result ? { minHeight: retainedHeight.current } : undefined },
          active && result && result.revision !== revision ? h('span', { className: 'jc-updating' }, '更新中…') : null,
          active ? h(Diff, { value: result?.value, wrap }) : h('div', { className: 'jc-diff-placeholder', style: { height: retainedHeight.current }, 'aria-hidden': true }));
    }
    function FileEntry({ file, expanded, onToggle, actions, id, ...diffProps }) {
      const root = React.useRef(null);
      const toggle = () => onToggle(file.id);
      return h('section', { className: 'jc-entry', ref: root, 'data-file-id': file.id, 'data-expanded': expanded },
        h('div', { className: 'jc-file-head' },
          h('button', { className: 'jc-file-toggle', 'aria-expanded': expanded, 'aria-controls': expanded ? id : undefined,
            'aria-label': `${fileState[file.status]} ${file.display}，${file.binary ? '二进制文件' : file.oversized ? '超限文件' : `新增 ${file.added} 行，删除 ${file.deleted} 行`}`,
            title: (file.oldDisplay ? file.oldDisplay + ' → ' : '') + file.display, onClick: toggle }, h(FileIcon, { display: file.display }), h(FileLabel, { display: file.display })),
          file.binary || file.oversized ? h('span', { className: 'jc-file-kind' }, file.binary ? '二进制' : '超限') : counts(file),
          h('button', { className: 'jc-button jc-icon-button', disabled: file.status === 'deleted', title: file.status === 'deleted' ? '文件已删除，无法打开' : '打开当前文件', 'aria-label': '打开 ' + file.display,
            onClick: () => {
              const path = file.path.replaceAll('\\', '/').split('/').map(part => encodeURIComponent(part)).join('/');
              actions.openResource('dsh-resource://file/session/' + encodeURIComponent(diffProps.sessionId) + '/' + path);
            } }, h(Icon, { name: 'external-link', size: 15 })),
          h(Menu, { label: file.display + ' 的更多操作', items: [{ label: expanded ? '折叠差异' : '展开差异', run: toggle }] })),
        expanded ? h(FileDiff, { ...diffProps, file, entryRef: root, id }) : null);
    }
    function apply(ctx) {
      const resetListeners = new Set();
      ctx.effect(() => {
        const style = document.createElement('style'); style.textContent = CSS; document.head.appendChild(style);
        return () => style.remove();
      });
      ctx.on('connection/reset', () => resetListeners.forEach(listener => listener()));
      function Page({ sessionId, useTabInfo }) {
        const { tab } = useTabInfo();
        const [turns, setTurns] = React.useState([]), [selection, setSelection] = React.useState('latest'), [maxTurns, setMaxTurns] = React.useState(30);
        const [summary, setSummary] = React.useState(null), [error, setError] = React.useState(null);
        const [expanded, setExpanded] = React.useState(() => new Set());
        const [refresh, setRefresh] = React.useState(0), [generation, setGeneration] = React.useState(0);
        const requestGeneration = React.useRef(0), pageRef = React.useRef(null), pendingFocus = React.useRef(null);
        const [wrap, setWrap] = React.useState(true), diffId = React.useId();
        const [copy, setCopy] = React.useState(null), copyAttempt = React.useRef(0);
        React.useEffect(() => {
          setCopy(null);
          return () => { copyAttempt.current++; };
        }, [summary?.turn, generation]);
        React.useEffect(() => {
          if (copy?.kind !== 'success') return;
          const timer = setTimeout(() => setCopy(null), 3000);
          return () => clearTimeout(timer);
        }, [copy]);
        React.useEffect(() => {
          const reset = () => { requestGeneration.current++; setTurns([]); setSummary(null); setExpanded(new Set()); setGeneration(value => value + 1); };
          resetListeners.add(reset); return () => resetListeners.delete(reset);
        }, []);
        React.useEffect(() => {
          if (!tab.visible) return;
          const controller = new AbortController(); let timer, first = true;
          const epoch = requestGeneration.current;
          const stale = () => controller.signal.aborted || epoch !== requestGeneration.current;
          const poll = async () => {
            try {
              const info = await read('list', { sessionId }, controller.signal);
              if (stale()) return;
              setTurns(info.turns); setMaxTurns(info.maxTurns);
              const turn = selection === 'latest' ? info.turns[0]?.turn : selection === 'previous' ? info.turns[1]?.turn : Number(selection);
              if (turn === undefined) { setSummary(null); setExpanded(new Set()); }
              else {
                const data = await read('turn', { sessionId, turn: String(turn), ...(first && refresh ? { refresh: '1' } : {}) }, controller.signal);
                if (stale()) return;
                setSummary(data); setExpanded(value => value === 'all' ? value : new Set([...value].filter(id => data.files.some(file => file.id === id))));
              }
              setError(null);
            } catch (error) { if (!stale()) setError(error.message); }
            finally { first = false; if (!stale()) timer = setTimeout(poll, 1000); }
          };
          poll();
          return () => { controller.abort(); clearTimeout(timer); };
        }, [sessionId, tab.visible, selection, refresh, generation]);
        React.useEffect(() => tab.actions.bindCommands({ refresh: () => setRefresh(value => value + 1) }), [tab.actions]);
        const isExpanded = id => expanded === 'all' || expanded.has(id);
        const expandedFiles = summary?.files.filter(item => isExpanded(item.id)) ?? [];
        const allOpen = Boolean(summary?.files.length && expandedFiles.length === summary.files.length);
        React.useLayoutEffect(() => {
          if (!pendingFocus.current) return;
          [...pageRef.current?.querySelectorAll('[data-file-id]') ?? []].find(row => row.dataset.fileId === pendingFocus.current)?.querySelector('.jc-file-toggle')?.focus();
          pendingFocus.current = null;
        }, [expanded]);
        const toggleFile = id => {
          pendingFocus.current = id;
          setExpanded(value => {
            const next = new Set(value === 'all' ? summary.files.map(item => item.id) : value);
            if (next.has(id)) next.delete(id); else next.add(id);
            return next;
          });
        };
        const changeTurn = event => { setSelection(event.target.value); setSummary(null); setExpanded(new Set()); };
        const copySummary = async () => {
          const attempt = ++copyAttempt.current, turn = summary.turn;
          setCopy({ kind: 'pending' });
          try {
            if (!navigator.clipboard?.writeText) throw new Error('当前环境不支持剪贴板写入');
            await navigator.clipboard.writeText(formatSummary(summary, error));
            if (attempt === copyAttempt.current) setCopy({ kind: 'success', message: `已复制第 ${turn} 轮变更摘要` });
          } catch (error) {
            if (attempt === copyAttempt.current) setCopy({ kind: 'error', message: '复制失败：' + error.message });
          }
        };
        const emptyTitle = !turns.length ? '等待新一轮任务' : !summary ? '正在读取轮次…' : summary.status === 'running' ? '正在等待文件修改' : '这一轮没有文件变更';
        return h('section', { className: 'jc-page', 'aria-label': '文件变更', ref: pageRef, onKeyDown: event => {
          if (event.key === 'Escape' && expandedFiles.length) {
            event.stopPropagation();
            const id = event.target.closest('.jc-entry')?.dataset.fileId;
            if (id) toggleFile(id); else { pendingFocus.current = expandedFiles[0].id; setExpanded(new Set()); }
          }
        } },
          h('div', { className: 'jc-toolbar' },
            h('span', { className: 'jc-turn-group', title: summary ? `第 ${summary.turn} 轮 · ${statusName[summary.status] ?? summary.status} · ${summary.total} 个文件` : '选择轮次' },
              h('span', { className: 'jc-turn' }, h('select', { className: 'jc-select', 'aria-label': '选择轮次', value: selection, onChange: changeTurn },
              h('option', { value: 'latest' }, turns[0]?.status === 'running' ? '当前轮' : '最近一轮'),
              turns.length > 1 ? h('option', { value: 'previous' }, '上一轮') : null,
              turns.map(item => h('option', { key: item.turn, value: String(item.turn) }, `第 ${item.turn} 轮`))), h(Icon, { name: 'chevron-down', size: 14 })),
              counts(summary)),
            h('span', { className: 'jc-tools', role: 'group', 'aria-label': '变更操作' },
              h(Menu, { label: '更多变更操作', items: [
                { label: '自动换行', checked: wrap, run: () => setWrap(value => !value) },
                { label: allOpen ? '折叠全部差异' : '展开全部差异', disabled: !summary?.files.length, run: () => setExpanded(allOpen ? new Set() : 'all') },
              ] }),
              h('button', { className: 'jc-button jc-icon-button', onClick: () => setRefresh(value => value + 1), title: '刷新变更', 'aria-label': '刷新变更' }, h(Icon, { name: 'refresh-cw' })),
              h('button', { className: 'jc-button jc-icon-button', disabled: !summary || copy?.kind === 'pending', onClick: copySummary, title: copy?.kind === 'pending' ? '正在复制…' : '复制变更摘要', 'aria-label': '复制变更摘要' }, h(Icon, { name: copy?.kind === 'success' ? 'check' : 'copy' })))),
          summary ? h('span', { className: 'jc-sr-only', role: 'status' }, `第 ${summary.turn} 轮 · ${statusName[summary.status] ?? summary.status} · ${summary.total} 个文件`) : null,
          copy?.message ? h('div', { className: 'jc-copy-feedback' + (copy.kind === 'error' ? ' jc-error' : ''), role: copy.kind === 'error' ? 'alert' : 'status' }, copy.message) : null,
          error ? h('div', { className: 'jc-note jc-error', role: 'alert' }, error) : null,
          summary?.error ? h('div', { className: 'jc-note jc-error', role: 'alert' }, '快照未更新：' + summary.error) : null,
          summary?.warning ? h('div', { className: 'jc-note' }, summary.warning) : null,
          h('div', { className: 'jc-main' },
            h('div', { className: 'jc-files', 'aria-label': '变更文件列表' }, !summary || !summary.files.length ? h('div', { className: 'jc-empty' }, h(Icon, { size: 30 }), h('strong', null, emptyTitle),
              !turns.length ? 'Agent 开始新任务后，文件修改会在这里实时出现。' : summary?.status === 'running' ? 'Agent 修改文件后会自动显示，无需手动刷新。' : '可以切换轮次查看其他修改。') : summary.files.map(item => h(FileEntry, {
                key: summary.turn + ':' + item.id, id: diffId + item.id, file: item, sessionId, turn: summary.turn, revision: summary.revision, wrap,
                visible: tab.visible, generation, epochRef: requestGeneration, expanded: isExpanded(item.id), onToggle: toggleFile, actions: tab.actions,
              }))),
            summary && summary.total > summary.files.length ? h('div', { className: 'jc-note' }, `仅列出前 ${summary.files.length} 个文件；总计包含全部 ${summary.total} 个文件。`) : null),
          h('div', { className: 'jc-footer' }, h('span', { className: 'jc-footer-label', title: `重启 DSH 后记录清空；每会话保留最近 ${maxTurns} 轮。` }, h(Icon, { name: 'info', size: 12 }), '仅本次运行'), h('span', { className: 'jc-grow' }),
            summary?.officialSeq !== null && summary?.officialSeq !== undefined ? h('button', { className: 'jc-button', onClick: () => tab.actions.openResource(`dsh-resource://changes-review/session/${encodeURIComponent(sessionId)}/${summary.officialSeq}/${summary.turn}`) }, '官方轮次对比', h(Icon, { name: 'external-link', size: 11 })) : null));
      }
      function Body(props) { return h(Page, { ...props, key: props.sessionId }); }
      ctx.effect(() => ctx.sidebarRightTabs.register({ id: ID, kind: KIND, priority: 'extension', title: () => '变更',
        guide: [{ id: 'changes', order: 15, title: () => '变更', description: () => '实时查看本轮与历史轮次的文件修改', icon: Icon }] }));
      ctx.slots.inject('sidebar.right.pane.tab', () => ctx.slots.register({ name: 'sidebar.right.pane.tab', key: ID }, Body));
      ctx.slots.inject('sidebar.right.pane.tab.title', () => ctx.slots.register({ name: 'sidebar.right.pane.tab.title', key: ID },
        () => h('span', { className: 'jc-title' }, h(Icon, { size: 17 }), h('span', null, '变更'))));
      ctx.slots.inject('conversation.session.header.utilities', () => ctx.slots.register({ name: 'conversation.session.header.utilities', id: ID, order: 30 },
        () => h('button', { className: 'jc-open', title: '查看文件变更', 'aria-label': '查看文件变更', onClick: () => ctx.sidebarRight.openTab(KIND) }, h(Icon), '变更')));
    }
    return { apply, inject: ['slots', 'sidebarRightTabs', 'sidebarRight'] };
  }
});

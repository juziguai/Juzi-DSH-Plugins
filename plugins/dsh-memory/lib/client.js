window.__ModuleLoader__.load({
  id: '@juzi/dsh-memory',
  factory: require => {
    const React = require('react'), h = React.createElement, ID = '@juzi/dsh-memory', KIND = 'juzi-memory';
    const labels = { active: '已收录事实', candidate: '候选', episode: '已采集经历', superseded: '已纠正', deprecated: '已失效', consolidated: '已整理经历' };
    const errors = { memory_connection_failed: '无法连接本机记忆。请检查本地入口后重新连接。', capture_in_progress: '正在提交本轮记忆，请等待回执。', memory_startup_timeout: '连接启动超时，正常对话可以继续；请检查本地入口后重新连接。', project_not_bound: '项目尚未绑定，请在设置 → 记忆中选择当前会话并绑定项目。', connection_not_configured: '尚未配置连接，请在本地插件配置中设置 LocalMemory 入口和数据目录。', memory_timeout_or_cancelled: '记忆请求超时或已取消，正常对话可以继续。', memory_call_failed: '连接或记忆操作失败，请检查本地连接、数据库版本及宿主日志。', version_conflict: '目标版本已变化，请刷新详情后重新预览。', session_not_durable: '宿主未确认日志落盘，尚未采集；请检查会话存储后重试。', turn_binding_missing: '该轮没有可信项目绑定，不能猜测归属。', memory_operation_requires_active_turn: '记忆工具需要活动回合，请开始新一轮。', context_time_boundary_invalid: '记忆有效期信息不完整，请检查本地 Core 版本并重连。', context_expired_before_use: '准备请求时记忆已到期，本次不注入；下一请求重新选择。', batch_budget: '单次提炼预算已用完，可以续做。', evidence_not_current: '来源证据已失效，请核查原始经历。', evidence_requires_review: '来源证据需要本地审核。', retired_content_requires_explicit_correction: '对应事实已被纠正或遗忘，需要显式纠正。', schema_requires_explicit_migration: '数据库需要显式迁移，请先在副本验证并使用本地 CLI。' };
    const textError = error => errors[error?.message ?? error] ?? (error?.name === 'TimeoutError' ? '请求超时，请重试。' : String(error?.message ?? error));
    const css = `
.jm{--jm-text:var(--dsw-alias-label-primary,#25272c);--jm-muted:var(--dsw-alias-label-secondary,#858994);--jm-line:var(--dsw-alias-border-l2,#e7e9ed);--jm-bg:var(--dsw-alias-bg-layer-1,#fff);--jm-accent:var(--dsw-alias-brand-primary,#3c70d9);color:var(--jm-text);font-family:inherit;font-size:14px;line-height:1.6;min-width:0;box-sizing:border-box}.jm *{box-sizing:border-box}.jm button,.jm input,.jm select,.jm textarea{font:inherit;color:inherit}.jm button,.jm input,.jm select,.jm textarea{border:1px solid var(--jm-line);border-radius:7px;background:var(--jm-bg);padding:7px 10px}.jm button{cursor:pointer}.jm button:disabled{opacity:.5;cursor:default}.jm button:hover:not(:disabled){background:color-mix(in srgb,var(--jm-text) 5%,var(--jm-bg))}.jm :focus-visible{outline:2px solid var(--jm-accent);outline-offset:2px}.jm button[data-active=true]{color:var(--jm-accent);border-color:currentColor}.jm-page{height:100%;display:flex;flex-direction:column;background:var(--jm-bg);padding:28px 30px 0;overflow:hidden;container-type:inline-size}.jm h1{font-size:23px;line-height:1.4;margin:0;font-weight:600}.jm h2{font-size:17px;margin:0 0 12px;font-weight:600}.jm h3{font-size:14px;margin:18px 0 6px;font-weight:600}.jm-row{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.jm-grow{flex:1}.jm-muted{color:var(--jm-muted);font-size:12px}.jm-toolbar{margin:20px 0 16px;gap:8px}.jm-toolbar input{flex:1;min-width:160px}.jm-tabs{display:flex;gap:8px;padding-bottom:16px;flex-wrap:wrap}.jm-status{font-size:12px;color:var(--jm-muted);display:flex;align-items:center;gap:6px}.jm-dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:currentColor}.jm-workspace{display:grid;grid-template-columns:minmax(240px,34%) minmax(0,1fr);flex:1;min-height:0;border-top:1px solid var(--jm-line)}.jm-list{overflow:auto;border-right:1px solid var(--jm-line);padding:12px 12px 20px 0}.jm-item{display:block;width:100%;text-align:left!important;margin-bottom:8px;padding:12px!important}.jm-item strong{display:block;font-weight:500;font-size:14px;margin:4px 0}.jm-preview{font-size:12px;color:var(--jm-muted);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}.jm-badge{display:inline-flex;border-radius:4px;background:color-mix(in srgb,var(--jm-text) 5%,var(--jm-bg));padding:1px 6px;font-size:11px;color:var(--jm-muted)}.jm-detail{overflow:auto;padding:20px 0 30px 24px}.jm-detail pre{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit;margin:8px 0 16px}.jm-note{padding:12px;border:1px solid var(--jm-line);border-radius:8px;margin:10px 0;font-size:12px;overflow-wrap:anywhere}.jm-error{color:var(--dsw-alias-error-primary,#bd3947)}.jm-empty{padding:46px 20px;text-align:center;color:var(--jm-muted)}.jm-empty strong{display:block;color:var(--jm-text);font-weight:500;margin-bottom:6px}.jm-info{display:grid;grid-template-columns:70px 1fr;gap:5px 12px;font-size:12px;margin:12px 0}.jm-info dt{color:var(--jm-muted)}.jm-info dd{margin:0;overflow-wrap:anywhere}.jm-actions{margin:18px 0}.jm-edit textarea{display:block;width:100%;min-height:110px;margin:10px 0;resize:vertical}.jm-foot{border-top:1px solid var(--jm-line);padding:10px 0;font-size:11px;color:var(--jm-muted)}.jm-settings{max-width:760px;padding:8px 4px 24px}.jm-setting{padding:18px 0;border-bottom:1px solid var(--jm-line);display:flex;gap:20px;align-items:center;justify-content:space-between}.jm-setting input[type=checkbox]{width:18px;height:18px;accent-color:var(--jm-accent)}.jm-setting p{margin:2px 0 0;color:var(--jm-muted);font-size:12px}.jm-settings label{display:flex;flex-direction:column;gap:6px;margin:12px 0}.jm-settings input[type=number]{width:130px}.jm-side{padding:14px;overflow:auto;height:100%}.jm-side button{max-width:100%}.jm-side h3{margin-top:18px}.jm-side .jm-item{font-size:12px}.jm-icon{display:inline-flex;align-items:center;gap:7px}.jm-header-button{display:flex;align-items:center;gap:5px;border:0;background:transparent;color:inherit;padding:4px 8px;cursor:pointer;font:inherit;font-size:12px}.jm-settings code{font-size:11px;overflow-wrap:anywhere}.jm-review{border-top:1px solid var(--jm-line);padding:12px 0}.jm-toast{font-size:12px;padding:9px 0;color:var(--jm-muted)}
@container(max-width:650px){.jm-workspace{grid-template-columns:1fr;overflow:auto}.jm-list{max-height:260px;border-right:0;border-bottom:1px solid var(--jm-line)}.jm-detail{overflow:visible;padding:18px 0}.jm-page{padding:20px 16px 0}}`;
    function Icon() { return h('svg', { width: 18, height: 18, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.6, 'aria-hidden': true }, h('path', { d: 'M7 3h10a2 2 0 0 1 2 2v16l-7-4-7 4V5a2 2 0 0 1 2-2Z' }), h('path', { d: 'M9 8h6M9 11h6' })); }
    async function api(action, params = {}, signal, post = false) {
      const response = await fetch('api/juzi.memory.' + action + (post ? '' : '?' + new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== ''))), { method: post ? 'POST' : 'GET', body: post ? JSON.stringify(params) : undefined, headers: post ? { 'content-type': 'application/json' } : undefined, signal: AbortSignal.any([...(signal ? [signal] : []), AbortSignal.timeout(8000)]), credentials: 'same-origin', cache: 'no-store' });
      const value = await response.json(); if (!response.ok) throw Error(value.error ?? 'memory_call_failed'); return value;
    }
    function useRead(action, params, refresh = 0, enabled = true) {
      const [state, set] = React.useState({ loading: true }), key = action + ':' + JSON.stringify(params);
      React.useEffect(() => {
        if (!enabled) { set({ key, loading: false }); return; }
        const controller = new AbortController(); set(previous => previous.key === key ? { ...previous, loading: true } : { key, loading: true });
        api(action, params, controller.signal).then(value => { if (!controller.signal.aborted) set({ key, value, loading: false }); }, error => { if (!controller.signal.aborted) set({ key, error: textError(error), loading: false }); });
        return () => controller.abort();
      }, [action, key, refresh, enabled]); return state.key === key ? state : { loading: true };
    }
    const note = (text, error = false) => h('div', { className: 'jm-note' + (error ? ' jm-error' : ''), role: error ? 'alert' : 'status' }, text);
    function apply(ctx) {
      let view = { scope: 'global', id: null }, generation = 0;
      const listeners = new Set();
      const update = patch => { view = { ...view, ...patch }; listeners.forEach(fn => fn()); };
      const useView = () => React.useSyncExternalStore(fn => { listeners.add(fn); return () => listeners.delete(fn); }, () => view);
      ctx.effect(() => { const style = document.createElement('style'); style.textContent = css; document.head.appendChild(style); return () => style.remove(); });
      ctx.on('connection/reset', () => { generation++; update({ id: null }); });
      function SourceDetails({ source, scope }) {
        let evidence, error;
        try { evidence = source.evidence_json ? JSON.parse(source.evidence_json) : null; }
        catch { error = '证据元数据无法解析，请检查本地存储。'; }
        return h('div', { className: 'jm-note' }, h('strong', null, source.kind ?? '关联事件'), h('div', null, source.path ?? source.episode_id),
          h('div', null, '原始角色：' + (evidence?.role ?? '未标注')),
          evidence?.source ? h('div', null, '来源位置：' + (evidence.source.event_id ?? evidence.source.line ?? '见事件详情')) : null,
          source.quote ? h('pre', null, source.quote) : null,
          source.evidence_hash ? h('div', { className: 'jm-muted' }, '指纹：' + source.evidence_hash) : null,
          source.episode_id ? h('button', { onClick: () => update({ scope, id: source.episode_id }) }, '查看原始事件') : null, error ? note(error, true) : null);
      }
      function Edit({ detail, scope, onDone }) {
        const item = detail.item, version = detail.versions.at(-1)?.version;
        const [mode, setMode] = React.useState(null), [content, setContent] = React.useState(item.content), [preview, setPreview] = React.useState(null), [busy, setBusy] = React.useState(false), [error, setError] = React.useState(null);
        const requestId = React.useRef(crypto.randomUUID());
        async function submit(confirm) {
          setBusy(true); setError(null);
          try {
            const args = mode === 'correct' ? { scope, target_id: item.id, expected_version: version, content, dry_run: !confirm, request_id: requestId.current } : { scope, id: item.id, expected_version: version, confirm, request_id: requestId.current };
            const value = await api(mode, args, undefined, true);
            if (value.ok === false) throw Error(value.reason ?? 'memory_call_failed');
            if (!confirm) setPreview({ content, value });
            else { setMode(null); onDone(value.requires_review ? '已提交本地审核，尚未生效。请在本地 CLI 确认：' + value.review_id : '操作已提交。后续召回按最新有效事实选择；已发送内容和宿主历史仍保留。'); }
          } catch (e) { setError(textError(e)); } finally { setBusy(false); }
        }
        return h('div', { className: 'jm-edit' }, h('div', { className: 'jm-row jm-actions' }, h('button', { onClick: () => { setMode('correct'); setPreview(null); requestId.current = crypto.randomUUID(); } }, '纠正'), h('button', { onClick: () => { setMode('forget'); setPreview(null); requestId.current = crypto.randomUUID(); } }, '遗忘')),
          mode ? note(h(React.Fragment, null, h('strong', null, mode === 'correct' ? '纠正此记忆' : '遗忘此记忆'), h('p', null, `目标：${item.title} · ${scope} · 版本 ${version}`), '受保护内容需要本地审核；来源经历与历史版本继续保留。', mode === 'correct' ? h('textarea', { 'aria-label': '纠正内容', value: content, onChange: e => { setContent(e.target.value); setPreview(null); } }) : h('p', null, '生效后不再召回，后续请求更新插件快照；不会删除宿主聊天或撤回已发送内容。'),
            preview ? h('p', null, '预览完成，请确认目标、范围与修改内容。') : null,
            h('div', { className: 'jm-row' }, h('button', { disabled: busy, onClick: () => submit(false) }, '预览影响'), h('button', { disabled: busy || !preview || preview.content !== content, onClick: () => submit(true) }, busy ? '处理中…' : '确认提交'), h('button', { disabled: busy, onClick: () => setMode(null) }, '取消')))) : null,
          error ? note(error, true) : null);
      }
      function Detail({ scope, id, refresh, onDone }) {
        const state = useRead('get', { scope, id }, refresh, Boolean(id));
        if (!id) return h('div', { className: 'jm-empty' }, h('strong', null, '选择一条记忆'), '查看来源、版本、有效期和冲突。');
        if (state.loading) return note('正在读取证据详情…');
        if (state.error) return note(state.error, true);
        const detail = state.value; if (!detail?.ok) return note('该记忆已不可见，请刷新列表。');
        const item = detail.item, version = detail.versions?.at(-1)?.version;
        let label = labels[item.status] ?? item.status;
        if (item.status === 'active' && detail.owner_type === 'fact') {
          const now = Date.now();
          if (Date.parse(item.valid_to) <= now) label = '已到期';
          else if (Date.parse(item.valid_from) > now) label = '待生效';
        }
        return h(React.Fragment, null, h('span', { className: 'jm-badge' }, detail.owner_type === 'episode' ? '已采集经历' : label), h('h2', { style: { marginTop: 10 } }, item.title), h('pre', null, item.content),
          h('dl', { className: 'jm-info' }, h('dt', null, '范围'), h('dd', null, item.scope_id), h('dt', null, '版本'), h('dd', null, version ?? '事件证据'), h('dt', null, '信任'), h('dd', null, item.source_trust ?? '原始经历'), h('dt', null, '有效期'), h('dd', null, `${item.valid_from || '未设置'} → ${item.valid_to || '未设置'}`), h('dt', null, '标识'), h('dd', null, item.id)),
          h('h3', null, '来源与证据'), (detail.sources ?? []).length ? detail.sources.map((source, i) => h(SourceDetails, { source, scope, key: i })) : note('没有可用来源，不能凭引用存在判断结论已证实。'),
          detail.evidence ? h('div', { className: 'jm-note' }, h('div', null, '角色：' + (detail.evidence.role ?? '未标注')), h('div', null, '事件：' + (detail.evidence.source?.event_id ?? detail.evidence.source?.line ?? '未标注')), h('div', null, '调用：' + (detail.evidence.call_id ?? '无')), h('div', null, '验证状态：' + JSON.stringify(detail.evidence.outcome ?? {})), detail.evidence.truncated ? '此证据因预算截断，不能视为完整原文。' : null) : null,
          h('h3', null, '冲突与关联'), detail.related?.length ? detail.related.map((r, i) => h('div', { className: 'jm-note', key: i }, r.relation + ' · ' + r.status)) : h('div', { className: 'jm-muted' }, '无已记录的冲突关联'),
          detail.owner_type === 'fact' ? h(Edit, { key: item.id + ':' + version, detail, scope, onDone }) : null,
          item.status === 'candidate' ? note('候选尚未确认为有效事实，不进入自动注入。待审核请使用本地 CLI：review --scope ' + scope) : null);
      }
      function Main() {
        const current = useView(), [query, setQuery] = React.useState(''), [search, setSearch] = React.useState(''), [type, setType] = React.useState('active'), [refresh, setRefresh] = React.useState(0), [reviews, setReviews] = React.useState(false), [actionError, setActionError] = React.useState(null), [actionNotice, setActionNotice] = React.useState(null);
        const status = useRead('status', {}, refresh + generation), params = { scope: current.scope, query: search, ...(type === 'episode' ? { owner_type: 'episode' } : { owner_type: 'fact', status: type }), limit: 50 };
        const list = useRead('list', params, refresh + generation, status.value?.configured === true), queue = useRead('reviews', { scope: current.scope }, refresh, reviews);
        const title = current.scope === 'global' ? '全局' : '项目 · ' + current.scope.slice(8);
        return h('section', { className: 'jm jm-page', 'aria-label': '记忆管理' }, h('header', { className: 'jm-row' }, h(Icon), h('h1', null, '记忆'), h('span', { className: 'jm-grow' }), h('span', { className: 'jm-status' }, h('span', { className: 'jm-dot' }), list.value ? '已连接 · 本机' : list.loading ? '连接中…' : '未连接')),
          h('form', { className: 'jm-row jm-toolbar', onSubmit: e => { e.preventDefault(); setSearch(query); } }, h('select', { 'aria-label': '记忆范围', value: current.scope, onChange: e => update({ scope: e.target.value, id: null }) }, (status.value?.scopes ?? ['global']).map(scope => h('option', { key: scope, value: scope }, scope === 'global' ? '全局' : '项目 · ' + scope.slice(8)))), h('input', { 'aria-label': '搜索记忆', placeholder: '搜索当前范围的记忆', value: query, onChange: e => setQuery(e.target.value) }), h('button', { type: 'submit' }, '搜索'), h('button', { type: 'button', onClick: () => setRefresh(v => v + 1) }, '刷新'), status.value?.connection_error ? h('button', { type: 'button', onClick: async () => { try { await api('connect', {}, undefined, true); setActionError(null); } catch (e) { setActionError(textError(e)); } finally { setRefresh(v => v + 1); } } }, '重新连接') : null),
          h('div', { className: 'jm-row jm-tabs' }, ['active','candidate','episode'].map(key => h('button', { key, 'data-active': key === type, onClick: () => { setType(key); update({ id: null }); } }, labels[key])), h('span', { className: 'jm-grow' }), h('button', { onClick: () => setReviews(v => !v) }, reviews ? '收起待审核' : '查看待审核')),
          actionNotice?.scope === current.scope && actionNotice.id === current.id ? note(actionNotice.text) : null,
          actionError ? note(actionError, true) : status.error ? note(status.error, true) : status.value?.connection_error ? note(textError(status.value.connection_error), true) : status.value && !status.value.configured ? note(errors.connection_not_configured) : null,
          reviews ? h('div', { className: 'jm-review' }, h('strong', null, '待审核 · 仅查看'), note('本页不提供批准能力。请在本地 CLI 运行 review --scope ' + current.scope), queue.loading ? '读取中…' : queue.error ? note(queue.error, true) : queue.value?.items.length ? queue.value.items.map(r => h('div', { className: 'jm-muted', key: r.id }, r.kind + ' · ' + r.id)) : '当前范围无待审核项') : null,
          h('div', { className: 'jm-workspace' }, h('div', { className: 'jm-list', 'aria-label': '记忆列表' }, list.loading ? note('正在加载记忆…') : list.error ? note(list.error, true) : list.value?.items.length ? list.value.items.map(item => h('button', { className: 'jm-item', key: item.id, 'data-active': item.id === current.id, onClick: () => update({ id: item.id }) }, h('span', { className: 'jm-badge' }, labels[item.status] ?? (item.owner_type === 'episode' ? '已采集经历' : item.status)), h('strong', null, item.title), h('span', { className: 'jm-preview' }, item.preview))) : h('div', { className: 'jm-empty' }, h('strong', null, search ? '没有匹配的记忆' : '当前范围还没有此类记忆'), search ? '尝试其他关键词或范围。' : '绑定项目并启用采集后，经历和候选会显示在这里。'), list.value?.next_offset ? note('本页展示前50条，请使用搜索缩小范围。') : null), h('div', { className: 'jm-detail', 'aria-label': '记忆证据详情' }, h(Detail, { id: current.id, scope: current.scope, refresh, onDone: text => { setActionNotice({ scope: current.scope, id: current.id, text }); setRefresh(v => v + 1); } }))),
          h('footer', { className: 'jm-foot' }, `当前范围：${title} · 本地 SQLite · 候选需本地审核后进入自动注入`));
      }
      function Settings() {
        const [refresh, setRefresh] = React.useState(0), status = useRead('status', {}, refresh), [session, setSession] = React.useState(''), [project, setProject] = React.useState(''), [budget, setBudget] = React.useState(4000), [busy, setBusy] = React.useState(false), [result, setResult] = React.useState(null);
        React.useEffect(() => { if (status.value) setBudget(status.value.settings.budget); }, [status.value]);
        async function save(patch) { setBusy(true); setResult(null); try { await api('settings', patch, undefined, true); setRefresh(v => v + 1); setResult(patch.binding ? '绑定已保存；进行中的回合保持原范围，新绑定下一回合生效。' : '设置已保存；后续模型请求按新设置选择记忆。'); } catch (e) { setResult(textError(e)); } finally { setBusy(false); } }
        return h('section', { className: 'jm jm-settings', 'aria-label': '记忆设置' }, h('h2', null, '记忆'), status.loading ? note('读取设置…') : status.error ? note(status.error, true) : status.value ? h(React.Fragment, null,
          note(status.value.configured ? 'LocalMemory 连接入口已配置，使用官方 MCP stdio。' : errors.connection_not_configured),
          [['autoRecall','自动召回','新输入召回当前有效事实；每次请求检查修订。'],['autoCapture','自动采集','回合落盘后保留角色、工具结果和末尾纠正；候选不自动确认。'],['includeGlobal','同时读取全局偏好','项目请求可读取全局；不会授予项目写全局权限。']].map(([key, title, description]) => h('div', { className: 'jm-setting', key }, h('div', null, title, h('p', null, description)), h('input', { type: 'checkbox', role: 'switch', 'aria-label': title, checked: status.value.settings[key], disabled: busy, onChange: e => save({ [key]: e.target.checked }) }))),
          h('div', { className: 'jm-setting' }, h('div', null, '注入预算', h('p', null, '按字符计数，256–16000；无匹配返回空。')), h('div', { className: 'jm-row' }, h('input', { type: 'number', 'aria-label': '注入字符预算', min: 256, max: 16000, value: budget, onChange: e => setBudget(Number(e.target.value)) }), h('button', { disabled: busy, onClick: () => save({ budget }) }, '保存预算'))),
          h('h3', null, '项目绑定'), h('div', { className: 'jm-muted' }, '选择宿主已知的会话，将其工作目录绑定到稳定项目ID。同名目录不会自动共享；改绑下一回合生效。'),
          h('label', null, '会话', h('select', { 'aria-label': '待绑定会话', value: session, onChange: e => setSession(e.target.value) }, h('option', { value: '' }, '选择当前会话'), status.value.sessions.map(s => h('option', { key: s.id, value: s.id }, s.label || s.id)))),
          h('label', null, '稳定项目ID（或 global）', h('input', { 'aria-label': '稳定项目ID', placeholder: '例如 quartz；不要填路径', value: project, onChange: e => setProject(e.target.value) })), h('button', { disabled: busy || !session || !project, onClick: () => save({ binding: { session_id: session, project_id: project } }) }, '绑定所选会话'),
          status.value.projects.map((p, i) => h('div', { className: 'jm-note', key: i }, `${p.label} → project:${p.project_id}`)),
          h('h3', null, '纠正、遗忘与审核'), h('p', { className: 'jm-muted' }, '管理页提供预览及提交；受保护内容仍需本地 CLI 审核。清理插件快照不会撤回已发送内容，也不会删除宿主聊天。')) : null,
          result ? note(result) : null);
      }
      function captureLabel(turn) {
        switch (turn.capture) {
          case 'committed':
            return turn.receipts?.some(receipt => receipt.derivation?.status === 'complete_with_rejections')
              ? '证据已保存，提炼结束（有拒绝项）' : '证据已保存，提炼已完成';
          case 'partial': return '证据已保存，提炼待续做';
          case 'failed': return '采集或提炼失败，可重试';
          case 'disabled': return '本轮未启用自动采集';
          case 'queued': return '等待保存证据';
          case 'capturing': return '正在保存证据和提炼进度';
          default: return '待回合结束';
        }
      }
      function Side({ sessionId, useTabInfo }) {
        const { tab } = useTabInfo(), [refresh, setRefresh] = React.useState(0);
        const status = useRead('status', { session_id: sessionId }, refresh, tab.visible);
        const [retry, setRetry] = React.useState(null);
        React.useEffect(() => {
          if (!tab.visible) return;
          const timer = setInterval(() => setRefresh(v => v + 1), 2000);
          return () => clearInterval(timer);
        }, [tab.visible, sessionId]);
        const value = status.value, turn = value?.turns[0];
        const pending = retry?.sessionId === sessionId && retry?.turn === turn?.turn ? retry : null;
        const current = value?.current_injection;
        const history = turn?.injection;
        const jump = item => {
          update({ scope: item?.scope_id ?? value.scope_id ?? 'global', id: item?.id ?? null });
          ctx.layout.selectPanel(ID);
        };
        const links = snapshot => snapshot.items.map(item => h('button', { className: 'jm-item', key: item.id, onClick: () => jump(item) },
          h('strong', null, item.title), h('span', { className: 'jm-muted' }, item.scope_id + ' · v' + item.version)));
        async function retryCapture() {
          const target = { sessionId, turn: turn.turn };
          setRetry({ ...target, busy: true });
          try {
            await api('capture', { session_id: sessionId, turn: turn.turn }, undefined, true);
            setRetry(null);
          } catch (error) {
            setRetry({ ...target, error: textError(error) });
          } finally {
            setRefresh(v => v + 1);
          }
        }
        return h('section', { className: 'jm jm-side', 'aria-label': '本轮记忆' }, h('h2', null, '本轮记忆'),
          status.loading && !value ? note('读取本轮记录…') : status.error ? note(status.error, true) : value ? h(React.Fragment, null,
            note(value.scope_id ? '当前范围：' + value.scope_id : errors[value.binding_error] ?? value.binding_error),
            value.next_scope_id ? note('下一回合生效：' + value.next_scope_id) : null,
            value.recall_error ? note(textError(value.recall_error), true) : null,
            h('h3', null, '当前可用快照'),
            current?.items.length ? links(current) : h('div', { className: 'jm-muted' }, '当前没有可用的注入快照。'),
            h('h3', null, '本轮最近一次注入'),
            history?.items.length ? history.message_id === current?.message_id
              ? h('div', { className: 'jm-muted' }, '与当前快照相同。') : links(history)
              : h('div', { className: 'jm-muted' }, '本轮尚无已接受的记忆注入。'),
            h('h3', null, '采集与候选'),
            turn ? h(React.Fragment, null,
              h('div', { className: 'jm-muted' }, '第 ' + turn.turn + ' 轮 · ' + turn.scope_id + ' · ' + captureLabel(turn)),
              turn.error ? note(textError(turn.error), true) : null,
              (turn.receipts ?? []).map((receipt, i) => {
                const { candidates, derivation } = receipt;
                const issues = new Map();
                for (const {status, reason} of derivation?.items ?? []) {
                  if (status !== 'pending' && status !== 'rejected') continue;
                  const key = (status === 'pending' ? '待提炼：' : '已拒绝：') + textError(reason);
                  issues.set(key, (issues.get(key) ?? 0) + 1);
                }
                return h('div', { className: 'jm-note', key: i },
                  receipt.evidence.length + ' 条事件证据 · ' + (candidates?.candidates ?? 0) + ' 个候选 · ' + (candidates?.duplicates ?? 0) + ' 个复用 · ' + (candidates?.pending ?? 0) + ' 个待提炼 · ' + (candidates?.rejected ?? 0) + ' 个拒绝',
                  receipt.derivation_resumed ? h('div', { className: 'jm-muted' }, '已续做未完成提炼。证据已复用。') : null,
                  [...issues].map(([label, count]) => h('div', { className: 'jm-muted', key: label }, label + '（' + count + '）')));
              }),
              ['failed','partial'].includes(turn.capture)
                ? h('button', { onClick: retryCapture, disabled: pending?.busy }, pending?.busy ? '正在提交…' : turn.capture === 'partial' ? '续做本轮提炼' : '重试本轮采集与提炼')
                : null,
              pending?.error ? note(pending.error, true) : null)
              : h('div', { className: 'jm-muted' }, '开始新任务后显示回合证据。'),
            h('div', { className: 'jm-actions' }, h('button', { onClick: () => jump() }, '打开记忆管理')),
            note('每次模型请求前重新校验快照。历史记录表示宿主接受了注入。已发送内容和聊天历史会保留。'))
            : null);
      }
      ctx.slots.inject('main', () => ctx.slots.register({ name: 'main', key: ID }, Main));
      ctx.slots.inject('sidebar.panellist', () => ctx.slots.register({ name: 'sidebar.panellist', id: ID, order: 11, label: () => '记忆' }, Icon));
      ctx.slots.inject('settings.section', () => ctx.slots.register({ name: 'settings.section', id: ID, order: 35, label: () => '记忆' }, Settings));
      ctx.effect(() => ctx.sidebarRightTabs.register({ id: ID, kind: KIND, priority: 'extension', title: () => '记忆', guide: [{ id: 'memory', order: 16, title: () => '记忆', description: () => '本轮注入、证据采集与候选', icon: Icon }] }));
      ctx.slots.inject('sidebar.right.pane.tab', () => ctx.slots.register({ name: 'sidebar.right.pane.tab', key: ID }, Side));
      ctx.slots.inject('sidebar.right.pane.tab.title', () => ctx.slots.register({ name: 'sidebar.right.pane.tab.title', key: ID }, () => h('span', { className: 'jm-icon' }, h(Icon), '记忆')));
      ctx.slots.inject('conversation.session.header.utilities', () => ctx.slots.register({ name: 'conversation.session.header.utilities', id: ID, order: 31 }, () => h('button', { className: 'jm-header-button', onClick: () => ctx.sidebarRight.openTab(KIND), 'aria-label': '查看本轮记忆' }, h(Icon), '记忆')));
    }
    return { apply, inject: ['slots', 'layout', 'sidebarRightTabs', 'sidebarRight'] };
  }
});

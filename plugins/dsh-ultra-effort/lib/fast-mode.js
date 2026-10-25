import { FAST_PATH, FAST_PROTOCOL, validSessionId, eligibleSession, createTurnState } from './fast-state.js';
import { FAST_POLICY } from './fast-policy.js';

export function applyFastMode(ctx, config) {
  const namespace = ctx.fiber.entry?.options.id;
  ctx.inject(['settings'], scope => {
    scope.effect(() => scope.settings.configure({ auto: false }, ctx.fiber));
  });
  ctx.inject(['settings', 'sessions', 'systemPrompt', 'connection'], scope => {
    // Volatile Config fields are official references; read their value at the turn boundary.
    const turns = createTurnState(() => config.fastSessions.get());
    scope.effect(() => () => turns.clear());
    scope.on('session/event', (session, event) => {
      if (event.type === 'turn/start') turns.start(session, event.data.turn);
      if (event.type === 'turn/end') turns.end(session, event.data.turn);
    });
    scope.on('session/disposed', session => turns.forget(session));
    scope.effect(() => scope.systemPrompt.section({
      name: 'juzi-ultra:fast-execution', order: 85, interpolate: false,
      text(context) {
        const agent = context.agent;
        // DSH assembleContextFor sets scope=agent. Identity prevents foreign scopes leaking policy.
        if (!agent || context.scope !== agent || scope.sessions.get(agent.session?.id) !== agent.session) return '';
        return turns.get(agent.session)?.enabled ? FAST_POLICY : '';
      },
    }));
    scope.connection.fetch.register({
      path: FAST_PATH, methods: ['GET'], requestBody: 'buffered',
      fetch(request) {
        const id = new URL(request.url).searchParams.get('sessionId');
        const json = (value, status = 200) => Response.json(value, { status, headers: { 'cache-control': 'no-store' } });
        if (!validSessionId(id)) return json({ reason: 'session' }, 400);
        const session = scope.sessions.get(id);
        if (!eligibleSession(session)) return json({ reason: 'session' }, 404);
        const descriptor = scope.settings.describe({ redactSecrets: true }).find(row => row.ns === namespace);
        if (!descriptor || descriptor.applies !== 'live') return json({ reason: 'settings' }, 503);
        return json({ protocol: FAST_PROTOCOL, namespace, ready: true, writable: scope.settings.writable,
          idle: !turns.get(session), boundary: 'next-turn' });
      },
    });
  });
}

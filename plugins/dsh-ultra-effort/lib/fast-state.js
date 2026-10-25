export const FAST_PROTOCOL = 1;
export const FAST_PATH = '/api/juzi.ultra.capabilities';

export const validSessionId = id => typeof id === 'string' && id.length > 0 && id.length <= 200
  && !/[\u0000-\u001f]/.test(id) && !['__proto__', 'prototype', 'constructor'].includes(id);
export const eligibleSession = session => !!session && validSessionId(session.id)
  && session.header.origin !== 'subagent' && !(session.header.delegationDepth > 0);
export const fastEnabled = (preferences, id) => validSessionId(id)
  && Object.hasOwn(preferences, id) && preferences[id] === true;

export function createTurnState(readPreferences) {
  const turns = new Map();
  return {
    start(session, turn) {
      if (eligibleSession(session) && Number.isSafeInteger(turn) && turn > 0) {
        turns.set(session.id, { session, turn, enabled: fastEnabled(readPreferences(), session.id) });
      }
    },
    end(session, turn) {
      const current = turns.get(session.id);
      if (current?.session === session && current.turn === turn) turns.delete(session.id);
    },
    forget(session) { if (turns.get(session.id)?.session === session) turns.delete(session.id); },
    get(session) { const current = turns.get(session?.id); return current?.session === session ? current : undefined; },
    clear() { turns.clear(); },
  };
}

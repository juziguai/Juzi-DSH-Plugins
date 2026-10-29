import { attachLayoutMemory } from '../lib/memory.js';

export const inject = ['slots'];
export function apply(ctx) {
  ctx.effect(() => {
    const messages = {
      incompatible: '当前宿主布局接口不兼容，已停止接管宽度。',
      storage: '布局偏好存储不可用，已停止记忆宽度。',
      'invalid-record': '布局偏好记录无效，已保留原记录并停止接管宽度。',
    };
    const warn = code => ctx.logger.warn(`layout-memory: ${messages[code] ?? messages.incompatible}`);
    let storage;
    try { storage = window.localStorage; } catch { warn('storage'); return; }
    return attachLayoutMemory({ slots: ctx.slots, storage, events: window, warn });
  });
}

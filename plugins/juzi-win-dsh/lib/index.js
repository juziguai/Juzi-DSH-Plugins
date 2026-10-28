import * as mcpClient from '@deepseek-ai/dsh-mcp-client';
import { createConfig } from './config.js';

export const name = 'juzi-win-dsh';
export const inject = ['tools'];

const WRITE_TOOLS = new Set([
  'input_batch', 'click', 'scroll', 'type_text', 'press_keys', 'hover', 'drag', 'launch_app',
]);

function isWriteInvocation(publicName, args) {
  const prefix = 'mcp__win__';
  if (typeof publicName !== 'string' || !publicName.startsWith(prefix)) return false;
  const raw = publicName.slice(prefix.length);
  if (WRITE_TOOLS.has(raw)) return true;
  if (raw === 'manage_window') return typeof args.action === 'string' && args.action !== 'get_work_area';
  if (raw === 'clipboard') return ['set', 'clear', 'restore'].includes(args.action);
  if (raw === 'system') {
    const hasWrite = key => args[key] !== undefined && args[key] !== null;
    return hasWrite('brightness') || hasWrite('volume') || hasWrite('mute') || args.lock === true;
  }
  return false;
}

export function apply(ctx, config) {
  // 宿主有 approval seam 且策略为 ask 时，给所有电脑控制写操作加一层原生审批。
  // 策略为 never（本机 danger-full-access）时不添加 ask，保留服务内 confirm_token 两阶段协议；
  // 此时服务端无法证明 token 经人工批准，README 已写明该边界。
  ctx.on('tools/pre-execute', async (exec, next) => {
    const args = exec.arguments && typeof exec.arguments === 'object' ? exec.arguments : {};
    if (!isWriteInvocation(exec.name, args)) return next();
    const approval = typeof ctx.get === 'function' ? ctx.get('approval') : ctx.approval;
    const session = exec.agent?.session;
    if (!approval || !session || typeof approval.overrideOf !== 'function') return next();
    let policy;
    try {
      policy = approval.overrideOf(session);
    } catch {
      return next();
    }
    if (policy === 'never') return next();
    const downstream = await next();
    if (downstream.kind !== 'allow') return downstream;
    return { kind: 'ask', reason: `电脑控制写操作需要宿主批准：${exec.name}` };
  });

  return ctx.plugin(mcpClient, createConfig(config));
}

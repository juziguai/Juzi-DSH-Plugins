import z from '@deepseek-ai/schemastery';
import { applyFastMode } from './fast-mode.js';

export const Config = z.object({
  fastSessions: z.dict(z.boolean()).default({}).volatile(),
});

// Missing fast-execution services must not park Ultra's existing model UI.
export function apply(ctx, config) { applyFastMode(ctx, config); }

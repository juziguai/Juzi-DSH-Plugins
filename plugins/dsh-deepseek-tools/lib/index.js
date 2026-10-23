import * as mcpClient from '@deepseek-ai/dsh-mcp-client';
import { createConfig } from './config.js';

export const name = 'juzi-deepseek-tools';
export const inject = ['tools'];

export function apply(ctx, config) {
  return ctx.plugin(mcpClient, createConfig(config));
}

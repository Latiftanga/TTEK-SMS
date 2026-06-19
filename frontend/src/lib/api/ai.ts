import { api } from './client';

export type AiProvider = 'GEMINI' | 'GROQ' | 'ANTHROPIC' | 'OPENAI';

export interface AiProviderInfo {
  provider: AiProvider;
  name: string;
  description: string;
  free_tier: string | null;
  default_model: string;
  docs_url: string;
}

export interface AiConfigRead {
  id: string;
  provider: AiProvider;
  model: string | null;
  daily_limit_per_teacher: number;
  is_active: boolean;
  created_at: string;
}

export interface AiConfigCreate {
  provider: AiProvider;
  api_key: string;
  model?: string;
  daily_limit_per_teacher?: number;
}

export interface AiTestResult {
  provider: AiProvider;
  ok: boolean;
  message: string;
}

export const listAiProviders = (): Promise<AiProviderInfo[]> =>
  api.get('/ai/providers').then(r => r.data);

export const listAiConfigs = (): Promise<AiConfigRead[]> =>
  api.get('/ai/configs').then(r => r.data);

export const saveAiConfig = (data: AiConfigCreate): Promise<AiConfigRead> =>
  api.post('/ai/configs', data).then(r => r.data);

export const activateAiProvider = (provider: AiProvider): Promise<AiConfigRead> =>
  api.post('/ai/configs/activate', { provider }).then(r => r.data);

export const testAiProvider = (): Promise<AiTestResult> =>
  api.post('/ai/configs/test').then(r => r.data);

export const deleteAiConfig = (provider: AiProvider): Promise<void> =>
  api.delete(`/ai/configs/${provider}`).then(r => r.data);

import client from './client';

export type SmsProvider = 'AFRICAS_TALKING' | 'HUBTEL' | 'ARKESEL' | 'WIGAL' | 'TWILIO';

export interface SmsConfig {
  id: string;
  provider: SmsProvider;
  sender_id: string;
  is_active: boolean;
}

export interface SmsConfigPayload {
  provider: SmsProvider;
  api_key: string;
  api_secret?: string;
  sender_id: string;
}

export interface SmsLog {
  id: string;
  provider: SmsProvider;
  recipient: string;
  message: string;
  status: 'SENT' | 'FAILED';
  error_message: string | null;
  entity_type: string | null;
  sent_at: string;
}

export async function listSmsConfigs(): Promise<SmsConfig[]> {
  const { data } = await client.get<SmsConfig[]>('/sms/configs');
  return data;
}

export async function upsertSmsConfig(payload: SmsConfigPayload): Promise<SmsConfig> {
  const { data } = await client.post<SmsConfig>('/sms/configs', payload);
  return data;
}

export async function activateSmsProvider(provider: SmsProvider): Promise<SmsConfig> {
  const { data } = await client.post<SmsConfig>('/sms/configs/activate', { provider });
  return data;
}

export async function deleteSmsConfig(provider: SmsProvider): Promise<void> {
  await client.delete(`/sms/configs/${provider}`);
}

export async function listSmsLogs(limit = 100, offset = 0): Promise<SmsLog[]> {
  const { data } = await client.get<SmsLog[]>('/sms/logs', { params: { limit, offset } });
  return data;
}

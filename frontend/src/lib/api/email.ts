import client from './client';

export type EmailProvider = 'SMTP' | 'SENDGRID' | 'MAILGUN' | 'BREVO';

export interface EmailConfig {
  id: string;
  provider: EmailProvider;
  host: string | null;
  port: number | null;
  from_name: string;
  from_address: string;
  use_tls: boolean;
  is_active: boolean;
}

export interface EmailConfigPayload {
  provider: EmailProvider;
  host?: string;
  port?: number;
  username: string;
  password?: string;
  from_name: string;
  from_address: string;
  use_tls?: boolean;
}

export interface EmailLog {
  id: string;
  provider: EmailProvider;
  recipient: string;
  subject: string;
  status: 'SENT' | 'FAILED';
  error_message: string | null;
  entity_type: string | null;
  sent_at: string;
}

export async function listEmailConfigs(): Promise<EmailConfig[]> {
  const { data } = await client.get<EmailConfig[]>('/email/configs');
  return data;
}

export async function upsertEmailConfig(payload: EmailConfigPayload): Promise<EmailConfig> {
  const { data } = await client.post<EmailConfig>('/email/configs', payload);
  return data;
}

export async function activateEmailConfig(config_id: string): Promise<EmailConfig> {
  const { data } = await client.post<EmailConfig>('/email/configs/activate', { config_id });
  return data;
}

export async function deleteEmailConfig(config_id: string): Promise<void> {
  await client.delete(`/email/configs/${config_id}`);
}

export async function listEmailLogs(limit = 100, offset = 0): Promise<EmailLog[]> {
  const { data } = await client.get<EmailLog[]>('/email/logs', { params: { limit, offset } });
  return data;
}

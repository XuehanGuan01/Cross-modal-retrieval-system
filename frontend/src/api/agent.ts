import axios from 'axios';
import type { ImageResult } from './search';

const client = axios.create({
  baseURL: '/api/agent',
  timeout: 60000,
});

export interface AgentChatRequest {
  message: string;
  session_id?: string;
  domain?: string;
}

export interface AgentChatResponse {
  session_id: string;
  state: string;
  reply: string;
  results: ImageResult[];
  reasoning_steps: string[];
  suggestions: string[];
  is_low_confidence: boolean;
  domain: string;
}

export async function createSession(domain = 'auto'): Promise<{ session_id: string; domain: string }> {
  const { data } = await client.post('/session/new', null, { params: { domain } });
  return data;
}

export async function sendMessage(req: AgentChatRequest): Promise<AgentChatResponse> {
  const { data } = await client.post<AgentChatResponse>('/chat', req);
  return data;
}

export async function deleteSession(sessionId: string): Promise<void> {
  await client.delete(`/session/${sessionId}`);
}

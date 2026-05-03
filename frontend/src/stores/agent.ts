import { defineStore } from 'pinia';
import type { ImageResult } from '@/api/search';
import { sendMessage, createSession, deleteSession } from '@/api/agent';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  image?: File;
  imagePreviewUrl?: string;
  timestamp: string;
  reasoningSteps?: string[];
  results?: ImageResult[];
}

interface AgentState {
  sessionId: string | null;
  messages: ChatMessage[];
  currentResults: ImageResult[];
  top5Results: ImageResult[];
  loading: boolean;
  reasoning: string;
  suggestions: string[];
  isLowConfidence: boolean;
}

let msgCounter = 0;
function nextId(): string {
  return `msg_${Date.now()}_${++msgCounter}`;
}

export const useAgentStore = defineStore('agent', {
  state: (): AgentState => ({
    sessionId: null,
    messages: [],
    currentResults: [],
    top5Results: [],
    loading: false,
    reasoning: '',
    suggestions: [],
    isLowConfidence: false,
  }),
  getters: {
    lastAssistantMessage(): ChatMessage | null {
      for (let i = this.messages.length - 1; i >= 0; i--) {
        if (this.messages[i].role === 'assistant') return this.messages[i];
      }
      return null;
    },
    hasResults(): boolean {
      return this.currentResults.length > 0;
    },
  },
  actions: {
    async initSession(domain = 'auto') {
      try {
        const res = await createSession(domain);
        this.sessionId = res.session_id;
      } catch (e) {
        console.error('创建会话失败:', e);
      }
    },
    addUserMessage(content: string, image?: File) {
      const msg: ChatMessage = {
        id: nextId(),
        role: 'user',
        content,
        image,
        imagePreviewUrl: image ? URL.createObjectURL(image) : undefined,
        timestamp: new Date().toLocaleString(),
      };
      this.messages.push(msg);
    },
    addAssistantMessage(
      content: string,
      results?: ImageResult[],
      reasoningSteps?: string[],
    ) {
      const msg: ChatMessage = {
        id: nextId(),
        role: 'assistant',
        content,
        results,
        reasoningSteps,
        timestamp: new Date().toLocaleString(),
      };
      this.messages.push(msg);
      if (results) {
        this.currentResults = results;
        this.top5Results = results.slice(0, 5);
      }
    },
    async sendMessage(text: string, domain: string, image?: File) {
      this.addUserMessage(text, image);
      this.loading = true;
      this.reasoning = '';
      this.suggestions = [];
      this.isLowConfidence = false;

      try {
        const res = await sendMessage({
          message: text,
          session_id: this.sessionId ?? undefined,
          domain,
        });

        this.sessionId = res.session_id;
        this.suggestions = res.suggestions;
        this.isLowConfidence = res.is_low_confidence;

        this.addAssistantMessage(
          res.reply,
          res.results,
          res.reasoning_steps,
        );
      } catch (e: any) {
        this.addAssistantMessage(
          `抱歉，请求失败：${e?.message ?? '未知错误'}`,
          [],
          ['API请求失败'],
        );
      } finally {
        this.loading = false;
      }
    },
    setLoading(val: boolean) {
      this.loading = val;
    },
    setReasoning(val: string) {
      this.reasoning = val;
    },
    async clearSession() {
      if (this.sessionId) {
        try {
          await deleteSession(this.sessionId);
        } catch (e) {
          // ignore
        }
      }
      this.sessionId = null;
      this.messages = [];
      this.currentResults = [];
      this.top5Results = [];
      this.reasoning = '';
      this.suggestions = [];
      this.isLowConfidence = false;
    },
  },
});

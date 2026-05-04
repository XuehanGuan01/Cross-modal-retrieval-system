import { defineStore } from 'pinia';
import type { ImageResult } from '@/api/search';
import { sendMessage, createSession, deleteSession, educateResult } from '@/api/agent';

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

interface EducateData {
  knowledgeText: string;
  subject: string;
  scientificName: string;
  similarImages: ImageResult[];
  mainImage: string;
  domain: string;
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
  progressTrail: string[];
  currentProgress: string;
  educateData: EducateData | null;
  educateLoading: boolean;
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
    progressTrail: [],
    currentProgress: '',
    educateData: null,
    educateLoading: false,
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
    startProgressCycle() {
      const phrases = [
        '正在理解你的需求...',
        '正在分析特征...',
        '正在检索图片库...',
        '正在匹配最佳结果...',
        '马上就好...',
      ];
      let i = 0;
      this.currentProgress = phrases[0];
      const timer = setInterval(() => {
        i = (i + 1) % phrases.length;
        this.currentProgress = phrases[i];
      }, 1200);
      // 存储timer以便后续清除
      (this as any)._progressTimer = timer;
    },
    stopProgressCycle() {
      const timer = (this as any)._progressTimer;
      if (timer) {
        clearInterval(timer);
        (this as any)._progressTimer = null;
      }
    },
    async sendMessage(text: string, domain: string, image?: File) {
      this.addUserMessage(text, image);
      this.loading = true;
      this.reasoning = '';
      this.suggestions = [];
      this.isLowConfidence = false;
      this.progressTrail = [];
      this.startProgressCycle();

      try {
        const res = await sendMessage({
          message: text,
          session_id: this.sessionId ?? undefined,
          domain,
        });

        this.sessionId = res.session_id;
        this.suggestions = res.suggestions;
        this.isLowConfidence = res.is_low_confidence;
        this.progressTrail = res.progress_trail || [];

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
        this.stopProgressCycle();
      }
    },
    async educateResult(resultIndex: number) {
      if (!this.sessionId) return;
      this.educateLoading = true;
      try {
        const res = await educateResult(this.sessionId, resultIndex);
        this.educateData = {
          knowledgeText: res.knowledge_text,
          subject: res.subject,
          scientificName: res.scientific_name,
          similarImages: res.similar_images,
          mainImage: res.main_image,
          domain: res.domain,
        };
      } catch (e: any) {
        console.error('科普请求失败:', e);
      } finally {
        this.educateLoading = false;
      }
    },
    clearEducateData() {
      this.educateData = null;
    },
    setLoading(val: boolean) {
      this.loading = val;
    },
    async clearSession() {
      if (this.sessionId) {
        try { await deleteSession(this.sessionId); } catch (e) { /* ignore */ }
      }
      this.sessionId = null;
      this.messages = [];
      this.currentResults = [];
      this.top5Results = [];
      this.reasoning = '';
      this.suggestions = [];
      this.isLowConfidence = false;
      this.progressTrail = [];
      this.educateData = null;
    },
  },
});

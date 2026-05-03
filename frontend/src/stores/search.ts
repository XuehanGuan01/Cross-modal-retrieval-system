import { defineStore } from 'pinia';
import type { ImageResult, TextResult, DomainInfo } from '@/api/search';
import { searchTextToImage, searchImageToText, fetchDomains } from '@/api/search';

export type SearchMode = 'text-to-image' | 'image-to-text';

interface HistoryItem {
  type: SearchMode;
  query: string;
  time: string;
}

interface SearchState {
  mode: SearchMode;
  queryText: string;
  lastImageFileName: string | null;
  imageResults: ImageResult[];
  textResults: TextResult[];
  loading: boolean;
  error: string | null;
  history: HistoryItem[];
  currentDomain: string;
  domains: DomainInfo[];
  currentDomainDescription: string;
}

export const useSearchStore = defineStore('search', {
  state: (): SearchState => ({
    mode: 'text-to-image',
    queryText: '',
    lastImageFileName: null,
    imageResults: [],
    textResults: [],
    loading: false,
    error: null,
    history: [],
    currentDomain: 'auto',
    domains: [],
    currentDomainDescription: '',
  }),
  getters: {
    currentDomainInfo(): DomainInfo | undefined {
      return this.domains.find((d) => d.name === this.currentDomain);
    },
  },
  actions: {
    setMode(mode: SearchMode) {
      this.mode = mode;
      this.error = null;
    },
    setQueryText(text: string) {
      this.queryText = text;
    },
    setDomain(domain: string) {
      this.currentDomain = domain;
      this.error = null;
    },
    async loadDomains() {
      try {
        this.domains = await fetchDomains();
        const info = this.domains.find((d) => d.name === this.currentDomain);
        this.currentDomainDescription = info?.description ?? '';
      } catch (e: any) {
        console.error('加载领域列表失败:', e);
      }
    },
    async searchByText() {
      if (!this.queryText.trim()) return;
      this.loading = true;
      this.error = null;
      try {
        const res = await searchTextToImage(
          this.queryText.trim(),
          50,
          this.currentDomain,
        );
        this.imageResults = res.results;
        this.textResults = [];
        this.history.unshift({
          type: 'text-to-image',
          query: `[${this.currentDomain}] ${this.queryText.trim()}`,
          time: new Date().toLocaleString(),
        });
      } catch (e: any) {
        this.error = e?.message ?? '搜索失败，请稍后重试';
      } finally {
        this.loading = false;
      }
    },
    async searchByImage(file: File) {
      this.loading = true;
      this.error = null;
      this.lastImageFileName = file.name;
      try {
        const res = await searchImageToText(file, 5, this.currentDomain);
        this.textResults = res.results;
        this.imageResults = [];
        this.history.unshift({
          type: 'image-to-text',
          query: file.name,
          time: new Date().toLocaleString(),
        });
      } catch (e: any) {
        this.error = e?.message ?? '搜索失败，请稍后重试';
      } finally {
        this.loading = false;
      }
    },
    clearResults() {
      this.imageResults = [];
      this.textResults = [];
      this.error = null;
    },
  },
});

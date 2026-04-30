import { defineStore } from 'pinia';
import type { ImageResult, TextResult } from '@/api/search';
import { searchTextToImage, searchImageToText } from '@/api/search';

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
    history: []
  }),
  actions: {
    setMode(mode: SearchMode) {
      this.mode = mode;
      this.error = null;
    },
    setQueryText(text: string) {
      this.queryText = text;
    },
    async searchByText() {
      if (!this.queryText.trim()) return;
      this.loading = true;
      this.error = null;
      try {
        const res = await searchTextToImage(this.queryText.trim());
        this.imageResults = res.results;
        this.textResults = [];
        this.history.unshift({
          type: 'text-to-image',
          query: this.queryText.trim(),
          time: new Date().toLocaleString()
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
        const res = await searchImageToText(file, 5);
        this.textResults = res.results;
        this.imageResults = [];
        this.history.unshift({
          type: 'image-to-text',
          query: file.name,
          time: new Date().toLocaleString()
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
    }
  }
});


import axios from 'axios';

// ---------- 类型定义 ----------

export interface ImageResult {
  image_url: string;
  score: number;
  meta?: Record<string, unknown>;
}

export interface TextResult {
  text: string;
  score: number;
  meta?: Record<string, unknown>;
}

export interface TextToImageResponse {
  results: ImageResult[];
  domain?: string;
}

export interface ImageToTextResponse {
  results: TextResult[];
  domain?: string;
}

export interface DomainInfo {
  name: string;
  description: string;
  image_count: number;
  gallery_style: string;
}

// ---------- 创建 axios 实例 ----------

const client = axios.create({
  baseURL: '/api',
  timeout: 30000,
});

// ---------- 功能函数 ----------

export async function fetchDomains(): Promise<DomainInfo[]> {
  const { data } = await client.get<DomainInfo[]>('/domains');
  return data;
}

export async function searchTextToImage(query: string, topK = 50, domain = 'auto') {
  const { data } = await client.post<TextToImageResponse>('/search/text', {
    query,
    top_k: topK,
    domain,
  });
  return data;
}

export async function searchImageToText(file: File, topK = 5, domain = 'auto') {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('top_k', String(topK));
  formData.append('domain', domain);

  const { data } = await client.post<ImageToTextResponse>('/search/image', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return data;
}

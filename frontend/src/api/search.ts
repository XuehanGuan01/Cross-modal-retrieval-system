// 导入 axios 库，用于发送 HTTP 请求
import axios from 'axios';

// ---------- 类型定义 ----------

// 定义图片搜索结果的数据结构
export interface ImageResult {
  image_url: string;          // 图片的 URL 地址
  score: number;              // 相似度分数（越高表示越匹配）
  meta?: Record<string, unknown>;  // 可选的元数据，例如图片的其他属性
}

// 定义文本搜索结果的数据结构
export interface TextResult {
  text: string;               // 匹配到的文本内容
  score: number;              // 相似度分数
  meta?: Record<string, unknown>;  // 可选的元数据
}

// 定义“文本搜图片”接口返回的整体结构
export interface TextToImageResponse {
  results: ImageResult[];     // 返回一组图片结果
}

// 定义“图片搜文本”接口返回的整体结构
export interface ImageToTextResponse {
  results: TextResult[];      // 返回一组文本结果
}

// ---------- 创建 axios 实例 ----------

// 创建一个配置好的 axios 实例，避免重复写配置
const client = axios.create({
  baseURL: '/api',            // 所有请求都会以 '/api' 开头
  timeout: 30000              // 请求超时时间 30 秒
});

// ---------- 功能函数 ----------

/**
 * 文本搜图片：根据输入的文本，搜索最匹配的图片
 * @param query - 用户输入的搜索文本
 * @param topK  - 返回的结果数量，默认为 50
 * @returns 返回 TextToImageResponse 类型的数据，包含图片列表
 */
export async function searchTextToImage(query: string, topK = 50) {
  // 发送 POST 请求到 '/api/search/text'，携带 query 和 top_k 参数
  const { data } = await client.post<TextToImageResponse>('/search/text', {
    query,
    top_k: topK
  });
  return data;  // 返回接口响应数据（符合 TextToImageResponse 结构）
}

/**
 * 图片搜文本：根据上传的图片，搜索最匹配的文本
 * @param file - 用户上传的图片文件（File 对象）
 * @param topK - 返回的结果数量，默认为 5
 * @returns 返回 ImageToTextResponse 类型的数据，包含文本列表
 */
export async function searchImageToText(file: File, topK = 5) {
  // 创建 FormData 对象，用于发送文件（multipart/form-data 格式）
  const formData = new FormData();
  formData.append('file', file);        // 添加图片文件
  formData.append('top_k', String(topK)); // 添加 top_k 参数（转为字符串）

  // 发送 POST 请求到 '/api/search/image'
  const { data } = await client.post<ImageToTextResponse>('/search/image', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'  // 指定请求头，用于文件上传
    }
  });
  return data;  // 返回接口响应数据（符合 ImageToTextResponse 结构）
}
<template>
  <div class="result-wrapper">
    <template v-if="mode === 'text-to-image'">
      <div v-if="loading" class="skeleton-wrapper">
        <el-skeleton
          v-for="n in 8"
          :key="n"
          animated
          class="skeleton-item"
        >
          <template #template>
            <el-skeleton-item variant="image" style="width: 100%; height: 160px" />
          </template>
        </el-skeleton>
      </div>

      <div v-else-if="!imageResults.length" class="empty-tip">
        暂无图片结果，可尝试输入描述或调整查询。
      </div>

      <div v-else class="waterfall">
        <div class="waterfall-column">
          <ImageCard
            v-for="(item, index) in imageResults"
            :key="index"
            :item="item"
          />
        </div>
      </div>
    </template>

    <template v-else>
      <div v-if="loading" class="skeleton-wrapper">
        <el-skeleton
          v-for="n in 5"
          :key="n"
          animated
          class="skeleton-text-item"
        >
          <template #template>
            <el-skeleton-item variant="text" style="width: 80%; margin-bottom: 8px" />
            <el-skeleton-item variant="text" style="width: 60%" />
          </template>
        </el-skeleton>
      </div>

      <div v-else-if="!textResults.length" class="empty-tip">
        暂无文本结果，可尝试上传一张图片进行“图搜文”检索。
      </div>

      <el-card
        v-else
        class="text-result-card"
        shadow="never"
      >
        <div class="text-result-header">
          <span>图搜文结果</span>
          <span class="count">共 {{ textResults.length }} 条</span>
        </div>
        <el-scrollbar height="400px">
          <div class="text-result-list">
            <div
              v-for="(item, index) in textResults"
              :key="index"
              class="text-result-item"
            >
              <div class="line">
                <span class="index">#{{ index + 1 }}</span>
                <span class="score" :class="getScoreLevel(item.score)">
                  {{ item.score.toFixed(3) }}
                </span>
              </div>
              <div class="content-row">
                <div v-if="getImageUrlFromMeta(item.meta)" class="image-container">
                  <div class="image-label">最相关图片 top{{ index + 1 }}</div>
                  <el-image
                    :src="getImageUrlFromMeta(item.meta)"
                    fit="cover"
                    class="thumb"
                    @click="copyImageUrl(getImageUrlFromMeta(item.meta))"
                    :preview-src-list="[getImageUrlFromMeta(item.meta)]"
                  />
                </div>
                <div class="text">{{ item.text }}</div>
              </div>
            </div>
          </div>
        </el-scrollbar>
      </el-card>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useSearchStore } from '@/stores/search';
import ImageCard from './ImageCard.vue';

const store = useSearchStore();

const mode = computed(() => store.mode);
const loading = computed(() => store.loading);
const imageResults = computed(() => store.imageResults);
const textResults = computed(() => store.textResults);

const getScoreLevel = (score: number) => {
  if (score >= 0.9) return 'score-high';
  if (score >= 0.7) return 'score-mid';
  return 'score-low';
};

const getImageUrlFromMeta = (meta: Record<string, unknown> | undefined): string => {
  if (!meta) return '';
  const url = (meta as any).image_url;
  return typeof url === 'string' ? url : '';
};

const copyImageUrl = async (url: string) => {
  try {
    await navigator.clipboard.writeText(url);
    alert('图片 URL 已复制到剪贴板：' + url);
  } catch (err) {
    console.error('复制失败:', err);
    alert('复制失败，请手动复制：' + url);
  }
};
</script>

<style scoped lang="scss">
.result-wrapper {
  margin-top: 16px;
}

.skeleton-wrapper {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 16px;
}

.skeleton-item,
.skeleton-text-item {
  border-radius: 6px;
}

.empty-tip {
  margin-top: 40px;
  text-align: center;
  color: #909399;
  font-size: 13px;
}

.waterfall {
  column-count: 5;
  column-gap: 16px;
}

.waterfall-column {
  break-inside: avoid;
}

@media (max-width: 1600px) {
  .waterfall {
    column-count: 4;
  }
}

@media (max-width: 1200px) {
  .waterfall {
    column-count: 3;
  }
}

@media (max-width: 768px) {
  .waterfall {
    column-count: 2;
  }
}

.text-result-card {
  margin-top: 8px;
}

.text-result-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 13px;
}

.text-result-header .count {
  color: #909399;
}

.text-result-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.text-result-item {
  padding: 8px 0;
  border-bottom: 1px solid #ebeef5;
}

.text-result-item:last-child {
  border-bottom: none;
}

.line {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.index {
  font-weight: 500;
}

.score {
  font-size: 12px;
}

.score-high {
  color: #67c23a;
}

.score-mid {
  color: #e6a23c;
}

.score-low {
  color: #909399;
}

.content-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.thumb {
  width: 80px;
  height: 80px;
  border-radius: 4px;
  flex-shrink: 0;
  cursor: pointer;
  transition: opacity 0.2s;
}

.thumb:hover {
  opacity: 0.8;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
}

.image-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.image-label {
  font-size: 11px;
  color: #909399;
  text-align: center;
}

.text {
  font-size: 13px;
  color: #606266;
  white-space: pre-wrap;
}
</style>


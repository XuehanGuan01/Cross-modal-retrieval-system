<template>
  <div class="agent-result-panel">
    <div class="panel-header">
      <span class="panel-title">检索结果</span>
      <span class="result-count" v-if="results.length">
        共 {{ results.length }} 条
      </span>
    </div>

    <!-- Top-3 推荐 -->
    <div v-if="top3.length" class="top3-section">
      <div class="section-label">
        <el-icon color="#e6a23c"><Trophy /></el-icon>
        AI 推荐 Top-3
      </div>
      <div class="top3-grid">
        <div
          v-for="(item, idx) in top3"
          :key="`top3-${idx}`"
          class="top3-item"
          :class="`rank-${idx + 1}`"
        >
          <div class="rank-badge">{{ idx + 1 }}</div>
          <el-image
            :src="item.image_url"
            fit="cover"
            class="top3-image"
            :preview-src-list="[item.image_url]"
          />
          <div class="top3-info">
            <span class="top3-score">{{ item.score.toFixed(3) }}</span>
            <span class="top3-caption" :title="item.meta?.caption as string">
              {{ truncateCaption(String(item.meta?.caption ?? '')) }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <el-divider v-if="top3.length && results.length > 3" />

    <!-- 全部结果瀑布流 -->
    <div v-if="results.length > 3" class="all-results">
      <div class="section-label">全部结果</div>
      <div class="waterfall">
        <ImageCard
          v-for="(item, idx) in results.slice(3)"
          :key="`result-${idx}`"
          :item="item"
        />
      </div>
    </div>

    <div v-if="!results.length" class="empty-placeholder">
      <el-icon :size="36" color="#c0c4cc"><Picture /></el-icon>
      <p>检索结果将在这里展示</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { Trophy, Picture } from '@element-plus/icons-vue';
import type { ImageResult } from '@/api/search';
import ImageCard from './ImageCard.vue';

const props = defineProps<{
  results: ImageResult[];
  top3?: ImageResult[];
}>();

const top3Computed = computed(() => {
  if (props.top3 && props.top3.length) return props.top3;
  return props.results.slice(0, 3);
});

const truncateCaption = (text: string, maxLen = 20): string => {
  if (!text) return '';
  return text.length > maxLen ? text.slice(0, maxLen) + '...' : text;
};
</script>

<style scoped lang="scss">
.agent-result-panel {
  height: 100%;
  overflow-y: auto;
  padding: 12px 16px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.panel-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.result-count {
  font-size: 12px;
  color: #909399;
}

.section-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: #606266;
  margin-bottom: 10px;
}

.top3-section {
  margin-bottom: 8px;
}

.top3-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.top3-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px;
  border-radius: 8px;
  background: #fafafa;
  transition: background 0.2s;

  &:hover {
    background: #f0f2f5;
  }

  &.rank-1 {
    border-left: 3px solid #e6a23c;
  }
  &.rank-2 {
    border-left: 3px solid #c0c4cc;
  }
  &.rank-3 {
    border-left: 3px solid #cd9b6c;
  }
}

.rank-badge {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #409eff;
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.top3-image {
  width: 64px;
  height: 64px;
  border-radius: 6px;
  flex-shrink: 0;
  cursor: pointer;
}

.top3-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  overflow: hidden;
}

.top3-score {
  font-size: 13px;
  font-weight: 600;
  color: #409eff;
}

.top3-caption {
  font-size: 12px;
  color: #909399;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.all-results {
  margin-top: 4px;
}

.waterfall {
  column-count: 2;
  column-gap: 12px;
}

.empty-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
  color: #c0c4cc;

  p {
    margin-top: 12px;
    font-size: 13px;
  }
}
</style>

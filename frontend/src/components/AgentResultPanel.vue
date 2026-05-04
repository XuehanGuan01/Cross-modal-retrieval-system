<template>
  <div class="agent-result-panel">
    <div class="panel-header">
      <span class="panel-title">检索结果</span>
      <span class="result-count" v-if="results.length">共 {{ results.length }} 条</span>
    </div>

    <!-- Top-5 推荐 -->
    <div v-if="top3.length" class="top-section">
      <div class="section-label">
        <el-icon color="#e6a23c"><Trophy /></el-icon>
        AI 推荐 Top-{{ top3.length }}
      </div>
      <div class="top-grid">
        <div
          v-for="(item, idx) in top3"
          :key="`top-${idx}`"
          class="top-item"
          :class="`rank-${idx + 1}`"
          @click="$emit('educate', idx)"
        >
          <div class="rank-badge">{{ idx + 1 }}</div>
          <el-image
            :src="item.image_url"
            fit="cover"
            class="top-image"
            :preview-src-list="[item.image_url]"
          />
          <div class="top-info">
            <span class="top-score">{{ item.score.toFixed(3) }}</span>
            <span class="top-caption" :title="item.meta?.caption as string">
              {{ truncateCaption(String(item.meta?.caption ?? '')) }}
            </span>
            <el-button size="small" text type="primary" class="learn-btn">
              了解更多 →
            </el-button>
          </div>
        </div>
      </div>
    </div>

    <el-divider v-if="top3.length && results.length > top3.length" />

    <!-- 全部结果瀑布流 -->
    <div v-if="results.length > top3.length" class="all-results">
      <div class="section-label">全部结果</div>
      <div class="waterfall">
        <div
          v-for="(item, idx) in results.slice(top3.length)"
          :key="`r-${idx}`"
          class="wf-item"
          @click="$emit('educate', top3.length + idx)"
        >
          <ImageCard :item="item" />
          <el-button size="small" text type="primary" class="wf-learn-btn">
            了解更多
          </el-button>
        </div>
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

defineEmits<{
  (e: 'educate', index: number): void;
}>();

const top3 = computed(() => {
  if (props.top3 && props.top3.length) return props.top3;
  return props.results.slice(0, 5);
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
  padding: 10px 14px;
}

.panel-header {
  display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;
}
.panel-title { font-size: 14px; font-weight: 600; color: #303133; }
.result-count { font-size: 11px; color: #909399; }

.section-label {
  display: flex; align-items: center; gap: 6px;
  font-size: 12px; font-weight: 600; color: #606266; margin-bottom: 8px;
}

.top-section { margin-bottom: 6px; }
.top-grid { display: flex; flex-direction: column; gap: 6px; }

.top-item {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 8px; border-radius: 8px; background: #fafafa;
  cursor: pointer; transition: background 0.2s;
  &:hover { background: #f0f2f5; }
  &.rank-1 { border-left: 3px solid #e6a23c; }
  &.rank-2 { border-left: 3px solid #c0c4cc; }
  &.rank-3 { border-left: 3px solid #cd9b6c; }
}

.rank-badge {
  width: 22px; height: 22px; border-radius: 50%;
  background: #409eff; color: #fff; font-size: 11px; font-weight: 600;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}

.top-image {
  width: 56px; height: 56px; border-radius: 6px; flex-shrink: 0; cursor: pointer;
}

.top-info {
  display: flex; flex-direction: column; gap: 1px; overflow: hidden; flex: 1;
}
.top-score { font-size: 12px; font-weight: 600; color: #409eff; }
.top-caption {
  font-size: 11px; color: #909399; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.learn-btn { font-size: 11px; padding: 0; height: auto; margin-top: 2px; }

.all-results { margin-top: 4px; }
.waterfall { column-count: 2; column-gap: 10px; }
.wf-item {
  break-inside: avoid; margin-bottom: 10px; position: relative; cursor: pointer;
}
.wf-learn-btn {
  position: absolute; bottom: 4px; right: 4px;
  background: rgba(255,255,255,0.9); border-radius: 4px; font-size: 11px; padding: 2px 6px;
}

.empty-placeholder {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 60px 16px; color: #c0c4cc;
  p { margin-top: 10px; font-size: 12px; }
}
</style>

<template>
  <div class="image-card">
    <el-image
      :src="item.image_url"
      fit="cover"
      loading="lazy"
      lazy
      class="image"
    />
    <div class="info">
      <div class="score" :class="scoreLevel">
        相似度：{{ formattedScore }}
      </div>
      <div class="actions">
        <el-button size="small" text @click="previewVisible = true">放大预览</el-button>
      </div>
    </div>

    <ImagePreviewDialog
      v-model="previewVisible"
      :image-url="item.image_url"
      :meta="item.meta"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import type { ImageResult } from '@/api/search';
import ImagePreviewDialog from './ImagePreviewDialog.vue';

const props = defineProps<{
  item: ImageResult;
}>();

const previewVisible = ref(false);

const formattedScore = computed(() => props.item.score.toFixed(3));

const scoreLevel = computed(() => {
  const s = props.item.score;
  if (s >= 0.9) return 'score-high';
  if (s >= 0.7) return 'score-mid';
  return 'score-low';
});
</script>

<style scoped lang="scss">
.image-card {
  margin-bottom: 16px;
  border-radius: 6px;
  overflow: hidden;
  background: #ffffff;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

.image {
  width: 100%;
  display: block;
}

.info {
  padding: 8px 10px;
  display: flex;
  align-items: center;
  justify-content: space-between;
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
</style>


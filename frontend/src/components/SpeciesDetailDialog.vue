<template>
  <el-dialog
    v-model="visibleInner"
    :title="title"
    width="65%"
    :close-on-click-modal="false"
    :destroy-on-close="true"
    @closed="$emit('closed')"
  >
    <div v-if="loading" class="loading-wrap">
      <el-icon class="is-loading" :size="24"><Loading /></el-icon>
      <span>正在获取科普知识...</span>
    </div>

    <div v-else-if="data" class="detail-body">
      <!-- 主图 + 科普 -->
      <div class="detail-top">
        <el-image
          v-if="data.mainImage"
          :src="data.mainImage"
          fit="contain"
          class="main-image"
          :preview-src-list="[data.mainImage]"
        />
        <div class="knowledge-card">
          <h4>{{ data.subject }}</h4>
          <p v-if="data.scientificName" class="sci-name">{{ data.scientificName }}</p>
          <div class="knowledge-text" v-html="renderedKnowledge"></div>
        </div>
      </div>

      <!-- 同物种/类别更多图片 -->
      <div v-if="data.similarImages && data.similarImages.length" class="similar-section">
        <el-divider />
        <div class="section-title">
          <el-icon><PictureFilled /></el-icon>
          更多「{{ data.subject }}」的图片 ({{ data.similarImages.length }} 张)
        </div>
        <div class="similar-gallery">
          <el-image
            v-for="(img, i) in data.similarImages"
            :key="i"
            :src="img.image_url"
            fit="cover"
            class="similar-thumb"
            :preview-src-list="similarPreviewUrls"
            :initial-index="i"
          />
        </div>
      </div>
    </div>

    <template #footer>
      <el-button @click="visibleInner = false">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { Loading, PictureFilled } from '@element-plus/icons-vue';

const props = defineProps<{
  modelValue: boolean;
  data: {
    knowledgeText: string;
    subject: string;
    scientificName: string;
    similarImages: Array<{ image_url: string }>;
    mainImage: string;
    domain: string;
  } | null;
  loading: boolean;
}>();

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void;
  (e: 'closed'): void;
}>();

const visibleInner = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
});

const title = computed(() => {
  if (!props.data) return '详情';
  return props.data.subject || '物种详情';
});

const renderedKnowledge = computed(() => {
  if (!props.data) return '';
  return props.data.knowledgeText.replace(/\n/g, '<br>');
});

const similarPreviewUrls = computed(() => {
  if (!props.data) return [];
  return props.data.similarImages.map((i) => i.image_url);
});
</script>

<style scoped lang="scss">
.loading-wrap {
  display: flex; align-items: center; justify-content: center; gap: 10px;
  padding: 60px 0; color: #909399; font-size: 14px;
}

.detail-top {
  display: flex; gap: 20px;
}

.main-image {
  width: 260px; height: 260px; border-radius: 8px; flex-shrink: 0; object-fit: cover;
}

.knowledge-card {
  flex: 1;
  h4 { margin: 0 0 4px; font-size: 18px; color: #303133; }
  .sci-name { font-size: 13px; color: #909399; font-style: italic; margin-bottom: 12px; }
  .knowledge-text { font-size: 14px; color: #606266; line-height: 1.8; }
}

.similar-section {
  margin-top: 8px;
  .section-title { display: flex; align-items: center; gap: 6px; font-size: 14px; font-weight: 600; color: #303133; margin-bottom: 10px; }
}

.similar-gallery {
  display: flex; flex-wrap: wrap; gap: 8px;
  .similar-thumb { width: 100px; height: 100px; border-radius: 6px; cursor: pointer; object-fit: cover; transition: transform 0.2s;
    &:hover { transform: scale(1.05); } }
}
</style>

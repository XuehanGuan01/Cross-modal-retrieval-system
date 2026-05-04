<template>
  <div class="chat-message" :class="`msg-${message.role}`">
    <div class="msg-avatar">
      <el-avatar :size="32" :icon="message.role === 'user' ? 'UserFilled' : 'Service'">
        {{ message.role === 'user' ? '我' : 'AI' }}
      </el-avatar>
    </div>
    <div class="msg-body">
      <div class="msg-header">
        <span class="msg-sender">{{ message.role === 'user' ? '你' : '跨模态多领域·交互式Agent' }}</span>
        <span class="msg-time">{{ message.timestamp }}</span>
      </div>

      <div v-if="message.imagePreviewUrl" class="msg-image">
        <el-image
          :src="message.imagePreviewUrl"
          fit="cover"
          style="max-width: 200px; max-height: 150px; border-radius: 6px"
          :preview-src-list="[message.imagePreviewUrl]"
        />
      </div>

      <div class="msg-content" v-html="renderedContent"></div>

      <!-- 检索结果缩略图（点击可触发科普） -->
      <div v-if="message.results && message.results.length" class="msg-results-preview">
        <div class="preview-label">检索结果 ({{ message.results.length }} 条) — 点击图片了解更多</div>
        <div class="preview-grid">
          <div
            v-for="(r, i) in message.results.slice(0, 4)"
            :key="i"
            class="preview-item"
            @click="$emit('educate', i)"
          >
            <el-image
              :src="r.image_url"
              fit="cover"
              class="preview-thumb"
              :preview-src-list="[r.image_url]"
            />
            <span class="preview-rank">#{{ i + 1 }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { ChatMessage } from '@/stores/agent';

const props = defineProps<{
  message: ChatMessage;
}>();

defineEmits<{
  (e: 'educate', index: number): void;
}>();

const renderedContent = computed(() => {
  return props.message.content.replace(/\n/g, '<br>');
});
</script>

<style scoped lang="scss">
.chat-message {
  display: flex;
  gap: 10px;
  padding: 10px 0;

  &.msg-user {
    flex-direction: row-reverse;
    .msg-body { align-items: flex-end; }
    .msg-avatar { order: 1; }
    .msg-content { background: #ecf5ff; border-radius: 12px 4px 12px 12px; }
  }

  &.msg-assistant {
    .msg-content { background: #f5f7fa; border-radius: 4px 12px 12px 12px; }
  }
}

.msg-body { display: flex; flex-direction: column; max-width: 75%; gap: 4px; }
.msg-header { display: flex; align-items: center; gap: 8px; }
.msg-sender { font-size: 12px; font-weight: 600; color: #303133; }
.msg-time { font-size: 11px; color: #c0c4cc; }
.msg-image { margin: 4px 0; }

.msg-content {
  padding: 8px 12px;
  font-size: 13px;
  color: #303133;
  line-height: 1.6;
  word-break: break-word;
}

.msg-results-preview {
  margin-top: 6px;
  .preview-label { font-size: 11px; color: #909399; margin-bottom: 4px; }
  .preview-grid { display: flex; gap: 6px; flex-wrap: wrap; }
  .preview-item { position: relative; cursor: pointer;
    &:hover .preview-thumb { opacity: 0.8; box-shadow: 0 2px 8px rgba(0,0,0,0.2); } }
  .preview-thumb { width: 60px; height: 60px; border-radius: 4px; object-fit: cover; transition: all 0.2s; }
  .preview-rank {
    position: absolute; bottom: 2px; left: 2px;
    background: rgba(0,0,0,0.6); color: #fff; font-size: 10px;
    padding: 0 4px; border-radius: 2px;
  }
}
</style>

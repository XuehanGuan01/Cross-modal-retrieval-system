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

      <div v-if="message.reasoningSteps && message.reasoningSteps.length" class="reasoning-block">
        <el-collapse>
          <el-collapse-item title="查看推理过程">
            <div
              v-for="(step, idx) in message.reasoningSteps"
              :key="idx"
              class="reasoning-step"
            >
              <span class="step-index">Step {{ idx + 1 }}</span>
              <span>{{ step }}</span>
            </div>
          </el-collapse-item>
        </el-collapse>
      </div>

      <div v-if="message.results && message.results.length" class="msg-results-preview">
        <div class="preview-label">检索结果 ({{ message.results.length }} 条)</div>
        <div class="preview-grid">
          <el-image
            v-for="(r, i) in message.results.slice(0, 4)"
            :key="i"
            :src="r.image_url"
            fit="cover"
            class="preview-thumb"
            :preview-src-list="[r.image_url]"
          />
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

const renderedContent = computed(() => {
  return props.message.content.replace(/\n/g, '<br>');
});
</script>

<style scoped lang="scss">
.chat-message {
  display: flex;
  gap: 12px;
  padding: 12px 0;

  &.msg-user {
    flex-direction: row-reverse;
    .msg-body {
      align-items: flex-end;
    }
    .msg-avatar {
      order: 1;
    }
    .msg-content {
      background: #ecf5ff;
      border-radius: 12px 4px 12px 12px;
    }
  }

  &.msg-assistant {
    .msg-content {
      background: #f5f7fa;
      border-radius: 4px 12px 12px 12px;
    }
  }
}

.msg-body {
  display: flex;
  flex-direction: column;
  max-width: 75%;
  gap: 4px;
}

.msg-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.msg-sender {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
}

.msg-time {
  font-size: 11px;
  color: #c0c4cc;
}

.msg-image {
  margin: 4px 0;
}

.msg-content {
  padding: 10px 14px;
  font-size: 14px;
  color: #303133;
  line-height: 1.6;
  word-break: break-word;
}

.reasoning-block {
  margin-top: 4px;
  width: 100%;

  :deep(.el-collapse-item__header) {
    font-size: 12px;
    color: #909399;
    height: 32px;
    line-height: 32px;
  }

  :deep(.el-collapse-item__content) {
    font-size: 12px;
    color: #606266;
  }
}

.reasoning-step {
  padding: 4px 0;
  display: flex;
  gap: 8px;

  .step-index {
    font-weight: 600;
    color: #409eff;
    flex-shrink: 0;
  }
}

.msg-results-preview {
  margin-top: 8px;

  .preview-label {
    font-size: 12px;
    color: #909399;
    margin-bottom: 4px;
  }

  .preview-grid {
    display: flex;
    gap: 6px;
  }

  .preview-thumb {
    width: 64px;
    height: 64px;
    border-radius: 4px;
    cursor: pointer;
    object-fit: cover;
  }
}
</style>

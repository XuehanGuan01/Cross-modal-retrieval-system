<template>
  <div class="chat-panel">
    <div class="chat-messages" ref="msgContainer">
      <div v-if="messages.length === 0" class="chat-welcome">
        <div class="welcome-icon">
          <el-icon :size="48" color="#c0c4cc"><ChatDotRound /></el-icon>
        </div>
        <h3>跨模态多领域·交互式Agent</h3>
        <p>我是你的智能搜物助手，可以用自然语言描述你想找的图片，我会帮你精准定位。</p>
        <div class="example-queries">
          <p class="example-label">试试这样问我：</p>
          <el-tag
            v-for="q in exampleQueries"
            :key="q"
            class="example-tag"
            type="info"
            @click="$emit('quickQuery', q)"
          >
            {{ q }}
          </el-tag>
        </div>
      </div>

      <ChatMessage
        v-for="msg in messages"
        :key="msg.id"
        :message="msg"
      />

      <div v-if="loading" class="typing-indicator">
        <span></span><span></span><span></span>
      </div>
    </div>

    <div class="chat-input-area">
      <div class="input-row">
        <el-upload
          :show-file-list="false"
          :auto-upload="false"
          :on-change="onImageChange"
          accept="image/*"
          class="upload-btn"
        >
          <el-button :icon="PictureFilled" circle size="small" />
        </el-upload>

        <el-input
          v-model="inputText"
          placeholder="输入描述，如：帮我找一种开黄色小花的植物"
          @keyup.enter.native="handleSend"
          :disabled="loading"
          class="text-input"
          clearable
        >
          <template #append>
            <el-button
              type="primary"
              :loading="loading"
              :disabled="!inputText.trim()"
              @click="handleSend"
            >
              发送
            </el-button>
          </template>
        </el-input>
      </div>

      <div v-if="pendingImage" class="pending-image">
        <el-tag closable @close="pendingImage = null">
          图片已选择：{{ pendingImage.name }}
        </el-tag>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue';
import { ChatDotRound, PictureFilled } from '@element-plus/icons-vue';
import ChatMessage from './ChatMessage.vue';
import type { ChatMessage as ChatMessageType } from '@/stores/agent';

const props = defineProps<{
  messages: ChatMessageType[];
  loading: boolean;
}>();

const emit = defineEmits<{
  (e: 'send', text: string, image?: File): void;
  (e: 'quickQuery', q: string): void;
}>();

const inputText = ref('');
const pendingImage = ref<File | null>(null);
const msgContainer = ref<HTMLElement | null>(null);

const exampleQueries = [
  '帮我找一种开黄色小花、叶子心形的植物',
  '找一只黑白条纹的动物',
  '帮我找红色的连衣裙',
];

const handleSend = () => {
  const text = inputText.value.trim();
  if (!text) return;
  emit('send', text, pendingImage.value ?? undefined);
  inputText.value = '';
  pendingImage.value = null;
};

const onImageChange = (file: any) => {
  if (file?.raw) {
    pendingImage.value = file.raw;
  }
};

watch(
  () => props.messages.length,
  () => {
    nextTick(() => {
      if (msgContainer.value) {
        msgContainer.value.scrollTop = msgContainer.value.scrollHeight;
      }
    });
  },
);
</script>

<style scoped lang="scss">
.chat-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 500px;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
}

.chat-welcome {
  text-align: center;
  padding: 60px 20px;

  h3 {
    margin: 16px 0 8px;
    font-size: 18px;
    color: #303133;
  }

  p {
    font-size: 13px;
    color: #909399;
    margin-bottom: 24px;
  }
}

.example-queries {
  .example-label {
    font-size: 12px;
    color: #c0c4cc;
    margin-bottom: 8px;
  }

  .example-tag {
    margin: 4px;
    cursor: pointer;
    transition: all 0.2s;

    &:hover {
      transform: translateY(-1px);
      box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }
  }
}

.chat-input-area {
  border-top: 1px solid #ebeef5;
  padding: 12px 16px;
  background: #fff;
}

.input-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.upload-btn {
  flex-shrink: 0;
}

.text-input {
  flex: 1;
}

.pending-image {
  margin-top: 8px;
}

.typing-indicator {
  display: flex;
  gap: 4px;
  padding: 12px 0;

  span {
    width: 8px;
    height: 8px;
    background: #c0c4cc;
    border-radius: 50%;
    animation: typing 1.4s infinite both;

    &:nth-child(2) {
      animation-delay: 0.2s;
    }
    &:nth-child(3) {
      animation-delay: 0.4s;
    }
  }
}

@keyframes typing {
  0%, 60%, 100% {
    transform: translateY(0);
  }
  30% {
    transform: translateY(-6px);
  }
}
</style>

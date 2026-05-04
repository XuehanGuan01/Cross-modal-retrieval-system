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

      <!-- 推理进度条（加载中） -->
      <div v-if="loading" class="progress-banner">
        <div class="progress-bar">
          <el-icon class="is-loading" :size="14"><Loading /></el-icon>
          <span class="progress-text">{{ progressText }}</span>
        </div>
      </div>

      <ChatMessage
        v-for="msg in messages"
        :key="msg.id"
        :message="msg"
        @educate="(idx: number) => $emit('educate', idx)"
      />

      <!-- 结束后展示推理步骤 -->
      <div v-if="!loading && progressTrail.length" class="progress-done">
        <el-collapse>
          <el-collapse-item title="查看推理过程">
            <div v-for="(p, i) in progressTrail" :key="i" class="trail-step">
              <el-icon color="#67c23a"><CircleCheck /></el-icon>
              <span>{{ p }}</span>
            </div>
          </el-collapse-item>
        </el-collapse>
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
import { ChatDotRound, PictureFilled, Loading, CircleCheck } from '@element-plus/icons-vue';
import ChatMessage from './ChatMessage.vue';
import type { ChatMessage as ChatMessageType } from '@/stores/agent';
import { useAgentStore } from '@/stores/agent';

const props = defineProps<{
  messages: ChatMessageType[];
  loading: boolean;
  progressTrail?: string[];
  currentProgress?: string;
}>();

const emit = defineEmits<{
  (e: 'send', text: string, image?: File): void;
  (e: 'quickQuery', q: string): void;
  (e: 'educate', resultIndex: number): void;
}>();

const store = useAgentStore();
const inputText = ref('');
const pendingImage = ref<File | null>(null);
const msgContainer = ref<HTMLElement | null>(null);

const progressText = ref('正在思考...');

const exampleQueries = [
  '帮我找一种开黄色小花、叶子心形的植物',
  '找一只黑白条纹的动物',
  '帮我找红色的连衣裙',
];

// 模拟进度变化
watch(() => props.loading, (val) => {
  if (val) {
    const phrases = [
      '正在理解你的需求...',
      '正在分析特征，提取关键词...',
      '正在海量图库中搜索匹配...',
      '正在排序最佳结果...',
      '马上就好，正在整理回复...',
    ];
    let i = 0;
    progressText.value = phrases[0];
    const t = setInterval(() => {
      i = (i + 1) % phrases.length;
      progressText.value = phrases[i];
    }, 1200);
    (props as any)._t = t;
  } else {
    const t = (props as any)._t;
    if (t) clearInterval(t);
  }
});

const handleSend = () => {
  const text = inputText.value.trim();
  if (!text) return;
  emit('send', text, pendingImage.value ?? undefined);
  inputText.value = '';
  pendingImage.value = null;
};

const onImageChange = (file: any) => {
  if (file?.raw) pendingImage.value = file.raw;
};

watch(() => props.messages.length, () => {
  nextTick(() => {
    if (msgContainer.value) {
      msgContainer.value.scrollTop = msgContainer.value.scrollHeight;
    }
  });
});
</script>

<style scoped lang="scss">
.chat-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px;
}

.chat-welcome {
  text-align: center;
  padding: 40px 16px;
  h3 { margin: 12px 0 6px; font-size: 17px; color: #303133; }
  p { font-size: 13px; color: #909399; margin-bottom: 20px; }
}

.example-queries {
  .example-label { font-size: 12px; color: #c0c4cc; margin-bottom: 6px; }
  .example-tag { margin: 3px; cursor: pointer; transition: all 0.2s;
    &:hover { transform: translateY(-1px); box-shadow: 0 2px 4px rgba(0,0,0,0.1); } }
}

.progress-banner {
  padding: 8px 12px;
  margin: 8px 0;
  background: #ecf5ff;
  border-radius: 6px;
  .progress-bar { display: flex; align-items: center; gap: 8px; }
  .progress-text { font-size: 13px; color: #409eff; }
}

.progress-done {
  margin-top: 8px;
  :deep(.el-collapse-item__header) { font-size: 12px; color: #909399; }
  .trail-step { display: flex; align-items: center; gap: 6px; padding: 3px 0; font-size: 12px; color: #606266; }
}

.chat-input-area {
  border-top: 1px solid #ebeef5;
  padding: 10px 14px;
  background: #fff;
}

.input-row { display: flex; align-items: center; gap: 8px; }
.upload-btn { flex-shrink: 0; }
.text-input { flex: 1; }
.pending-image { margin-top: 6px; }
</style>

<template>
  <div class="agent-chat">
    <div class="domain-indicator" v-if="currentDomain">
      <el-tag type="warning" size="small">
        当前检索领域：{{ currentDomain }}
        <template v-if="domainInfo">
          — {{ domainInfo.image_count.toLocaleString() }} 张图片
        </template>
      </el-tag>
      <el-button
        type="danger"
        size="small"
        text
        @click="handleClearSession"
        v-if="store.messages.length > 0"
        style="margin-left: 12px"
      >
        清空对话
      </el-button>
    </div>

    <div class="chat-layout">
      <div class="chat-left">
        <ChatPanel
          :messages="store.messages"
          :loading="store.loading"
          @send="handleSend"
          @quickQuery="handleQuickQuery"
        />
      </div>
      <div class="chat-right">
        <!-- 低置信度警告 -->
        <el-alert
          v-if="store.isLowConfidence && store.hasResults"
          title="匹配度较低"
          type="warning"
          :closable="false"
          show-icon
          style="margin-bottom: 8px"
        >
          搜索结果与查询的相似度偏低（&lt;0.5），建议补充更多细节描述。
        </el-alert>

        <AgentResultPanel
          :results="store.currentResults"
          :top3="store.top5Results"
        />

        <!-- 追问建议 -->
        <div v-if="store.suggestions.length && !store.loading" class="suggestions-bar">
          <div class="suggestions-label">你可以：</div>
          <el-tag
            v-for="(s, idx) in store.suggestions"
            :key="idx"
            class="suggestion-tag"
            :type="idx === 0 ? 'warning' : 'info'"
            @click="handleQuickQuery(s)"
          >
            {{ s }}
          </el-tag>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, watch } from 'vue';
import { useAgentStore } from '@/stores/agent';
import { useSearchStore } from '@/stores/search';
import ChatPanel from '@/components/ChatPanel.vue';
import AgentResultPanel from '@/components/AgentResultPanel.vue';

const store = useAgentStore();
const searchStore = useSearchStore();

const currentDomain = computed(() => searchStore.currentDomain);
const domainInfo = computed(() => searchStore.currentDomainInfo);

// 领域切换时重建会话
watch(currentDomain, (newDomain) => {
  store.clearSession();
  store.initSession(newDomain);
});

const handleSend = (text: string, image?: File) => {
  store.sendMessage(text, currentDomain.value, image);
};

const handleQuickQuery = (q: string) => {
  store.sendMessage(q, currentDomain.value);
};

const handleClearSession = () => {
  store.clearSession();
  store.initSession(currentDomain.value);
};

// 初始化
store.initSession(currentDomain.value);

onBeforeUnmount(() => {
  store.clearSession();
});
</script>

<style scoped lang="scss">
.agent-chat {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.domain-indicator {
  margin-bottom: 8px;
  display: flex;
  align-items: center;
}

.chat-layout {
  flex: 1;
  display: flex;
  gap: 16px;
  min-height: 550px;
}

.chat-left {
  flex: 1;
  min-width: 0;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.chat-right {
  width: 400px;
  flex-shrink: 0;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.suggestions-bar {
  padding: 10px 16px;
  border-top: 1px solid #ebeef5;
  background: #fafafa;

  .suggestions-label {
    font-size: 12px;
    color: #909399;
    margin-bottom: 6px;
  }

  .suggestion-tag {
    margin: 3px 4px 3px 0;
    cursor: pointer;
    transition: all 0.2s;

    &:hover {
      transform: translateY(-1px);
      box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }
  }
}

@media (max-width: 960px) {
  .chat-layout {
    flex-direction: column;
  }
  .chat-right {
    width: 100%;
  }
}
</style>

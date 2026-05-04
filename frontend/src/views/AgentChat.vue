<template>
  <div class="agent-chat">
    <div class="domain-indicator" v-if="currentDomain">
      <el-tag type="warning" size="small">
        当前领域：{{ currentDomain }}
        <template v-if="domainInfo"> — {{ domainInfo.image_count.toLocaleString() }} 张图片</template>
      </el-tag>
      <el-button
        type="danger" size="small" text
        @click="handleClearSession"
        v-if="store.messages.length > 0"
        style="margin-left: 10px"
      >清空对话</el-button>
    </div>

    <div class="chat-layout">
      <div class="chat-left">
        <ChatPanel
          :messages="store.messages"
          :loading="store.loading"
          :progressTrail="store.progressTrail"
          :currentProgress="store.currentProgress"
          @send="handleSend"
          @quickQuery="handleQuickQuery"
          @educate="handleEducate"
        />
      </div>
      <div class="chat-right">
        <el-alert
          v-if="store.isLowConfidence && store.hasResults"
          title="匹配度较低" type="warning"
          :closable="false" show-icon style="margin-bottom: 6px"
        >相似度偏低（&lt;0.5），建议补充更多细节。</el-alert>

        <AgentResultPanel
          :results="store.currentResults"
          :top3="store.top5Results"
          @educate="handleEducate"
        />

        <div v-if="store.suggestions.length && !store.loading" class="suggestions-bar">
          <div class="sug-label">你可以：</div>
          <el-tag
            v-for="(s, idx) in store.suggestions" :key="idx"
            class="sug-tag" :type="idx === 0 ? 'warning' : 'info'"
            @click="handleQuickQuery(s)"
          >{{ s }}</el-tag>
        </div>
      </div>
    </div>

    <!-- 科普详情弹窗 -->
    <SpeciesDetailDialog
      v-model="educateVisible"
      :data="store.educateData"
      :loading="store.educateLoading"
      @closed="store.clearEducateData()"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onBeforeUnmount, watch } from 'vue';
import { useAgentStore } from '@/stores/agent';
import { useSearchStore } from '@/stores/search';
import ChatPanel from '@/components/ChatPanel.vue';
import AgentResultPanel from '@/components/AgentResultPanel.vue';
import SpeciesDetailDialog from '@/components/SpeciesDetailDialog.vue';

const store = useAgentStore();
const searchStore = useSearchStore();
const educateVisible = ref(false);

const currentDomain = computed(() => searchStore.currentDomain);
const domainInfo = computed(() => searchStore.currentDomainInfo);

watch(currentDomain, (d) => { store.clearSession(); store.initSession(d); });

const handleSend = (text: string, image?: File) => {
  store.sendMessage(text, currentDomain.value, image);
};

const handleQuickQuery = (q: string) => {
  store.sendMessage(q, currentDomain.value);
};

const handleEducate = (resultIndex: number) => {
  educateVisible.value = true;
  store.educateResult(resultIndex);
};

const handleClearSession = () => {
  store.clearSession();
  store.initSession(currentDomain.value);
};

store.initSession(currentDomain.value);
onBeforeUnmount(() => store.clearSession());
</script>

<style scoped lang="scss">
.agent-chat {
  height: calc(100vh - 190px);
  display: flex;
  flex-direction: column;
}

.domain-indicator {
  margin-bottom: 6px;
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

.chat-layout {
  flex: 1;
  display: flex;
  gap: 12px;
  min-height: 0;
  overflow: hidden;
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
  width: 380px;
  flex-shrink: 0;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.suggestions-bar {
  padding: 8px 14px;
  border-top: 1px solid #ebeef5;
  background: #fafafa;
  flex-shrink: 0;
  .sug-label { font-size: 11px; color: #909399; margin-bottom: 4px; }
  .sug-tag { margin: 2px 3px 2px 0; cursor: pointer;
    &:hover { transform: translateY(-1px); } }
}

@media (max-width: 960px) {
  .chat-layout { flex-direction: column; }
  .chat-right { width: 100%; }
}
</style>

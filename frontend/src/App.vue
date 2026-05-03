<template>
  <el-container class="app-container">
    <el-header class="app-header">
      <div class="title-block">
        <h1>跨模态检索系统 · 交互式 Agent</h1>
        <p class="subtitle">文本搜图 & 图搜文 · 智能搜物 Agent · 4领域</p>
      </div>
    </el-header>
    <el-main class="app-main">
      <el-tabs v-model="activeTab" type="border-card" class="main-tabs">
        <el-tab-pane label="直接检索" name="direct">
          <DirectSearch />
        </el-tab-pane>
        <el-tab-pane label="智能搜物 Agent" name="agent">
          <AgentChat />
        </el-tab-pane>
      </el-tabs>
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import DirectSearch from '@/views/DirectSearch.vue';
import AgentChat from '@/views/AgentChat.vue';

const activeTab = ref('direct');
</script>

<style scoped lang="scss">
.app-container {
  min-height: 100vh;
  background: #f5f7fa;
}

.app-header {
  display: flex;
  align-items: center;
  padding: 0 24px;
  background: #ffffff;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);

  .title-block {
    h1 {
      font-size: 22px;
      margin: 0;
      color: #303133;
    }

    .subtitle {
      font-size: 13px;
      color: #909399;
      margin: 4px 0 0;
    }
  }
}

.app-main {
  padding: 16px 24px 24px;
  max-width: 1440px;
  margin: 0 auto;
  width: 100%;
}

.main-tabs {
  :deep(.el-tabs__content) {
    padding: 16px 0 0;
    min-height: 500px;
  }
}
</style>

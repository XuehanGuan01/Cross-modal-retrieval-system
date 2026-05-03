<template>
  <el-card class="search-card" shadow="never">
    <div class="search-header">
      <div class="header-left">
        <span class="domain-label">检索领域：</span>
        <el-select
          v-model="currentDomain"
          size="small"
          style="width: 200px"
          @change="onDomainChange"
        >
          <el-option
            v-for="d in domains"
            :key="d.name"
            :label="`${d.name} — ${d.description}`"
            :value="d.name"
          />
        </el-select>
        <span class="domain-count" v-if="currentDomainInfo">
          {{ currentDomainInfo.image_count.toLocaleString() }} 张图片
        </span>
      </div>
      <div class="header-right">
        <el-radio-group v-model="mode" size="small">
          <el-radio-button label="text-to-image">文本搜图</el-radio-button>
          <el-radio-button label="image-to-text">图搜文</el-radio-button>
        </el-radio-group>
        <div class="history-tip" v-if="history.length">
          最近搜索：{{ history[0].query }}（{{ history[0].time }}）
        </div>
      </div>
    </div>

    <div class="search-body">
      <template v-if="mode === 'text-to-image'">
        <el-input
          v-model="queryText"
          size="large"
          placeholder="输入中文描述，如：一只白色的猫在窗台上晒太阳"
          @keyup.enter.native="handleSearchText"
          class="search-input"
          clearable
        >
          <template #append>
            <el-button type="primary" :loading="loading" @click="handleSearchText">
              搜索图片
            </el-button>
          </template>
        </el-input>
      </template>

      <template v-else>
        <el-upload
          drag
          :show-file-list="false"
          :auto-upload="false"
          :on-change="onImageChange"
          accept="image/*"
          class="upload-area"
        >
          <el-icon class="el-icon--upload"><upload-filled /></el-icon>
          <div class="el-upload__text">
            拖拽图片到此处，或 <em>点击上传</em>
          </div>
          <template #tip>
            <div class="el-upload__tip">
              支持 jpg/png/webp 等格式，上传后自动进行“图搜文”检索
              <span v-if="lastImageFileName">（最近：{{ lastImageFileName }}）</span>
            </div>
          </template>
        </el-upload>
      </template>
    </div>

    <div class="search-footer">
      <el-alert
        v-if="error"
        :title="error"
        type="error"
        show-icon
        :closable="false"
      />
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue';
import { UploadFilled } from '@element-plus/icons-vue';
import { useSearchStore } from '@/stores/search';

const store = useSearchStore();

const mode = computed({
  get: () => store.mode,
  set: (val) => store.setMode(val),
});

const queryText = computed({
  get: () => store.queryText,
  set: (val) => store.setQueryText(val),
});

const loading = computed(() => store.loading);
const error = computed(() => store.error);
const history = computed(() => store.history);
const lastImageFileName = computed(() => store.lastImageFileName);
const currentDomain = computed({
  get: () => store.currentDomain,
  set: (val) => store.setDomain(val),
});
const domains = computed(() => store.domains);
const currentDomainInfo = computed(() => store.currentDomainInfo);

const onDomainChange = (val: string) => {
  store.setDomain(val);
};

const handleSearchText = () => {
  store.searchByText();
};

const onImageChange = (file: any) => {
  if (file?.raw) {
    store.searchByImage(file.raw);
  }
};

onMounted(() => {
  store.loadDomains();
});
</script>

<style scoped lang="scss">
.search-card {
  margin-bottom: 24px;
}

.search-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 12px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.domain-label {
  font-size: 13px;
  color: #606266;
  font-weight: 500;
}

.domain-count {
  font-size: 12px;
  color: #909399;
  margin-left: 8px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.history-tip {
  font-size: 12px;
  color: #909399;
}

.search-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.search-input {
  max-width: 800px;
}

.upload-area {
  max-width: 600px;
}

.search-footer {
  margin-top: 12px;
}
</style>

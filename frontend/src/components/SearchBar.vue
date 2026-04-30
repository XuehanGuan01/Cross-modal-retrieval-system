<template>
  <el-card class="search-card" shadow="never">
    <div class="search-header">
      <el-radio-group v-model="mode" size="small">
        <el-radio-button label="text-to-image">文本搜图</el-radio-button>
        <el-radio-button label="image-to-text">图搜文</el-radio-button>
      </el-radio-group>
      <div class="history-tip" v-if="history.length">
        最近搜索：{{ history[0].query }}（{{ history[0].time }}）
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
import { computed } from 'vue';
import { UploadFilled } from '@element-plus/icons-vue';
import { useSearchStore } from '@/stores/search';

const store = useSearchStore();

const mode = computed({
  get: () => store.mode,
  set: (val) => store.setMode(val)
});

const queryText = computed({
  get: () => store.queryText,
  set: (val) => store.setQueryText(val)
});

const loading = computed(() => store.loading);
const error = computed(() => store.error);
const history = computed(() => store.history);
const lastImageFileName = computed(() => store.lastImageFileName);

const handleSearchText = () => {
  store.searchByText();
};

const onImageChange = (file: any) => {
  if (file?.raw) {
    store.searchByImage(file.raw);
  }
};
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


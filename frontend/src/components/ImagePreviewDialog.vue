<template>
  <el-dialog
    v-model="visibleInner"
    width="60%"
    :close-on-click-modal="false"
    :destroy-on-close="true"
    title="图片预览"
  >
    <div class="preview-body">
      <el-image
        v-if="imageUrl"
        :src="imageUrl"
        fit="contain"
        :preview-src-list="[imageUrl]"
        style="max-height: 480px"
      />
      <div class="meta-block" v-if="meta">
        <h4>相关文本/说明</h4>
        <pre>{{ meta }}</pre>
      </div>
    </div>
    <template #footer>
      <span class="dialog-footer">
        <el-button @click="visibleInner = false">关 闭</el-button>
      </span>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{
  modelValue: boolean;
  imageUrl?: string;
  meta?: unknown;
}>();

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void;
}>();

const visibleInner = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
});
</script>

<style scoped lang="scss">
.preview-body {
  display: flex;
  gap: 16px;
}

.meta-block {
  flex: 1;
  font-size: 13px;
  color: #606266;
  background: #f5f7fa;
  padding: 12px;
  border-radius: 4px;
  overflow: auto;
}
</style>


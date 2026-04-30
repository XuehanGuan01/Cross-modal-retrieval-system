<template>
  <el-container class="app-container">
    <el-header class="app-header">
      <div class="title-block">
        <h1>跨模态检索系统</h1>
        <p class="subtitle">文本搜图 & 图搜文 · 支持图片上传与相似度排序</p>
      </div>
    </el-header>
    <el-main class="app-main">
      <SearchBar />
      <ResultGallery />
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import SearchBar from './components/SearchBar.vue';
import ResultGallery from './components/ResultGallery.vue';
</script>


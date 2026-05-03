<template>
  <div class="direct-search">
    <SearchBar />
    <ResultGallery />
  </div>
</template>

<script setup lang="ts">
import SearchBar from '@/components/SearchBar.vue';
import ResultGallery from '@/components/ResultGallery.vue';
</script>

<style scoped lang="scss">
.direct-search {
  width: 100%;
}
</style>

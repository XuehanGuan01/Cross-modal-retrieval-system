整体架构设计
技术栈：Vue 3 + Vite + TypeScript（可选）+ Element Plus + Pinia + Axios
目录结构建议（放在 frontend 下）：
frontend/
  index.html
  vite.config.ts
  package.json
  src/
    main.ts
    App.vue
    router/
        index.ts（如果你要多页，这里先可以不加路由）
    stores/
        search.ts（Pinia 搜索状态）
    api/
        search.ts（封装请求）
    components/
        SearchBar.vue
    components/
        ResultGallery.vue
    components/
        ImageCard.vue
    components/
        ImagePreviewDialog.vue
    styles/
        global.scss（或 .css）
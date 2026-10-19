<script setup lang="ts">
import {onUnmounted} from 'vue'
import {notifications,dismissNotification,clearNotifications} from '../notifications'
onUnmounted(clearNotifications)
</script>
<template><Teleport to="body"><div class="notifications" aria-label="Notifiche">
  <div v-for="n in notifications" :key="n.id" class="toast" :class="n.kind" :role="n.kind==='error'?'alert':'status'">
    <span>{{n.text}}</span><button aria-label="Chiudi notifica" @click="dismissNotification(n.id)">×</button>
  </div>
</div></Teleport></template>
<style scoped>
.notifications{position:fixed;bottom:18px;right:18px;z-index:1000;display:grid;gap:8px;width:min(360px,calc(100vw - 36px));pointer-events:none}
.toast{display:flex;align-items:start;gap:12px;background:white;color:#172033;border:1px solid #ccd8e5;border-left:4px solid #2563eb;border-radius:8px;padding:12px 14px;box-shadow:0 4px 20px #13253c30;font-size:.9rem;pointer-events:auto;overflow-wrap:anywhere}
.toast.error{border-left-color:#b42318}.toast span{flex:1}.toast button{background:transparent;color:#526173;padding:0 4px;line-height:1.1;font-size:1.2rem}
</style>

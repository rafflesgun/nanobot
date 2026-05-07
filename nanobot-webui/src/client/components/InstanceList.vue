<script setup lang="ts">
import type { PublicInstance } from '../api'

defineProps<{ instances: PublicInstance[] }>()
</script>

<template>
  <section class="panel">
    <h2>Instances</h2>
    <article v-for="instance in instances" :key="instance.id" class="instance-card">
      <strong>{{ instance.name }}</strong>
      <span>{{ instance.baseUrl }}</span>
      <em>{{ instance.enabled ? 'enabled' : 'disabled' }}</em>
    </article>
  </section>
</template>

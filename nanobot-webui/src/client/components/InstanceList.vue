<script setup lang="ts">
import type { PublicInstance } from '../api'

defineProps<{ instances: PublicInstance[] }>()
</script>

<template>
  <section class="instance-strip" aria-label="Instance status">
    <span v-if="instances.length === 0" class="instance-empty">No instances</span>
    <span v-for="instance in instances" :key="instance.id" class="instance-pill" :title="`${instance.name} (${instance.enabled ? 'enabled' : 'disabled'})`">
      <span data-testid="instance-dot" class="instance-dot" :class="{ 'is-enabled': instance.enabled, 'is-disabled': !instance.enabled }" />
      <span>{{ instance.name }}</span>
    </span>
  </section>
</template>

<style scoped>
.instance-strip {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.instance-empty {
  color: #7f8aa3;
  font-size: 0.85rem;
}

.instance-pill {
  align-items: center;
  border: 1px solid rgba(148, 163, 184, 0.24);
  border-radius: 999px;
  color: #dbe7ff;
  display: inline-flex;
  font-size: 0.82rem;
  gap: 0.45rem;
  padding: 0.35rem 0.6rem;
  background: rgba(15, 23, 42, 0.72);
}

.instance-dot {
  border-radius: 999px;
  display: inline-block;
  height: 0.5rem;
  width: 0.5rem;
}

.instance-dot.is-enabled {
  background: #22c55e;
  box-shadow: 0 0 10px rgba(34, 197, 94, 0.75);
}

.instance-dot.is-disabled {
  background: #64748b;
}
</style>

<script setup lang="ts">
import type { PublicInstance } from '../api'

defineProps<{ instances: PublicInstance[] }>()
</script>

<template>
  <section class="panel">
    <div class="panel-heading">
      <div>
        <h2>Instances</h2>
        <p>{{ instances.length }} configured</p>
      </div>
    </div>
    <p v-if="instances.length === 0" class="empty-state">Log in with a valid dashboard token to load configured instances.</p>
    <div v-else class="instance-list">
      <article v-for="instance in instances" :key="instance.id" class="instance-card">
        <div class="instance-main">
          <strong>{{ instance.name }}</strong>
          <span class="instance-id">{{ instance.id }}</span>
        </div>
        <code>{{ instance.baseUrl }}</code>
        <em :class="['status-badge', instance.enabled ? 'is-enabled' : 'is-disabled']">
          {{ instance.enabled ? 'enabled' : 'disabled' }}
        </em>
      </article>
    </div>
  </section>
</template>

<style scoped>
.panel-heading {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
}

.panel-heading p {
  color: #69778c;
  font-size: 0.9rem;
  margin: 0.25rem 0 0;
}

.empty-state {
  border: 1px dashed #c9d4e5;
  border-radius: 0.75rem;
  color: #69778c;
  line-height: 1.5;
  margin: 0;
  padding: 1rem;
}

.instance-list {
  display: grid;
  gap: 0.8rem;
}

.instance-card {
  display: grid;
  gap: 0.65rem;
  border: 1px solid #dce4ef;
  border-radius: 0.85rem;
  background: #fbfdff;
  padding: 0.95rem;
}

.instance-main {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.instance-main strong {
  color: #101827;
  font-size: 1rem;
}

.instance-id {
  color: #69778c;
  font-size: 0.8rem;
}

code {
  overflow: hidden;
  border-radius: 0.5rem;
  background: #edf2f9;
  color: #34445c;
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
  font-size: 0.82rem;
  padding: 0.45rem 0.55rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-badge {
  justify-self: start;
  border-radius: 999px;
  font-size: 0.76rem;
  font-style: normal;
  font-weight: 800;
  padding: 0.25rem 0.65rem;
  text-transform: uppercase;
}

.is-enabled {
  background: #dcfce7;
  color: #166534;
}

.is-disabled {
  background: #f1f5f9;
  color: #475569;
}
</style>

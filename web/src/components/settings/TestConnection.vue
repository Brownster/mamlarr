<template>
  <section class="test-connection">
    <header>
      <h3>Test Connection</h3>
      <p class="text-muted">Validate that the configured download client is reachable.</p>
    </header>
    <button class="btn" :disabled="pending" @click="runTest">
      <span v-if="pending">Testing…</span>
      <span v-else>Test Connection</span>
    </button>
    <div v-if="result" class="result" :class="result.kind">
      <p>{{ result.message }}</p>
      <p v-if="result.hint" class="hint">{{ result.hint }}</p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref } from 'vue';

type TestResponse = {
  status: 'ok' | 'error';
  message?: string;
  hint?: string | null;
};

type ResultState = {
  kind: 'success' | 'error';
  message: string;
  hint?: string | null;
};

const pending = ref(false);
const result = ref<ResultState | null>(null);

async function runTest() {
  pending.value = true;
  result.value = null;
  try {
    const response = await fetch('/mamlarr/api/test-connection', {
      method: 'POST',
      headers: { Accept: 'application/json' },
    });
    const data = (await response.json()) as TestResponse;
    const kind: ResultState['kind'] = response.ok && data.status === 'ok' ? 'success' : 'error';
    const message = data.message || (kind === 'success' ? 'Connection succeeded.' : 'Connection failed.');
    result.value = {
      kind,
      message,
      hint: data.hint ?? null,
    };
  } catch (error) {
    result.value = {
      kind: 'error',
      message: 'Unable to run connection test.',
      hint: (error as Error).message,
    };
  } finally {
    pending.value = false;
  }
}
</script>

<style scoped>
.test-connection {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.text-muted {
  color: var(--muted-color, #6b7280);
}
.btn {
  align-self: flex-start;
}
.result.success {
  color: #16a34a;
}
.result.error {
  color: #dc2626;
}
.result .hint {
  margin-top: 0.25rem;
  font-size: 0.85rem;
  color: inherit;
  opacity: 0.8;
}
</style>

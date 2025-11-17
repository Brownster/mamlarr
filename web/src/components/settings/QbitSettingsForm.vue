<template>
  <section class="qbit-settings">
    <header>
      <h3>qBittorrent</h3>
      <p class="text-muted">Mirror Radarr's advanced controls for the qBittorrent download client.</p>
    </header>

    <form class="field" @submit.prevent="saveCategory">
      <label for="qbit-category">Category</label>
      <input id="qbit-category" v-model="form.category" type="text" placeholder="mamlarr" />
      <small>Will be created automatically in qBittorrent if it does not already exist.</small>
      <p v-if="errors.category" class="error">{{ errors.category }}</p>
      <button type="submit">Save</button>
    </form>

    <form class="field" @submit.prevent="savePostCategory">
      <label for="qbit-post-category">Post-import Category</label>
      <input id="qbit-post-category" v-model="form.postImportCategory" type="text" placeholder="Optional" />
      <small>Recategorize completed downloads just like Radarr's post-import category.</small>
      <p v-if="errors.postImportCategory" class="error">{{ errors.postImportCategory }}</p>
      <button type="submit">Save</button>
    </form>

    <form class="field" @submit.prevent="saveInitialState">
      <label for="qbit-initial-state">Initial State</label>
      <select id="qbit-initial-state" v-model="form.initialState">
        <option value="start">Started</option>
        <option value="force_start">Force Start</option>
        <option value="stop">Stopped</option>
      </select>
      <small>Choose whether torrents begin queued, force-started, or stopped.</small>
      <p v-if="errors.initialState" class="error">{{ errors.initialState }}</p>
      <button type="submit">Save</button>
    </form>

    <label class="toggle-field">
      <input type="checkbox" v-model="form.sequential" @change="saveSequential" />
      <span>
        <strong>Sequential Downloading</strong>
        <small>Request pieces in order to allow early playback.</small>
      </span>
    </label>
    <p v-if="errors.sequential" class="error">{{ errors.sequential }}</p>

    <form class="field" @submit.prevent="saveContentLayout">
      <label for="qbit-content-layout">Content Layout</label>
      <select id="qbit-content-layout" v-model="form.contentLayout">
        <option value="default">Use Client Default</option>
        <option value="original">Original</option>
        <option value="subfolder">Create Subfolder</option>
      </select>
      <small>Match Radarr's "Content Layout" dropdown.</small>
      <p v-if="errors.contentLayout" class="error">{{ errors.contentLayout }}</p>
      <button type="submit">Save</button>
    </form>

    <form class="field" @submit.prevent="saveSeedRatio">
      <label for="qbit-seed-ratio">Seed Ratio</label>
      <input id="qbit-seed-ratio" v-model.number="form.seedRatio" type="number" step="0.1" min="1" placeholder="Use client default" />
      <small>Ratio target before stopping (Radarr recommends at least 1.0).</small>
      <p v-if="errors.seedRatio" class="error">{{ errors.seedRatio }}</p>
      <button type="submit">Save</button>
    </form>

    <form class="field" @submit.prevent="saveSeedTime">
      <label for="qbit-seed-time">Seed Time (minutes)</label>
      <input id="qbit-seed-time" v-model.number="form.seedTime" type="number" min="1" placeholder="Use client default" />
      <small>Minimum seeding duration before stopping.</small>
      <p v-if="errors.seedTime" class="error">{{ errors.seedTime }}</p>
      <button type="submit">Save</button>
    </form>
  </section>
</template>

<script setup lang="ts">
import { reactive } from 'vue';

const CATEGORY_PATTERN = /^([^\\/](\/?[^\\/])*)?$/;

type InitialState = 'start' | 'force_start' | 'stop';
type ContentLayout = 'default' | 'original' | 'subfolder';

type Props = {
  settings: {
    category: string;
    postImportCategory: string | null;
    initialState: InitialState;
    sequential: boolean;
    contentLayout: ContentLayout;
    seedRatio: number | null;
    seedTime: number | null;
  };
};

const props = defineProps<Props>();
const emit = defineEmits<{ (e: 'update', payload: Partial<Props['settings']>): void }>();

const form = reactive({ ...props.settings });
const errors = reactive<Record<string, string | null>>({
  category: null,
  postImportCategory: null,
  initialState: null,
  sequential: null,
  contentLayout: null,
  seedRatio: null,
  seedTime: null,
});

function setError(field: keyof typeof errors, message: string | null) {
  errors[field] = message;
}

async function request(endpoint: string, payload: Record<string, string>) {
  const response = await fetch(endpoint, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams(payload),
  });
  const body = await response.text();
  if (!response.ok || (!response.headers.get('HX-Trigger') && body)) {
    return body || 'Failed to save setting.';
  }
  emit('update', { ...form });
  return '';
}

function validateCategory(value: string | null, required = true) {
  if (!value || !value.trim()) {
    if (required) {
      throw new Error('Category cannot be empty.');
    }
    return '';
  }
  if (!CATEGORY_PATTERN.test(value)) {
    throw new Error("Cannot contain '\\', '//' or start/end with '/'.");
  }
  return value.trim();
}

async function saveCategory() {
  try {
    const value = validateCategory(form.category, true);
    const error = await request('/mamlarr/api/settings/qb-category', { category: value });
    setError('category', error || null);
  } catch (err) {
    setError('category', (err as Error).message);
  }
}

async function savePostCategory() {
  try {
    const value = form.postImportCategory ? validateCategory(form.postImportCategory, false) : '';
    const error = await request('/mamlarr/api/settings/qb-post-category', { category: value ?? '' });
    setError('postImportCategory', error || null);
  } catch (err) {
    setError('postImportCategory', (err as Error).message);
  }
}

async function saveInitialState() {
  const value = form.initialState;
  const error = await request('/mamlarr/api/settings/qb-initial-state', { initial_state: value });
  setError('initialState', error || null);
}

async function saveSequential() {
  const value = form.sequential ? 'true' : 'false';
  const error = await request('/mamlarr/api/settings/qb-sequential', { enabled: value });
  setError('sequential', error || null);
}

async function saveContentLayout() {
  const value = form.contentLayout;
  const error = await request('/mamlarr/api/settings/qb-content-layout', { content_layout: value });
  setError('contentLayout', error || null);
}

function validateRatio(value: number | null) {
  if (value == null || value === 0) {
    return '';
  }
  if (value < 1) {
    throw new Error('Seed ratio must be at least 1.0.');
  }
  return value.toString();
}

async function saveSeedRatio() {
  try {
    const val = validateRatio(form.seedRatio ?? null);
    const error = await request('/mamlarr/api/settings/qb-seed-ratio', { seed_ratio: val });
    setError('seedRatio', error || null);
  } catch (err) {
    setError('seedRatio', (err as Error).message);
  }
}

function validateSeedTime(value: number | null) {
  if (value == null || value === 0) {
    return '';
  }
  if (value < 1) {
    throw new Error('Seed time must be at least 1 minute.');
  }
  return value.toString();
}

async function saveSeedTime() {
  try {
    const val = validateSeedTime(form.seedTime ?? null);
    const error = await request('/mamlarr/api/settings/qb-seed-time', { seed_time: val });
    setError('seedTime', error || null);
  } catch (err) {
    setError('seedTime', (err as Error).message);
  }
}
</script>

<style scoped>
.qbit-settings {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}
.text-muted,
small {
  color: var(--muted-color, #6b7280);
}
.error {
  color: #dc2626;
  font-size: 0.85rem;
}
.toggle-field {
  display: flex;
  gap: 0.75rem;
  align-items: center;
}
.toggle-field input {
  width: 1.25rem;
  height: 1.25rem;
}
button {
  align-self: flex-start;
}
</style>

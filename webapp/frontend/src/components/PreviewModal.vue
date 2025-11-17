<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="show"
        class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
        @click.self="$emit('close')"
      >
        <div class="glass rounded-lg shadow-2xl max-w-4xl w-full max-h-[90vh] flex flex-col">
          <!-- Header -->
          <div class="flex items-center justify-between p-6 border-b border-gray-700">
            <div>
              <h2 class="text-2xl font-bold">{{ title }}</h2>
              <p class="text-sm text-gray-400 mt-1">
                {{ previewInfo }}
              </p>
            </div>
            <button
              @click="$emit('close')"
              class="btn btn-secondary"
              aria-label="Close"
            >
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <!-- Content -->
          <div class="flex-1 overflow-hidden p-6">
            <!-- Loading State -->
            <div v-if="loading" class="flex items-center justify-center h-full">
              <div class="text-center">
                <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-500 mx-auto mb-4"></div>
                <p class="text-gray-400">Loading preview...</p>
              </div>
            </div>

            <!-- Error State -->
            <div v-else-if="error" class="flex items-center justify-center h-full">
              <div class="text-center text-red-400">
                <svg class="w-16 h-16 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <p class="font-bold mb-2">Failed to load preview</p>
                <p class="text-sm">{{ error }}</p>
              </div>
            </div>

            <!-- Preview Content -->
            <div v-else class="h-full flex flex-col">
              <!-- Toolbar -->
              <div class="flex items-center justify-between mb-4 pb-3 border-b border-gray-700">
                <div class="flex items-center gap-2">
                  <svg class="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  <span class="text-sm text-gray-400">UltraStar Format</span>
                </div>
                <div class="flex items-center gap-2">
                  <label class="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      v-model="wordWrap"
                      class="rounded"
                    />
                    <span class="text-gray-400">Word wrap</span>
                  </label>
                </div>
              </div>

              <!-- Text Editor -->
              <div class="flex-1 overflow-auto">
                <textarea
                  v-model="content"
                  :class="[
                    'w-full h-full min-h-[400px] p-4 bg-gray-900 text-gray-100 rounded-lg font-mono text-sm',
                    'border border-gray-700 focus:border-primary-500 focus:outline-none',
                    'resize-none',
                    wordWrap ? 'whitespace-pre-wrap' : 'whitespace-pre'
                  ]"
                  spellcheck="false"
                  readonly
                ></textarea>
              </div>

              <!-- Info Footer -->
              <div class="mt-4 pt-3 border-t border-gray-700 text-xs text-gray-500 flex justify-between">
                <span>Lines: {{ lineCount }}</span>
                <span v-if="!isComplete" class="text-yellow-400">
                  ⚠️ Showing first {{ previewLines }} lines of {{ totalLines }} total
                </span>
                <span v-else class="text-green-400">
                  ✓ Complete file
                </span>
              </div>
            </div>
          </div>

          <!-- Footer Actions -->
          <div class="flex justify-end gap-3 p-6 border-t border-gray-700">
            <button
              @click="$emit('close')"
              class="btn btn-secondary"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { previewResult } from '@/services/api'

const props = defineProps({
  show: {
    type: Boolean,
    required: true,
  },
  jobId: {
    type: String,
    default: null,
  },
  title: {
    type: String,
    default: 'Preview Result',
  },
})

defineEmits(['close'])

const loading = ref(false)
const error = ref(null)
const content = ref('')
const totalLines = ref(0)
const previewLines = ref(0)
const isComplete = ref(true)
const wordWrap = ref(false)

const lineCount = computed(() => {
  return content.value.split('\n').length
})

const previewInfo = computed(() => {
  if (loading.value) return 'Loading...'
  if (error.value) return 'Error'
  if (isComplete.value) return `Complete file (${totalLines.value} lines)`
  return `Preview (${previewLines.value} of ${totalLines.value} lines)`
})

// Load preview when modal opens or jobId changes
watch(
  () => [props.show, props.jobId],
  async ([newShow, newJobId]) => {
    if (newShow && newJobId) {
      await loadPreview(newJobId)
    }
  },
  { immediate: true }
)

const loadPreview = async (jobId) => {
  loading.value = true
  error.value = null
  content.value = ''

  try {
    const data = await previewResult(jobId)
    content.value = data.content
    totalLines.value = data.total_lines
    previewLines.value = data.preview_lines
    isComplete.value = data.is_complete
  } catch (err) {
    error.value = err.response?.data?.detail || err.message || 'Failed to load preview'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.3s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-active .glass,
.modal-leave-active .glass {
  transition: transform 0.3s ease;
}

.modal-enter-from .glass,
.modal-leave-to .glass {
  transform: scale(0.95);
}
</style>

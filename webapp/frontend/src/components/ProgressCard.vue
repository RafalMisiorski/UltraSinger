<template>
  <div class="card p-6">
    <div class="flex items-center justify-between mb-4">
      <div class="flex-1 min-w-0">
        <h3 class="text-lg font-bold truncate">
          {{ displayName }}
        </h3>
        <p v-if="queueMessage" class="text-sm text-gray-400 mt-1">
          {{ queueMessage }}
        </p>
      </div>
      <span
        :class="[
          'px-3 py-1 rounded-full text-xs font-bold ml-3',
          statusColors[job.status]
        ]"
      >
        {{ job.status.toUpperCase() }}
      </span>
    </div>

    <!-- Progress Bar -->
    <div v-if="job.status === 'processing' || job.status === 'queued'" class="mb-4">
      <div class="flex justify-between text-sm mb-2">
        <span class="text-gray-400">{{ currentStepMessage }}</span>
        <span class="text-primary-400 font-bold">{{ progressPercentage }}%</span>
      </div>
      <div class="w-full bg-gray-700 rounded-full h-2 overflow-hidden mb-2">
        <div
          class="bg-gradient-to-r from-primary-500 to-primary-400 h-full transition-all duration-300 ease-out"
          :style="{ width: progressPercentage + '%' }"
        >
          <div class="w-full h-full animate-pulse-slow"></div>
        </div>
      </div>
      <!-- Time Information -->
      <div class="flex justify-between text-xs text-gray-500">
        <span v-if="elapsedTime">⏱️ {{ elapsedTime }} elapsed</span>
        <span v-if="estimatedRemaining" class="text-primary-400">~{{ estimatedRemaining }} remaining</span>
      </div>
    </div>

    <!-- Step Indicators -->
    <div v-if="job.status === 'processing'" class="mb-4">
      <div class="space-y-2">
        <div
          v-for="step in steps"
          :key="step.key"
          class="flex items-center gap-3 text-sm"
        >
          <!-- Icon -->
          <div
            :class="[
              'w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0',
              getStepStatus(step.key) === 'completed' ? 'bg-green-500' :
              getStepStatus(step.key) === 'active' ? 'bg-primary-500 animate-pulse' :
              'bg-gray-700'
            ]"
          >
            <svg
              v-if="getStepStatus(step.key) === 'completed'"
              class="w-4 h-4 text-white"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
            </svg>
            <svg
              v-else-if="getStepStatus(step.key) === 'active'"
              class="w-4 h-4 text-white animate-spin"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <div v-else class="w-2 h-2 bg-gray-500 rounded-full"></div>
          </div>

          <!-- Label -->
          <span
            :class="[
              getStepStatus(step.key) === 'completed' ? 'text-green-400' :
              getStepStatus(step.key) === 'active' ? 'text-primary-400 font-medium' :
              'text-gray-500'
            ]"
          >
            {{ step.label }}
          </span>
        </div>
      </div>
    </div>

    <!-- Success State -->
    <div v-if="job.status === 'completed'" class="mb-4">
      <div class="flex items-center gap-3 text-green-400 mb-3">
        <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <span class="font-bold">Processing completed successfully!</span>
      </div>

      <!-- Regular (Solo) Download -->
      <a
        v-if="!job.is_duet"
        :href="downloadUrl"
        download
        class="btn btn-primary w-full"
      >
        <svg class="w-5 h-5 mr-2 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
        </svg>
        Download UltraStar File
      </a>

      <!-- Duet Downloads -->
      <div v-else class="space-y-3">
        <h4 class="font-bold text-green-400 flex items-center gap-2">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
          </svg>
          Duet files ready!
        </h4>

        <!-- Primary duet file -->
        <a
          :href="downloadDuetUrl"
          download
          class="btn btn-primary w-full"
        >
          <svg class="w-5 h-5 mr-2 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
          Download Duet File (P1 + P2)
        </a>

        <!-- Solo files -->
        <div class="grid grid-cols-2 gap-2">
          <a
            :href="downloadSolo1Url"
            download
            class="btn btn-secondary text-sm py-2"
          >
            <svg class="w-4 h-4 mr-1 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
            {{ job.speaker_1_name || 'Singer 1' }}
          </a>
          <a
            :href="downloadSolo2Url"
            download
            class="btn btn-secondary text-sm py-2"
          >
            <svg class="w-4 h-4 mr-1 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
            {{ job.speaker_2_name || 'Singer 2' }}
          </a>
        </div>

        <!-- Download All as ZIP -->
        <a
          :href="downloadZipUrl"
          download
          class="btn bg-purple-600 hover:bg-purple-700 text-white w-full text-sm"
        >
          <svg class="w-4 h-4 mr-2 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M9 19l3 3m0 0l3-3m-3 3V10" />
          </svg>
          Download All Files (ZIP)
        </a>
      </div>

      <!-- Preview & Export Options -->
      <div class="mt-4 p-4 bg-gray-800/50 rounded-lg border border-gray-700">
        <h4 class="text-sm font-bold mb-3 text-gray-300 flex items-center gap-2">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8.5V8a4 4 0 10-8 0v7.5m14 0h-3m-9 0H2m9-1.5h.01" />
          </svg>
          Preview & Export
        </h4>

        <!-- Preview Button -->
        <button
          @click="$emit('preview', job.job_id)"
          class="btn bg-gray-700 hover:bg-gray-600 text-white w-full mb-3"
        >
          <svg class="w-4 h-4 mr-2 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
          </svg>
          Preview Result
        </button>

        <!-- Export Format Buttons -->
        <div class="text-xs text-gray-400 mb-2">Export as:</div>
        <div class="grid grid-cols-2 gap-2">
          <a
            :href="exportUrl('srt')"
            download
            class="btn btn-secondary text-xs py-2"
            title="SubRip subtitle format"
          >
            <svg class="w-3 h-3 mr-1 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
            </svg>
            SRT
          </a>
          <a
            :href="exportUrl('lrc')"
            download
            class="btn btn-secondary text-xs py-2"
            title="LRC lyrics format"
          >
            <svg class="w-3 h-3 mr-1 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
            </svg>
            LRC
          </a>
          <a
            :href="exportUrl('json')"
            download
            class="btn btn-secondary text-xs py-2"
            title="JSON structured data"
          >
            <svg class="w-3 h-3 mr-1 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
            </svg>
            JSON
          </a>
          <a
            :href="exportUrl('txt')"
            download
            class="btn btn-secondary text-xs py-2"
            title="Plain text lyrics"
          >
            <svg class="w-3 h-3 mr-1 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            TXT
          </a>
        </div>
      </div>
    </div>

    <!-- Error State -->
    <div v-if="job.status === 'failed'" class="mb-4">
      <div class="flex items-center gap-3 text-red-400 mb-2">
        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <span class="font-bold">Processing failed</span>
      </div>
      <p class="text-sm text-gray-400 mb-3">{{ job.error_message || 'Unknown error occurred' }}</p>
    </div>

    <!-- Metadata -->
    <div class="grid grid-cols-2 gap-4 text-sm border-t border-gray-700 pt-4">
      <div>
        <span class="text-gray-400">Language:</span>
        <span class="ml-2 font-medium">{{ languageNames[job.language] }}</span>
      </div>
      <div>
        <span class="text-gray-400">Quality:</span>
        <span class="ml-2 font-medium capitalize">{{ job.quality }}</span>
      </div>
      <div>
        <span class="text-gray-400">Source:</span>
        <span class="ml-2 font-medium capitalize">{{ job.source }}</span>
      </div>
      <div v-if="elapsedTime">
        <span class="text-gray-400">Time:</span>
        <span class="ml-2 font-medium">{{ elapsedTime }}</span>
      </div>
    </div>

    <!-- Actions -->
    <div class="flex gap-2 mt-4">
      <button
        v-if="job.status === 'processing' || job.status === 'queued'"
        @click="$emit('cancel', job.job_id)"
        class="btn btn-secondary flex-1"
      >
        Cancel
      </button>
      <button
        v-if="job.status === 'failed' || job.status === 'cancelled'"
        @click="$emit('retry', job.job_id)"
        class="btn bg-blue-600 hover:bg-blue-700 text-white flex-1"
      >
        <svg class="w-4 h-4 mr-1 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
        Retry
      </button>
      <button
        @click="$emit('delete', job.job_id)"
        class="btn bg-red-600 hover:bg-red-700 text-white flex-1"
      >
        Delete
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useWebSocket } from '@/composables/useWebSocket'
import { downloadResult, downloadZip, exportResult } from '@/services/api'
import { formatDuration, formatTimeRemaining } from '@/utils/time'

const props = defineProps({
  job: {
    type: Object,
    required: true,
  },
})

defineEmits(['cancel', 'delete', 'retry', 'preview'])

const { progress } = useWebSocket(props.job.job_id)

const statusColors = {
  queued: 'bg-yellow-500/20 text-yellow-400',
  processing: 'bg-blue-500/20 text-blue-400',
  completed: 'bg-green-500/20 text-green-400',
  failed: 'bg-red-500/20 text-red-400',
  cancelled: 'bg-gray-500/20 text-gray-400',
}

const languageNames = {
  it: 'Italian',
  en: 'English',
  pl: 'Polish',
}

const steps = [
  { key: 'downloading', label: 'Downloading audio' },
  { key: 'separating', label: 'Separating vocals' },
  { key: 'transcribing', label: 'Transcribing lyrics' },
  { key: 'pitching', label: 'Detecting pitch' },
  { key: 'generating', label: 'Generating file' },
]

// Display name (custom name takes precedence)
const displayName = computed(() => {
  return props.job.custom_name || props.job.title || 'Processing...'
})

// Queue position message
const queueMessage = computed(() => {
  const pos = props.job.queue_position
  if (pos === null || pos === undefined) return null
  if (pos === 0) return '⚡ Currently processing'
  return `📋 Position ${pos} in queue`
})

const currentStepMessage = computed(() => {
  if (progress.value?.message) {
    return progress.value.message
  }
  if (props.job.progress?.message) {
    return props.job.progress.message
  }
  return 'Initializing...'
})

const progressPercentage = computed(() => {
  if (progress.value?.percentage !== undefined) {
    return Math.round(progress.value.percentage)
  }
  if (props.job.progress?.percentage !== undefined) {
    return Math.round(props.job.progress.percentage)
  }
  return 0
})

const getStepStatus = (stepKey) => {
  const currentStep = progress.value?.step || props.job.progress?.step
  const stepIndex = steps.findIndex(s => s.key === stepKey)
  const currentIndex = steps.findIndex(s => s.key === currentStep)

  if (currentIndex === -1) return 'pending'
  if (stepIndex < currentIndex) return 'completed'
  if (stepIndex === currentIndex) return 'active'
  return 'pending'
}

const elapsedTime = computed(() => {
  const seconds = progress.value?.elapsed_seconds || props.job.progress?.elapsed_seconds || props.job.elapsed_seconds
  return seconds ? formatDuration(seconds) : null
})

const estimatedRemaining = computed(() => {
  const elapsed = progress.value?.elapsed_seconds || props.job.progress?.elapsed_seconds || props.job.elapsed_seconds
  const estimated = props.job.estimated_duration_seconds

  if (!estimated || !elapsed) return null
  return formatTimeRemaining(estimated, elapsed)
})

const downloadUrl = computed(() => {
  return downloadResult(props.job.job_id)
})

const downloadDuetUrl = computed(() => {
  return downloadResult(props.job.job_id, 'duet')
})

const downloadSolo1Url = computed(() => {
  return downloadResult(props.job.job_id, 'solo1')
})

const downloadSolo2Url = computed(() => {
  return downloadResult(props.job.job_id, 'solo2')
})

const downloadZipUrl = computed(() => {
  return downloadZip(props.job.job_id)
})

const exportUrl = (format) => {
  return exportResult(props.job.job_id, format)
}
</script>

<template>
  <div class="card p-6">
    <h2 class="text-2xl font-bold mb-6">Create New Karaoke File</h2>

    <!-- Tab Switcher -->
    <div class="flex gap-2 mb-6">
      <button
        @click="sourceType = 'youtube'"
        :class="[
          'btn flex-1',
          sourceType === 'youtube' ? 'btn-primary' : 'btn-secondary'
        ]"
      >
        YouTube URL
      </button>
      <button
        @click="sourceType = 'upload'"
        :class="[
          'btn flex-1',
          sourceType === 'upload' ? 'btn-primary' : 'btn-secondary'
        ]"
      >
        Upload File
      </button>
    </div>

    <!-- YouTube URL Input -->
    <div v-if="sourceType === 'youtube'" class="mb-6">
      <label class="block text-sm font-medium mb-2">YouTube URL</label>
      <input
        v-model="youtubeUrl"
        type="url"
        placeholder="https://www.youtube.com/watch?v=..."
        class="input"
        :class="{ 'border-red-500': errors.youtubeUrl }"
      />
      <p v-if="errors.youtubeUrl" class="text-red-400 text-sm mt-1">
        {{ errors.youtubeUrl }}
      </p>
    </div>

    <!-- File Upload -->
    <div v-if="sourceType === 'upload'" class="mb-6">
      <label class="block text-sm font-medium mb-2">Audio File</label>
      <div
        @drop.prevent="handleDrop"
        @dragover.prevent="isDragging = true"
        @dragleave="isDragging = false"
        :class="[
          'border-2 border-dashed rounded-lg p-8 text-center transition-all',
          isDragging ? 'border-primary-500 bg-primary-500/10' : 'border-gray-600',
          errors.file && 'border-red-500'
        ]"
      >
        <input
          ref="fileInput"
          type="file"
          accept=".mp3,.wav,.ogg,.m4a,.flac"
          @change="handleFileSelect"
          class="hidden"
        />

        <div v-if="!selectedFile">
          <svg class="mx-auto h-12 w-12 text-gray-400 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
          </svg>
          <p class="text-gray-400 mb-2">Drag and drop your audio file here, or</p>
          <button @click="$refs.fileInput.click()" class="btn btn-primary">
            Browse Files
          </button>
          <p class="text-sm text-gray-500 mt-2">Supported: MP3, WAV, OGG, M4A, FLAC</p>
        </div>

        <div v-else class="flex items-center justify-between">
          <div class="flex items-center gap-3">
            <svg class="h-8 w-8 text-primary-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
            </svg>
            <div class="text-left">
              <p class="font-medium">{{ selectedFile.name }}</p>
              <p class="text-sm text-gray-400">{{ formatFileSize(selectedFile.size) }}</p>
            </div>
          </div>
          <button @click="selectedFile = null" class="text-red-400 hover:text-red-300">
            <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>
      <p v-if="errors.file" class="text-red-400 text-sm mt-1">
        {{ errors.file }}
      </p>
    </div>

    <!-- Language Selection -->
    <div class="mb-6">
      <label class="block text-sm font-medium mb-2">Language</label>
      <div class="grid grid-cols-3 gap-3">
        <button
          v-for="lang in languages"
          :key="lang.code"
          @click="selectedLanguage = lang.code"
          :class="[
            'btn py-3',
            selectedLanguage === lang.code ? 'btn-primary' : 'btn-secondary'
          ]"
        >
          <span class="text-2xl mr-2">{{ lang.flag }}</span>
          {{ lang.name }}
        </button>
      </div>
    </div>

    <!-- Quality Preset -->
    <div class="mb-6">
      <label class="block text-sm font-medium mb-2">Quality Preset</label>
      <div class="grid grid-cols-3 gap-3">
        <button
          v-for="preset in qualityPresets"
          :key="preset.value"
          @click="selectedQuality = preset.value"
          :class="[
            'btn py-4 flex flex-col items-start',
            selectedQuality === preset.value ? 'btn-primary' : 'btn-secondary'
          ]"
        >
          <span class="font-bold mb-1">{{ preset.name }}</span>
          <span class="text-xs opacity-75">{{ preset.description }}</span>
        </button>
      </div>
    </div>

    <!-- Duet Mode Toggle -->
    <div class="mb-6">
      <div class="flex items-center gap-3 mb-4">
        <input
          id="duet-mode"
          type="checkbox"
          v-model="isDuetMode"
          class="w-5 h-5 rounded border-gray-600 bg-gray-700 text-primary-600 focus:ring-2 focus:ring-primary-500"
        />
        <label for="duet-mode" class="flex items-center gap-2 cursor-pointer">
          <svg class="w-6 h-6 text-primary-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
          </svg>
          <span class="text-lg font-medium">Create Duet Version (2 singers)</span>
        </label>
      </div>

      <!-- Duet Options (shown when enabled) -->
      <transition name="slide-down">
        <div v-if="isDuetMode" class="glass p-4 rounded-lg space-y-4">
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium mb-2">Singer 1 Name (optional)</label>
              <input
                v-model="speaker1Name"
                type="text"
                placeholder="e.g., Lady Gaga"
                class="input"
              />
            </div>
            <div>
              <label class="block text-sm font-medium mb-2">Singer 2 Name (optional)</label>
              <input
                v-model="speaker2Name"
                type="text"
                placeholder="e.g., Bradley Cooper"
                class="input"
              />
            </div>
          </div>

          <!-- Info Box -->
          <div class="bg-blue-500/10 border border-blue-500/30 rounded-lg p-3 flex gap-3">
            <svg class="w-5 h-5 text-blue-400 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div class="text-sm text-blue-300">
              <p class="font-medium mb-1">AI will automatically:</p>
              <ul class="list-disc list-inside space-y-1 text-blue-200">
                <li>Detect and separate the two main vocal tracks</li>
                <li>Create individual karaoke files for each singer</li>
                <li>Generate a combined duet file with P1/P2 markers</li>
              </ul>
              <p class="mt-2 text-xs text-blue-400">
                ⚠️ Processing time will be approximately 2x longer for duets
              </p>
            </div>
          </div>
        </div>
      </transition>
    </div>

    <!-- Submit Button -->
    <button
      @click="handleSubmit"
      :disabled="isSubmitting"
      class="btn btn-primary w-full py-3 text-lg font-bold"
      :class="{ 'opacity-50 cursor-not-allowed': isSubmitting }"
    >
      <span v-if="!isSubmitting">Generate Karaoke File</span>
      <span v-else class="flex items-center justify-center gap-2">
        <svg class="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        Processing...
      </span>
    </button>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { uploadFile, createJob } from '@/services/api'

const emit = defineEmits(['job-created'])

const sourceType = ref('youtube')
const youtubeUrl = ref('')
const selectedFile = ref(null)
const selectedLanguage = ref('en')
const selectedQuality = ref('balanced')
const isDragging = ref(false)
const isSubmitting = ref(false)
const errors = ref({})
const fileInput = ref(null)
// Duet mode
const isDuetMode = ref(false)
const speaker1Name = ref('')
const speaker2Name = ref('')

const languages = [
  { code: 'it', name: 'Italian', flag: '🇮🇹' },
  { code: 'en', name: 'English', flag: '🇬🇧' },
  { code: 'pl', name: 'Polish', flag: '🇵🇱' },
]

const qualityPresets = [
  { value: 'fast', name: 'Fast', description: '~5 min, lower quality' },
  { value: 'balanced', name: 'Balanced', description: '~10 min, good quality' },
  { value: 'accurate', name: 'Accurate', description: '~20 min, best quality' },
]

const handleFileSelect = (event) => {
  const file = event.target.files[0]
  if (file) {
    selectedFile.value = file
    errors.value.file = null
  }
}

const handleDrop = (event) => {
  isDragging.value = false
  const file = event.dataTransfer.files[0]
  if (file) {
    selectedFile.value = file
    errors.value.file = null
  }
}

const formatFileSize = (bytes) => {
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
}

const validateForm = () => {
  errors.value = {}

  if (sourceType.value === 'youtube') {
    if (!youtubeUrl.value) {
      errors.value.youtubeUrl = 'Please enter a YouTube URL'
      return false
    }
    // Basic YouTube URL validation
    const youtubeRegex = /^(https?:\/\/)?(www\.)?(youtube\.com|youtu\.be)\/.+/
    if (!youtubeRegex.test(youtubeUrl.value)) {
      errors.value.youtubeUrl = 'Please enter a valid YouTube URL'
      return false
    }
  } else {
    if (!selectedFile.value) {
      errors.value.file = 'Please select an audio file'
      return false
    }
  }

  return true
}

const handleSubmit = async () => {
  if (!validateForm()) return

  isSubmitting.value = true

  try {
    let uploadFilename = null

    // Upload file if source is upload
    if (sourceType.value === 'upload') {
      const uploadResponse = await uploadFile(selectedFile.value)
      uploadFilename = uploadResponse.filename
    }

    // Create job
    const jobData = {
      source: sourceType.value,
      language: selectedLanguage.value,
      quality: selectedQuality.value,
      youtube_url: sourceType.value === 'youtube' ? youtubeUrl.value : null,
      upload_filename: uploadFilename,
      is_duet: isDuetMode.value,
      speaker_1_name: speaker1Name.value || null,
      speaker_2_name: speaker2Name.value || null,
    }

    const job = await createJob(jobData)
    emit('job-created', job)

    // Reset form
    youtubeUrl.value = ''
    selectedFile.value = null
    errors.value = {}

  } catch (error) {
    console.error('Failed to create job:', error)
    alert('Failed to create job: ' + (error.response?.data?.detail || error.message))
  } finally {
    isSubmitting.value = false
  }
}
</script>

<style scoped>
.slide-down-enter-active,
.slide-down-leave-active {
  transition: all 0.3s ease;
}

.slide-down-enter-from {
  opacity: 0;
  transform: translateY(-10px);
}

.slide-down-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}
</style>

<template>
  <div>
    <div class="flex items-center justify-between mb-6">
      <h2 class="text-2xl font-bold">Job Queue</h2>
      <button @click="refreshJobs" class="btn btn-secondary" :disabled="isLoading">
        <svg class="w-5 h-5" :class="{ 'animate-spin': isLoading }" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
      </button>
    </div>

    <!-- Status Filter Tabs -->
    <div class="flex flex-wrap gap-2 mb-6">
      <button
        v-for="filter in statusFilters"
        :key="filter.value"
        @click="selectedFilter = filter.value"
        :class="[
          'btn px-4 py-2 text-sm',
          selectedFilter === filter.value ? 'btn-primary' : 'btn-secondary'
        ]"
      >
        {{ filter.label }}
        <span
          v-if="filter.count > 0"
          :class="[
            'ml-2 px-2 py-0.5 rounded-full text-xs font-bold',
            selectedFilter === filter.value ? 'bg-white/20' : 'bg-primary-500/20 text-primary-400'
          ]"
        >
          {{ filter.count }}
        </span>
      </button>
    </div>

    <!-- Loading State -->
    <div v-if="isLoading && jobs.length === 0" class="space-y-4">
      <div v-for="i in 3" :key="i" class="card p-6 animate-shimmer"></div>
    </div>

    <!-- Empty State -->
    <div v-else-if="filteredJobs.length === 0 && jobs.length === 0" class="card p-12 text-center">
      <svg class="mx-auto h-16 w-16 text-gray-600 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 13h6m-3-3v6m5 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
      <h3 class="text-xl font-bold mb-2">No jobs yet</h3>
      <p class="text-gray-400">Create your first karaoke file using the form above!</p>
    </div>

    <!-- No Results for Filter -->
    <div v-else-if="filteredJobs.length === 0" class="card p-12 text-center">
      <svg class="mx-auto h-16 w-16 text-gray-600 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
      </svg>
      <h3 class="text-xl font-bold mb-2">No {{ selectedFilter }} jobs</h3>
      <p class="text-gray-400">Try selecting a different filter</p>
    </div>

    <!-- Jobs List -->
    <div v-else class="space-y-4">
      <ProgressCard
        v-for="job in filteredJobs"
        :key="job.job_id"
        :job="job"
        @cancel="handleCancel"
        @delete="handleDelete"
        @retry="handleRetry"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import ProgressCard from './ProgressCard.vue'
import { listJobs, cancelJob, deleteJob, retryJob } from '@/services/api'

const jobs = ref([])
const isLoading = ref(false)
const selectedFilter = ref('all')
let refreshInterval = null

// Computed: Job counts by status
const jobCounts = computed(() => {
  const counts = {
    all: jobs.value.length,
    queued: 0,
    processing: 0,
    completed: 0,
    failed: 0,
    cancelled: 0,
  }

  jobs.value.forEach(job => {
    if (counts[job.status] !== undefined) {
      counts[job.status]++
    }
  })

  return counts
})

// Computed: Filter options with counts
const statusFilters = computed(() => [
  { value: 'all', label: 'All', count: jobCounts.value.all },
  { value: 'processing', label: 'Active', count: jobCounts.value.queued + jobCounts.value.processing },
  { value: 'completed', label: 'Completed', count: jobCounts.value.completed },
  { value: 'failed', label: 'Failed', count: jobCounts.value.failed },
  { value: 'cancelled', label: 'Cancelled', count: jobCounts.value.cancelled },
])

// Computed: Filtered jobs
const filteredJobs = computed(() => {
  if (selectedFilter.value === 'all') {
    return jobs.value
  }

  if (selectedFilter.value === 'processing') {
    return jobs.value.filter(job => job.status === 'queued' || job.status === 'processing')
  }

  return jobs.value.filter(job => job.status === selectedFilter.value)
})

const refreshJobs = async () => {
  isLoading.value = true
  try {
    const response = await listJobs()
    jobs.value = response.jobs
  } catch (error) {
    console.error('Failed to load jobs:', error)
  } finally {
    isLoading.value = false
  }
}

const handleCancel = async (jobId) => {
  try {
    await cancelJob(jobId)
    await refreshJobs()
  } catch (error) {
    console.error('Failed to cancel job:', error)
    alert('Failed to cancel job')
  }
}

const handleRetry = async (jobId) => {
  try {
    await retryJob(jobId)
    await refreshJobs()
    // Switch to "Active" filter to see the new job
    selectedFilter.value = 'processing'
  } catch (error) {
    console.error('Failed to retry job:', error)
    alert('Failed to retry job: ' + (error.response?.data?.detail || error.message))
  }
}

const handleDelete = async (jobId) => {
  if (!confirm('Are you sure you want to delete this job?')) {
    return
  }

  try {
    await deleteJob(jobId)
    await refreshJobs()
  } catch (error) {
    console.error('Failed to delete job:', error)
    alert('Failed to delete job')
  }
}

onMounted(() => {
  refreshJobs()
  // Auto-refresh every 5 seconds
  refreshInterval = setInterval(refreshJobs, 5000)
})

onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
})

defineExpose({
  refreshJobs,
})
</script>

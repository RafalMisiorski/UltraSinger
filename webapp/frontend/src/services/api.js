import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 300000, // 5 minutes for uploads
  headers: {
    'Content-Type': 'application/json',
  },
})

export const uploadFile = async (file, onProgress) => {
  const formData = new FormData()
  formData.append('file', file)

  const response = await api.post('/api/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    onUploadProgress: (progressEvent) => {
      const percentage = Math.round((progressEvent.loaded * 100) / progressEvent.total)
      onProgress?.(percentage)
    },
  })

  return response.data
}

export const uploadBatch = async (files, onProgress) => {
  const formData = new FormData()
  files.forEach(file => {
    formData.append('files', file)
  })

  const response = await api.post('/api/upload/batch', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    onUploadProgress: (progressEvent) => {
      const percentage = Math.round((progressEvent.loaded * 100) / progressEvent.total)
      onProgress?.(percentage)
    },
  })

  return response.data
}

export const createJob = async (jobData) => {
  const response = await api.post('/api/jobs/create', jobData)
  return response.data
}

export const getJob = async (jobId) => {
  const response = await api.get(`/api/jobs/${jobId}`)
  return response.data
}

export const listJobs = async (limit = 50, offset = 0) => {
  const response = await api.get('/api/jobs', {
    params: { limit, offset },
  })
  return response.data
}

export const cancelJob = async (jobId) => {
  const response = await api.post(`/api/jobs/${jobId}/cancel`)
  return response.data
}

export const retryJob = async (jobId) => {
  const response = await api.post(`/api/jobs/${jobId}/retry`)
  return response.data
}

export const deleteJob = async (jobId) => {
  const response = await api.delete(`/api/jobs/${jobId}`)
  return response.data
}

export const downloadResult = (jobId, fileType = 'main') => {
  return `${API_BASE_URL}/api/jobs/${jobId}/download?file_type=${fileType}`
}

export const downloadZip = (jobId) => {
  return `${API_BASE_URL}/api/jobs/${jobId}/download-zip`
}

export const exportResult = (jobId, format) => {
  return `${API_BASE_URL}/api/jobs/${jobId}/export?format=${format}`
}

export const previewResult = async (jobId) => {
  const response = await api.get(`/api/jobs/${jobId}/preview`)
  return response.data
}

export const getYouTubePreview = async (url) => {
  const response = await api.get('/api/youtube/preview', {
    params: { url },
  })
  return response.data
}

export default api

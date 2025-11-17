/**
 * Browser notification utilities
 */

let permissionGranted = false

export const requestNotificationPermission = async () => {
  if (!('Notification' in window)) {
    console.warn('This browser does not support notifications')
    return false
  }

  if (Notification.permission === 'granted') {
    permissionGranted = true
    return true
  }

  if (Notification.permission !== 'denied') {
    const permission = await Notification.requestPermission()
    permissionGranted = permission === 'granted'
    return permissionGranted
  }

  return false
}

export const showNotification = (title, options = {}) => {
  if (!permissionGranted || Notification.permission !== 'granted') {
    return null
  }

  return new Notification(title, {
    icon: '/icon.png',
    badge: '/icon.png',
    ...options,
  })
}

export const notifyJobComplete = (jobTitle, isSuccess = true) => {
  const title = isSuccess ? '✅ Job Completed!' : '❌ Job Failed'
  const body = isSuccess
    ? `${jobTitle} has been processed successfully`
    : `${jobTitle} processing failed`

  return showNotification(title, {
    body,
    tag: 'job-complete',
    requireInteraction: false,
  })
}

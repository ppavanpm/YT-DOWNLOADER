import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import useLocalStorage from './hooks/useLocalStorage'
import { Toast } from './components/Toast'
import { VideoCard } from './components/VideoCard'
import { DownloadProgress } from './components/DownloadProgress'

function App() {
  const [url, setUrl] = useState('')
  const [videoInfo, setVideoInfo] = useState(null)
  const [selectedFormat, setSelectedFormat] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [downloadHistory, setDownloadHistory] = useLocalStorage('downloadHistory', [])
  const [isDarkMode, setIsDarkMode] = useLocalStorage('darkMode', false)
  const [downloadProgress, setDownloadProgress] = useState(0)
  const [isDownloading, setIsDownloading] = useState(false)
  const [toast, setToast] = useState({ show: false, message: '', type: 'info' })

  const API_BASE = 'https://yt-downloader-7oz6.onrender.com'

  useEffect(() => {
    document.documentElement.classList.toggle('dark', isDarkMode)
  }, [isDarkMode])

  const showToast = (message, type = 'info') => {
    setToast({ show: true, message, type })
    setTimeout(() => setToast({ show: false, message: '', type: 'info' }), 3000)
  }

  const validateYouTubeUrl = (url) => {
    const pattern = /^(https?:\/\/)?(www\.)?(youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})$/
    return pattern.test(url)
  }

  const fetchVideoInfo = async () => {
    if (!validateYouTubeUrl(url)) {
      showToast('Please enter a valid YouTube URL', 'error')
      return
    }

    try {
      setLoading(true)
      setError(null)

      const response = await fetch(`${API_BASE}/api/video-info`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ url }),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to fetch video info')
      }

      const data = await response.json()
      setVideoInfo(data)
      setSelectedFormat(data.formats[0]?.format_id)
      showToast('Video information loaded successfully', 'success')
    } catch (err) {
      setError(err.message)
      showToast(err.message, 'error')
    } finally {
      setLoading(false)
    }
  }

  const downloadVideo = async () => {
    try {
      setIsDownloading(true)
      setDownloadProgress(0)

      const response = await fetch(`${API_BASE}/api/download?format_id=${selectedFormat}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ url }),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Download failed')
      }

      const reader = response.body.getReader()
      const contentLength = +response.headers.get('content-length')

      let receivedLength = 0
      const chunks = []

      while (true) {
        const { done, value } = await reader.read()

        if (done) break

        chunks.push(value)
        receivedLength += value.length

        if (contentLength) {
          setDownloadProgress((receivedLength / contentLength) * 100)
        }
      }

      const blob = new Blob(chunks)
      const downloadUrl = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = downloadUrl
      a.download = `${videoInfo.title}.mp4`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(downloadUrl)

      setDownloadHistory(prev => [
        {
          title: videoInfo.title,
          thumbnail: videoInfo.thumbnail,
          timestamp: new Date().toISOString(),
          format: videoInfo.formats.find(f => f.format_id === selectedFormat)?.quality
        },
        ...prev.slice(0, 9),
      ])

      showToast('Download completed successfully', 'success')
    } catch (err) {
      setError(err.message)
      showToast(err.message, 'error')
    } finally {
      setIsDownloading(false)
      setDownloadProgress(0)
    }
  }

  return (
    <div className={`min-h-screen ${isDarkMode ? 'dark bg-gray-900' : 'bg-gray-50'}`}>
      <Toast {...toast} />
      {/* Rest of the component */}
      {isDownloading && (
        <DownloadProgress progress={downloadProgress} />
      )}
    </div>
  )
}

export default App

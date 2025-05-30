import { motion } from 'framer-motion'

export function DownloadProgress({ progress }) {
  return (
    <div className="fixed bottom-4 right-4 w-64 bg-white dark:bg-gray-800 rounded-lg shadow-lg p-4">
      <div className="text-sm font-semibold mb-2 dark:text-white">
        Downloading: {Math.round(progress)}%
      </div>
      <div className="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
        <motion.div
          className="h-full bg-blue-500"
          initial={{ width: 0 }}
          animate={{ width: `${progress}%` }}
          transition={{ duration: 0.3 }}
        />
      </div>
    </div>
  )
}

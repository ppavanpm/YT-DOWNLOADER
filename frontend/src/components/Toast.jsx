import { motion, AnimatePresence } from 'framer-motion'

export function Toast({ show, message, type }) {
  const bgColor = {
    info: 'bg-blue-500',
    success: 'bg-green-500',
    error: 'bg-red-500',
  }[type]

  return (
    <AnimatePresence>
      {show && (
        <motion.div
          initial={{ opacity: 0, y: -50 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -50 }}
          className={`fixed top-4 right-4 ${bgColor} text-white px-6 py-3 rounded-lg shadow-lg z-50`}
        >
          {message}
        </motion.div>
      )}
    </AnimatePresence>
  )
}

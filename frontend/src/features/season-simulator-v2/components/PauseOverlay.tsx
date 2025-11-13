import { motion } from 'framer-motion'
import { Pause } from 'lucide-react'

export const PauseOverlay = () => {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center"
    >
      <motion.div
        initial={{ scale: 0.8, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        className="text-center"
      >
        <Pause className="w-24 h-24 text-white mx-auto mb-4" />
        <h2 className="text-4xl font-bold text-white mb-2">Paused</h2>
        <p className="text-slate-300">Press Space or click Play to resume</p>
      </motion.div>
    </motion.div>
  )
}


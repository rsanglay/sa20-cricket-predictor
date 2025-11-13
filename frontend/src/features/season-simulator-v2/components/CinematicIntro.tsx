import { motion } from 'framer-motion'
import { Play } from 'lucide-react'

interface CinematicIntroProps {
  onStart: () => void
  isLoading?: boolean
}

export const CinematicIntro = ({ onStart, isLoading = false }: CinematicIntroProps) => {
  return (
    <div className="min-h-[calc(100vh-4rem)] bg-gradient-to-br from-slate-900 via-blue-900 to-slate-900 relative overflow-hidden">
      {/* Animated gradient background */}
      <div className="absolute inset-0 bg-gradient-to-br from-slate-900 via-blue-900 to-slate-900 animate-gradient-x"></div>
      
      {/* Floating cricket ball animation */}
      <motion.div
        animate={{ 
          y: [0, -20, 0],
          rotate: [0, 360],
          x: [0, 10, 0]
        }}
        transition={{ 
          duration: 4, 
          repeat: Infinity,
          ease: "easeInOut"
        }}
        className="absolute top-20 right-20 opacity-20 text-6xl"
        style={{ willChange: 'transform' }}
      >
        🏏
      </motion.div>
      
      <motion.div
        animate={{ 
          y: [0, -15, 0],
          rotate: [0, -360],
          x: [0, -15, 0]
        }}
        transition={{ 
          duration: 5, 
          repeat: Infinity,
          ease: "easeInOut",
          delay: 1
        }}
        className="absolute top-40 left-20 opacity-15 text-5xl"
        style={{ willChange: 'transform' }}
      >
        ⚾
      </motion.div>

      <div className="relative z-10 flex items-center justify-center min-h-[calc(100vh-4rem)]">
        <motion.div
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 1, ease: 'easeOut' }}
          className="text-center"
        >
          {/* SA20 Logo with pulse animation */}
          <motion.div
            initial={{ y: -50, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.3, duration: 0.8 }}
            className="mb-8"
          >
            <motion.h1
              animate={{ scale: [1, 1.02, 1] }}
              transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
              className="text-9xl font-black text-transparent bg-clip-text bg-gradient-to-r from-orange-400 to-orange-600 mb-4"
              style={{ willChange: 'transform' }}
            >
              SA20
            </motion.h1>
            <motion.div 
              className="w-32 h-1 bg-gradient-to-r from-orange-400 to-orange-600 mx-auto"
              initial={{ width: 0 }}
              animate={{ width: 128 }}
              transition={{ delay: 0.6, duration: 0.8 }}
            />
          </motion.div>

          {/* Title */}
          <motion.h2
            initial={{ y: 50, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.6, duration: 0.8 }}
            className="text-5xl font-bold text-white mb-4"
          >
            Season 2026 Simulation
          </motion.h2>

          {/* Subtitle */}
          <motion.p
            initial={{ y: 50, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.9, duration: 0.8 }}
            className="text-xl text-gray-300 mb-12"
          >
            Experience the entire season in cinematic detail
          </motion.p>

          {/* Enhanced Start Button */}
          <motion.button
            initial={{ y: 50, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            whileHover={!isLoading ? { 
              scale: 1.05, 
              boxShadow: "0 0 25px rgba(251, 146, 60, 0.5)" 
            } : {}}
            whileTap={!isLoading ? { scale: 0.95 } : {}}
            transition={{ delay: 1.2, duration: 0.8 }}
            onClick={(e) => {
              console.log('Button clicked!', e)
              e.preventDefault()
              e.stopPropagation()
              onStart()
            }}
            disabled={isLoading}
            className="group relative px-12 py-6 text-2xl font-bold text-white bg-gradient-to-r from-orange-500 to-orange-600 rounded-full shadow-2xl hover:shadow-orange-500/50 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed overflow-hidden"
            style={{ willChange: 'transform' }}
          >
            {/* Animated background glow */}
            {!isLoading && (
              <motion.div
                className="absolute inset-0 rounded-full bg-gradient-to-r from-orange-400 to-orange-500 opacity-0 group-hover:opacity-100 blur-xl"
                animate={{ scale: [1, 1.2, 1] }}
                transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
              />
            )}
            
            <span className="relative z-10 flex items-center gap-3">
              {isLoading ? (
                <>
                  <motion.div
                    className="w-6 h-6 border-2 border-white border-t-transparent rounded-full"
                    animate={{ rotate: 360 }}
                    transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                  />
                  Loading Simulation...
                </>
              ) : (
                <>
                  <Play className="w-6 h-6" fill="currentColor" />
                  Press Start to Begin
                </>
              )}
            </span>
          </motion.button>
        </motion.div>
      </div>
    </div>
  )
}


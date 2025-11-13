import React from 'react'
import { motion } from 'framer-motion'
import { StartingXIPlayer } from '../../../types/prediction'

interface LineupRevealProps {
  teamName: string
  lineup: StartingXIPlayer[]
  isHomeTeam: boolean
}

const formatRole = (role?: string) => {
  if (!role) return 'Player'
  return role
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char: string) => char.toUpperCase())
}

// Helper to preload image
const preloadImage = (url: string): Promise<void> => {
  return new Promise((resolve) => {
    const img = new Image()
    img.onload = () => resolve()
    img.onerror = () => resolve() // Don't block on error
    img.src = url
    setTimeout(resolve, 2000) // Timeout after 2 seconds
  })
}

export const LineupReveal = React.memo(({ teamName, lineup, isHomeTeam }: LineupRevealProps) => {
  // Pre-load images when component mounts
  React.useEffect(() => {
    const imageUrls = lineup
      .map(player => (player as any).image_url || (player as any).imageUrl)
      .filter(Boolean)
    
    Promise.all(imageUrls.map(url => preloadImage(url)))
  }, [lineup])

  return (
    <div className="flex flex-col items-center justify-center min-h-screen px-4 py-8 overflow-auto">
      {/* Team header */}
      <motion.div 
        initial={{ opacity: 0, y: -50 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        className="text-center mb-8"
      >
        <motion.h2
          initial={{ scale: 0.8 }}
          animate={{ scale: 1 }}
          transition={{ delay: 0.2, type: "spring", stiffness: 200 }}
          className="text-4xl md:text-5xl font-bold text-white mb-2"
        >
          {teamName}
        </motion.h2>
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.4 }}
          className="text-lg md:text-xl text-gray-400"
        >
          Starting XI
        </motion.p>
      </motion.div>

      {/* Players grid - Responsive grid that fits screen */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3 md:gap-4 max-w-7xl w-full px-2">
        {lineup && lineup.length > 0 ? (
          lineup.slice(0, 10).map((player, index) => (
            <motion.div
              key={player.player_id}
              initial={{ opacity: 0, scale: 0.8, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              transition={{ 
                delay: index * 0.1, // Stagger by 100ms each
                duration: 0.4,
                ease: "easeOut"
              }}
              className="relative group"
              style={{ willChange: 'transform, opacity' }}
            >
              {/* Player card with image */}
              <div className="relative aspect-[3/4] rounded-xl overflow-hidden bg-gradient-to-br from-slate-800 to-slate-900 border-2 border-slate-700 group-hover:border-orange-500 transition-colors">
                {/* Player photo with loading state */}
                {(player as any).image_url || (player as any).imageUrl ? (
                  <img 
                    src={(player as any).image_url || (player as any).imageUrl}
                    alt={player.player_name}
                    className="w-full h-full object-cover object-center"
                    style={{ objectFit: 'cover', objectPosition: 'center top' }}
                    loading="eager"
                    onError={(e) => {
                      // Fallback to placeholder if image fails
                      e.currentTarget.style.display = 'none'
                      const placeholder = e.currentTarget.nextElementSibling as HTMLElement
                      if (placeholder) placeholder.style.display = 'flex'
                    }}
                  />
                ) : null}
                
                {/* Placeholder if no image */}
                <div 
                  className="w-full h-full flex items-center justify-center text-4xl font-bold text-slate-400 bg-gradient-to-br from-slate-700 to-slate-800"
                  style={{ display: (player as any).image_url || (player as any).imageUrl ? 'none' : 'flex' }}
                >
                  {player.player_name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)}
                </div>
                
                {/* Gradient overlay for name visibility */}
                <div className="absolute inset-x-0 bottom-0 h-24 bg-gradient-to-t from-black/90 via-black/70 to-transparent" />
                
                {/* Player info */}
                <div className="absolute inset-x-0 bottom-0 p-3 text-center">
                  <p className="text-white font-bold text-sm truncate mb-1">{player.player_name}</p>
                  <p className="text-orange-400 text-xs uppercase">{formatRole(player.role)}</p>
                </div>
              </div>
            </motion.div>
          ))
        ) : (
          <div className="col-span-4 text-center text-slate-400 py-8">
            Lineup not available
          </div>
        )}
      </div>
    </div>
  )
})

LineupReveal.displayName = 'LineupReveal'

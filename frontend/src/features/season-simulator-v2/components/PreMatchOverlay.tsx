import React from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useSimulationStore } from '../store/simulationStore'
import { TossAnimation } from './TossAnimation'
import { LineupReveal } from './LineupReveal'

export const PreMatchOverlay = React.memo(() => {
  const showOverlay = useSimulationStore(state => state.showPreMatchOverlay)
  const preMatchStage = useSimulationStore(state => state.preMatchStage)
  const currentMatch = useSimulationStore(state => state.currentMatch)

  console.log('[PreMatchOverlay] Render check:', { showOverlay, preMatchStage, hasMatch: !!currentMatch, hasPrediction: !!currentMatch?.prediction_data })

  if (!showOverlay || !currentMatch) {
    console.log('[PreMatchOverlay] Not showing - showOverlay:', showOverlay, 'currentMatch:', !!currentMatch)
    return null
  }

  const prediction = currentMatch.prediction_data
  if (!prediction) {
    console.log('[PreMatchOverlay] Not showing - no prediction data')
    return null
  }
  
  console.log('[PreMatchOverlay] Rendering overlay with stage:', preMatchStage)

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: showOverlay ? 1 : 0 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.5 }}
      className="fixed inset-0 z-50 bg-slate-900/95 backdrop-blur-sm"
      style={{ 
        willChange: 'opacity, transform',
        transform: 'translateZ(0)',
        backfaceVisibility: 'hidden',
        display: showOverlay ? 'block' : 'none',
      }}
    >
      <AnimatePresence mode="wait">
        {preMatchStage === 'toss' && (
          <TossAnimation
            key="toss"
            homeTeam={currentMatch.home_team_name}
            awayTeam={currentMatch.away_team_name}
            tossWinner={currentMatch.toss_winner || 'home'}
            batFirst={currentMatch.bat_first || 'home'}
          />
        )}
        {preMatchStage === 'lineup-team1' && (
          <LineupReveal
            key="lineup-team1"
            teamName={currentMatch.home_team_name}
            lineup={prediction.predicted_starting_xi?.home || []}
            isHomeTeam={true}
          />
        )}
        {preMatchStage === 'lineup-team2' && (
          <LineupReveal
            key="lineup-team2"
            teamName={currentMatch.away_team_name}
            lineup={prediction.predicted_starting_xi?.away || []}
            isHomeTeam={false}
          />
        )}
      </AnimatePresence>
    </motion.div>
  )
})

PreMatchOverlay.displayName = 'PreMatchOverlay'


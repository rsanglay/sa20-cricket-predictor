import { motion } from 'framer-motion'
import { LiveMatchCard } from './LiveMatchCard'
import { StandingsTable } from './StandingsTable'
import { RecentResults } from './RecentResults'
import { TopPerformers } from './TopPerformers'
import { PreMatchOverlay } from './PreMatchOverlay'
import { useSimulationStore } from '../store/simulationStore'

export const LeagueSimulation = () => {
  // Use selective subscriptions to prevent unnecessary re-renders
  const currentMatch = useSimulationStore(state => state.currentMatch)
  const matches = useSimulationStore(state => state.matches)
  const standings = useSimulationStore(state => state.standings)
  const currentMatchIndex = useSimulationStore(state => state.currentMatchIndex)
  const topPerformers = useSimulationStore(state => state.topPerformers)
  const isPreparingMatch = useSimulationStore(state => state.isPreparingMatch)
  
  const isMatchCompleted = currentMatch?.completed || false

  return (
    <div className="min-h-[calc(100vh-4rem)] bg-gradient-to-br from-slate-50 to-slate-100 p-8 pb-32">
      <div className="max-w-7xl mx-auto">
        <div className="space-y-2 mb-8">
          <p className="text-xs uppercase tracking-wider font-semibold text-emerald-600">Season Simulation</p>
          <h1 className="text-3xl font-bold text-slate-900">League Stage</h1>
        </div>
        
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-8">
          {/* Main Match Card */}
          <div className="lg:col-span-2">
            <LiveMatchCard match={currentMatch} isCompleted={isMatchCompleted} />
          </div>

          {/* Standings */}
          <div className="lg:col-span-1">
            <StandingsTable standings={standings} />
          </div>
        </div>

        {/* Bottom Row: Recent Results and Top Performers */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <RecentResults matches={matches} />
          <TopPerformers performers={topPerformers} />
        </div>

        {/* Progress Indicator */}
        <div className="mt-8 text-center">
          <motion.div 
            className="text-slate-600 text-sm mb-2"
            key={currentMatchIndex}
            initial={{ opacity: 0, y: -5 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2 }}
          >
            Match {currentMatchIndex + 1} of {matches.length}
          </motion.div>
          <div className="w-full max-w-2xl mx-auto h-2 bg-slate-200 rounded-full overflow-hidden">
            <motion.div
              className="h-full bg-gradient-to-r from-emerald-500 to-emerald-600"
              initial={{ width: 0 }}
              animate={{ width: `${((currentMatchIndex + 1) / matches.length) * 100}%` }}
              transition={{ duration: 0.5, ease: "easeOut" }}
            />
          </div>
        </div>
      </div>

      {/* Loading state while preparing match */}
      {isPreparingMatch && (
        <div className="fixed inset-0 z-40 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center">
          <div className="text-center">
            <motion.div
              className="w-16 h-16 border-4 border-orange-500 border-t-transparent rounded-full mx-auto mb-4"
              animate={{ rotate: 360 }}
              transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
            />
            <p className="text-white text-xl">Preparing match...</p>
          </div>
        </div>
      )}

      {/* Pre-match overlay - rendered on top */}
      <PreMatchOverlay />
    </div>
  )
}


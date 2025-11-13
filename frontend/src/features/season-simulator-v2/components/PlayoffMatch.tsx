import React, { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Team } from '../types'
import { Trophy } from 'lucide-react'
import { predictionsAPI } from '../../../api/endpoints/predictions'
import { matchesAPI } from '../../../api/endpoints/matches'

interface PlayoffMatchProps {
  team1: Team
  team2: Team
  matchType: 'semifinal_1' | 'semifinal_2' | 'eliminator' | 'final'
  onComplete?: (winner: Team, loser: Team) => void
}

const matchTypeLabels = {
  semifinal_1: 'Semifinal 1',
  semifinal_2: 'Semifinal 2',
  eliminator: 'Eliminator',
  final: 'Final',
}

export const PlayoffMatch = ({ team1, team2, matchType, onComplete }: PlayoffMatchProps) => {
  const matchLabel = matchTypeLabels[matchType]
  const [showResult, setShowResult] = useState(false)
  const [winner, setWinner] = useState<Team | null>(null)
  const [loser, setLoser] = useState<Team | null>(null)
  const [homeScore, setHomeScore] = useState<number | null>(null)
  const [awayScore, setAwayScore] = useState<number | null>(null)
  const [isPredicting, setIsPredicting] = useState(true)

  useEffect(() => {
    const predictMatch = async () => {
      try {
        // Get venue ID - we'll need to find a match between these teams or use a default venue
        // For now, let's try to find a match or use venue_id 1 as default
        const matches = await matchesAPI.getAll({ season: 2026 })
        const match = matches.find((m: any) => 
          (m.home_team_id === team1.id && m.away_team_id === team2.id) ||
          (m.home_team_id === team2.id && m.away_team_id === team1.id)
        )
        const venueId = match?.venue_id || 1

        // Determine which team is home (use team1 as home for playoff matches)
        const homeTeamId = team1.id
        const awayTeamId = team2.id

        // Predict match
        const prediction = await predictionsAPI.predictMatch(homeTeamId, awayTeamId, venueId)
        
        // Determine winner based on prediction
        const homeWinProb = prediction.home_win_probability || 50
        const predictedWinner = Math.random() * 100 < homeWinProb ? team1 : team2
        const predictedLoser = predictedWinner.id === team1.id ? team2 : team1

        setWinner(predictedWinner)
        setLoser(predictedLoser)
        setHomeScore(prediction.predicted_scores?.home_score || Math.floor(Math.random() * 50) + 150)
        setAwayScore(prediction.predicted_scores?.away_score || Math.floor(Math.random() * 50) + 150)
        setIsPredicting(false)

        // Show result after delay
        setTimeout(() => {
          setShowResult(true)
          if (onComplete && predictedWinner && predictedLoser) {
            setTimeout(() => {
              onComplete(predictedWinner, predictedLoser)
            }, 2000)
          }
        }, 3000)
      } catch (error) {
        console.error('Error predicting playoff match:', error)
        // Fallback: random winner
        const predictedWinner = Math.random() > 0.5 ? team1 : team2
        const predictedLoser = predictedWinner.id === team1.id ? team2 : team1
        setWinner(predictedWinner)
        setLoser(predictedLoser)
        setHomeScore(Math.floor(Math.random() * 50) + 150)
        setAwayScore(Math.floor(Math.random() * 50) + 150)
        setIsPredicting(false)
        setTimeout(() => {
          setShowResult(true)
          if (onComplete) {
            setTimeout(() => {
              onComplete(predictedWinner, predictedLoser)
            }, 2000)
          }
        }, 3000)
      }
    }

    predictMatch()
  }, [team1, team2, matchType, onComplete])

  return (
    <div className="min-h-[calc(100vh-4rem)] bg-gradient-to-br from-[#1a1a2e] via-[#16213e] to-[#0f3460] p-8 flex items-center justify-center">
      <div className="max-w-6xl w-full">
        <motion.h2
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-4xl font-bold text-white mb-8 text-center"
        >
          {matchLabel}
        </motion.h2>

        {isPredicting && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="text-center text-white mb-8"
          >
            <div className="text-xl">Predicting match...</div>
          </motion.div>
        )}

        <div className="grid grid-cols-2 gap-8 mb-8 relative">
          {/* Team 1 */}
          <motion.div
            initial={{ x: -100, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            transition={{ duration: 1 }}
            className={`text-center p-8 rounded-2xl border-2 ${
              winner?.id === team1.id
                ? 'bg-gradient-to-br from-[#FFD700]/20 to-yellow-900/20 border-[#FFD700]'
                : 'bg-slate-800/50 border-slate-700'
            }`}
          >
            <div className="text-3xl font-bold text-white mb-4">{team1.name}</div>
            {showResult && homeScore !== null && (
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                className="text-4xl font-bold text-white mb-2"
              >
                {homeScore}
              </motion.div>
            )}
            {showResult && winner?.id === team1.id && (
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                className="flex items-center justify-center gap-2 text-[#FFD700] mt-4"
              >
                <Trophy className="w-6 h-6" />
                <span className="font-bold">WINNER</span>
              </motion.div>
            )}
          </motion.div>

          {/* VS */}
          <div className="absolute left-1/2 top-1/2 transform -translate-x-1/2 -translate-y-1/2 z-10">
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ delay: 0.5, type: 'spring' }}
              className="text-6xl font-bold text-slate-500"
            >
              VS
            </motion.div>
          </div>

          {/* Team 2 */}
          <motion.div
            initial={{ x: 100, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            transition={{ duration: 1 }}
            className={`text-center p-8 rounded-2xl border-2 ${
              winner?.id === team2.id
                ? 'bg-gradient-to-br from-[#FFD700]/20 to-yellow-900/20 border-[#FFD700]'
                : 'bg-slate-800/50 border-slate-700'
            }`}
          >
            <div className="text-3xl font-bold text-white mb-4">{team2.name}</div>
            {showResult && awayScore !== null && (
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                className="text-4xl font-bold text-white mb-2"
              >
                {awayScore}
              </motion.div>
            )}
            {showResult && winner?.id === team2.id && (
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                className="flex items-center justify-center gap-2 text-[#FFD700] mt-4"
              >
                <Trophy className="w-6 h-6" />
                <span className="font-bold">WINNER</span>
              </motion.div>
            )}
          </motion.div>
        </div>

        {/* Scoreboard Simulation */}
        {showResult && winner && homeScore !== null && awayScore !== null && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-center text-white"
          >
            <div className="text-2xl font-bold mb-2">
              {winner.name} wins by {Math.abs(homeScore - awayScore)} {homeScore > awayScore ? 'runs' : 'wickets'}
            </div>
            <div className="text-slate-400">Player of the Match: TBD</div>
          </motion.div>
        )}
      </div>
    </div>
  )
}

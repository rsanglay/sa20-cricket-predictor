import { motion } from 'framer-motion'
import { useState, useEffect, useRef } from 'react'
import { Team } from '../types'
import { Trophy, Coins } from 'lucide-react'
import { predictionsAPI } from '../../../api/endpoints/predictions'
import { matchesAPI } from '../../../api/endpoints/matches'

interface FinalMatchProps {
  team1: Team
  team2: Team
  onComplete?: (winner: Team) => void
}

export const FinalMatch = ({ team1, team2, onComplete }: FinalMatchProps) => {
  const [phase, setPhase] = useState<'intro' | 'toss' | 'innings1' | 'innings2' | 'result'>('intro')
  const [tossWinner, setTossWinner] = useState<Team | null>(null)
  const [score1, setScore1] = useState(0)
  const [score2, setScore2] = useState(0)
  const [winner, setWinner] = useState<Team | null>(null)
  const winnerRef = useRef<Team | null>(null)

  useEffect(() => {
    const predictMatch = async () => {
      try {
        // Get venue ID
        const matches = await matchesAPI.getAll({ season: 2026 })
        const match = matches.find((m: any) => 
          (m.home_team_id === team1.id && m.away_team_id === team2.id) ||
          (m.home_team_id === team2.id && m.away_team_id === team1.id)
        )
        const venueId = match?.venue_id || 1

        // Predict match
        const prediction = await predictionsAPI.predictMatch(team1.id, team2.id, venueId)
        
        // Determine winner based on prediction
        const homeWinProb = prediction.home_win_probability || 50
        const predictedWinner = Math.random() * 100 < homeWinProb ? team1 : team2
        setWinner(predictedWinner)
        winnerRef.current = predictedWinner
        setScore1(prediction.predicted_scores?.home_score || Math.floor(Math.random() * 50) + 150)
        setScore2(prediction.predicted_scores?.away_score || Math.floor(Math.random() * 50) + 150)
      } catch (error) {
        console.error('Error predicting final match:', error)
        // Fallback: random winner
        const predictedWinner = Math.random() > 0.5 ? team1 : team2
        setWinner(predictedWinner)
        winnerRef.current = predictedWinner
        setScore1(Math.floor(Math.random() * 50) + 150)
        setScore2(Math.floor(Math.random() * 50) + 150)
      }
    }

    predictMatch()

    const timers = [
      setTimeout(() => setPhase('toss'), 2000),
      setTimeout(() => {
        setTossWinner(Math.random() > 0.5 ? team1 : team2)
        setPhase('innings1')
      }, 4000),
      setTimeout(() => {
        setPhase('innings2')
      }, 8000),
      setTimeout(() => {
        setPhase('result')
      }, 12000),
      setTimeout(() => {
        if (onComplete && winnerRef.current) {
          onComplete(winnerRef.current)
        }
      }, 15000),
    ]

    return () => {
      timers.forEach(clearTimeout)
    }
  }, [team1, team2, onComplete])

  return (
    <div className="min-h-[calc(100vh-4rem)] bg-gradient-to-br from-[#1a1a2e] via-[#16213e] to-[#0f3460] p-8 flex items-center justify-center">
      <div className="max-w-6xl w-full">
        <motion.h1
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          className="text-6xl font-black text-transparent bg-clip-text bg-gradient-to-r from-[#FFD700] to-[#FF6B35] mb-12 text-center"
        >
          GRAND FINAL
        </motion.h1>

        <div className="grid grid-cols-2 gap-8 mb-8">
          {/* Team 1 */}
          <motion.div
            initial={{ x: -100, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            className={`text-center p-8 rounded-2xl border-2 ${
              winner?.id === team1.id
                ? 'bg-gradient-to-br from-[#FFD700]/30 to-yellow-900/30 border-[#FFD700]'
                : 'bg-slate-800/50 border-slate-700'
            }`}
          >
            <div className="text-4xl font-bold text-white mb-4">{team1.name}</div>
            {phase === 'result' && (
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                className="text-5xl font-bold text-white mb-2"
              >
                {score1}
              </motion.div>
            )}
            {winner?.id === team1.id && (
              <motion.div
                initial={{ scale: 0, rotate: -180 }}
                animate={{ scale: 1, rotate: 0 }}
                className="flex items-center justify-center gap-2 text-[#FFD700] mt-4"
              >
                <Trophy className="w-8 h-8" />
                <span className="text-2xl font-bold">CHAMPIONS</span>
              </motion.div>
            )}
          </motion.div>

          {/* VS */}
          <div className="absolute left-1/2 top-1/2 transform -translate-x-1/2 -translate-y-1/2 z-10">
            <motion.div
              initial={{ scale: 0, rotate: -180 }}
              animate={{ scale: 1, rotate: 0 }}
              transition={{ type: 'spring', stiffness: 200 }}
              className="text-7xl font-black text-slate-500"
            >
              VS
            </motion.div>
          </div>

          {/* Team 2 */}
          <motion.div
            initial={{ x: 100, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            className={`text-center p-8 rounded-2xl border-2 ${
              winner?.id === team2.id
                ? 'bg-gradient-to-br from-[#FFD700]/30 to-yellow-900/30 border-[#FFD700]'
                : 'bg-slate-800/50 border-slate-700'
            }`}
          >
            <div className="text-4xl font-bold text-white mb-4">{team2.name}</div>
            {phase === 'result' && (
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                className="text-5xl font-bold text-white mb-2"
              >
                {score2}
              </motion.div>
            )}
            {winner?.id === team2.id && (
              <motion.div
                initial={{ scale: 0, rotate: -180 }}
                animate={{ scale: 1, rotate: 0 }}
                className="flex items-center justify-center gap-2 text-[#FFD700] mt-4"
              >
                <Trophy className="w-8 h-8" />
                <span className="text-2xl font-bold">CHAMPIONS</span>
              </motion.div>
            )}
          </motion.div>
        </div>

        {/* Toss Animation */}
        {phase === 'toss' && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="text-center"
          >
            <motion.div
              animate={{ rotateY: [0, 360, 720, 1080] }}
              transition={{ duration: 2, repeat: Infinity }}
              className="inline-block"
            >
              <Coins className="w-16 h-16 text-[#FFD700] mx-auto" />
            </motion.div>
            <div className="text-white text-xl mt-4">Tossing...</div>
          </motion.div>
        )}

        {/* Match Result */}
        {phase === 'result' && winner && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-center text-white mt-8"
          >
            <div className="text-3xl font-bold mb-2">
              {winner.name} wins by {Math.abs(score1 - score2)} runs!
            </div>
            <div className="text-slate-400">Player of the Match: TBD</div>
          </motion.div>
        )}
      </div>
    </div>
  )
}


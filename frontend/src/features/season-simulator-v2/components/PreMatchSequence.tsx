import { useState } from 'react'
import { Match } from '../types'
import { TossAnimation } from './TossAnimation'
import { LineupReveal } from './LineupReveal'

interface PreMatchSequenceProps {
  match: Match
  onComplete: () => void
}

export const PreMatchSequence = ({ match, onComplete }: PreMatchSequenceProps) => {
  const [showToss, setShowToss] = useState(true)
  const prediction = match.prediction_data

  if (!prediction) {
    onComplete()
    return null
  }

  if (showToss) {
    return (
      <TossAnimation
        homeTeam={match.home_team_name}
        awayTeam={match.away_team_name}
        tossWinner={match.result?.toss_winner_id 
          ? (match.result.toss_winner_id === match.home_team_id ? 'home' : 'away')
          : (match.toss_winner || 'home')}
        batFirst={match.result?.toss_decision 
          ? (match.result.toss_decision === 'bat' 
              ? (match.result.toss_winner_id === match.home_team_id ? 'home' : 'away')
              : (match.result.toss_winner_id === match.home_team_id ? 'away' : 'home'))
          : (match.bat_first || 'home')}
        onComplete={() => setShowToss(false)}
      />
    )
  }

  return (
    <LineupReveal
      homeTeam={match.home_team_name}
      awayTeam={match.away_team_name}
      homeLineup={prediction.predicted_starting_xi?.home || []}
      awayLineup={prediction.predicted_starting_xi?.away || []}
      onComplete={onComplete}
    />
  )
}


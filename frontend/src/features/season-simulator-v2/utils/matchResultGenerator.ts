import { MatchResult } from '../types'
import { Team } from '../types'

interface MatchResultGeneratorOptions {
  homeTeam: Team
  awayTeam: Team
  prediction: {
    home_win_probability: number
    away_win_probability: number
  }
  determinedWinner: 'home' | 'away' // Based on probability roll
  venue: {
    id: number
    avg_first_innings_score?: number | null
  }
  seededRandom: () => number // Deterministic random function
  existingTossResult?: {
    toss_winner_id: number
    toss_decision: 'bat' | 'bowl'
  } // Optional: use existing toss result if available
}

export function generateRealisticMatchResult(options: MatchResultGeneratorOptions): MatchResult {
  const { homeTeam, awayTeam, prediction, determinedWinner, venue, seededRandom, existingTossResult } = options

  // Use existing toss result if provided, otherwise generate deterministically
  let tossWinner: 'home' | 'away'
  let tossDecision: 'bat' | 'bowl'

  if (existingTossResult) {
    tossWinner = existingTossResult.toss_winner_id === homeTeam.id ? 'home' : 'away'
    tossDecision = existingTossResult.toss_decision
  } else {
    // Determine who won toss (random 50/50)
    tossWinner = seededRandom() < 0.5 ? 'home' : 'away'
    // In T20, teams usually bat first 60% of time if they win toss
    tossDecision = seededRandom() < 0.6 ? 'bat' : 'bowl'
  }

  // Determine batting order based on toss
  let firstBattingTeam: Team
  let secondBattingTeam: Team

  if ((tossWinner === 'home' && tossDecision === 'bat') || (tossWinner === 'away' && tossDecision === 'bowl')) {
    firstBattingTeam = homeTeam
    secondBattingTeam = awayTeam
  } else {
    firstBattingTeam = awayTeam
    secondBattingTeam = homeTeam
  }

  // Generate realistic first innings score
  // Use venue average and team batting strength
  const venueAvgScore = venue.avg_first_innings_score || 165
  // Simple team strength based on win probability (normalized)
  const teamStrength = firstBattingTeam.id === homeTeam.id
    ? 0.9 + (prediction.home_win_probability / 100) * 0.3 // 0.9 to 1.2 range
    : 0.9 + (prediction.away_win_probability / 100) * 0.3

  const firstInningsRuns = Math.round(
    venueAvgScore * teamStrength * (0.85 + seededRandom() * 0.3) // Add variance
  )

  // Clamp to realistic T20 range (100-250)
  const clampedFirstInnings = Math.max(100, Math.min(250, firstInningsRuns))

  // Generate wickets (most teams lose 4-8 wickets)
  const firstInningsWickets = Math.floor(4 + seededRandom() * 5)

  // Overs (usually 20, sometimes less if all out)
  const firstInningsOvers = firstInningsWickets === 10
    ? 15 + seededRandom() * 4 // All out between 15-19 overs
    : 20

  // Generate second innings based on winner
  let secondInningsRuns: number
  let secondInningsWickets: number
  let secondInningsOvers: number
  let margin: string

  const winnerIsSecondBatting =
    (determinedWinner === 'home' && secondBattingTeam.id === homeTeam.id) ||
    (determinedWinner === 'away' && secondBattingTeam.id === awayTeam.id)

  if (winnerIsSecondBatting) {
    // Second batting team won (successful chase)
    // They need to score target + 1
    const runMargin = 1 + Math.floor(seededRandom() * 15) // Win by 1-15 runs margin
    secondInningsRuns = clampedFirstInnings + runMargin

    // If they won, they didn't lose all wickets
    secondInningsWickets = Math.floor(4 + seededRandom() * 5) // Lost 4-8 wickets

    // Calculate overs based on how comfortable the win was
    if (runMargin > 30) {
      // Comfortable win, finished early
      secondInningsOvers = 16 + seededRandom() * 3
    } else if (runMargin > 15) {
      // Moderate win
      secondInningsOvers = 18 + seededRandom() * 2
    } else {
      // Close win, went to last over
      secondInningsOvers = 19 + seededRandom() * 1
    }

    margin = `${10 - secondInningsWickets} wicket${10 - secondInningsWickets === 1 ? '' : 's'}`
  } else {
    // First batting team won (defended)
    // Second team fell short
    const shortfall = 5 + Math.floor(seededRandom() * 30) // Lost by 5-35 runs
    secondInningsRuns = clampedFirstInnings - shortfall

    // Usually lose more wickets when defending
    secondInningsWickets = Math.floor(6 + seededRandom() * 4) // Lost 6-9 wickets

    // Usually bat full 20 overs when chasing and losing
    secondInningsOvers = 20

    margin = `${shortfall} run${shortfall === 1 ? '' : 's'}`
  }

  return {
    winner_id: determinedWinner === 'home' ? homeTeam.id : awayTeam.id,
    margin,
    first_innings: {
      team_id: firstBattingTeam.id,
      runs: Math.round(clampedFirstInnings),
      wickets: Math.round(firstInningsWickets),
      overs: Math.round(firstInningsOvers * 10) / 10, // Round to 1 decimal
    },
    second_innings: {
      team_id: secondBattingTeam.id,
      runs: Math.round(secondInningsRuns),
      wickets: Math.round(secondInningsWickets),
      overs: Math.round(secondInningsOvers * 10) / 10,
    },
    toss_winner_id: tossWinner === 'home' ? homeTeam.id : awayTeam.id,
    toss_decision: tossDecision,
  }
}


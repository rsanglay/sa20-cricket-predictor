export type SimulationPhase = 
  | 'INTRO'
  | 'FIXTURE_REVEAL'
  | 'LEAGUE'
  | 'QUALIFICATION'
  | 'PLAYOFFS'
  | 'FINAL'
  | 'CHAMPION'
  | 'TROPHY'
  | 'REWIND'
  | 'ANALYTICS'

export type PreMatchStage = 'toss' | 'lineup-team1' | 'lineup-team2' | 'complete' | null

export type SpeedMultiplier = 1 | 2 | 5 | 10

export interface MatchResult {
  winner_id: number
  margin: string // "5 wickets", "23 runs", "Super Over"
  // First innings (team that batted first)
  first_innings: {
    team_id: number
    runs: number
    wickets: number
    overs: number
  }
  // Second innings (team that chased)
  second_innings: {
    team_id: number
    runs: number
    wickets: number
    overs: number
  }
  // Toss data
  toss_winner_id: number
  toss_decision: 'bat' | 'bowl'
  // Top performers in this match
  player_of_match?: string
  top_scorer?: { name: string, runs: number, balls: number }
  best_bowler?: { name: string, wickets: number, runs: number }
}

export interface Match {
  id: number
  match_id: number
  home_team_id: number
  away_team_id: number
  venue_id: number
  home_team_name: string
  away_team_name: string
  venue_name: string
  winner_id?: number
  winner_name?: string
  home_score?: number // Deprecated: use result instead
  away_score?: number // Deprecated: use result instead
  home_win_probability?: number
  away_win_probability?: number
  completed: boolean
  match_type?: 'league' | 'semifinal_1' | 'semifinal_2' | 'eliminator' | 'final'
  no_result?: boolean
  toss_winner?: 'home' | 'away' // Deprecated: use result.toss_winner_id instead
  bat_first?: 'home' | 'away' // Deprecated: use result.toss_decision instead
  prediction_data?: any // Full prediction data including lineups
  // NEW: Simulated match result (generated during simulation)
  result?: MatchResult
}

export interface Standing {
  team_id: number
  team_name: string
  position: number
  matches_played: number
  wins: number
  losses: number
  no_result: number
  points: number
  net_run_rate: number
  playoff_probability: number
  championship_probability: number
}

export interface TopPerformers {
  orangeCap: {
    player_id: number
    player_name: string
    team_name?: string
    runs: number
  } | null
  purpleCap: {
    player_id: number
    player_name: string
    team_name?: string
    wickets: number
  } | null
  mvp: {
    player_id: number
    player_name: string
    team_name?: string
    runs: number
    wickets: number
    score: number
  } | null
}

export interface Team {
  id: number
  name: string
  short_name: string
}

export interface Player {
  id: number
  name: string
  team_id?: number
  team_name?: string
  runs?: number
  wickets?: number
}


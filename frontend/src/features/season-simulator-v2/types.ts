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
  home_score?: number
  away_score?: number
  home_win_probability?: number
  away_win_probability?: number
  completed: boolean
  match_type?: 'league' | 'semifinal_1' | 'semifinal_2' | 'eliminator' | 'final'
  no_result?: boolean
  toss_winner?: 'home' | 'away'
  bat_first?: 'home' | 'away'
  prediction_data?: any // Full prediction data including lineups
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


export interface TeamSeasonStat {
  competition: string
  season: string | number
  team_name: string
  matches_played: number
  wins: number
  total_runs: number
  total_wickets: number
  total_overs: number
  win_percentage: number
  run_rate: number
}

export interface PlayerSeasonStat {
  competition: string
  season: string | number
  team_name?: string
  player_id?: string
  player_name: string
  matches_played: number
  innings: number
  runs: number
  balls: number
  fours: number
  sixes: number
  wickets: number
  runs_conceded: number
  deliveries: number
  strike_rate: number
  economy_rate: number
}

export interface MatchScorecard {
  competition: string
  season: string | number
  match_id: string | number
  match_date?: string
  innings_team: string
  runs_scored: number
  wickets_lost: number
  deliveries_faced: number
  overs_float: number
  winning_team?: string
  winning_margin_runs?: number
}

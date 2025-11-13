export type PlayerRole = 'batsman' | 'bowler' | 'all_rounder' | 'wicket_keeper'

export interface Player {
  id: number
  team_id?: number
  name: string
  role: PlayerRole
  batting_style?: string
  bowling_style?: string
  country: string
  age: number
  birth_date?: string
  auction_price?: number
  image_url?: string
  has_projection?: boolean
}

export interface MatchPerformance {
  match_id: number
  date: string
  opponent: string
  runs: number
  balls_faced: number
  wickets: number
}

export interface CareerStats {
  matches_played: number
  runs_scored: number
  batting_average: number
  strike_rate: number
  highest_score: number
  fours: number
  sixes: number
  fifties: number
  hundreds: number
  wickets_taken: number
  bowling_average?: number
  economy_rate?: number
  best_bowling_figures?: string
  five_wickets: number
}

export interface RecentForm {
  last_5_matches: MatchPerformance[]
  trend: 'improving' | 'declining' | 'stable'
}

export interface SeasonBattingStats {
  matches: number
  runs: number
  highest_score: number
  average: number
  strike_rate: number
  balls_faced: number
  fours: number
  sixes: number
}

export interface SeasonBowlingStats {
  matches: number
  balls: number
  runs: number
  wickets: number
  average: number
  economy: number
  strike_rate: number
  best_figures?: string
  five_wickets: number
}

export interface SeasonStats {
  season: number
  team: string
  batting: SeasonBattingStats
  bowling: SeasonBowlingStats
}

export interface PlayerDetail extends Player {
  international_caps: number
  career_stats: CareerStats
  season_stats: SeasonStats[]
  recent_form: RecentForm
}

export interface PlayerProjection {
  player_id: number
  team_id?: number
  player_name: string
  predicted_runs: number
  predicted_wickets: number
  features: Record<string, number>
}

export interface PlayerStats {
  player_id: number
  season?: number
  batting: Record<string, number>
  bowling?: Record<string, number>
}

export interface TopRunScorer {
  player_id: number
  player_name: string
  predicted_runs: number
}

export interface TopWicketTaker {
  player_id: number
  player_name: string
  predicted_wickets: number
}

export interface StartingXIPlayer {
  player_id: number
  player_name: string
  role?: string
  team_name?: string
  predicted_runs: number
  predicted_wickets: number
}

export interface ManOfTheMatch {
  player_id: number
  player_name: string
  team: string
  team_name: string
  predicted_runs: number
  predicted_wickets: number
}

export interface PredictedScores {
  home_score: number
  home_wickets: number
  away_score: number
  away_wickets: number
  first_innings_score: number
  first_innings_wickets: number
  second_innings_score: number
  second_innings_wickets: number
  first_team: string
  second_team: string
}

export interface MatchResult {
  winner: string
  result_type: 'runs' | 'wickets'
  result_text: string
  margin: number
}

export interface Top3RunScorer {
  player_id: number
  player_name: string
  predicted_runs: number
}

export interface Top3WicketTaker {
  player_id: number
  player_name: string
  predicted_wickets: number
}

export interface MatchPrediction {
  home_team: string
  away_team: string
  venue: string
  home_win_probability: number
  away_win_probability: number
  predicted_winner: string
  confidence: number
  key_factors: Array<[string, number]>
  toss_winner: string
  bat_first: string
  predicted_scores: PredictedScores
  match_result: MatchResult
  top_run_scorers: {
    home: TopRunScorer | null
    away: TopRunScorer | null
  }
  top_3_run_scorers: {
    home: Top3RunScorer[]
    away: Top3RunScorer[]
  }
  top_wicket_takers: {
    home: TopWicketTaker | null
    away: TopWicketTaker | null
  }
  top_3_wicket_takers: {
    home: Top3WicketTaker[]
    away: Top3WicketTaker[]
  }
  man_of_the_match: ManOfTheMatch | null
  predicted_starting_xi?: {
    home: StartingXIPlayer[]
    away: StartingXIPlayer[]
  }
}

export interface Standing {
  team_id: number
  avg_position: number
  avg_points: number
  position_std: number
  playoff_probability: number
  championship_probability: number
}

export interface OrangeCap {
  player_id: number
  player_name: string
  team_id?: number
  team_name?: string
  avg_runs: number
  total_runs_range: [number, number]
}

export interface PurpleCap {
  player_id: number
  player_name: string
  team_id?: number
  team_name?: string
  avg_wickets: number
  total_wickets_range: [number, number]
}

export interface Champion {
  team_id: number
  team_name?: string
  win_probability: number
}

export interface MVP {
  player_id: number
  player_name: string
  team_id?: number
  team_name?: string
  avg_runs: number
  avg_wickets: number
  mvp_score: number
}

export interface TeamOfTournamentPlayer {
  player_id: number
  player_name: string
  team_id?: number
  team_name?: string
  role: string
  avg_runs: number
  avg_wickets: number
  performance_score: number
}

export interface UpsetTracker {
  team_id: number
  team_name: string
  expected_position: number
  actual_avg_position: number
  improvement: number
}

export interface SeasonPrediction {
  predicted_standings: Standing[]
  playoff_probabilities: Record<number, number>
  championship_probabilities: Record<number, number>
  num_simulations: number
  orange_cap?: OrangeCap | null
  purple_cap?: PurpleCap | null
  champion?: Champion | null
  mvp?: MVP | null
  team_of_tournament?: TeamOfTournamentPlayer[]
  upset_tracker?: UpsetTracker[]
}

export type StandingsPrediction = Standing[]

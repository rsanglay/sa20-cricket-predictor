import { apiClient } from '../client'

export interface BattingOrderRequest {
  xi_player_ids: number[]
  wickets_fallen: number
  overs_left: number
  striker_id?: number
  non_striker_id?: number
  venue_id?: number
}

export interface BowlingChangeRequest {
  available_bowlers: number[]
  remaining_overs: number
  wickets_down: number
  striker_id?: number
  non_striker_id?: number
  current_bowler_id?: number
  phase?: string
  overs_ahead?: number
}

export interface DRSRequest {
  delivery_type: string
  line: string
  length: string
  batter_id: number
  bowler_id: number
  match_id: number
  phase?: string
  umpire_id?: number
}

export interface PowerplayRequest {
  batting_team_id: number
  bowling_team_id: number
  venue_id?: number
  wickets_down?: number
  overs_completed?: number
}

export const strategyAPI = {
  suggestBattingOrder: (request: BattingOrderRequest) =>
    apiClient.post('/strategy/batting-order', request),

  recommendBowlingChange: (request: BowlingChangeRequest) =>
    apiClient.post('/strategy/bowling-change', request),

  drsReviewAdvice: (request: DRSRequest) =>
    apiClient.post('/strategy/drs', request),

  powerplayStrategy: (request: PowerplayRequest) =>
    apiClient.post('/strategy/powerplay', request)
}


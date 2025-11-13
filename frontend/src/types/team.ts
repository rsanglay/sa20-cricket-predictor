export interface Team {
  id: number
  name: string
  short_name: string
  home_venue?: string
  founded_year?: number
}

export interface TeamDetail extends Team {
  squad_size: number
  squad_value: number
  avg_age: number
  international_players: number
  role_distribution: Record<string, number>
}

export interface TeamComparison {
  teams: TeamDetail[]
  comparison: {
    avg_squad_value: number[]
    avg_age: number[]
    international_players: number[]
  }
}

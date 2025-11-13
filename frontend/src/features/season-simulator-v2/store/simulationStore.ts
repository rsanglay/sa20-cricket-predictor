import { create } from 'zustand'
import { SimulationPhase, SpeedMultiplier, Match, Standing, TopPerformers, Team, PreMatchStage } from '../types'

interface SimulationState {
  // Phase management
  phase: SimulationPhase
  setPhase: (phase: SimulationPhase) => void
  
  // Data
  matches: Match[]
  standings: Standing[]
  topPerformers: TopPerformers
  playoffTeams: Team[]
  champion: Team | null
  
  // Playoff tracking
  semifinal1Winner: Team | null
  semifinal1Loser: Team | null
  semifinal2Winner: Team | null
  semifinal2Loser: Team | null
  eliminatorWinner: Team | null
  
  // Current animation
  currentMatchIndex: number
  currentMatch: Match | null
  currentPlayoffPhase: 'semifinal_1' | 'semifinal_2' | 'eliminator' | 'final' | null
  
  // Controls
  isPlaying: boolean
  isPaused: boolean
  speedMultiplier: SpeedMultiplier
  
  // Actions
  startSimulation: () => Promise<void>
  pauseSimulation: () => void
  resumeSimulation: () => void
  setSpeed: (speed: SpeedMultiplier) => void
  skipToPlayoffs: () => void
  skipToFinal: () => void
  reset: () => void
  
  // Internal state
  simulationData: any | null
  setSimulationData: (data: any) => void
  setMatches: (matches: Match[]) => void
  setStandings: (standings: Standing[]) => void
  setTopPerformers: (performers: TopPerformers) => void
  setPlayoffTeams: (teams: Team[]) => void
  setChampion: (team: Team | null) => void
  setCurrentMatchIndex: (index: number) => void
  setCurrentMatch: (match: Match | null) => void
  setSemifinal1Winner: (team: Team | null) => void
  setSemifinal1Loser: (team: Team | null) => void
  setSemifinal2Winner: (team: Team | null) => void
  setSemifinal2Loser: (team: Team | null) => void
  setEliminatorWinner: (team: Team | null) => void
  setCurrentPlayoffPhase: (phase: 'semifinal_1' | 'semifinal_2' | 'eliminator' | 'final' | null) => void
  
  // Batched update function for match completion (reduces re-renders)
  updateMatchComplete: (updates: {
    standings: Standing[]
    topPerformers: TopPerformers
    currentMatchIndex: number
    matches: Match[]
  }) => void
  
  // Pre-match overlay state (no phase switching, overlay stays in LEAGUE phase)
  showPreMatchOverlay: boolean
  preMatchStage: PreMatchStage
  isPreparingMatch: boolean
  startPreMatchSequence: () => void
  setPreMatchStage: (stage: PreMatchStage) => void
  completePreMatchSequence: () => void
  setIsPreparingMatch: (preparing: boolean) => void
}

export const useSimulationStore = create<SimulationState>((set, get) => ({
  // Initial state
  phase: 'INTRO',
  matches: [],
  standings: [],
  topPerformers: {
    orangeCap: null,
    purpleCap: null,
    mvp: null,
  },
  playoffTeams: [],
  champion: null,
  semifinal1Winner: null,
  semifinal1Loser: null,
  semifinal2Winner: null,
  semifinal2Loser: null,
  eliminatorWinner: null,
  currentMatchIndex: 0,
  currentMatch: null,
  currentPlayoffPhase: null,
  isPlaying: false,
  isPaused: false,
  speedMultiplier: 1,
  simulationData: null,
  showPreMatchOverlay: false,
  preMatchStage: null,
  isPreparingMatch: false,
  
  // Actions
  setPhase: (phase) => set({ phase }),
  
  startSimulation: async () => {
    set({ isPlaying: true, isPaused: false })
    // Simulation logic will be handled by useSimulation hook
  },
  
  pauseSimulation: () => set({ isPaused: true, isPlaying: false }),
  
  resumeSimulation: () => set({ isPaused: false, isPlaying: true }),
  
  setSpeed: (speed) => set({ speedMultiplier: speed }),
  
  skipToPlayoffs: () => {
    const { matches } = get()
    const leagueMatches = matches.filter(m => m.match_type === 'league')
    set({
      currentMatchIndex: leagueMatches.length,
      phase: 'QUALIFICATION',
    })
  },
  
  skipToFinal: () => {
    const { matches } = get()
    const leagueMatches = matches.filter(m => m.match_type === 'league')
    set({
      currentMatchIndex: leagueMatches.length,
      phase: 'PLAYOFFS',
    })
  },
  
  reset: () => set({
    phase: 'INTRO',
    matches: [],
    standings: [],
    topPerformers: {
      orangeCap: null,
      purpleCap: null,
      mvp: null,
    },
    playoffTeams: [],
    champion: null,
    semifinal1Winner: null,
    semifinal1Loser: null,
    semifinal2Winner: null,
    semifinal2Loser: null,
    eliminatorWinner: null,
    currentMatchIndex: 0,
    currentMatch: null,
    currentPlayoffPhase: null,
    isPlaying: false,
    isPaused: false,
    simulationData: null,
  }),
  
  setSimulationData: (data) => set({ simulationData: data }),
  setMatches: (matches) => set((state) => {
    // CRITICAL: Merge matches, preserving completed matches - NEVER overwrite completed matches
    // Handle case where new matches array might be shorter or longer
    const maxLength = Math.max(state.matches.length, matches.length)
    const mergedMatches: Match[] = []
    
    for (let i = 0; i < maxLength; i++) {
      const existingMatch = state.matches[i]
      const newMatch = matches[i]
      
      // If no new match at this index, keep existing
      if (!newMatch) {
        if (existingMatch) mergedMatches.push(existingMatch)
        continue
      }
      
      // If no existing match at this index, use new match
      if (!existingMatch) {
        mergedMatches.push(newMatch)
        continue
      }
      
      // CRITICAL: If existing match is completed, NEVER overwrite it
      if (existingMatch.completed) {
        mergedMatches.push(existingMatch)
        continue
      }
      
      // If new match is completed, use it
      if (newMatch.completed) {
        mergedMatches.push(newMatch)
        continue
      }
      
      // Otherwise use the new match data (for incomplete matches)
      mergedMatches.push(newMatch)
    }
    
    return { matches: mergedMatches }
  }),
  setStandings: (standings) => set({ standings }),
  setTopPerformers: (performers) => set({ topPerformers: performers }),
  setPlayoffTeams: (teams) => set({ playoffTeams: teams }),
  setChampion: (team) => set({ champion: team }),
  setCurrentMatchIndex: (index) => set({ currentMatchIndex: index }),
  setCurrentMatch: (match) => set({ currentMatch: match }),
  setSemifinal1Winner: (team) => set({ semifinal1Winner: team }),
  setSemifinal1Loser: (team) => set({ semifinal1Loser: team }),
  setSemifinal2Winner: (team) => set({ semifinal2Winner: team }),
  setSemifinal2Loser: (team) => set({ semifinal2Loser: team }),
  setEliminatorWinner: (team) => set({ eliminatorWinner: team }),
  setCurrentPlayoffPhase: (phase) => set({ currentPlayoffPhase: phase }),
  
  // Batched update function - updates all match completion state in one atomic operation
  // This prevents multiple re-renders when standings, topPerformers, and match index update
  updateMatchComplete: (updates) => set((state) => {
    // CRITICAL: Preserve completed matches - NEVER overwrite them
    // Handle arrays of different lengths
    const maxLength = Math.max(state.matches.length, updates.matches.length)
    const mergedMatches: Match[] = []
    
    for (let i = 0; i < maxLength; i++) {
      const existingMatch = state.matches[i]
      const newMatch = updates.matches[i]
      
      // If no new match at this index, keep existing
      if (!newMatch) {
        if (existingMatch) mergedMatches.push(existingMatch)
        continue
      }
      
      // If no existing match at this index, use new match
      if (!existingMatch) {
        mergedMatches.push(newMatch)
        continue
      }
      
      // CRITICAL: If existing match is completed, NEVER overwrite it (even if newMatch is also completed)
      // This prevents race conditions where multiple updates try to set the same match
      if (existingMatch.completed) {
        mergedMatches.push(existingMatch)
        continue
      }
      
      // If new match is completed, use it (this is the first time this match is being completed)
      if (newMatch.completed) {
        mergedMatches.push(newMatch)
        continue
      }
      
      // Otherwise use the new match data (for incomplete matches)
      mergedMatches.push(newMatch)
    }
    
    return {
      standings: updates.standings,
      topPerformers: updates.topPerformers,
      currentMatchIndex: updates.currentMatchIndex,
      matches: mergedMatches,
      // Update currentMatch based on new index
      currentMatch: mergedMatches[updates.currentMatchIndex] || null,
    }
  }),
  
  // Pre-match overlay actions
  startPreMatchSequence: () => set({ 
    showPreMatchOverlay: true, 
    preMatchStage: 'toss',
    isPreparingMatch: false 
  }),
  setPreMatchStage: (stage) => set({ preMatchStage: stage }),
  completePreMatchSequence: () => set({ 
    showPreMatchOverlay: false, 
    preMatchStage: null 
  }),
  setIsPreparingMatch: (preparing) => set({ isPreparingMatch: preparing }),
}))


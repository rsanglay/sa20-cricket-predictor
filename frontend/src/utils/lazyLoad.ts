import { lazy } from 'react'

export const LazyHome = lazy(() => import('../features/home/Home'))
export const LazySeasonSimulatorV2 = lazy(() => import('../features/season-simulator-v2/SeasonSimulatorV2'))
export const LazyPlayerProfiler = lazy(() => import('../features/player-profiler/PlayerProfiler'))
export const LazyMatchPredictor = lazy(() => import('../features/match-predictor/MatchPredictor'))
export const LazyFantasyOptimizer = lazy(() => import('../features/fantasy-optimizer/FantasyOptimizer'))
export const LazyTeams = lazy(() => import('../features/teams/Teams'))

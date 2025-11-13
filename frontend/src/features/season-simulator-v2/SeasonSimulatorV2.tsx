import { useEffect, useState } from 'react'
import { useSimulationStore } from './store/simulationStore'
import { useSimulation } from './hooks/useSimulation'
import { useSimulationLoop } from './hooks/useSimulationLoop'
import { Team } from './types'
import { CinematicIntro } from './components/CinematicIntro'
import { FixtureReveal } from './components/FixtureReveal'
import { LeagueSimulation } from './components/LeagueSimulation'
import { PlayoffQualification } from './components/PlayoffQualification'
import { PlayoffMatch } from './components/PlayoffMatch'
import { FinalMatch } from './components/FinalMatch'
import { ChampionReveal } from './components/ChampionReveal'
import { TrophyPresentation } from './components/TrophyPresentation'
import { SeasonRewind } from './components/SeasonRewind'
import { AnalyticsDashboard } from './components/AnalyticsDashboard'
import { SimulationControls } from './components/SimulationControls'
import { PauseOverlay } from './components/PauseOverlay'

const SeasonSimulatorV2 = () => {
  const {
    phase,
    setPhase,
    isPlaying,
    isPaused,
    speedMultiplier,
    matches,
    standings,
    playoffTeams,
    champion,
    topPerformers,
    simulationData,
    startSimulation,
    currentMatch,
    currentMatchIndex,
  } = useSimulationStore()
  const { fetchSimulationData, fetchTeamsOnly } = useSimulation()
  const [isLoadingData, setIsLoadingData] = useState(false)
  useSimulationLoop() // Wire up the simulation loop

  useEffect(() => {
    // Only fetch teams and generate fixtures immediately (fast)
    // Heavy simulation data will load when user starts
    fetchTeamsOnly()
  }, [fetchTeamsOnly])

  // Keyboard controls
  useEffect(() => {
    const handleKeyPress = (e: KeyboardEvent) => {
      if (e.code === 'Space') {
        e.preventDefault()
        if (isPlaying) {
          useSimulationStore.getState().pauseSimulation()
        } else {
          useSimulationStore.getState().resumeSimulation()
        }
      }
    }

    window.addEventListener('keydown', handleKeyPress)
    return () => window.removeEventListener('keydown', handleKeyPress)
  }, [isPlaying])

  const handleStart = async () => {
    console.log('handleStart called - button clicked!')
    setIsLoadingData(true)
    // Load teams and fixtures - matches will be predicted individually
    try {
      console.log('Starting data fetch...')
      await fetchSimulationData(1) // Just load teams and fixtures
      
      // Ensure first match is set as current
      const store = useSimulationStore.getState()
      if (store.matches.length > 0 && store.currentMatchIndex === 0 && !store.currentMatch) {
        store.setCurrentMatch(store.matches[0])
        store.setCurrentMatchIndex(0)
      }
      
      // Start simulation and go directly to league stage
      console.log('Starting simulation and setting phase to LEAGUE')
      startSimulation()
      setPhase('LEAGUE')
      console.log('Phase set, current phase:', useSimulationStore.getState().phase)
      console.log('Current match:', useSimulationStore.getState().currentMatch)
    } catch (error) {
      console.error('Error in handleStart:', error)
    } finally {
      setIsLoadingData(false)
    }
  }

  const handleFixtureComplete = () => {
    startSimulation()
    setPhase('LEAGUE')
  }

  const handleQualificationComplete = () => {
    // Start with Semifinal 1 (1 vs 2)
    useSimulationStore.getState().setCurrentPlayoffPhase('semifinal_1')
    setPhase('PLAYOFFS')
  }

  const handleSemifinal1Complete = (winner: Team, loser: Team) => {
    useSimulationStore.getState().setSemifinal1Winner(winner)
    useSimulationStore.getState().setSemifinal1Loser(loser)
    // Move to Semifinal 2 (3 vs 4)
    useSimulationStore.getState().setCurrentPlayoffPhase('semifinal_2')
  }

  const handleSemifinal2Complete = (winner: Team, loser: Team) => {
    useSimulationStore.getState().setSemifinal2Winner(winner)
    useSimulationStore.getState().setSemifinal2Loser(loser)
    // Move to Eliminator (loser of 1 vs 2 vs winner of 3 vs 4)
    useSimulationStore.getState().setCurrentPlayoffPhase('eliminator')
  }

  const handleEliminatorComplete = (winner: Team) => {
    useSimulationStore.getState().setEliminatorWinner(winner)
    // Move to Final (winner of 1 vs 2 vs winner of eliminator)
    useSimulationStore.getState().setCurrentPlayoffPhase('final')
  }

  const handleFinalComplete = (winner: Team) => {
    useSimulationStore.getState().setChampion(winner)
    setPhase('CHAMPION')
  }

  const handleChampionComplete = () => {
    setPhase('TROPHY')
  }

  const handleTrophyComplete = () => {
    setPhase('REWIND')
  }

  const handleRewindComplete = () => {
    setPhase('ANALYTICS')
  }

  // Debug: Log phase changes
  useEffect(() => {
    console.log('Phase changed to:', phase)
    console.log('Matches count:', matches.length)
    console.log('Standings count:', standings.length)
  }, [phase, matches.length, standings.length])

  return (
    <div className="relative w-full min-h-[calc(100vh-4rem)] overflow-auto -mx-4 -my-6 md:-mx-10">
      {phase === 'INTRO' && <CinematicIntro onStart={handleStart} isLoading={isLoadingData} />}
      
      {phase === 'FIXTURE_REVEAL' && (
        <FixtureReveal matches={matches} onComplete={handleFixtureComplete} />
      )}

      {phase === 'LEAGUE' && <LeagueSimulation />}

      {phase === 'QUALIFICATION' && (
        <PlayoffQualification standings={standings} onComplete={handleQualificationComplete} />
      )}

      {phase === 'PLAYOFFS' && playoffTeams.length >= 4 && (() => {
        const { currentPlayoffPhase, semifinal1Winner, semifinal1Loser, semifinal2Winner, eliminatorWinner } = useSimulationStore.getState()
        
        if (currentPlayoffPhase === 'semifinal_1') {
          return (
            <PlayoffMatch
              team1={playoffTeams[0]}
              team2={playoffTeams[1]}
              matchType="semifinal_1"
              onComplete={handleSemifinal1Complete}
            />
          )
        }
        
        if (currentPlayoffPhase === 'semifinal_2') {
          return (
            <PlayoffMatch
              team1={playoffTeams[2]}
              team2={playoffTeams[3]}
              matchType="semifinal_2"
              onComplete={handleSemifinal2Complete}
            />
          )
        }
        
        if (currentPlayoffPhase === 'eliminator' && semifinal1Loser && semifinal2Winner) {
          return (
            <PlayoffMatch
              team1={semifinal1Loser}
              team2={semifinal2Winner}
              matchType="eliminator"
              onComplete={handleEliminatorComplete}
            />
          )
        }
        
        if (currentPlayoffPhase === 'final' && semifinal1Winner && eliminatorWinner) {
          return (
            <FinalMatch
              team1={semifinal1Winner}
              team2={eliminatorWinner}
              onComplete={handleFinalComplete}
            />
          )
        }
        
        return null
      })()}

      {phase === 'CHAMPION' && champion && (
        <ChampionReveal champion={champion} onComplete={handleChampionComplete} />
      )}

      {phase === 'TROPHY' && champion && (
        <TrophyPresentation
          champion={champion}
          orangeCap={topPerformers.orangeCap}
          purpleCap={topPerformers.purpleCap}
          mvp={topPerformers.mvp}
          onComplete={handleTrophyComplete}
        />
      )}

      {phase === 'REWIND' && (
        <SeasonRewind matches={matches} standings={standings} onComplete={handleRewindComplete} />
      )}

      {phase === 'ANALYTICS' && (
        <AnalyticsDashboard matches={matches} standings={standings} />
      )}

      {/* Pause Overlay */}
      {isPaused && phase !== 'INTRO' && <PauseOverlay />}

      {/* Controls are always visible except during intro */}
      {phase !== 'INTRO' && <SimulationControls />}
    </div>
  )
}

export default SeasonSimulatorV2

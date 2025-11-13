import { Play, Pause, SkipForward, FastForward, RotateCcw, BarChart3 } from 'lucide-react'
import { useSimulationStore } from '../store/simulationStore'
import { SpeedMultiplier } from '../types'

export const SimulationControls = () => {
  const {
    isPlaying,
    isPaused,
    speedMultiplier,
    phase,
    pauseSimulation,
    resumeSimulation,
    setSpeed,
    skipToPlayoffs,
    skipToFinal,
    reset,
  } = useSimulationStore()

  const speeds: SpeedMultiplier[] = [1, 2, 5, 10]

  return (
    <div className="fixed bottom-0 left-0 right-0 bg-slate-900/95 backdrop-blur-sm border-t border-slate-700 p-4 z-50">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        {/* Play/Pause */}
        <button
          onClick={isPlaying ? pauseSimulation : resumeSimulation}
          className="px-6 py-2 bg-[#FF6B35] hover:bg-[#FF8C42] text-white rounded-lg font-semibold transition-colors flex items-center gap-2"
        >
          {isPlaying ? (
            <>
              <Pause className="w-5 h-5" />
              Pause
            </>
          ) : (
            <>
              <Play className="w-5 h-5" />
              Play
            </>
          )}
        </button>

        {/* Speed Control */}
        <div className="flex items-center gap-2">
          <span className="text-slate-400 text-sm">Speed:</span>
          {speeds.map((speed) => (
            <button
              key={speed}
              onClick={() => setSpeed(speed)}
              className={`px-4 py-2 rounded-lg font-semibold transition-colors ${
                speedMultiplier === speed
                  ? 'bg-[#FF6B35] text-white'
                  : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
              }`}
            >
              {speed}x
            </button>
          ))}
        </div>

        {/* Skip Controls */}
        <div className="flex items-center gap-2">
          {phase === 'LEAGUE' && (
            <button
              onClick={skipToPlayoffs}
              className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg font-semibold transition-colors flex items-center gap-2"
            >
              <SkipForward className="w-4 h-4" />
              Skip to Playoffs
            </button>
          )}
          {phase === 'LEAGUE' || phase === 'PLAYOFFS' ? (
            <button
              onClick={skipToFinal}
              className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg font-semibold transition-colors flex items-center gap-2"
            >
              <FastForward className="w-4 h-4" />
              Skip to Final
            </button>
          ) : null}
        </div>

        {/* Reset & Analytics */}
        <div className="flex items-center gap-2">
          <button
            onClick={reset}
            className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg font-semibold transition-colors flex items-center gap-2"
          >
            <RotateCcw className="w-4 h-4" />
            Replay
          </button>
          {phase === 'ANALYTICS' && (
            <button
              className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg font-semibold transition-colors flex items-center gap-2"
            >
              <BarChart3 className="w-4 h-4" />
              Analytics
            </button>
          )}
        </div>
      </div>
    </div>
  )
}


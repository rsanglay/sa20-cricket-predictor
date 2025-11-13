import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useParams, useSearchParams, useNavigate } from 'react-router-dom'
import { playersAPI } from '../../api/endpoints/players'
import Loading from '../../components/common/Loading'
import { PlayerDetail } from '../../types/player'
import usePlayerProjections from '../../hooks/usePlayerProjections'

const PlayerProfiler = () => {
  const { id: routePlayerId } = useParams<{ id?: string }>()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const queryPlayerId = searchParams.get('player')
  
  // Get player ID from route params, query params, or null
  const initialPlayerId = routePlayerId 
    ? parseInt(routePlayerId, 10) 
    : queryPlayerId 
    ? parseInt(queryPlayerId, 10) 
    : null

  const { data: players, isLoading } = useQuery({ queryKey: ['players-all'], queryFn: playersAPI.getAll })
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedPlayerId, setSelectedPlayerId] = useState<number | null>(initialPlayerId)

  const filteredPlayers = useMemo(() => {
    if (!players) return []
    const term = searchTerm.trim().toLowerCase()
    return players
      .filter((player) => player.name.toLowerCase().includes(term))
      .sort((a, b) => a.name.localeCompare(b.name))
  }, [players, searchTerm])

  // Update selected player when route/query params change
  useEffect(() => {
    if (initialPlayerId && initialPlayerId !== selectedPlayerId) {
      setSelectedPlayerId(initialPlayerId)
    } else if (!selectedPlayerId && !initialPlayerId && filteredPlayers.length > 0) {
      // Only auto-select if no player ID in URL
      setSelectedPlayerId(filteredPlayers[0].id)
    }
  }, [initialPlayerId, filteredPlayers, selectedPlayerId])

  // Update URL when player is selected
  const handlePlayerSelect = (playerId: number) => {
    setSelectedPlayerId(playerId)
    navigate(`/players/${playerId}`, { replace: true })
  }
  const projectionsQuery = usePlayerProjections()

  const { data: selectedPlayer } = useQuery({
    queryKey: ['player-detail', selectedPlayerId],
    queryFn: () => playersAPI.getPlayer(selectedPlayerId ?? 0),
    enabled: selectedPlayerId != null
  })

  const projection = useMemo(() => {
    if (!projectionsQuery.data || selectedPlayerId == null) return undefined
    return projectionsQuery.data.find((proj) => proj.player_id === selectedPlayerId)
  }, [projectionsQuery.data, selectedPlayerId])

  if (isLoading) return <Loading message="Loading player directory..." />

  return (
    <div className="grid gap-8 lg:grid-cols-[340px,1fr]">
      <aside className="rounded-2xl border border-slate-200 bg-white p-6 shadow-lg sticky top-24 h-fit">
        <div className="mb-6">
          <h2 className="text-lg font-extrabold text-slate-900 mb-1">Player Directory</h2>
          <p className="text-xs text-slate-500">Search and browse all players</p>
        </div>
        <div className="relative">
          <input
            className="w-full rounded-xl border-2 border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-900 placeholder-slate-400 focus:border-emerald-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-emerald-200 transition-all"
            placeholder="Search by name..."
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
          />
          <svg className="absolute right-3 top-1/2 -translate-y-1/2 h-5 w-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        </div>
        <div className="mt-6 max-h-[calc(100vh-280px)] overflow-y-auto pr-2 space-y-2 custom-scrollbar">
          {filteredPlayers.map((player) => (
            <button
              key={player.id}
              onClick={() => handlePlayerSelect(player.id)}
              className={`w-full flex items-center gap-3 rounded-xl border-2 px-4 py-3 text-left transition-all ${
                selectedPlayerId === player.id
                  ? 'bg-gradient-to-r from-emerald-50 to-emerald-100 text-emerald-900 border-emerald-500 shadow-md transform scale-[1.02]'
                  : 'border-slate-200 bg-white text-slate-700 hover:border-emerald-300 hover:bg-slate-50 hover:shadow-sm'
              }`}
            >
              <div className={`flex-shrink-0 h-10 w-10 rounded-full flex items-center justify-center text-xs font-bold ${
                selectedPlayerId === player.id
                  ? 'bg-emerald-500 text-white'
                  : 'bg-slate-200 text-slate-600'
              }`}>
                {player.name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-semibold truncate">{player.name}</div>
                <div className="text-xs text-slate-500 uppercase tracking-wide">{player.role.replace('_', ' ')}</div>
              </div>
            </button>
          ))}
          {filteredPlayers.length === 0 && (
            <div className="py-12 text-center">
              <svg className="mx-auto h-12 w-12 text-slate-300 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <p className="text-sm text-slate-500">No players found</p>
            </div>
          )}
        </div>
      </aside>

      <section className="space-y-8">
        {!selectedPlayer && (
          <div className="rounded-2xl border-2 border-dashed border-slate-300 bg-gradient-to-br from-slate-50 to-white p-12 text-center">
            <div className="mx-auto w-20 h-20 rounded-full bg-emerald-100 flex items-center justify-center mb-6">
              <svg className="w-10 h-10 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
              </svg>
            </div>
            <h3 className="text-2xl font-extrabold text-slate-900 mb-2">Select a Player</h3>
            <p className="text-base text-slate-600 max-w-md mx-auto">
              Choose a player from the directory to view their complete profile, career statistics, season-by-season performance, and ML-powered projections.
            </p>
          </div>
        )}

            {selectedPlayer && (
              <div className="space-y-8">
                {/* Player Header - Premium profile section */}
                <header className="relative overflow-hidden rounded-2xl border border-slate-200 bg-gradient-to-br from-white to-slate-50 shadow-xl">
                  {/* Background pattern */}
                  <div className="absolute inset-0 opacity-5">
                    <div className="absolute inset-0" style={{
                      backgroundImage: 'radial-gradient(circle at 2px 2px, rgb(16 185 129) 1px, transparent 0)',
                      backgroundSize: '40px 40px'
                    }} />
                  </div>
                  
                  <div className="relative p-8 md:p-10">
                    <div className="flex flex-col gap-8 lg:flex-row lg:items-start">
                      {/* Player Image - Fixed aspect ratio container */}
                      <div className="flex-shrink-0 mx-auto lg:mx-0">
                        <div className="relative w-48 h-48 md:w-56 md:h-56 lg:w-64 lg:h-64 rounded-2xl overflow-hidden bg-gradient-to-br from-emerald-100 to-slate-100 shadow-2xl border-4 border-white ring-4 ring-emerald-100/50">
                          {selectedPlayer.image_url ? (
                            <img
                              src={selectedPlayer.image_url}
                              alt={selectedPlayer.name}
                              className="w-full h-full object-cover object-center"
                              style={{ objectFit: 'contain', padding: '8px' }}
                              onError={(e) => {
                                const target = e.target as HTMLImageElement
                                target.style.display = 'none'
                                const placeholder = target.parentElement?.querySelector('.placeholder')
                                if (placeholder) {
                                  (placeholder as HTMLElement).style.display = 'flex'
                                }
                              }}
                            />
                          ) : null}
                          <div
                            className={`absolute inset-0 flex items-center justify-center ${selectedPlayer.image_url ? 'hidden placeholder' : 'flex'}`}
                          >
                            <div className="flex h-32 w-32 md:h-40 md:w-40 items-center justify-center rounded-full bg-gradient-to-br from-emerald-500 to-emerald-700 text-5xl md:text-6xl font-bold text-white shadow-xl">
                              {selectedPlayer.name
                                .split(' ')
                                .map((n) => n[0])
                                .join('')
                                .toUpperCase()
                                .slice(0, 2)}
                            </div>
                          </div>
                        </div>
                      </div>
                      
                      {/* Player Info */}
                      <div className="flex-1 min-w-0">
                        <p className="text-xs uppercase tracking-wider font-bold text-emerald-600 mb-3">Player Profile</p>
                        <h1 className="text-4xl md:text-5xl font-extrabold text-slate-900 mb-4 leading-tight">{selectedPlayer.name}</h1>
                        
                        <div className="flex flex-wrap items-center gap-3 mb-6">
                          <span className="inline-flex items-center px-4 py-2 rounded-full bg-gradient-to-r from-emerald-500 to-emerald-600 text-white text-sm font-bold shadow-md">
                            {selectedPlayer.role.replace('_', ' ').toUpperCase()}
                          </span>
                          <span className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-slate-100 text-slate-700 text-sm font-semibold">
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                            {selectedPlayer.country}
                          </span>
                          <span className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-slate-100 text-slate-700 text-sm font-semibold">
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                            </svg>
                            {selectedPlayer.birth_date 
                              ? `Born ${formatBirthDate(selectedPlayer.birth_date)} (Age ${selectedPlayer.age})`
                              : `Age ${selectedPlayer.age}`
                            }
                          </span>
                        </div>
                        
                        {selectedPlayer.batting_style && (
                          <div className="mb-4 flex flex-wrap items-center gap-4 text-sm text-slate-600">
                            <span className="font-medium">
                              <span className="text-slate-500">Batting:</span> {selectedPlayer.batting_style.replace('_', ' ')}
                            </span>
                            {selectedPlayer.bowling_style && (
                              <span className="font-medium">
                                <span className="text-slate-500">Bowling:</span> {selectedPlayer.bowling_style.replace('_', ' ')}
                              </span>
                            )}
                          </div>
                        )}
                        
                        {selectedPlayer.international_caps > 0 && (
                          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-amber-50 border border-amber-200 text-amber-800">
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
                            </svg>
                            <span className="font-bold">{selectedPlayer.international_caps}</span>
                            <span className="text-sm">International Caps</span>
                          </div>
                        )}
                      </div>

                      {/* Projections - Enhanced */}
                      {projection && (
                        <div className="flex-shrink-0 w-full lg:w-auto">
                          <div className="grid grid-cols-2 gap-4 rounded-xl bg-gradient-to-br from-emerald-500 to-emerald-600 p-6 shadow-xl border border-emerald-400">
                            <div className="text-center">
                              <div className="text-xs uppercase tracking-wider font-bold text-emerald-50 mb-2">Predicted Runs</div>
                              <div className="text-4xl font-extrabold text-white">{projection.predicted_runs.toFixed(0)}</div>
                            </div>
                            <div className="text-center">
                              <div className="text-xs uppercase tracking-wider font-bold text-emerald-50 mb-2">Predicted Wickets</div>
                              <div className="text-4xl font-extrabold text-white">{projection.predicted_wickets.toFixed(0)}</div>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </header>

                {/* Career Stats Grid */}
                <div className="grid gap-6 lg:grid-cols-2">
                  <ProfileCard title="Batting Statistics" data={buildBattingStats(selectedPlayer)} />
                  <ProfileCard title="Bowling Statistics" data={buildBowlingStats(selectedPlayer)} />
                </div>

                {/* Season-by-Season Stats */}
                {selectedPlayer.season_stats && selectedPlayer.season_stats.length > 0 && (
                  <div className="space-y-6">
                    <SeasonStatsTables seasonStats={selectedPlayer.season_stats} />
                  </div>
                )}

                {/* Model Features */}
                {projection && (
                  <ProfileCard title="ML Model Features" data={projection.features} compact />
                )}

                {/* Recent Form */}
                <RecentFormTable player={selectedPlayer} />
              </div>
            )}
      </section>
    </div>
  )
}

const formatBirthDate = (birthDate: string): string => {
  try {
    const date = new Date(birthDate)
    return date.toLocaleDateString('en-US', { 
      month: 'short', 
      day: 'numeric', 
      year: 'numeric' 
    })
  } catch {
    return birthDate
  }
}

interface ProfileCardProps {
  title: string
  data: Record<string, number | string>
  compact?: boolean
}

const ProfileCard = ({ title, data, compact = false }: ProfileCardProps) => (
  <div className="rounded-2xl border border-slate-200 bg-white p-8 shadow-lg hover:shadow-xl transition-shadow">
    <h3 className="text-xl font-extrabold text-slate-900 mb-6 pb-3 border-b border-slate-200">{title}</h3>
    <dl className={`grid gap-4 ${compact ? 'text-sm' : 'text-base'}`}>
      {Object.entries(data).map(([key, value]) => (
        <div key={key} className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-slate-50 transition-colors">
          <dt className="text-slate-600 capitalize font-medium">{key.replace(/_/g, ' ')}</dt>
          <dd className="font-extrabold text-slate-900 text-lg">{formatValue(value)}</dd>
        </div>
      ))}
    </dl>
  </div>
)

const RecentFormTable = ({ player }: { player: PlayerDetail }) => (
  <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-lg">
    <div className="border-b border-slate-200 bg-gradient-to-r from-slate-50 to-white px-8 py-5">
      <h3 className="text-xl font-extrabold text-slate-900">Recent Form</h3>
      <p className="text-sm text-slate-600 mt-1">Last 5 matches performance</p>
    </div>
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
        <thead className="bg-slate-50">
          <tr>
            <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-wider text-slate-700">Date</th>
            <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-wider text-slate-700">Opponent</th>
            <th className="px-6 py-4 text-right text-xs font-bold uppercase tracking-wider text-slate-700">Runs</th>
            <th className="px-6 py-4 text-right text-xs font-bold uppercase tracking-wider text-slate-700">Balls</th>
            <th className="px-6 py-4 text-right text-xs font-bold uppercase tracking-wider text-slate-700">Wickets</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 bg-white">
          {player.recent_form.last_5_matches.map((perf) => (
            <tr key={perf.match_id} className="hover:bg-emerald-50/50 transition-colors">
              <td className="px-6 py-4 text-sm text-slate-700">
                {perf.date ? new Date(perf.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '—'}
              </td>
              <td className="px-6 py-4 text-sm font-semibold text-slate-900">{perf.opponent || '—'}</td>
              <td className="px-6 py-4 text-sm font-bold text-slate-900 text-right">{perf.runs || 0}</td>
              <td className="px-6 py-4 text-sm text-slate-600 text-right">{perf.balls_faced || 0}</td>
              <td className="px-6 py-4 text-sm font-semibold text-emerald-700 text-right">{perf.wickets || 0}</td>
            </tr>
          ))}
          {player.recent_form.last_5_matches.length === 0 && (
            <tr>
              <td className="px-6 py-12 text-center text-sm text-slate-500" colSpan={5}>
                No recent matches recorded.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  </div>
)

const formatValue = (value: number | string) => {
  if (typeof value === 'number') {
    return Number.isInteger(value) ? value.toFixed(0) : value.toFixed(2)
  }
  return value
}

const buildBattingStats = (player: PlayerDetail): Record<string, number | string> => {
  const stats = player.career_stats
  return {
    matches: stats.matches_played,
    runs: stats.runs_scored,
    'highest score': stats.highest_score,
    average: stats.batting_average > 0 ? stats.batting_average.toFixed(2) : '—',
    'strike rate': stats.strike_rate > 0 ? stats.strike_rate.toFixed(2) : '—',
    fours: stats.fours,
    sixes: stats.sixes,
    fifties: stats.fifties,
    hundreds: stats.hundreds,
  }
}

const buildBowlingStats = (player: PlayerDetail): Record<string, number | string> => {
  const stats = player.career_stats
  return {
    matches: stats.matches_played,
    wickets: stats.wickets_taken,
    'best figures': stats.best_bowling_figures || '—',
    average: stats.bowling_average && stats.bowling_average > 0 ? stats.bowling_average.toFixed(2) : '—',
    economy: stats.economy_rate && stats.economy_rate > 0 ? stats.economy_rate.toFixed(2) : '—',
    '5-wicket hauls': stats.five_wickets,
  }
}

interface SeasonStatsTablesProps {
  seasonStats: Array<{
    season: number
    team: string
    batting: {
      matches: number
      runs: number
      highest_score: number
      average: number
      strike_rate: number
      balls_faced: number
      fours: number
      sixes: number
    }
    bowling: {
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
  }>
}

const SeasonStatsTables = ({ seasonStats }: SeasonStatsTablesProps) => {
  return (
    <div className="space-y-8">
      {/* Bowling Stats Table */}
      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-lg">
        <div className="border-b border-slate-200 bg-gradient-to-r from-blue-50 to-white px-8 py-5">
          <h3 className="text-xl font-extrabold text-slate-900">Bowling Statistics by Season</h3>
          <p className="text-sm text-slate-600 mt-1">Detailed bowling performance across seasons</p>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-wider text-slate-700">Year</th>
                <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-wider text-slate-700">Team</th>
                <th className="px-6 py-4 text-right text-xs font-bold uppercase tracking-wider text-slate-700">Mat</th>
                <th className="px-6 py-4 text-right text-xs font-bold uppercase tracking-wider text-slate-700">Balls</th>
                <th className="px-6 py-4 text-right text-xs font-bold uppercase tracking-wider text-slate-700">Runs</th>
                <th className="px-6 py-4 text-right text-xs font-bold uppercase tracking-wider text-slate-700">Wkts</th>
                <th className="px-6 py-4 text-right text-xs font-bold uppercase tracking-wider text-slate-700">BBM</th>
                <th className="px-6 py-4 text-right text-xs font-bold uppercase tracking-wider text-slate-700">Ave</th>
                <th className="px-6 py-4 text-right text-xs font-bold uppercase tracking-wider text-slate-700">Econ</th>
                <th className="px-6 py-4 text-right text-xs font-bold uppercase tracking-wider text-slate-700">SR</th>
                <th className="px-6 py-4 text-right text-xs font-bold uppercase tracking-wider text-slate-700">5W</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 bg-white">
              {seasonStats.map((stat) => (
                <tr key={`bowling-${stat.season}-${stat.team}`} className="hover:bg-blue-50/50 transition-colors">
                  <td className="px-6 py-4 text-sm font-bold text-slate-900">{stat.season}</td>
                  <td className="px-6 py-4 text-sm font-medium text-slate-700">{stat.team}</td>
                  <td className="px-6 py-4 text-sm text-right text-slate-900">{stat.bowling.matches}</td>
                  <td className="px-6 py-4 text-sm text-right text-slate-600">{stat.bowling.balls}</td>
                  <td className="px-6 py-4 text-sm text-right text-slate-600">{stat.bowling.runs}</td>
                  <td className="px-6 py-4 text-sm text-right font-bold text-blue-700">{stat.bowling.wickets}</td>
                  <td className="px-6 py-4 text-sm text-right text-slate-700">{stat.bowling.best_figures || '—'}</td>
                  <td className="px-6 py-4 text-sm text-right text-slate-700">{stat.bowling.average > 0 ? stat.bowling.average.toFixed(2) : '—'}</td>
                  <td className="px-6 py-4 text-sm text-right text-slate-700">{stat.bowling.economy > 0 ? stat.bowling.economy.toFixed(2) : '—'}</td>
                  <td className="px-6 py-4 text-sm text-right text-slate-700">{stat.bowling.strike_rate > 0 ? stat.bowling.strike_rate.toFixed(0) : '—'}</td>
                  <td className="px-6 py-4 text-sm text-right text-slate-700">{stat.bowling.five_wickets}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Batting Stats Table */}
      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-lg">
        <div className="border-b border-slate-200 bg-gradient-to-r from-emerald-50 to-white px-8 py-5">
          <h3 className="text-xl font-extrabold text-slate-900">Batting & Fielding Statistics by Season</h3>
          <p className="text-sm text-slate-600 mt-1">Detailed batting performance across seasons</p>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-wider text-slate-700">Year</th>
                <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-wider text-slate-700">Team</th>
                <th className="px-6 py-4 text-right text-xs font-bold uppercase tracking-wider text-slate-700">Mat</th>
                <th className="px-6 py-4 text-right text-xs font-bold uppercase tracking-wider text-slate-700">Runs</th>
                <th className="px-6 py-4 text-right text-xs font-bold uppercase tracking-wider text-slate-700">HS</th>
                <th className="px-6 py-4 text-right text-xs font-bold uppercase tracking-wider text-slate-700">Avg</th>
                <th className="px-6 py-4 text-right text-xs font-bold uppercase tracking-wider text-slate-700">BF</th>
                <th className="px-6 py-4 text-right text-xs font-bold uppercase tracking-wider text-slate-700">SR</th>
                <th className="px-6 py-4 text-right text-xs font-bold uppercase tracking-wider text-slate-700">4s</th>
                <th className="px-6 py-4 text-right text-xs font-bold uppercase tracking-wider text-slate-700">6s</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 bg-white">
              {seasonStats.map((stat) => (
                <tr key={`batting-${stat.season}-${stat.team}`} className="hover:bg-emerald-50/50 transition-colors">
                  <td className="px-6 py-4 text-sm font-bold text-slate-900">{stat.season}</td>
                  <td className="px-6 py-4 text-sm font-medium text-slate-700">{stat.team}</td>
                  <td className="px-6 py-4 text-sm text-right text-slate-900">{stat.batting.matches}</td>
                  <td className="px-6 py-4 text-sm text-right font-bold text-emerald-700">{stat.batting.runs}</td>
                  <td className="px-6 py-4 text-sm text-right text-slate-700">{stat.batting.highest_score}</td>
                  <td className="px-6 py-4 text-sm text-right text-slate-700">{stat.batting.average > 0 ? stat.batting.average.toFixed(2) : '—'}</td>
                  <td className="px-6 py-4 text-sm text-right text-slate-600">{stat.batting.balls_faced}</td>
                  <td className="px-6 py-4 text-sm text-right text-slate-700">{stat.batting.strike_rate > 0 ? stat.batting.strike_rate.toFixed(2) : '—'}</td>
                  <td className="px-6 py-4 text-sm text-right text-slate-600">{stat.batting.fours}</td>
                  <td className="px-6 py-4 text-sm text-right text-slate-600">{stat.batting.sixes}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

export default PlayerProfiler

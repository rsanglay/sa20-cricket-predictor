import { useMemo, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import Loading from '../../components/common/Loading'
import { predictionsAPI } from '../../api/endpoints/predictions'
import { matchesAPI, Match } from '../../api/endpoints/matches'
import { StartingXIPlayer } from '../../types/prediction'
import { Calendar, MapPin } from 'lucide-react'

const MatchPredictor = () => {
  const [selectedMatchId, setSelectedMatchId] = useState<number | null>(null)

  const { data: upcomingMatches, isLoading: matchesLoading } = useQuery({
    queryKey: ['upcoming-matches'],
    queryFn: () => matchesAPI.getUpcoming(2026, 30)
  })

  const selectedMatch = useMemo(() => {
    if (!selectedMatchId || !upcomingMatches) return null
    return upcomingMatches.find(m => m.id === selectedMatchId)
  }, [selectedMatchId, upcomingMatches])

  const mutation = useMutation({
    mutationFn: () => {
      if (!selectedMatch) throw new Error('No match selected')
      return predictionsAPI.predictMatch(
        selectedMatch.home_team_id,
        selectedMatch.away_team_id,
        selectedMatch.venue_id
      )
    },
    enabled: !!selectedMatch
  })

  const handlePredict = () => {
    if (!selectedMatch) return
    mutation.mutate()
  }

  const handleMatchSelect = (match: Match) => {
    setSelectedMatchId(match.id)
    mutation.reset()
  }


  return (
    <div className="space-y-8">
      <div className="space-y-2">
        <p className="text-xs uppercase tracking-wider font-semibold text-emerald-600">Match engine</p>
        <h1 className="text-3xl font-bold text-slate-900">Match Predictor</h1>
        <p className="max-w-xl text-sm text-slate-600">Select an upcoming SA20 2026 fixture and generate pre-match win probabilities.</p>
      </div>

      {matchesLoading && <Loading message="Loading upcoming fixtures..." />}

      {!matchesLoading && upcomingMatches && (
        <div className="grid gap-6 lg:grid-cols-[400px,1fr]">
          {/* Upcoming Matches List */}
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-md">
            <h2 className="text-lg font-bold text-slate-900 mb-4">Upcoming Fixtures</h2>
            <div className="space-y-2 max-h-[600px] overflow-y-auto">
              {upcomingMatches.map((match) => (
                <button
                  key={match.id}
                  onClick={() => handleMatchSelect(match)}
                  className={`w-full text-left rounded-lg border p-4 transition-all ${
                    selectedMatchId === match.id
                      ? 'border-emerald-500 bg-emerald-50 shadow-md'
                      : 'border-slate-200 hover:border-emerald-300 hover:bg-slate-50'
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-semibold text-slate-500">
                      {match.match_number ? `Match ${match.match_number}` : 'TBD'}
                    </span>
                    <span className="text-xs text-slate-500 flex items-center gap-1">
                      <Calendar className="h-3 w-3" />
                      {new Date(match.match_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                    </span>
                  </div>
                  <div className="font-semibold text-slate-900 mb-1">{match.home_team_name || `Team ${match.home_team_id}`}</div>
                  <div className="text-sm text-slate-600 mb-2">vs</div>
                  <div className="font-semibold text-slate-900 mb-2">{match.away_team_name || `Team ${match.away_team_id}`}</div>
                  <div className="text-xs text-slate-500 flex items-center gap-1">
                    <MapPin className="h-3 w-3" />
                    {match.venue_name || `Venue ${match.venue_id}`}
                  </div>
                </button>
              ))}
              {upcomingMatches.length === 0 && (
                <div className="text-center text-slate-500 py-8">No upcoming matches found</div>
              )}
            </div>
          </div>

          {/* Prediction Panel */}
          <div className="space-y-6">
            {!selectedMatch && (
              <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-12 text-center">
                <p className="text-slate-600">Select a fixture from the list to generate predictions</p>
              </div>
            )}

            {selectedMatch && (
              <>
                <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-md">
                  <h2 className="text-xl font-bold text-slate-900 mb-4">Selected Match</h2>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-slate-600">Match</span>
                      <span className="font-semibold text-slate-900">
                        {selectedMatch.match_number ? `Match ${selectedMatch.match_number}` : 'TBD'}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-slate-600">Date</span>
                      <span className="font-semibold text-slate-900">
                        {new Date(selectedMatch.match_date).toLocaleDateString('en-US', { 
                          weekday: 'long', 
                          year: 'numeric', 
                          month: 'long', 
                          day: 'numeric' 
                        })}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-slate-600">Venue</span>
                      <span className="font-semibold text-slate-900">{selectedMatch.venue_name}</span>
                    </div>
                    <div className="pt-4 border-t border-slate-200">
                      <div className="text-center">
                        <div className="text-lg font-bold text-slate-900 mb-1">{selectedMatch.home_team_name}</div>
                        <div className="text-sm text-slate-500 mb-1">vs</div>
                        <div className="text-lg font-bold text-slate-900">{selectedMatch.away_team_name}</div>
                      </div>
                    </div>
                  </div>
                  <button
                    className="w-full mt-6 rounded-lg border-2 border-emerald-600 bg-emerald-600 px-4 py-3 text-sm font-semibold text-white shadow-md transition hover:bg-emerald-700 disabled:opacity-50"
                    onClick={handlePredict}
                    disabled={mutation.isPending}
                  >
                    {mutation.isPending ? 'Predicting...' : 'Generate Prediction'}
                  </button>
                </div>

                {mutation.isPending && <Loading message="Calculating match probabilities" />}

                {mutation.data && !mutation.isPending && (
                  <div className="space-y-6">
                    <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-md">
                      <h2 className="text-2xl font-bold text-slate-900">Prediction Result</h2>
                      <p className="mt-2 text-sm text-slate-600">
                        {mutation.data.predicted_winner === 'home' ? selectedMatch.home_team_name : selectedMatch.away_team_name} 
                        {' '}favored with {(mutation.data.confidence * 100).toFixed(1)}% confidence
                      </p>
                      <div className="mt-4 grid gap-4 md:grid-cols-2">
                        <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
                          <h3 className="text-xs uppercase tracking-wider font-semibold text-emerald-700">Home Win Probability</h3>
                          <p className="mt-2 text-3xl font-bold text-emerald-900">
                            {(mutation.data.home_win_probability * 100).toFixed(1)}%
                          </p>
                        </div>
                        <div className="rounded-xl border border-blue-200 bg-blue-50 p-4">
                          <h3 className="text-xs uppercase tracking-wider font-semibold text-blue-700">Away Win Probability</h3>
                          <p className="mt-2 text-3xl font-bold text-blue-900">
                            {(mutation.data.away_win_probability * 100).toFixed(1)}%
                          </p>
                        </div>
                      </div>
                    </div>

                    {/* Toss and Match Result */}
                    {mutation.data.toss_winner && mutation.data.match_result && (
                      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-md">
                        <h2 className="text-xl font-bold text-slate-900 mb-4">Match Details</h2>
                        <div className="space-y-3">
                          <div className="flex items-center justify-between">
                            <span className="text-sm text-slate-600">Toss Winner</span>
                            <span className="font-semibold text-slate-900">
                              {mutation.data.toss_winner === 'home' ? selectedMatch.home_team_name : selectedMatch.away_team_name}
                            </span>
                          </div>
                          <div className="flex items-center justify-between">
                            <span className="text-sm text-slate-600">Batted First</span>
                            <span className="font-semibold text-slate-900">
                              {mutation.data.bat_first === 'home' ? selectedMatch.home_team_name : selectedMatch.away_team_name}
                            </span>
                          </div>
                          <div className="pt-3 border-t border-slate-200">
                            <div className="text-center">
                              <div className="text-lg font-bold text-emerald-600 mb-1">{mutation.data.match_result.result_text}</div>
                              <div className="text-sm text-slate-500">
                                {mutation.data.match_result.result_type === 'runs' 
                                  ? `Won by ${mutation.data.match_result.margin} runs`
                                  : `Won by ${mutation.data.match_result.margin} wickets`}
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Predicted Scores */}
                    {mutation.data.predicted_scores && (
                      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-md">
                        <h2 className="text-xl font-bold text-slate-900 mb-4">Predicted Scores</h2>
                        <div className="space-y-4">
                          <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                            <div className="text-xs text-slate-500 mb-1">First Innings</div>
                            <div className="text-sm text-slate-600 mb-1">{mutation.data.predicted_scores.first_team}</div>
                            <div className="text-3xl font-bold text-slate-900">
                              {mutation.data.predicted_scores.first_innings_score}/{mutation.data.predicted_scores.first_innings_wickets}
                            </div>
                            {mutation.data.predicted_scores.first_innings_wickets === 10 && (
                              <div className="text-xs text-red-600 mt-1">All out</div>
                            )}
                          </div>
                          <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                            <div className="text-xs text-slate-500 mb-1">Second Innings</div>
                            <div className="text-sm text-slate-600 mb-1">{mutation.data.predicted_scores.second_team}</div>
                            <div className="text-3xl font-bold text-slate-900">
                              {mutation.data.predicted_scores.second_innings_score}/{mutation.data.predicted_scores.second_innings_wickets}
                            </div>
                            {mutation.data.predicted_scores.second_innings_wickets === 10 && (
                              <div className="text-xs text-red-600 mt-1">All out</div>
                            )}
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Top Performers */}
                    <div className="grid gap-6 md:grid-cols-2">
                      {/* Top 3 Run Scorers */}
                      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-md">
                        <h3 className="text-lg font-bold text-slate-900 mb-4">Top 3 Run Scorers</h3>
                        <div className="space-y-4">
                          {/* Home Team */}
                          <div>
                            <div className="text-xs font-semibold text-emerald-700 mb-2">{selectedMatch.home_team_name}</div>
                            <div className="space-y-2">
                              {mutation.data.top_3_run_scorers?.home && mutation.data.top_3_run_scorers.home.length > 0 ? (
                                mutation.data.top_3_run_scorers.home.map((player, idx) => (
                                  <div key={player.player_id} className="rounded-lg border border-emerald-200 bg-emerald-50 p-3">
                                    <div className="flex items-center justify-between">
                                      <div>
                                        <div className="font-semibold text-slate-900">{idx + 1}. {player.player_name}</div>
                                        <div className="text-sm text-slate-600">Predicted: {player.predicted_runs} runs</div>
                                      </div>
                                    </div>
                                  </div>
                                ))
                              ) : (
                                <p className="text-sm text-slate-500">No predictions available</p>
                              )}
                            </div>
                          </div>
                          {/* Away Team */}
                          <div>
                            <div className="text-xs font-semibold text-blue-700 mb-2">{selectedMatch.away_team_name}</div>
                            <div className="space-y-2">
                              {mutation.data.top_3_run_scorers?.away && mutation.data.top_3_run_scorers.away.length > 0 ? (
                                mutation.data.top_3_run_scorers.away.map((player, idx) => (
                                  <div key={player.player_id} className="rounded-lg border border-blue-200 bg-blue-50 p-3">
                                    <div className="flex items-center justify-between">
                                      <div>
                                        <div className="font-semibold text-slate-900">{idx + 1}. {player.player_name}</div>
                                        <div className="text-sm text-slate-600">Predicted: {player.predicted_runs} runs</div>
                                      </div>
                                    </div>
                                  </div>
                                ))
                              ) : (
                                <p className="text-sm text-slate-500">No predictions available</p>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* Top 3 Wicket Takers */}
                      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-md">
                        <h3 className="text-lg font-bold text-slate-900 mb-4">Top 3 Wicket Takers</h3>
                        <div className="space-y-4">
                          {/* Home Team */}
                          <div>
                            <div className="text-xs font-semibold text-emerald-700 mb-2">{selectedMatch.home_team_name}</div>
                            <div className="space-y-2">
                              {mutation.data.top_3_wicket_takers?.home && mutation.data.top_3_wicket_takers.home.length > 0 ? (
                                mutation.data.top_3_wicket_takers.home.map((player, idx) => (
                                  <div key={player.player_id} className="rounded-lg border border-emerald-200 bg-emerald-50 p-3">
                                    <div className="flex items-center justify-between">
                                      <div>
                                        <div className="font-semibold text-slate-900">{idx + 1}. {player.player_name}</div>
                                        <div className="text-sm text-slate-600">Predicted: {player.predicted_wickets} wickets</div>
                                      </div>
                                    </div>
                                  </div>
                                ))
                              ) : (
                                <p className="text-sm text-slate-500">No predictions available</p>
                              )}
                            </div>
                          </div>
                          {/* Away Team */}
                          <div>
                            <div className="text-xs font-semibold text-blue-700 mb-2">{selectedMatch.away_team_name}</div>
                            <div className="space-y-2">
                              {mutation.data.top_3_wicket_takers?.away && mutation.data.top_3_wicket_takers.away.length > 0 ? (
                                mutation.data.top_3_wicket_takers.away.map((player, idx) => (
                                  <div key={player.player_id} className="rounded-lg border border-blue-200 bg-blue-50 p-3">
                                    <div className="flex items-center justify-between">
                                      <div>
                                        <div className="font-semibold text-slate-900">{idx + 1}. {player.player_name}</div>
                                        <div className="text-sm text-slate-600">Predicted: {player.predicted_wickets} wickets</div>
                                      </div>
                                    </div>
                                  </div>
                                ))
                              ) : (
                                <p className="text-sm text-slate-500">No predictions available</p>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Man of the Match */}
                    {mutation.data.man_of_the_match && (
                      <div className="rounded-xl border-2 border-amber-300 bg-gradient-to-r from-amber-50 to-yellow-50 p-6 shadow-md">
                        <div className="flex items-center gap-2 mb-3">
                          <span className="text-2xl">🏆</span>
                          <h3 className="text-xl font-bold text-slate-900">Man of the Match</h3>
                        </div>
                        <div className="space-y-2">
                          <div className="text-lg font-semibold text-slate-900">{mutation.data.man_of_the_match.player_name}</div>
                          <div className="text-sm text-slate-600">{mutation.data.man_of_the_match.team_name}</div>
                          <div className="flex gap-4 mt-3 text-sm">
                            <span className="text-slate-700">
                              <span className="font-semibold">Runs:</span> {mutation.data.man_of_the_match.predicted_runs}
                            </span>
                            <span className="text-slate-700">
                              <span className="font-semibold">Wickets:</span> {mutation.data.man_of_the_match.predicted_wickets}
                            </span>
                          </div>
                        </div>
                      </div>
                    )}


                    {mutation.data.predicted_starting_xi && (
                      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-md">
                        <h3 className="text-lg font-bold text-slate-900 mb-4">Projected Starting XIs</h3>
                        <div className="grid gap-6 md:grid-cols-2">
                          <StartingXIColumn
                            title={selectedMatch.home_team_name}
                            players={mutation.data.predicted_starting_xi.home}
                          />
                          <StartingXIColumn
                            title={selectedMatch.away_team_name}
                            players={mutation.data.predicted_starting_xi.away}
                          />
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

const StartingXIColumn = ({
  title,
  players,
}: {
  title: string
  players?: StartingXIPlayer[]
}) => {
  const formatRole = (role?: string) => {
    if (!role) return 'Player'
    return role
      .replace(/_/g, ' ')
      .replace(/\b\w/g, (char: string) => char.toUpperCase())
  }

  return (
    <div className="space-y-3">
      <div className="text-xs font-semibold uppercase tracking-wider text-slate-500">{title}</div>
      {players && players.length > 0 ? (
        <ul className="space-y-2">
          {players.map((player, idx) => (
            <li
              key={player.player_id}
              className="flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50 px-3 py-2"
            >
              <div>
                <div className="text-sm font-semibold text-slate-900">
                  {idx + 1}. {player.player_name}
                </div>
                <div className="text-xs text-slate-500">{formatRole(player.role)}</div>
              </div>
              <div className="text-right text-xs text-slate-600">
                <div>Runs: {player.predicted_runs}</div>
                <div>Wkts: {player.predicted_wickets}</div>
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-slate-500">Not enough data to project an XI.</p>
      )}
    </div>
  )
}

export default MatchPredictor

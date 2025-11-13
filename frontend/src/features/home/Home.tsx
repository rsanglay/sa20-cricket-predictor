import { Trophy, TrendingUp, Users, Calendar, BarChart3, Zap, Target } from 'lucide-react'
import { ReactNode, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { analyticsAPI } from '../../api/endpoints/analytics'
import { matchesAPI } from '../../api/endpoints/matches'
import { predictionsAPI } from '../../api/endpoints/predictions'
import { TeamSeasonStat, PlayerSeasonStat } from '../../types/analytics'

const metricClasses = 'rounded-xl border border-slate-200 bg-white p-6 shadow-md' as const

const Home = () => {
  const { data: teamStats } = useQuery({
    queryKey: ['home-team-stats'],
    queryFn: () => analyticsAPI.getTeamStats({ competition: 'sa20' })
  })

  const { data: batterStats } = useQuery({
    queryKey: ['home-batter-stats'],
    queryFn: () => analyticsAPI.getPlayerStats({ competition: 'sa20', minMatches: 3 }),
  })

  const { data: upcomingMatches } = useQuery({
    queryKey: ['upcoming-matches-home'],
    queryFn: () => matchesAPI.getUpcoming(2026, 5)
  })

  const { data: teamStatsAll } = useQuery({
    queryKey: ['home-all-team-stats'],
    queryFn: () => analyticsAPI.getTeamStats({ competition: 'sa20' })
  })

  const { data: topRunScorers } = useQuery({
    queryKey: ['top-run-scorers'],
    queryFn: () => predictionsAPI.getTopRunScorers(5),
    retry: false
  })

  const { data: topWicketTakers } = useQuery({
    queryKey: ['top-wicket-takers'],
    queryFn: () => predictionsAPI.getTopWicketTakers(5),
    retry: false
  })

  const topTeam = useMemo(() => {
    if (!teamStats || teamStats.length === 0) return undefined
    return teamStats.reduce<TeamSeasonStat | undefined>((best, curr) => {
      if (!best) return curr
      return curr.win_percentage > best.win_percentage ? curr : best
    }, undefined)
  }, [teamStats])

  const topBatter = useMemo(() => {
    if (!batterStats || batterStats.length === 0) return undefined
    return batterStats
      .filter((player) => player.runs > 0)
      .reduce<PlayerSeasonStat | undefined>((best, curr) => {
        if (!best) return curr
        return curr.strike_rate > best.strike_rate ? curr : best
      }, undefined)
  }, [batterStats])

  const topBowler = useMemo(() => {
    if (!batterStats || batterStats.length === 0) return undefined
    return batterStats
      .filter((player) => player.wickets > 0)
      .reduce<PlayerSeasonStat | undefined>((best, curr) => {
        if (!best) return curr
        return curr.wickets > best.wickets ? curr : best
      }, undefined)
  }, [batterStats])

  return (
    <div className="space-y-10">
      {/* Hero Section */}
      <section className="relative overflow-hidden rounded-3xl border-2 border-emerald-200 bg-gradient-to-br from-emerald-50 via-white to-emerald-50/30 p-10 md:p-12 shadow-2xl">
        {/* Background Pattern */}
        <div className="absolute inset-0 opacity-5">
          <div className="absolute inset-0" style={{
            backgroundImage: 'radial-gradient(circle at 2px 2px, rgb(16 185 129) 1px, transparent 0)',
            backgroundSize: '50px 50px'
          }} />
        </div>
        
        <div className="relative flex flex-col gap-8 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex-1">
            <div className="inline-flex items-center gap-2 rounded-full bg-emerald-100 px-4 py-2 mb-4">
              <Zap className="h-4 w-4 text-emerald-600" />
              <p className="text-xs uppercase tracking-wider text-emerald-700 font-bold">AI-Powered Cricket Intelligence</p>
            </div>
            <h1 className="text-5xl md:text-6xl font-extrabold leading-tight text-slate-900 mb-4">
              SA20 Pre-Season Intelligence Platform
            </h1>
            <p className="max-w-3xl text-lg text-slate-700 leading-relaxed mb-6">
              A comprehensive analytics platform that combines historical performance data, machine learning predictions, and advanced scenario analysis to help you make data-driven decisions for the SA20 cricket league. 
              <span className="font-semibold text-slate-900"> Understand team strengths, predict match outcomes, analyze player performance, and optimize fantasy teams</span> — all before the season begins.
            </p>
            
            {/* Key Features */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
              <div className="flex items-start gap-3 p-4 rounded-xl bg-white/80 backdrop-blur-sm border border-emerald-100">
                <div className="rounded-lg bg-emerald-100 p-2">
                  <TrendingUp className="h-5 w-5 text-emerald-600" />
                </div>
                <div>
                  <p className="font-bold text-sm text-slate-900 mb-1">ML Predictions</p>
                  <p className="text-xs text-slate-600">Match & player performance forecasts</p>
                </div>
              </div>
              <div className="flex items-start gap-3 p-4 rounded-xl bg-white/80 backdrop-blur-sm border border-emerald-100">
                <div className="rounded-lg bg-emerald-100 p-2">
                  <BarChart3 className="h-5 w-5 text-emerald-600" />
                </div>
                <div>
                  <p className="font-bold text-sm text-slate-900 mb-1">Multi-League Data</p>
                  <p className="text-xs text-slate-600">SA20, IPL, BBL, IT20s coverage</p>
                </div>
              </div>
              <div className="flex items-start gap-3 p-4 rounded-xl bg-white/80 backdrop-blur-sm border border-emerald-100">
                <div className="rounded-lg bg-emerald-100 p-2">
                  <Target className="h-5 w-5 text-emerald-600" />
                </div>
                <div>
                  <p className="font-bold text-sm text-slate-900 mb-1">Season Simulation</p>
                  <p className="text-xs text-slate-600">Monte Carlo tournament modeling</p>
                </div>
              </div>
            </div>
            
            <div className="flex flex-wrap gap-3">
              <Link
                to="/season-simulator-v2"
                className="rounded-xl bg-emerald-600 px-8 py-3 text-sm font-bold text-white shadow-lg transition-all hover:bg-emerald-700 hover:shadow-xl hover:-translate-y-0.5"
              >
                Explore Season Simulator
              </Link>
              <Link
                to="/players"
                className="rounded-xl border-2 border-emerald-600 bg-white px-8 py-3 text-sm font-bold text-emerald-700 transition-all hover:bg-emerald-50 hover:shadow-md"
              >
                Analyze Players
              </Link>
              <Link
                to="/teams"
                className="rounded-xl border-2 border-slate-300 bg-white px-8 py-3 text-sm font-bold text-slate-700 transition-all hover:bg-slate-50 hover:border-slate-400"
              >
                Browse Teams
              </Link>
            </div>
          </div>
          <div className="lg:w-96">
            <div className="rounded-2xl border-2 border-emerald-200 bg-white p-6 shadow-xl">
              <p className="text-xs uppercase tracking-wider text-emerald-600 font-bold mb-3">Platform Status</p>
              <div className="space-y-4">
                <div className="flex items-center justify-between p-3 rounded-lg bg-emerald-50">
                  <span className="text-sm font-semibold text-slate-700">ML Models</span>
                  <span className="text-sm font-bold text-emerald-700">Active</span>
                </div>
                <div className="flex items-center justify-between p-3 rounded-lg bg-blue-50">
                  <span className="text-sm font-semibold text-slate-700">Data Sources</span>
                  <span className="text-sm font-bold text-blue-700">4 Leagues</span>
                </div>
                <div className="flex items-center justify-between p-3 rounded-lg bg-purple-50">
                  <span className="text-sm font-semibold text-slate-700">Players Analyzed</span>
                  <span className="text-sm font-bold text-purple-700">200+</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* What This Platform Does */}
      <section className="rounded-3xl border-2 border-slate-200 bg-gradient-to-br from-slate-50 to-white p-10 shadow-xl">
        <div className="mb-8">
          <div className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-4 py-2 mb-4">
            <BarChart3 className="h-4 w-4 text-slate-600" />
            <p className="text-xs uppercase tracking-wider text-slate-700 font-bold">Platform Overview</p>
          </div>
          <h2 className="text-4xl font-extrabold text-slate-900 mb-4">What This Platform Does</h2>
          <p className="text-lg text-slate-700 max-w-4xl leading-relaxed">
            This platform provides comprehensive pre-season intelligence for the SA20 cricket league through advanced data analytics, 
            machine learning predictions, and interactive visualization tools. Whether you're a coach, analyst, fantasy cricket enthusiast, 
            or cricket fan, you can leverage data-driven insights to understand team dynamics, predict outcomes, and make informed decisions.
          </p>
        </div>
        
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3 mt-8">
          <div className="rounded-2xl border-2 border-emerald-200 bg-white p-6 shadow-lg hover:shadow-xl transition-shadow">
            <div className="rounded-xl bg-emerald-100 w-12 h-12 flex items-center justify-center mb-4">
              <Users className="h-6 w-6 text-emerald-600" />
            </div>
            <h3 className="text-xl font-extrabold text-slate-900 mb-2">Team & Player Analysis</h3>
            <p className="text-sm text-slate-600 leading-relaxed">
              Explore comprehensive player profiles with photos, statistics, career history, and performance trends. Analyze team squads, 
              compare players across different metrics, and identify key strengths and weaknesses.
            </p>
          </div>
          
          <div className="rounded-2xl border-2 border-blue-200 bg-white p-6 shadow-lg hover:shadow-xl transition-shadow">
            <div className="rounded-xl bg-blue-100 w-12 h-12 flex items-center justify-center mb-4">
              <TrendingUp className="h-6 w-6 text-blue-600" />
            </div>
            <h3 className="text-xl font-extrabold text-slate-900 mb-2">Machine Learning Predictions</h3>
            <p className="text-sm text-slate-600 leading-relaxed">
              Get AI-powered predictions for match outcomes, player performance (runs and wickets), and season-long projections. 
              Models are trained on historical data from SA20, IPL, BBL, and IT20s leagues.
            </p>
          </div>
          
          <div className="rounded-2xl border-2 border-purple-200 bg-white p-6 shadow-lg hover:shadow-xl transition-shadow">
            <div className="rounded-xl bg-purple-100 w-12 h-12 flex items-center justify-center mb-4">
              <Target className="h-6 w-6 text-purple-600" />
            </div>
            <h3 className="text-xl font-extrabold text-slate-900 mb-2">Season Simulation</h3>
            <p className="text-sm text-slate-600 leading-relaxed">
              Run Monte Carlo simulations to predict tournament outcomes, playoff probabilities, and final standings. 
              Understand different scenarios and how team performance variations affect overall results.
            </p>
          </div>
          
          <div className="rounded-2xl border-2 border-amber-200 bg-white p-6 shadow-lg hover:shadow-xl transition-shadow">
            <div className="rounded-xl bg-amber-100 w-12 h-12 flex items-center justify-center mb-4">
              <Trophy className="h-6 w-6 text-amber-600" />
            </div>
            <h3 className="text-xl font-extrabold text-slate-900 mb-2">Match Predictions</h3>
            <p className="text-sm text-slate-600 leading-relaxed">
              Analyze upcoming fixtures with win probability predictions, key factors, and team matchup insights. 
              Get detailed breakdowns of what influences match outcomes.
            </p>
          </div>
          
          <div className="rounded-2xl border-2 border-red-200 bg-white p-6 shadow-lg hover:shadow-xl transition-shadow">
            <div className="rounded-xl bg-red-100 w-12 h-12 flex items-center justify-center mb-4">
              <Zap className="h-6 w-6 text-red-600" />
            </div>
            <h3 className="text-xl font-extrabold text-slate-900 mb-2">Fantasy Optimizer</h3>
            <p className="text-sm text-slate-600 leading-relaxed">
              Optimize your fantasy cricket teams using predicted player performance metrics. 
              Identify undervalued players and build winning combinations based on data-driven insights.
            </p>
          </div>
          
          <div className="rounded-2xl border-2 border-indigo-200 bg-white p-6 shadow-lg hover:shadow-xl transition-shadow">
            <div className="rounded-xl bg-indigo-100 w-12 h-12 flex items-center justify-center mb-4">
              <BarChart3 className="h-6 w-6 text-indigo-600" />
            </div>
            <h3 className="text-xl font-extrabold text-slate-900 mb-2">Historical Analytics</h3>
            <p className="text-sm text-slate-600 leading-relaxed">
              Access comprehensive historical data across multiple T20 leagues. Compare team performance, 
              player statistics, head-to-head records, and seasonal trends to inform your analysis.
            </p>
          </div>
        </div>
      </section>

      {/* Key Metrics */}
      <section className="grid gap-6 md:grid-cols-3">
        <MetricCard
          icon={<Trophy className="h-8 w-8 text-amber-500" />}
          label="Top franchise by win %"
          primary={topTeam ? topTeam.team_name : 'Awaiting data'}
          secondary={topTeam ? `${(topTeam.win_percentage * 100).toFixed(1)}% win rate` : 'Run training pipeline to populate'}
        />
        <MetricCard
          icon={<TrendingUp className="h-8 w-8 text-emerald-600" />}
          label="Explosive batter"
          primary={topBatter ? topBatter.player_name : 'Awaiting data'}
          secondary={topBatter ? `${topBatter.runs.toFixed(0)} runs • SR ${(topBatter.strike_rate).toFixed(1)}` : 'Need aggregated stats'}
        />
        <MetricCard
          icon={<Users className="h-8 w-8 text-blue-600" />}
          label="Wicket magnet"
          primary={topBowler ? topBowler.player_name : 'Awaiting data'}
          secondary={
            topBowler
              ? `${topBowler.wickets.toFixed(0)} wickets • Econ ${(topBowler.economy_rate ?? 0).toFixed(2)}`
              : 'Need aggregated stats'
          }
        />
      </section>

      {/* Upcoming Matches Section */}
      {upcomingMatches && upcomingMatches.length > 0 && (
        <section className="rounded-3xl border-2 border-slate-200 bg-white p-8 shadow-xl">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-3xl font-extrabold text-slate-900 mb-2">Upcoming Fixtures</h2>
              <p className="text-base text-slate-600">SA20 2026 season schedule</p>
            </div>
            <Link
              to="/matches"
              className="rounded-xl border-2 border-emerald-600 bg-white px-5 py-2.5 text-sm font-bold text-emerald-700 transition-all hover:bg-emerald-50 hover:shadow-md"
            >
              View all →
            </Link>
          </div>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {upcomingMatches.slice(0, 6).map((match) => (
              <div
                key={match.id}
                className="rounded-2xl border-2 border-slate-200 bg-gradient-to-br from-slate-50 to-white p-5 hover:border-emerald-300 hover:shadow-lg transition-all"
              >
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs font-bold text-emerald-600 bg-emerald-50 px-3 py-1 rounded-full">
                    {match.match_number ? `Match ${match.match_number}` : 'TBD'}
                  </span>
                  <span className="text-xs text-slate-600 flex items-center gap-1 font-semibold">
                    <Calendar className="h-3 w-3" />
                    {new Date(match.match_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                  </span>
                </div>
                <div className="font-extrabold text-slate-900 text-base mb-2">
                  {match.home_team_name || `Team ${match.home_team_id}`}
                </div>
                <div className="text-xs text-slate-400 mb-2 font-bold">VS</div>
                <div className="font-extrabold text-slate-900 text-base mb-3">
                  {match.away_team_name || `Team ${match.away_team_id}`}
                </div>
                <div className="text-xs text-slate-600 font-medium flex items-center gap-1">
                  <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                  {match.venue_name}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Tournament Structure */}
      <section className="rounded-3xl border-2 border-slate-200 bg-gradient-to-br from-slate-50 to-white p-8 shadow-xl">
        <div className="flex items-center gap-3 mb-6">
          <div className="rounded-xl bg-emerald-100 p-2">
            <BarChart3 className="h-6 w-6 text-emerald-600" />
          </div>
          <div>
            <h2 className="text-3xl font-extrabold text-slate-900">SA20 2026 Tournament Structure</h2>
            <p className="text-sm text-slate-600 mt-1">Complete tournament format and schedule</p>
          </div>
        </div>
        <div className="grid gap-6 md:grid-cols-3">
          <div className="rounded-2xl border-2 border-emerald-200 bg-gradient-to-br from-emerald-50 to-emerald-100/50 p-6 shadow-lg hover:shadow-xl transition-shadow">
            <div className="text-sm font-bold text-emerald-700 mb-2 uppercase tracking-wider">Group Stage</div>
            <div className="text-4xl font-extrabold text-emerald-900 mb-2">30 Matches</div>
            <div className="text-sm text-emerald-700 font-semibold mb-3">Dec 26, 2025 - Jan 19, 2026</div>
            <div className="text-sm text-slate-700 leading-relaxed">Each team plays every other team twice in a round-robin format</div>
          </div>
          <div className="rounded-2xl border-2 border-blue-200 bg-gradient-to-br from-blue-50 to-blue-100/50 p-6 shadow-lg hover:shadow-xl transition-shadow">
            <div className="text-sm font-bold text-blue-700 mb-2 uppercase tracking-wider">Playoffs</div>
            <div className="text-4xl font-extrabold text-blue-900 mb-2">3 Matches</div>
            <div className="text-sm text-blue-700 font-semibold mb-3">Jan 21-23, 2026</div>
            <div className="text-sm text-slate-700 leading-relaxed">Top 4 teams compete for final spots through eliminator and qualifier matches</div>
          </div>
          <div className="rounded-2xl border-2 border-amber-200 bg-gradient-to-br from-amber-50 to-amber-100/50 p-6 shadow-lg hover:shadow-xl transition-shadow">
            <div className="text-sm font-bold text-amber-700 mb-2 uppercase tracking-wider">Final</div>
            <div className="text-4xl font-extrabold text-amber-900 mb-2">1 Match</div>
            <div className="text-sm text-amber-700 font-semibold mb-3">Jan 25, 2026</div>
            <div className="text-sm text-slate-700 leading-relaxed">Championship decider match to crown the SA20 2026 champions</div>
          </div>
        </div>
      </section>

      {/* Platform Modules */}
      <section className="rounded-3xl border-2 border-slate-200 bg-gradient-to-br from-white to-slate-50 p-10 shadow-xl">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between mb-8">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full bg-emerald-100 px-4 py-2 mb-4">
              <Zap className="h-4 w-4 text-emerald-600" />
              <p className="text-xs uppercase tracking-wider text-emerald-700 font-bold">Explore Features</p>
            </div>
            <h2 className="text-4xl font-extrabold text-slate-900 mb-2">Platform Modules</h2>
            <p className="text-lg text-slate-700 max-w-2xl">
              Navigate to dedicated workspaces to begin your comprehensive pre-season analysis and predictions.
            </p>
          </div>
          <span className="rounded-full border-2 border-emerald-300 bg-gradient-to-r from-emerald-50 to-emerald-100 px-6 py-2.5 text-xs uppercase tracking-wider font-bold text-emerald-700 shadow-md">
            Powered by ML
          </span>
        </div>
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {featureCards.map((card) => (
            <Link
              key={card.title}
              to={card.href}
              className="group rounded-2xl border-2 border-slate-200 bg-white p-6 shadow-lg transition-all hover:-translate-y-2 hover:border-emerald-400 hover:shadow-2xl"
            >
              <div className="flex items-center justify-between mb-4">
                <span className="text-xs font-bold uppercase tracking-wider text-emerald-600 bg-emerald-50 px-3 py-1 rounded-full">{card.tag}</span>
                <svg className="h-5 w-5 text-slate-400 transition-transform group-hover:translate-x-1 group-hover:text-emerald-600" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} viewBox="0 0 24 24">
                  <path d="M5 12h14" />
                  <path d="M12 5l7 7-7 7" />
                </svg>
              </div>
              <div className="mt-3 text-xl font-extrabold text-slate-900 mb-3 group-hover:text-emerald-700 transition-colors">{card.title}</div>
              <p className="text-sm text-slate-600 leading-relaxed mb-4">{card.description}</p>
              <span className="inline-flex items-center text-sm font-bold text-emerald-600 group-hover:text-emerald-700">
                Explore module
                <svg className="ml-2 h-4 w-4 transition-transform group-hover:translate-x-1" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} viewBox="0 0 24 24">
                  <path d="M9 5l7 7-7 7" />
                </svg>
              </span>
            </Link>
          ))}
        </div>
      </section>

      {/* Top Run Scorer & Wicket Taker Predictions */}
      {(topRunScorers || topWicketTakers) && (
        <section className="grid gap-8 md:grid-cols-2">
          {topRunScorers && topRunScorers.predictions && topRunScorers.predictions.length > 0 && (
            <div className="rounded-3xl border-2 border-emerald-200 bg-gradient-to-br from-emerald-50 via-white to-emerald-50/30 p-8 shadow-xl">
              <div className="flex items-center gap-4 mb-6">
                <div className="rounded-xl bg-emerald-100 p-3">
                  <Target className="h-6 w-6 text-emerald-600" />
                </div>
                <div>
                  <h2 className="text-2xl font-extrabold text-slate-900">Predicted Top Run Scorer</h2>
                  <p className="text-sm text-slate-600 mt-1">ML-powered season projections</p>
                </div>
              </div>
              <div className="space-y-3">
                {topRunScorers.predictions.slice(0, 5).map((player, index) => (
                  <div
                    key={player.player_id}
                    className="flex items-center justify-between rounded-xl border-2 border-emerald-200 bg-white p-4 shadow-md hover:shadow-lg hover:border-emerald-300 transition-all"
                  >
                    <div className="flex items-center gap-4">
                      <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-emerald-500 to-emerald-600 text-sm font-extrabold text-white shadow-md">
                        {index + 1}
                      </div>
                      <div>
                        <div className="font-extrabold text-slate-900">{player.player_name}</div>
                        <div className="text-xs text-slate-600 font-medium">{player.team_name || 'TBD'}</div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-2xl font-extrabold text-emerald-700">{player.predicted_runs.toFixed(0)}</div>
                      <div className="text-xs text-slate-500 font-semibold uppercase tracking-wide">runs</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {topWicketTakers && topWicketTakers.predictions && topWicketTakers.predictions.length > 0 && (
            <div className="rounded-3xl border-2 border-blue-200 bg-gradient-to-br from-blue-50 via-white to-blue-50/30 p-8 shadow-xl">
              <div className="flex items-center gap-4 mb-6">
                <div className="rounded-xl bg-blue-100 p-3">
                  <Target className="h-6 w-6 text-blue-600" />
                </div>
                <div>
                  <h2 className="text-2xl font-extrabold text-slate-900">Predicted Top Wicket Taker</h2>
                  <p className="text-sm text-slate-600 mt-1">ML-powered season projections</p>
                </div>
              </div>
              <div className="space-y-3">
                {topWicketTakers.predictions.slice(0, 5).map((player, index) => (
                  <div
                    key={player.player_id}
                    className="flex items-center justify-between rounded-xl border-2 border-blue-200 bg-white p-4 shadow-md hover:shadow-lg hover:border-blue-300 transition-all"
                  >
                    <div className="flex items-center gap-4">
                      <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-blue-500 to-blue-600 text-sm font-extrabold text-white shadow-md">
                        {index + 1}
                      </div>
                      <div>
                        <div className="font-extrabold text-slate-900">{player.player_name}</div>
                        <div className="text-xs text-slate-600 font-medium">{player.team_name || 'TBD'}</div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-2xl font-extrabold text-blue-700">{player.predicted_wickets.toFixed(0)}</div>
                      <div className="text-xs text-slate-500 font-semibold uppercase tracking-wide">wickets</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>
      )}

      {/* Additional Stats */}
      {teamStatsAll && teamStatsAll.length > 0 && (
        <section className="rounded-3xl border-2 border-slate-200 bg-gradient-to-br from-white to-slate-50 p-8 shadow-xl">
          <div className="flex items-center gap-4 mb-6">
            <div className="rounded-xl bg-emerald-100 p-3">
              <Zap className="h-6 w-6 text-emerald-600" />
            </div>
            <div>
              <h2 className="text-3xl font-extrabold text-slate-900">Platform Statistics</h2>
              <p className="text-sm text-slate-600 mt-1">Key metrics and data coverage</p>
            </div>
          </div>
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
            <StatCard
              label="Total Teams"
              value="6"
              subtitle="SA20 franchises"
            />
            <StatCard
              label="Total Matches"
              value="34"
              subtitle="30 group + 4 playoffs"
            />
            <StatCard
              label="Players Analyzed"
              value="200+"
              subtitle="Across all teams"
            />
            <StatCard
              label="Data Sources"
              value="4"
              subtitle="SA20, IPL, BBL, IT20s"
            />
          </div>
        </section>
      )}
    </div>
  )
}

interface MetricCardProps {
  icon: ReactNode
  label: string
  primary: string
  secondary: string
}

const MetricCard = ({ icon, label, primary, secondary }: MetricCardProps) => (
  <div className="rounded-2xl border-2 border-slate-200 bg-white p-6 shadow-lg hover:shadow-xl transition-shadow">
    <div className="flex items-center justify-between mb-4">
      <div className="rounded-xl bg-slate-100 p-3 shadow-md">{icon}</div>
      <span className="text-xs font-bold uppercase tracking-wide text-slate-500 bg-slate-100 px-3 py-1 rounded-full">Snapshot</span>
    </div>
    <div className="mt-4 text-sm font-semibold text-slate-600 mb-2">{label}</div>
    <div className="mt-2 text-2xl font-extrabold text-slate-900 mb-2">{primary}</div>
    <div className="mt-1 text-sm text-slate-500">{secondary}</div>
  </div>
)

const StatCard = ({ label, value, subtitle }: { label: string; value: string; subtitle: string }) => (
  <div className="rounded-2xl border-2 border-slate-200 bg-white p-6 shadow-lg hover:shadow-xl transition-shadow">
    <div className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">{label}</div>
    <div className="text-4xl font-extrabold text-slate-900 mb-2">{value}</div>
    <div className="text-sm text-slate-600 font-medium">{subtitle}</div>
  </div>
)

const featureCards = [
  {
    title: 'Teams',
    description: 'Browse all SA20 teams and explore player squads with photos, roles, and statistics.',
    href: '/teams',
    tag: 'Explore'
  },
  {
    title: 'Season Simulator',
    description: 'Simulate full tournament from group stage to final. Monte Carlo modelling with playoff progression.',
    href: '/season-simulator-v2',
    tag: 'Forecast'
  },
  {
    title: 'Player Profiler',
    description: 'Inspect player resumes, form lines, and ML projections for upcoming fixtures.',
    href: '/players',
    tag: 'Scout'
  },
  {
    title: 'Match Predictor',
    description: 'Select actual SA20 2026 fixtures and generate match-day win probabilities with key factors.',
    href: '/matches',
    tag: 'Plan'
  }
]

export default Home

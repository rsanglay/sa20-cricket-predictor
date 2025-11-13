# Season Simulator - Current State & Performance Issues

## What We Have Built

### Features Implemented:
1. **Match-by-Match Simulation**: Simulates each match individually (not bulk), updating the league table after each match
2. **Pre-Match Sequence**: Shows toss animation (heads/tails) and lineup reveal with player photos before each match
3. **League Standings Table**: Displays:
   - Position, Team Name
   - Matches Played (P), Wins (W), Losses (L), No Results (NR)
   - Points (2 for win, 1 for no result, 0 for loss)
   - Net Run Rate (NRR)
   - Top 4 teams highlighted with trophy icon
4. **Playoff Structure**: 
   - Top 4 teams qualify
   - Semifinal 1: 1st vs 2nd
   - Semifinal 2: 3rd vs 4th
   - Eliminator: Loser of Semifinal 1 vs Winner of Semifinal 2
   - Final: Winner of Semifinal 1 vs Winner of Eliminator
5. **Top Performers Tracking**: Tracks Orange Cap (top run scorer), Purple Cap (top wicket taker), and MVP throughout season
6. **Design**: Matches MatchPredictor component style (light theme, white cards, emerald accents)
7. **Speed Control**: 1x, 2x, 5x, 10x speed multipliers
8. **Match Duration**: 15 seconds per match at 1x speed

### Technical Stack:
- React + TypeScript
- Zustand for state management
- Framer Motion for animations
- Tailwind CSS for styling
- Individual API calls for each match prediction

### Components Structure:
- `SeasonSimulatorV2.tsx` - Main orchestrator component
- `LeagueSimulation.tsx` - Main league stage view
- `LiveMatchCard.tsx` - Shows current match details, win probabilities, scores, top performers
- `StandingsTable.tsx` - League standings table with animations
- `RecentResults.tsx` - Shows recent match results
- `TopPerformers.tsx` - Shows current top performers
- `PreMatchSequence.tsx` - Orchestrates toss + lineup reveal
- `TossAnimation.tsx` - Coin toss animation
- `LineupReveal.tsx` - Team lineups with player photos
- `useSimulationLoop.ts` - Hook that manages the simulation loop

### State Management:
- Zustand store (`simulationStore.ts`) manages:
  - Current phase (INTRO, LEAGUE, PRE_MATCH, QUALIFICATION, PLAYOFFS, etc.)
  - Matches array
  - Standings array
  - Current match index
  - Top performers
  - Play/pause state
  - Speed multiplier

## UI Problems Stated

### Primary Issue:
**"the simulation isnt smooth and i need it to be smooth"**
**"still very glitchy and not smooth"**

### Specific Symptoms (Inferred):
1. **Janky animations**: Animations stutter or lag during match transitions
2. **Standings table glitches**: Table updates cause visual jumps or flickering
3. **Match card transitions**: Smooth transitions between matches are not working properly
4. **Performance issues**: Multiple re-renders causing UI lag
5. **State update delays**: Visual updates don't happen smoothly when standings change

## What We've Tried (Current Optimizations)

1. **RequestAnimationFrame batching**: Wrapped state updates in `requestAnimationFrame` for smoother rendering
2. **useCallback memoization**: Memoized `updateStandings`, `updateTopPerformers`, `determinePlayoffTeams`
3. **useMemo for current match**: Memoized current match calculation
4. **Transition delays**: Added 500ms delays between matches
5. **Framer Motion animations**: Used layout animations for standings table
6. **AnimatePresence**: Used for match card transitions
7. **Cleanup**: Proper cleanup of timers and animation frames

## Desired Outcome

### Performance Requirements:
1. **Smooth 60fps animations**: All animations should run at consistent 60fps without stuttering
2. **Seamless match transitions**: When moving from one match to the next, transitions should be fluid
3. **Smooth standings updates**: When standings table updates after a match, rows should smoothly animate to new positions without jumping
4. **No visual glitches**: No flickering, jumping, or jarring visual updates
5. **Responsive UI**: UI should remain responsive during simulation (no freezing or lag)

### Expected Behavior:
- Match card should smoothly fade/transition when moving to next match
- Standings table rows should smoothly animate to new positions when rankings change
- Progress bar should smoothly animate
- Win probability bars should animate smoothly
- All state updates should be visually smooth without causing re-render jank

## Technical Details

### Current Simulation Flow:
1. User clicks "Play" → Goes directly to LEAGUE phase
2. For each match:
   - Fetch prediction data (if not already fetched)
   - Transition to PRE_MATCH phase → Show toss + lineups
   - Return to LEAGUE phase → Show match card with probabilities
   - After 15 seconds (at 1x speed), determine winner
   - Update match with result
   - Update standings (recalculate all stats, sort by points/NRR/wins)
   - Update top performers
   - Move to next match
3. After all matches → QUALIFICATION → PLAYOFFS → FINAL → CHAMPION → TROPHY → REWIND → ANALYTICS

### Potential Performance Bottlenecks:
1. **Standings recalculation**: Recalculating all team stats and sorting on every match completion
2. **Top performers aggregation**: Aggregating player stats from all matches on every update
3. **Multiple state updates**: Multiple Zustand store updates happening in quick succession
4. **Component re-renders**: Large components (StandingsTable, RecentResults) re-rendering on every state change
5. **Animation conflicts**: Multiple animations running simultaneously
6. **No component memoization**: Components not memoized, causing unnecessary re-renders

## Questions for Claude

1. How can we optimize the standings table updates to prevent visual glitches when rankings change?
2. What's the best way to batch Zustand state updates to prevent multiple re-renders?
3. Should we use React.memo for components like StandingsTable, RecentResults, TopPerformers?
4. How can we optimize the standings recalculation to be more performant?
5. Are there better animation strategies for smooth transitions between matches?
6. Should we debounce or throttle certain state updates?
7. Are there React performance best practices we're missing?
8. How can we ensure 60fps smooth animations during the simulation?


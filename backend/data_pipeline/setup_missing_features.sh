#!/bin/bash
# Setup script to populate all missing features

set -e

echo "🚀 Setting up missing features for SA20 Cricket Predictor"
echo ""

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"
cd "$PROJECT_ROOT"

# Check if we're in a virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  Warning: Not in a virtual environment"
    echo "   Consider activating your virtual environment first"
    echo ""
fi

# Step 1: Run database migration
echo "📦 Step 1: Running database migration..."
cd backend
if command -v alembic &> /dev/null; then
    alembic upgrade head
    echo "✅ Migration complete"
else
    echo "❌ Alembic not found. Please install: pip install alembic"
    exit 1
fi
echo ""

# Step 2: Populate match data (toss, UTC, stage)
echo "📊 Step 2: Populating match data (toss, UTC times, match stages)..."
if python -c "import sys; sys.path.insert(0, '.'); from data_pipeline.populate_match_data import main" 2>/dev/null; then
    python -m data_pipeline.populate_match_data --all
    echo "✅ Match data populated"
else
    echo "❌ Error: Could not import populate_match_data"
    echo "   Make sure you're in the backend directory and dependencies are installed"
    exit 1
fi
echo ""

# Step 3: Calculate player form trends
echo "👤 Step 3: Calculating player form trends..."
if python -c "import sys; sys.path.insert(0, '.'); from data_pipeline.calculate_player_form import main" 2>/dev/null; then
    python -m data_pipeline.calculate_player_form --window 5
    echo "✅ Player form trends calculated"
else
    echo "⚠️  Warning: Could not calculate player form trends"
    echo "   You can run this manually later: python -m data_pipeline.calculate_player_form"
fi
echo ""

# Step 4: Calculate venue statistics
echo "🏟️  Step 4: Calculating venue statistics (including toss bias)..."
if python -c "import sys; sys.path.insert(0, '.'); from data_pipeline.calculate_venue_stats import main" 2>/dev/null; then
    python -m data_pipeline.calculate_venue_stats
    echo "✅ Venue statistics calculated"
else
    echo "⚠️  Warning: Could not calculate venue statistics"
    echo "   You can run this manually later: python -m data_pipeline.calculate_venue_stats"
fi
echo ""

echo "✅ Setup complete!"
echo ""
echo "📝 Next steps:"
echo "   1. Verify data was populated correctly"
echo "   2. Check the database for updated records"
echo "   3. Update ML models to use new features"
echo "   4. Test predictions with new data"
echo ""


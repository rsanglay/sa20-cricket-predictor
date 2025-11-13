#!/bin/bash
# Setup script for SA20 Cricket Predictor

set -e

echo "🚀 Setting up SA20 Cricket Predictor..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker and try again."
    exit 1
fi

echo "✓ Docker is running"

# Start PostgreSQL and Redis
echo "📦 Starting PostgreSQL and Redis..."
docker-compose up -d postgres redis

# Wait for PostgreSQL to be ready
echo "⏳ Waiting for PostgreSQL to be ready..."
sleep 5

# Check if PostgreSQL is ready
until docker-compose exec -T postgres pg_isready -U postgres > /dev/null 2>&1; do
    echo "Waiting for PostgreSQL..."
    sleep 2
done

echo "✓ PostgreSQL is ready"

# Install backend dependencies if needed
if [ ! -d "backend/venv" ]; then
    echo "📦 Creating Python virtual environment..."
    cd backend
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    cd ..
else
    echo "✓ Python virtual environment exists"
fi

# Create initial migration
echo "📝 Creating initial Alembic migration..."
cd backend

if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Check if migration already exists
if [ -n "$(ls -A migrations/versions 2>/dev/null)" ]; then
    echo "⚠️  Migrations already exist. Skipping migration creation."
    echo "   To create a new migration, run: alembic revision --autogenerate -m 'Migration name'"
else
    echo "Creating initial migration..."
    alembic revision --autogenerate -m "Initial migration" || {
        echo "❌ Failed to create migration. Make sure:"
        echo "   1. PostgreSQL is running and accessible"
        echo "   2. DATABASE_URL is set correctly"
        echo "   3. All dependencies are installed"
        exit 1
    }
    
    echo "✓ Migration created successfully"
    
    # Apply migration
    echo "📊 Applying migration..."
    alembic upgrade head || {
        echo "⚠️  Migration apply failed. This might be normal if tables already exist."
        echo "   You can manually run: alembic upgrade head"
    }
fi

cd ..

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Start the backend: cd backend && python -m uvicorn app.main:app --reload --port 8002"
echo "  2. Start the frontend: cd frontend && npm run dev"
echo "  3. Or use Docker Compose: docker-compose up --build"
echo ""
echo "To train models:"
echo "  cd backend && python -m app.ml.training.train_match_model"
echo "  cd backend && python -m app.ml.training.train_player_models"
echo ""


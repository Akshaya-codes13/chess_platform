
#!/usr/bin/env bash
set -e

# Run inside your existing cloned GitHub repository
echo "Creating Chess Academy project structure..."

# ---------- root ----------
mkdir -p .github/workflows docs

touch .github/workflows/ci.yml
touch docker-compose.yml README.md

cat > .gitignore <<'EOF'
node_modules/
__pycache__/
*.pyc
venv/
.venv/
.env
dist/
.DS_Store
*.log
EOF

# ---------- backend ----------
mkdir -p backend/app/{core,models,schemas,routers,services,ws,workers,agents,utils}
mkdir -p backend/{alembic/versions,scripts,tests}

touch backend/app/__init__.py backend/app/main.py

touch backend/app/core/{__init__,config,database,redis,security,deps}.py

touch backend/app/models/{__init__,user,session,assignment,puzzle,game,gamification,content,feedback,notification}.py

touch backend/app/schemas/{__init__,auth,user,session,assignment,puzzle,game,gamification,content,feedback}.py

touch backend/app/routers/{__init__,auth,users,sessions,assignments,puzzles,games,gamification,reports,content,feedback,notifications}.py

touch backend/app/services/{__init__,auth_service,xp_service,streak_service,stats_service,assignment_service}.py

touch backend/app/ws/{__init__,manager,game_ws,notification_ws}.py

touch backend/app/workers/{__init__,worker,daily_stats,reminders}.py

touch backend/app/agents/{__init__,coach_agent,assignment_agent,insights_agent,tools}.py

touch backend/app/utils/{__init__,pagination}.py

touch backend/scripts/{seed,import_lichess_puzzles}.py

touch backend/tests/{__init__,conftest,test_auth,test_assignments}.py

touch backend/requirements.txt
touch backend/Dockerfile
touch backend/.env.example
touch backend/alembic.ini

# ---------- frontend ----------
# Scaffold React + Vite only if frontend does not exist
if [ ! -d "frontend" ]; then
    npm create vite@latest frontend -- --template react
else
    echo "Frontend directory already exists. Skipping Vite scaffold."
fi

cd frontend

mkdir -p public src/{api,assets,hooks,routes,store,lib,styles}
mkdir -p src/components/{ui,layout,chess}

for f in auth sessions assignments puzzles games gamification reports content feedback analyze; do
    mkdir -p src/features/$f
    touch src/features/$f/.gitkeep
done

mkdir -p src/pages/{admin,trainer,student,auth}

touch src/api/client.js
touch src/routes/{AppRouter,ProtectedRoute}.jsx
touch src/store/authStore.js

touch src/components/layout/{Sidebar,BottomNav,AppShell}.jsx
touch src/components/chess/{Board,MoveList,EnginePanel}.jsx
touch src/components/ui/{Button,Card,Tabs,EmptyState}.jsx

touch .env.example

cd ..

echo "=================================="
echo "Chess Academy structure created!"
echo "Repository: $(pwd)"
echo "=================================="

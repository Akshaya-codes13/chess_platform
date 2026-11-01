# ♟️ Chess Academy Platform

A full-stack Progressive Web Application (PWA) designed to manage chess academy operations, connect trainers with students, organize training sessions, assign chess puzzles, and track student progress.

## 🎯 Project Overview

Chess Academy provides a centralized platform for managing chess training activities.

The application supports three primary roles:

- **Admin:** Manages users, trainers, students, academy operations, and platform analytics.
- **Trainer:** Manages students, conducts sessions, assigns puzzles, and monitors student performance.
- **Student:** Accesses assignments, solves puzzles, views progress, and participates in chess activities.

## ✨ Planned Features

- Role-based authentication and authorization
- Student and trainer management
- Chessboard and interactive puzzle system
- Training sessions and attendance tracking
- Assignment creation and submission
- PGN game database and board editor
- Student progress reports and analytics
- XP, levels, badges, and streaks
- Blogs, gallery, and feedback
- Live chess games
- AI-powered coaching and assignment assistance
- Progressive Web App support

## 🏗️ Technology Stack

| Layer | Technologies |
|---|---|
| Frontend | React, Vite, JavaScript |
| Backend | Python, FastAPI |
| Database | PostgreSQL |
| ORM | SQLAlchemy |
| Migrations | Alembic |
| Cache / Queue | Redis, ARQ |
| Chess Logic | python-chess |
| Containerization | Docker, Docker Compose |
| Code Quality | ESLint, Prettier |
| CI | GitHub Actions |

## 📁 Project Structure

```text
chess_platform/
├── .github/
│   └── workflows/
│       └── ci.yml
├── backend/
│   ├── app/
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   └── database.py
│   │   └── main.py
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   │   └── client.js
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── .env
│   ├── eslint.config.js
│   └── package.json
├── docker-compose.yml
└── README.md
```

## ⚙️ Prerequisites

Install the following before running the project:

- Node.js 24 or later
- npm
- Docker Desktop
- Git

Python dependencies are installed inside the backend Docker container.

## 🚀 Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/Akshaya-codes13/chess_platform.git
cd chess_platform
```

### 2. Configure backend environment variables

Create `backend/.env` using `backend/.env.example` as a template.

Configure:

```env
DATABASE_URL=postgresql+psycopg2://chess:chess@db:5432/chess_academy
REDIS_URL=redis://redis:6379/0
SECRET_KEY=your-secret-key
CORS_ORIGINS=http://localhost:5173
```

Generate a strong secret key for your local environment. Never commit your actual `.env` file.

### 3. Configure frontend environment variables

Create `frontend/.env`:

```env
VITE_API_URL=http://localhost:8000
```

### 4. Start Docker services

From the project root:

```bash
docker compose up --build -d
```

### 5. Start the frontend

Open a separate terminal:

```bash
cd frontend
npm install
npm run dev
```

## 🌐 Application URLs

| Service | URL |
|---|---|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| Swagger API Docs | http://localhost:8000/docs |
| Backend Health | http://localhost:8000/health |
| Database Health | http://localhost:8000/health/db |

## 🧪 Development Commands

### Frontend

```bash
npm run dev
npm run lint
npm run format
npm run format:check
npm run build
```

### Backend

```bash
docker compose exec backend pytest
```

### Docker

```bash
docker compose up -d
docker compose ps
docker compose logs -f backend
docker compose down
```

## 🔄 Continuous Integration

GitHub Actions is configured to automate:

- Frontend dependency installation
- ESLint checks
- Prettier formatting checks
- Production frontend build
- Backend dependency installation
- Backend tests

The workflow runs on pushes and pull requests targeting `main`.

## 🗺️ Development Roadmap

| Milestone | Description |
|---|---|
| M0 | Requirements and planning |
| M1 | Project setup and infrastructure |
| M2 | Database design and migrations |
| M3 | Authentication and authorization |
| M4 | Application shell and navigation |
| M5 | User and profile management |
| M6 | Chessboard and puzzle system |
| M7 | Sessions and attendance |
| M8 | Assignments |
| M9 | Game database and board editor |
| M10 | Gamification |
| M11 | Reports and analytics |
| M12 | Gallery, blogs, and feedback |
| M13 | Live chess |
| M14 | AI-powered features |
| M15 | PWA, testing, and deployment |

## 🔐 Security Notes

- Keep environment variables and secret keys private.
- Do not commit `.env` files.
- Use `.env.example` for configuration templates.
- Apply role-based access control to protected APIs.
- Validate user input on the backend.

## 📌 Project Status

**Current milestone:** M1 — Project Setup

Core frontend, backend, PostgreSQL, and Redis connectivity have been established. Authentication, database models, and application features are planned for upcoming milestones.

---

**Built to make chess academy management smarter, simpler, and more organized. ♟️**
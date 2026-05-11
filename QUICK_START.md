# 🚀 Quick Start Guide

## One-Command Setup

```bash
# 1. Clone the repo
git clone https://github.com/aparsoft/django-nextjs-chatbot.git
cd django-nextjs-chatbot

# 2. Setup environment
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY

# 3. Start everything with watch mode (auto-reload on code changes)
./start.sh
```

That's it! 🎉

> **💡 Pro Tip:** The `./start.sh` script starts Docker with **watch mode** enabled - your code changes automatically sync without rebuilding! Perfect for development.

---

## What Happens Automatically?

When you run `./start.sh`, the system automatically:

1. **Checks for Backups** - Offers to restore from previous backup (if available)
2. **Builds Images** - Installs all dependencies
3. **Waits for PostgreSQL** - Ensures database is ready
4. **Runs Migrations** - Creates all database tables
5. **Creates Superuser** - Admin account ready to use (`admin` / `admin123`)
6. **Collects Static Files** - Prepares assets
7. **Starts with Watch Mode** - Auto-reloads on code changes:
   - **Backend**: Python files sync + Django auto-reload
   - **Frontend**: Source files sync + Next.js hot-reload
   - **Celery**: Changes sync + worker restart

---

## Access Your Application

| Service | URL | Credentials |
|---------|-----|-------------|
| **Frontend** | http://localhost:3000 | - |
| **Backend API** | http://localhost:8000 | - |
| **Django Admin** | http://localhost:8000/chatbot-admin/ | `admin` / `admin123` |
| **PostgreSQL** | localhost:5433 | `chatbot_user` / `chatbot_pass` |
| **Redis** | localhost:6380 | - |

---

## Default Superuser

- **Username:** `admin`
- **Password:** `admin123`
- **Email:** `admin@aparsoft.com`

⚠️ **Important:** Change this password immediately in production!

To change the password:
```bash
docker-compose exec backend python manage.py changepassword admin
```

---

## First Time Setup Checklist

- [x] Clone repository
- [x] Copy `.env.example` to `.env`
- [x] Add your `OPENAI_API_KEY` to `.env`
- [x] Make scripts executable: `chmod +x *.sh` (already done in repo)
- [x] Run `./start.sh`
- [ ] Wait for all services to start (watch the logs)
- [ ] Open http://localhost:3000
- [ ] Login to admin at http://localhost:8000/chatbot-admin/
- [ ] Start building your chatbot! 🤖

---

## Common Commands

### 🎬 Start/Stop Services

```bash
# Start with watch mode (recommended for development)
./start.sh

# Stop services (Ctrl+C when running, or:)
docker compose down

# Clean up everything (interactive - backs up database first!)
./cleanup.sh
```

### 💾 Database Backup & Restore

```bash
# Create manual backup anytime
./backup.sh

# Restore from backup (prompted during ./start.sh)
./start.sh
# Choose 'y' when asked about restore, select backup from list
```

> **🔒 Safety Feature:** The `cleanup.sh` script automatically backs up your database before removing volumes - no data loss!

### 📋 View Logs
```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f celery
```

### 🐚 Access Django Shell
```bash
docker compose exec backend python manage.py shell
```

### 👤 Create Another Superuser
```bash
docker compose exec backend python manage.py createsuperuser
```

### 🔄 Run Migrations (if needed manually)
```bash
docker compose exec backend python manage.py migrate
```

### 🔁 Restart Specific Service
```bash
docker compose restart backend
docker compose restart frontend
```

---

## Troubleshooting

### Port Already in Use?

If you see port conflicts, edit `docker-compose.yml`:
- PostgreSQL: Change `5433:5432`
- Redis: Change `6380:6379`
- Backend: Change `8000:8000`
- Frontend: Change `3000:3000`

### Database Connection Issues?

The entrypoint script waits for PostgreSQL. If issues persist:
```bash
docker compose restart backend
```

### Frontend Not Loading?

Check if all environment variables are set:
```bash
docker compose exec frontend env | grep NEXT_PUBLIC
```

### Code Changes Not Syncing?

Docker Compose Watch should auto-sync changes. If not working:
1. Stop with Ctrl+C
2. Restart: `./start.sh`
3. For dependency changes (package.json, requirements.txt), rebuild is required

### Need to Rebuild After Dependency Changes?

```bash
# Stop current containers
Ctrl+C

# Start (automatically rebuilds images)
./start.sh
```

### Database Issues or Want Fresh Start?

```bash
# Interactive cleanup (backs up database first!)
./cleanup.sh

# Then start fresh
./start.sh
```

---

## Need Help?

- **YouTube Tutorials:** [@aparsoft-ai](https://youtube.com/@aparsoft-ai)
- **GitHub Issues:** [Report a bug](https://github.com/aparsoft/django-nextjs-chatbot/issues)
- **Discord:** Ask in our community (link in YouTube description)

---

**Happy coding! 🚀**

*Built with ❤️ by Aparsoft Team*

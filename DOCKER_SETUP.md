# Docker Installation Guide

Complete setup guide for installing Docker on WSL 2 Ubuntu 24.04.

## 🐳 Installing Docker on WSL 2 (Ubuntu 24.04)

### Step 1: Update System Packages

```bash
sudo apt update
sudo apt upgrade -y
```

### Step 2: Install Prerequisites

```bash
sudo apt install -y ca-certificates curl gnupg lsb-release
```

### Step 3: Add Docker's Official GPG Key

```bash
sudo install -m 0755 -d /etc/apt/keyrings

curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

sudo chmod a+r /etc/apt/keyrings/docker.gpg
```

### Step 4: Set Up Docker Repository

```bash
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
```

### Step 5: Install Docker Engine

```bash
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

### Step 6: Start Docker Service

```bash
sudo service docker start
```

### Step 7: Verify Installation

```bash
sudo docker run hello-world
```

You should see: "Hello from Docker!" message.

### Step 8: Add Your User to Docker Group (Optional but Recommended)

This allows you to run Docker without sudo:

```bash
sudo usermod -aG docker $USER
```

**Important:** After this, you need to log out and log back in, or run:

```bash
newgrp docker
```

### Step 9: Test Without Sudo

```bash
docker run hello-world
```

### Step 10: Auto-Start Docker on WSL Boot

#### Option 1: Create a startup script

Edit your `.bashrc` or `.zshrc`:

```bash
nano ~/.bashrc
```

Add this at the end:

```bash
# Start Docker daemon automatically
if ! service docker status > /dev/null 2>&1; then
    sudo service docker start > /dev/null 2>&1
fi
```

#### Option 2: Set up passwordless sudo for Docker

Edit sudoers file:

```bash
sudo visudo
```

Add this line at the end:

```
%docker ALL=(ALL) NOPASSWD: /usr/sbin/service docker start
```

### Step 11: Verify Docker Compose

```bash
docker compose version
```

You should see something like: Docker Compose version v2.x.x

---

## 🚀 Quick Test with Your Project

```bash
# Navigate to your project
cd /your-project/django-nextjs-chatbot

# Test Docker
docker --version
docker compose version

# Build and run your project
docker compose up --build
```

---

## 📝 Common WSL2 Docker Commands

**Start Docker:**
```bash
sudo service docker start
```

**Stop Docker:**
```bash
sudo service docker stop
```

**Check Docker Status:**
```bash
sudo service docker status
```

**Restart Docker:**
```bash
sudo service docker restart
```

---

## ⚠️ Troubleshooting

### Issue: "Cannot connect to Docker daemon"

```bash
sudo service docker start
```

### Issue: Permission Denied

```bash
# Make sure you're in docker group
groups $USER

# If docker is not listed, add yourself again
sudo usermod -aG docker $USER
newgrp docker
```

### Issue: WSL2 Memory Limits

Create/edit `.wslconfig` in Windows:

```ini
# In Windows: C:\Users\YourUsername\.wslconfig
[wsl2]
memory=8GB
processors=4
swap=2GB
```

Then restart WSL from PowerShell (Windows):

```powershell
wsl --shutdown
```

---

## ✅ Verification Checklist

Run these to confirm everything works:

```bash
# Check Docker version
docker --version

# Check Docker Compose
docker compose version

# Check Docker service
sudo service docker status

# Run test container
docker run hello-world

# Check if you can run without sudo
docker ps
```

---

All set? Let me know if you hit any issues, and I'll help you troubleshoot! 🎯


# Docker Setup Guide

This guide will help you run the Django + Next.js chatbot using Docker.

## Prerequisites

- Docker Desktop installed
- Docker Compose installed (comes with Docker Desktop)
- OpenAI API key

## Quick Start

### 1. Set Up Environment Variables

**Backend:**
```bash
cd backend
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

**Frontend:**
```bash
cd frontend
cp .env.example .env.local
# Review the settings (defaults should work)
```

**Root .env (for docker-compose):**
```bash
# Create .env in project root
echo "OPENAI_API_KEY=your-actual-openai-key-here" > .env
```

### 2. Build and Run

```bash
# From project root
docker-compose up --build
```

This will:
- Create PostgreSQL database container
- Build and run Django backend on `http://localhost:8000`
- Build and run Next.js frontend on `http://localhost:3000`

### 3. Run Migrations (First Time Only)

In a new terminal:
```bash
docker-compose exec backend python manage.py migrate
```

### 4. Create Superuser (Optional)

```bash
docker-compose exec backend python manage.py createsuperuser
```

### 5. Access the Application

- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:8000
- **Django Admin:** http://localhost:8000/admin

## Common Commands

### Start Services
```bash
docker-compose up
```

### Start in Background
```bash
docker-compose up -d
```

### Stop Services
```bash
docker-compose down
```

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f frontend
```

### Rebuild After Changes
```bash
docker-compose up --build
```

### Run Django Commands
```bash
# Migrations
docker-compose exec backend python manage.py migrate

# Create app
docker-compose exec backend python manage.py startapp myapp

# Shell
docker-compose exec backend python manage.py shell

# Collect static files
docker-compose exec backend python manage.py collectstatic
```

### Run Frontend Commands
```bash
# Install new package
docker-compose exec frontend npm install package-name

# Run npm command
docker-compose exec frontend npm run build
```

### Database Access
```bash
# Access PostgreSQL
docker-compose exec db psql -U chatbot_user -d chatbot_db
```

### Clean Up Everything
```bash
# Stop and remove containers, networks
docker-compose down

# Also remove volumes (WARNING: deletes database data!)
docker-compose down -v
```

## Troubleshooting

### Port Already in Use
```bash
# Change ports in docker-compose.yml
# For example, change "3000:3000" to "3001:3000"
```

### Frontend Hot Reload Not Working
```bash
# Uncomment WATCHPACK_POLLING in docker-compose.yml
# Or add to frontend/.env.local:
WATCHPACK_POLLING=true
```

### Database Connection Issues
```bash
# Wait for database to be ready
# The backend service has a healthcheck that waits for PostgreSQL
# If issues persist, try:
docker-compose restart backend
```

### Permission Issues (Linux/Mac)
```bash
# Fix file permissions
sudo chown -R $USER:$USER .
```

### Clear Build Cache
```bash
docker-compose build --no-cache
```

## Development Workflow

1. **Edit code** - Changes auto-reload for both Django and Next.js
2. **Backend changes** - Auto-reload with Django's runserver
3. **Frontend changes** - Hot Module Replacement (HMR) with Next.js
4. **New dependencies:**
   - Backend: Add to `requirements.txt`, then `docker-compose up --build`
   - Frontend: `docker-compose exec frontend npm install`

## Production Deployment

For production, you'll need:
- Separate Dockerfile.prod files
- docker-compose.prod.yml
- Proper SECRET_KEY, DEBUG=0
- Static file serving via Nginx
- Gunicorn for Django

(These will be covered in our YouTube tutorial series!)

---

**Need help?** Check out our [YouTube tutorials](https://youtube.com/@aparsoft-ai) or ask in GitHub Discussions!

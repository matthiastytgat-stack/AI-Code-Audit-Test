#!/bin/bash

# Docker Compose Watch Startup Script - Best Practices 2025
# Starts the project with watch mode for automatic reloading

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Docker Compose Watch Startup ===${NC}"
echo ""

# Check if docker compose is available
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed or not in PATH${NC}"
    exit 1
fi

# Function to print status
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_info() {
    echo -e "${CYAN}ℹ${NC} $1"
}

# Check if containers are already running
RUNNING_CONTAINERS=$(docker compose ps -q 2>/dev/null | wc -l)

if [ "$RUNNING_CONTAINERS" -gt 0 ]; then
    print_warning "Containers are already running"
    echo ""
    docker compose ps
    echo ""
    echo -e "${YELLOW}Do you want to restart? (y/N)${NC}"
    read -r RESTART

    if [[ "$RESTART" =~ ^[Yy]$ ]]; then
        echo -e "${BLUE}Stopping existing containers...${NC}"
        docker compose down
        print_status "Containers stopped"
    else
        echo -e "${CYAN}Starting watch mode on existing containers...${NC}"
        echo ""
        exec docker compose watch
    fi
fi

echo ""

# Check for available backups and offer restore
BACKUP_DIR="./backups"
if [ -d "$BACKUP_DIR" ] && [ "$(ls -A $BACKUP_DIR/*.sql.gz 2>/dev/null)" ]; then
    echo -e "${BLUE}📦 Found database backups${NC}"
    echo ""
    echo -e "${YELLOW}Do you want to restore from a backup? (y/N)${NC}"
    read -r RESTORE_BACKUP

    if [[ "$RESTORE_BACKUP" =~ ^[Yy]$ ]]; then
        # List available backups
        echo ""
        echo -e "${BLUE}Available backups:${NC}"
        BACKUPS=($(ls -t $BACKUP_DIR/*.sql.gz))
        for i in "${!BACKUPS[@]}"; do
            BACKUP_SIZE=$(du -h "${BACKUPS[$i]}" | cut -f1)
            BACKUP_NAME=$(basename "${BACKUPS[$i]}")
            echo -e "  ${CYAN}[$((i+1))]${NC} $BACKUP_NAME ($BACKUP_SIZE)"
        done

        echo ""
        echo -e "${YELLOW}Enter backup number to restore [1-${#BACKUPS[@]}]:${NC}"
        read -r BACKUP_NUM

        if [[ "$BACKUP_NUM" =~ ^[0-9]+$ ]] && [ "$BACKUP_NUM" -ge 1 ] && [ "$BACKUP_NUM" -le "${#BACKUPS[@]}" ]; then
            SELECTED_BACKUP="${BACKUPS[$((BACKUP_NUM-1))]}"
            echo ""
            echo -e "${BLUE}Starting database for restore...${NC}"

            # Start only the database service
            docker compose up -d db

            # Wait for database to be ready
            echo -e "${BLUE}Waiting for database to be ready...${NC}"
            sleep 5

            # Restore backup
            echo -e "${BLUE}Restoring backup: $(basename $SELECTED_BACKUP)${NC}"
            if gunzip < "$SELECTED_BACKUP" | docker exec -i chatbot-db psql -U chatbot_user -d postgres; then
                print_status "Database restored successfully!"
            else
                print_warning "Restore completed with warnings (this is normal for first-time restore)"
            fi

            # Stop database to restart cleanly with all services
            docker compose down
        else
            print_warning "Invalid backup number, skipping restore"
        fi
    fi
fi

echo ""

# Check if we need to build images
echo -e "${BLUE}Checking for image updates...${NC}"

# Build images (BuildKit is used by default in modern Docker)
echo -e "${BLUE}Building images...${NC}"
docker compose build
print_status "Images built successfully"

echo ""

# Start services with watch mode
echo -e "${GREEN}Starting services with watch mode...${NC}"
echo ""
print_info "Watch mode will automatically sync changes:"
echo -e "  ${CYAN}•${NC} Backend: Python files sync + auto-reload"
echo -e "  ${CYAN}•${NC} Frontend: Source files sync + hot-reload"
echo -e "  ${CYAN}•${NC} Celery: Changes sync + restart workers"
echo ""
print_info "Press Ctrl+C to stop all services"
echo ""
echo -e "${YELLOW}----------------------------------------${NC}"
echo ""

# Start with watch mode
# Using 'up --watch' to see all logs (container + watch logs)
# Alternative: use 'watch' for only watch logs
docker compose up --watch

# This part will only execute after Ctrl+C
echo ""
echo -e "${YELLOW}Shutting down services...${NC}"
docker compose down
print_status "Services stopped"
echo ""
echo -e "${GREEN}Goodbye!${NC}"

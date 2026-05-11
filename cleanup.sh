#!/bin/bash

# Docker Cleanup Script - Best Practices 2025
# Properly stops and cleans up all Docker resources for this project

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Docker Cleanup Script ===${NC}"
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

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Check if containers are running
RUNNING_CONTAINERS=$(docker compose ps -q 2>/dev/null | wc -l)

if [ "$RUNNING_CONTAINERS" -gt 0 ]; then
    echo -e "${YELLOW}Found $RUNNING_CONTAINERS running container(s)${NC}"
    echo ""

    # Show running containers
    echo -e "${BLUE}Current containers:${NC}"
    docker compose ps
    echo ""

    # Stop and remove containers
    echo -e "${BLUE}Stopping and removing containers...${NC}"
    docker compose down --remove-orphans
    print_status "Containers stopped and removed"
else
    echo -e "${GREEN}No running containers found${NC}"
fi

echo ""

# Ask for volume cleanup
echo -e "${YELLOW}Do you want to remove volumes (database will be backed up first)? (y/N)${NC}"
read -r REMOVE_VOLUMES

if [[ "$REMOVE_VOLUMES" =~ ^[Yy]$ ]]; then
    # Check if database container exists and create backup
    DB_CONTAINER=$(docker compose ps -q db 2>/dev/null)

    if [ -n "$DB_CONTAINER" ] && [ "$(docker ps -q -f id=$DB_CONTAINER)" ]; then
        echo ""
        echo -e "${BLUE}🔒 Backing up database before removing volumes...${NC}"

        # Create backups directory
        BACKUP_DIR="./backups"
        mkdir -p "$BACKUP_DIR"

        # Create timestamped backup filename
        BACKUP_FILE="$BACKUP_DIR/postgres_backup_$(date +%Y%m%d_%H%M%S).sql.gz"

        # Perform backup using pg_dumpall
        if docker exec -t chatbot-db pg_dumpall -c -U chatbot_user | gzip > "$BACKUP_FILE"; then
            print_status "Database backed up to: $BACKUP_FILE"

            # Show backup file size
            BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
            echo -e "  ${GREEN}→${NC} Backup size: $BACKUP_SIZE"
        else
            print_error "Database backup failed!"
            echo -e "${RED}Aborting volume removal to prevent data loss${NC}"
            exit 1
        fi
    else
        print_warning "Database container not running, skipping backup"
    fi

    echo ""
    echo -e "${BLUE}Removing volumes...${NC}"
    docker compose down --volumes --remove-orphans
    print_status "Volumes removed"

    # Prune any dangling volumes
    echo -e "${BLUE}Pruning dangling volumes...${NC}"
    docker volume prune -f
    print_status "Dangling volumes pruned"
else
    print_warning "Volumes preserved"
fi

echo ""

# Ask for image cleanup
echo -e "${YELLOW}Do you want to remove project images? (y/N)${NC}"
read -r REMOVE_IMAGES

if [[ "$REMOVE_IMAGES" =~ ^[Yy]$ ]]; then
    echo -e "${BLUE}Removing project images...${NC}"
    docker compose down --rmi all --remove-orphans
    print_status "Project images removed"

    # Prune dangling images
    echo -e "${BLUE}Pruning dangling images...${NC}"
    docker image prune -f
    print_status "Dangling images pruned"
else
    print_warning "Images preserved"
fi

echo ""

# Clean up networks
echo -e "${BLUE}Cleaning up unused networks...${NC}"
docker network prune -f
print_status "Unused networks removed"

echo ""

# Optional: Full system prune
echo -e "${YELLOW}Do you want to run a full system prune (removes all unused Docker resources)? (y/N)${NC}"
read -r SYSTEM_PRUNE

if [[ "$SYSTEM_PRUNE" =~ ^[Yy]$ ]]; then
    echo -e "${BLUE}Running system prune...${NC}"
    docker system prune -f
    print_status "System prune completed"
fi

echo ""
echo -e "${GREEN}=== Cleanup Complete ===${NC}"
echo ""

# Show disk usage
echo -e "${BLUE}Current Docker disk usage:${NC}"
docker system df

echo ""
echo -e "${GREEN}✓ Cleanup finished successfully!${NC}"

# Show backup information if backups exist
if [ -d "./backups" ] && [ "$(ls -A ./backups 2>/dev/null)" ]; then
    echo ""
    echo -e "${BLUE}📦 Available backups:${NC}"
    ls -lh ./backups | tail -n +2 | awk '{printf "  %s %s %s\n", $9, $5, $6" "$7" "$8}'
    echo ""
    echo -e "${GREEN}💡 Tip: Use ./start.sh to restore from backup if needed${NC}"
fi

echo -e "${BLUE}Run ./start.sh to start the project with watch mode${NC}"

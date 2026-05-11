#!/bin/bash

# PostgreSQL Backup Script - Best Practices 2025
# Creates manual backups of the PostgreSQL database

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== PostgreSQL Backup Script ===${NC}"
echo ""

# Function to print status
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# Check if database container is running
DB_CONTAINER=$(docker compose ps -q db 2>/dev/null)

if [ -z "$DB_CONTAINER" ] || [ -z "$(docker ps -q -f id=$DB_CONTAINER)" ]; then
    print_error "Database container is not running!"
    echo ""
    echo -e "${YELLOW}Start the database with: ${NC}./start.sh"
    echo -e "${YELLOW}Or run: ${NC}docker compose up -d db"
    exit 1
fi

print_status "Database container is running"
echo ""

# Create backups directory
BACKUP_DIR="./backups"
mkdir -p "$BACKUP_DIR"

# Create timestamped backup filename
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/postgres_backup_$TIMESTAMP.sql.gz"

echo -e "${BLUE}Creating database backup...${NC}"
echo -e "${BLUE}Target: $BACKUP_FILE${NC}"
echo ""

# Perform backup using pg_dumpall
if docker exec -t chatbot-db pg_dumpall -c -U chatbot_user | gzip > "$BACKUP_FILE"; then
    print_status "Backup created successfully!"
    echo ""

    # Show backup details
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo -e "${GREEN}Backup details:${NC}"
    echo -e "  ${BLUE}→${NC} File: $(basename $BACKUP_FILE)"
    echo -e "  ${BLUE}→${NC} Size: $BACKUP_SIZE"
    echo -e "  ${BLUE}→${NC} Location: $BACKUP_FILE"
    echo ""

    # Count total backups
    BACKUP_COUNT=$(ls -1 $BACKUP_DIR/*.sql.gz 2>/dev/null | wc -l)
    print_info "Total backups: $BACKUP_COUNT"

    # Calculate total backup size
    TOTAL_SIZE=$(du -sh $BACKUP_DIR | cut -f1)
    echo -e "  ${BLUE}→${NC} Total backup size: $TOTAL_SIZE"
    echo ""

    # Show retention recommendation
    if [ "$BACKUP_COUNT" -gt 10 ]; then
        echo -e "${YELLOW}⚠ You have $BACKUP_COUNT backups. Consider cleaning old backups:${NC}"
        echo -e "  ${BLUE}→${NC} Keep last 7 days: ${CYAN}find $BACKUP_DIR -name '*.sql.gz' -mtime +7 -delete${NC}"
        echo -e "  ${BLUE}→${NC} Keep last 10: ${CYAN}ls -t $BACKUP_DIR/*.sql.gz | tail -n +11 | xargs rm -f${NC}"
    fi
else
    print_error "Backup failed!"
    exit 1
fi

echo ""
echo -e "${GREEN}✓ Backup completed successfully!${NC}"
echo ""
echo -e "${BLUE}To restore this backup, run: ${NC}./start.sh ${BLUE}(and choose restore option)${NC}"

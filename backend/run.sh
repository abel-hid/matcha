#!/bin/bash

# Colors for pretty output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Starting Matcha Backend${NC}"

# 1. Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python3 not found. Please install Python 3.9+${NC}"
    exit 1
fi

# 2. Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}📦 Creating virtual environment...${NC}"
    python3 -m venv venv
fi

# 3. Activate virtual environment
echo -e "${YELLOW}🔌 Activating virtual environment...${NC}"
source venv/bin/activate

# 4. Install/upgrade pip and dependencies
echo -e "${YELLOW}📦 Installing dependencies...${NC}"
pip install --upgrade pip > /dev/null
pip install -r requirements.txt 2>&1 | grep -v "Requirement already satisfied"

# 5. Create instance folder if missing
if [ ! -d "instance" ]; then
    echo -e "${YELLOW}📁 Creating instance folder...${NC}"
    mkdir -p instance
fi

# 6. Set Flask app environment variable
export FLASK_APP=run.py

# 7. Handle database migrations
if [ ! -d "migrations" ]; then
    echo -e "${YELLOW}🔧 Initializing migrations (first time)...${NC}"
    flask db init
fi

echo -e "${YELLOW}🔄 Generating migration script (if changes exist)...${NC}"
flask db migrate -m "auto" 2>&1 | grep -v "INFO  [alembic]"

echo -e "${YELLOW}⬆️ Applying migrations...${NC}"
flask db upgrade

# 8. (Optional) Verify that the database is up‑to‑date
echo -e "${GREEN}✅ Database is ready!${NC}"

# 9. Run the Flask server
echo -e "${GREEN}✅ Starting Flask server...${NC}"
echo -e "${GREEN}🌐 Server running at http://localhost:5000${NC}"
echo -e "${GREEN}🛑 Press Ctrl+C to stop${NC}"
python3 run.py
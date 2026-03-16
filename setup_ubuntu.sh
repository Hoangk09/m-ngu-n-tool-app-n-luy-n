#!/bin/bash
set -e  # Exit on error

# Configuration
APP_DIR="/root/quiz_solver"
USER="root"
GROUP="root"
PORT=5000
SERVICE_NAME="quiz_solver"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}Starting Robust Auto-Setup (v4)...${NC}"

# 0. Fix line endings (in case of Windows upload)
# This handles the case where the script itself has \r, skipping since we are running it, 
# but useful for other files if needed.

# 1. Update System & Install Dependencies
echo -e "${GREEN}[1/7] Updating system and installing dependencies...${NC}"
export DEBIAN_FRONTEND=noninteractive
apt-get update
# Install ALL possible python required packages to fix venv issues
# Added libgbm-dev libnss3 libatk-bridge2.0-0 libgtk-3-0 libasound2 for Chrome
# Added x11vnc novnc websockify for VNC remote control
apt-get install -y python3-full python3-pip python3-venv python3-dev build-essential nginx git xvfb libxi6 unzip jq curl dos2unix libgbm-dev libnss3 libatk-bridge2.0-0 libgtk-3-0 libasound2 x11vnc novnc python3-websockify

# 2. Setup Project Directory
echo -e "${GREEN}[2/7] Setting up project directory at $APP_DIR...${NC}"
mkdir -p "$APP_DIR"
if [ "$PWD" != "$APP_DIR" ]; then
    cp -r * "$APP_DIR/" || echo "No files to copy or already in dir"
fi
cd "$APP_DIR"

# Fix line endings of project files
find . -type f -name "*.py" -exec dos2unix {} +
find . -type f -name "*.sh" -exec dos2unix {} +
find . -type f -name "*.txt" -exec dos2unix {} +

# 3. Create Virtual Environment
echo -e "${GREEN}[3/7] Creating Python Virtual Environment...${NC}"
if [ -d "venv" ]; then
    echo "Removing old venv..."
    rm -rf venv
fi

# Try creating venv with allow-pip
python3 -m venv venv --without-pip 
# We install pip manually to be safe if ensurepip is broken on some distros
curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
./venv/bin/python3 get-pip.py
rm get-pip.py

if [ ! -f "venv/bin/python3" ]; then
    echo -e "${RED}CRITICAL: Virtual environment creation failed!${NC}"
    exit 1
fi

# 4. Install Python Dependencies
echo -e "${GREEN}[4/7] Installing Python dependencies...${NC}"
./venv/bin/pip install --upgrade pip
./venv/bin/pip install gunicorn flask flask-login flask-sqlalchemy werkzeug python-dotenv
# Install other requirements if file exists
if [ -f "requirements_web.txt" ]; then
    ./venv/bin/pip install -r requirements_web.txt
else
    echo "requirements_web.txt not found, installing minimal set..."
    ./venv/bin/pip install undetected-chromedriver google-generativeai requests payos
fi

# Verify Gunicorn
if [ ! -f "$APP_DIR/venv/bin/gunicorn" ]; then
    echo -e "${RED}CRITICAL: Gunicorn installation failed!${NC}"
    exit 1
fi

# 5. Install Chrome
echo -e "${GREEN}[5/7] Checking Chrome...${NC}"
if ! command -v google-chrome &> /dev/null; then
    echo "Installing Chrome..."
    wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -
    sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list'
    apt-get update
    apt-get install -y google-chrome-stable
fi

# 6. Setup Systemd
echo -e "${GREEN}[6/7] Configuring Systemd Service...${NC}"
# Stop existing service if any
systemctl stop $SERVICE_NAME || true

cat > /etc/systemd/system/$SERVICE_NAME.service <<EOL
[Unit]
Description=Gunicorn instance to serve Quiz Solver
After=network.target

[Service]
User=$USER
Group=$GROUP
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/venv/bin"
ExecStart=$APP_DIR/venv/bin/gunicorn --workers 3 --bind 0.0.0.0:$PORT web_app:app
Restart=always

[Install]
WantedBy=multi-user.target
EOL

systemctl daemon-reload
systemctl enable $SERVICE_NAME
systemctl start $SERVICE_NAME

# Check status
if ! systemctl is-active --quiet $SERVICE_NAME; then
    echo -e "${RED}Service failed to start! Checks logs below:${NC}"
    journalctl -u $SERVICE_NAME -n 20 --no-pager
    exit 1
fi

# 7. Setup Nginx
echo -e "${GREEN}[7/7] Configuring Nginx...${NC}"
rm -f /etc/nginx/sites-enabled/default
cat > /etc/nginx/sites-available/$SERVICE_NAME <<EOL
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:$PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }
}
EOL

ln -sf /etc/nginx/sites-available/$SERVICE_NAME /etc/nginx/sites-enabled/
nginx -t && systemctl restart nginx

echo -e "${GREEN}SUCCESS! Web App should be running.${NC}"
echo -e "Check URL: http://$(curl -s ifconfig.me)"

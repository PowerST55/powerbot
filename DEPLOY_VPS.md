# Deploy VPS (Discord Bot Nube)

This guide documents a simple VPS deployment for the Discord bot. It uses a Linux host with Python 3.10+.

## 1) Prepare server

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git
```

## 2) Clone and install

```bash
git clone <YOUR_REPO_URL> powerbot-discord
cd powerbot-discord
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 3) Configure env

```bash
cp keys/.env.example keys/.env
nano keys/.env
```

Set at least:

```
TOKEN=your_discord_token
PREFIX=!
DB_HOST=your_mysql_host
DB_PORT=3306
DB_NAME=your_db
DB_USER=your_user
DB_PASSWORD=your_password
```

## 4) Run (manual)

```bash
source .venv/bin/activate
python start.py
```

## 5) Optional systemd service

Create `/etc/systemd/system/powerbot-discord.service`:

```
[Unit]
Description=PowerBot Discord Bot
After=network.target

[Service]
Type=simple
User=YOUR_USER
WorkingDirectory=/home/YOUR_USER/powerbot-discord
Environment=PYTHONUNBUFFERED=1
ExecStart=/home/YOUR_USER/powerbot-discord/.venv/bin/python /home/YOUR_USER/powerbot-discord/start.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable powerbot-discord
sudo systemctl start powerbot-discord
sudo systemctl status powerbot-discord
```

## Notes

- Keep `keys/.env` out of git.
- If DB is offline, the bot keeps local cache and syncs when DB is back.

set -e
APP=/opt/neo-projectflow
id neoflow >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin neoflow
mkdir -p $APP/backend $APP/frontend $APP/data
tar -xzf /tmp/neoflow.tgz -C $APP
cd $APP
[ -d venv ] || python3 -m venv venv
venv/bin/pip install -q --upgrade pip
venv/bin/pip install -q -r backend/requirements.txt
[ -f .env ] || cat > .env <<ENV
NEO_DATA_DIR=$APP/data
NEO_SECRET=$(openssl rand -hex 32)
NEO_BASE_URL=http://200.141.0.195:8120
NEO_DEMO_LOGIN=1
NEO_AUTOSEED=1
ENV
chown -R root:neoflow $APP
chown -R neoflow:neoflow $APP/data
chmod 640 .env
cat > /etc/systemd/system/neoflow-api.service <<UNIT
[Unit]
Description=Neo Project Flow (project management API + web) - isolated deployment
After=network.target

[Service]
User=neoflow
Group=neoflow
WorkingDirectory=$APP/backend
EnvironmentFile=$APP/.env
ExecStart=$APP/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 9120 --workers 1 --proxy-headers
Restart=always
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$APP/data
MemoryMax=1G

[Install]
WantedBy=multi-user.target
UNIT
cat > /etc/nginx/sites-available/neo-projectflow <<NGX
# Neo Project Flow -> http://<server-ip>:8120 . Own port, own server block: no other site's config is edited.
server {
    listen 8120;
    listen [::]:8120;
    server_name _;
    client_max_body_size 25m;
    server_tokens off;
    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options SAMEORIGIN always;
    add_header Referrer-Policy strict-origin-when-cross-origin always;
    location / {
        proxy_pass http://127.0.0.1:9120;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 120s;
    }
}
NGX
ln -sf /etc/nginx/sites-available/neo-projectflow /etc/nginx/sites-enabled/neo-projectflow
systemctl daemon-reload
systemctl enable --now neoflow-api
nginx -t
systemctl reload nginx
ufw allow 8120/tcp comment 'Neo Project Flow' >/dev/null
sleep 25
systemctl is-active neoflow-api
curl -s -o /dev/null -w "local api %{http_code}\n" http://127.0.0.1:9120/api/auth/demo-users
curl -s -o /dev/null -w "via nginx %{http_code}\n" http://127.0.0.1:8120/

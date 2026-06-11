# Frontend Docker Quick Start

## Start

```bash
cd /data2/hmy/PPT_Agent/frontend
sudo docker-compose up -d --build
```

## Stop

```bash
cd /data2/hmy/PPT_Agent/frontend
sudo docker-compose down
```

## Restart

```bash
cd /data2/hmy/PPT_Agent/frontend
sudo docker-compose down
sudo docker-compose up -d --build
```

## Check Status

```bash
sudo docker ps
curl -I http://127.0.0.1:8080/
```

## Logs

```bash
sudo docker logs -f frontend_web_1
```

## Access URL

- Local machine browser: `http://127.0.0.1:8080/workspace`
- Remote host browser (same LAN/VPN): `http://<SERVER_IP>:8080/workspace`

## Backend API (for frontend integration)

```bash
cd /data2/hmy/PPT_Agent/agent
source .venv/bin/activate
pip install -r requirements.txt
uvicorn api_server:app --host 0.0.0.0 --port 8000
```

- Health check: `http://127.0.0.1:8000/api/health`

### Built-in templates via `template_name`

When you pick template from frontend dropdown (without uploading `.pptx`), backend now applies built-in templates:

- `学术极简模板`
- `会议汇报模板`
- `课题组周报模板`


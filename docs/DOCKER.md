# Docker and Unraid

Run Tower Optimizer as a container on your home server and open it from any browser on your LAN.

Published image (built from `main`):

```text
ghcr.io/tankietank/the-tower-optimizer:latest
```

Profiles, battle history, custom icons, and backups persist in a mounted **`/app/data`** volume.

## Quick start (Docker Compose)

On any machine with Docker:

```bash
mkdir -p ./data
docker compose up -d
```

Open `http://localhost:8501`.

To pull the newest image on each start:

```bash
docker compose pull
docker compose up -d
```

Environment overrides:

| Variable | Default | Purpose |
|----------|---------|---------|
| `TOWER_OPTIMIZER_PORT` | `8501` | Host port |
| `TOWER_OPTIMIZER_DATA_PATH` | `./data` | Host folder mounted to `/app/data` |
| `TOWER_OPTIMIZER_DATA_DIR` | `/app/data` | In-container data root |

## Unraid (Docker UI)

1. **Docker → Add Container**
2. **Name:** `tower-optimizer`
3. **Repository:** `ghcr.io/tankietank/the-tower-optimizer:latest`
4. **Network type:** `bridge`
5. **Add path (appdata):**
   - Container path: `/app/data`
   - Host path: `/mnt/user/appdata/tower-optimizer`
6. **Add port:**
   - Container port: `8501`
   - Host port: `8501` (or any free port)
7. **Apply** and start the container.
8. Open `http://<unraid-ip>:8501` from your browser.

Create the host folder first if it does not exist:

```bash
mkdir -p /mnt/user/appdata/tower-optimizer/profiles
```

### Pull updates on Unraid

**Option A — manual:** Docker tab → click the container → **Force Update** (or stop, remove container, re-add with the same paths/ports; data stays in appdata).

**Option B — Watchtower:** If you already run [Watchtower](https://hub.docker.com/r/containrrr/watchtower), add a label or include this container so it recreates when `latest` changes.

**Option C — Unraid Compose (6.12+):** Copy `docker-compose.yml` to `/boot/config/plugins/compose/tower-optimizer/` (or your compose folder), set:

```yaml
environment:
  TOWER_OPTIMIZER_DATA_PATH: /mnt/user/appdata/tower-optimizer
```

Then `docker compose pull && docker compose up -d` from the Unraid terminal.

## Unraid Community Applications template

Import `unraid/my-tower-optimizer.xml` via **Docker → Add Container → Template repositories** if you maintain a custom CA feed, or use the manual steps above.

## Build locally

```bash
docker build -t tower-optimizer:local .
docker run --rm -p 8501:8501 -v "$(pwd)/data:/app/data" tower-optimizer:local
```

## Privacy

Same as the desktop app: nothing is sent to the cloud. All profile and import data stays in your mounted `/app/data` folder on the host.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Blank page / connection refused | Confirm host port maps to container `8501` and the container is running. |
| Permission errors writing profiles | Ensure `/mnt/user/appdata/tower-optimizer` is writable by the container user. On Unraid, `chmod -R 777` on the appdata folder is a common quick fix. |
| Old version after update | Pull `latest` again and recreate the container. Streamlit ships inside the image; only `data/` is mounted. |
| GHCR pull denied | The package must be **public** on GitHub (Packages → the-tower-optimizer → Package settings → Change visibility). |

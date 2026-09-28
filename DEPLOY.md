# Deploying the Heat-Health Early Warning Platform

This guide is for whoever puts the app online. You don't need to know the code.

The app is **one Docker container**: a Python server (FastAPI) that also serves the web map, with a SQLite database inside a Docker volume. On first start it downloads weather, builds the May 2024 demo replay, and serves everything on port 8000.

> **Why not Vercel or Netlify?** They only host static pages. This app has a server that runs continuously (a daily forecast job and a database), so it needs a host that runs a container.

## Pick a route

| Route | Cost | Use it for | Time |
|---|---|---|---|
| **A. Hugging Face Space** | Free | The **SIH demo link** for judges | ~20 min |
| **B. Cloud VM with Docker** | Free with student credits (Azure for Students, $100), otherwise ~$6/month | A **real pilot**: daily forecasts, saved alerts, HTTPS on your own domain | ~45 min |

A Hugging Face Space sleeps after 48 hours without visitors (it wakes in about a minute), and restarting it resets the database. That's fine for a demo, because the demo data is rebuilt at start-up.

---

## Before either route: two checks

1. **Everything is on GitHub.** The owner of this laptop commits and pushes, and you pull. You need at least these files:
   - `Dockerfile`
   - `docker/entrypoint.sh`
   - `data/processed/access_cache.pkl`
   - `DEPLOY.md`
   
   The push script refuses to run if any are missing.
2. **The automatic Docker check is green.** On GitHub, open **Actions → docker**. That job builds the image on GitHub's machines, starts it and tests the main pages.
   - **Green:** the image works.
   - **Red:** open the job and read the last log lines, or send them to the project owner.
   - **To run it by hand:** **Actions → docker → Run workflow**.

## Security rule (both routes)

Set **`HEAT_API_TOKEN`** to a long random password. Without it, anyone who opens the site can approve alerts and submit health reports.
- **To generate one:** `python -c "import secrets; print(secrets.token_urlsafe(24))"`, or use any password generator with 30+ characters.
- **Where it's used:** officers type it once in **Alerts → API token** before approving; health workers need it to submit reports.
- **Where it's never stored:** it isn't in the code or on GitHub, only in the host's secret settings or the server's `.env`.

Alert **delivery stays simulated** unless Twilio variables are set, so a public site cannot text anyone by accident.

---

## Route A — Hugging Face Space (free demo link)

**You need:** a Hugging Face account, `git`, and **Git LFS** (install from https://git-lfs.com, then run `git lfs install` once).

1. **Create the Space:** https://huggingface.co/new-space
   - Name: e.g. `heat-health`
   - SDK: **Docker** → template **Blank**
   - Hardware: **CPU basic (free)**
   - Visibility: **Public** if judges should open it without logging in
2. **Add settings** in the Space's **Settings → Variables and secrets**:
   - **New secret:** `HEAT_API_TOKEN` = your password
   - **New variable:** `HEAT_DEMO` = `1`
3. **Create an access token:** https://huggingface.co/settings/tokens → **New token**, type **Write**. You'll paste it as the password when git asks.
4. **Push the app** from the project folder (Git Bash on Windows, or a terminal on macOS/Linux):
   ```
   git pull
   sh deploy/huggingface/push_to_space.sh https://huggingface.co/spaces/<your-username>/heat-health
   ```
   When asked, the username is your Hugging Face username and the password is the token from step 3. The script copies only the files the app needs; it never copies `.env` or phone-number files.
5. **Wait for the build** in the Space's **Logs** tab: 5–10 minutes to build, then about 2 minutes of start-up. Start-up has finished when you see:
   ```
   [start] serving on port 8000
   ```
6. **Open the demo.** On the Space page, **⋮ → Embed this Space** shows the direct URL, like `https://<user>-heat-health.hf.space`. Share **`https://<user>-heat-health.hf.space/?replay=may2024`**.

**To update later:** `git pull`, then run the same `push_to_space.sh` command again.

---

## Route B — Cloud VM with Docker (real pilot)

**You need:** an Ubuntu 22.04 or 24.04 VM with **2 GB RAM** or more and **20 GB disk**, with ports **22, 80 and 443** open in the provider's firewall or network settings.
- **Azure for Students:** portal.azure.com → Virtual machines → Create → Ubuntu Server, size **B2s**.
- **DigitalOcean / AWS Lightsail:** a 2 GB plan.

1. **Log in** with `ssh <user>@<server-ip>`, then install Docker:
   ```
   curl -fsSL https://get.docker.com | sudo sh
   sudo usermod -aG docker $USER && newgrp docker
   ```
2. **Get the code and set the password:**
   ```
   git clone https://github.com/janhavitupe/Heat-Health-Warning-SIH.git heat && cd heat
   cp .env.deploy.example .env
   nano .env          # set HEAT_API_TOKEN (required); keep HEAT_DEMO=1 for the demo view
   ```
3. **Start it:**
   ```
   docker compose up -d --build
   docker compose logs -f          # wait for "[start] serving on port 8000", then Ctrl+C
   ```
   Open `http://<server-ip>:8000/?replay=may2024`.
4. **Add HTTPS with a domain (recommended).** A free name from https://www.duckdns.org works: point it at the server IP.
   - Put `HEAT_DOMAIN=<your-name>.duckdns.org` in `.env`.
   - Then run:
     ```
     docker compose -f docker-compose.yml -f docker-compose.https.yml up -d --build
     ```
   - Caddy gets the certificate automatically. The site is then **https://<your-name>.duckdns.org/?replay=may2024**, and port 8000 is closed to the outside.

**Everyday commands** (run in the `heat` folder; add `-f docker-compose.yml -f docker-compose.https.yml` after `docker compose` if you use HTTPS):

| Task | Command |
|---|---|
| Update to the latest code | `git pull && docker compose up -d --build` |
| See logs | `docker compose logs -f heat` |
| Restart | `docker compose restart heat` |
| Fresh demo (resets the 17 May alert to draft) | `docker compose exec heat python scripts/demo_setup.py --no-pdf`, then restart |
| Back up the database | `docker compose cp heat:/app/data/api ./backup-$(date +%F)` |
| Stop | `docker compose down` (data stays in the volume) |

The daily forecast and ensemble refresh run by themselves (hourly forecast; ensemble at 05:45 IST).

---

## Settings reference

| Variable | Default | Meaning |
|---|---|---|
| `HEAT_API_TOKEN` | *(empty)* | **Set this.** Password for write actions (approve, dispatch, reports, saving scenarios) |
| `HEAT_DEMO` | `1` in compose | `1` = serve the demo copy (May 2024 replay, labelled synthetic reports, simulated approvals, 17 May Red alert left as a draft) |
| `HEAT_DEMO_RESET` | `0` | `1` = rebuild the demo copy at every start |
| `PORT` | `8000` | Port the server listens on |
| `HEAT_DOMAIN` | — | Domain for HTTPS (route B with Caddy) |
| `HEAT_DISPATCH_MODE`, `TWILIO_*` | simulated | Real SMS / WhatsApp / voice; see `docs/alerts_phase7.md` |

## If something goes wrong

| Symptom | Likely cause and fix |
|---|---|
| Page says "replay 'may2024' not built" | The weather download failed at start (no internet on the server?). Check the logs for `WARNING: replay build failed`, then restart |
| Build fails at `npm ci` | `frontend/package-lock.json` missing: pull the latest code |
| What-if "cooling centre" gives an error | `data/processed/access_cache.pkl` missing from git: pull the latest code |
| Approve button says 401 | Enter the `HEAT_API_TOKEN` value in **Alerts → API token** |
| HTTPS certificate not issued | The domain doesn't point at the server yet, or port 80/443 is closed in the firewall |
| Hugging Face "Build error" | Read the Logs tab; compare with the GitHub **Actions → docker** job, which runs the same build |
| Container restarts repeatedly | `docker compose logs heat`, then send the last 50 lines to the project owner |

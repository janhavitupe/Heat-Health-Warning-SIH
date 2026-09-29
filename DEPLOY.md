# Deploying the Heat-Health Early Warning Platform on Render (free, no card)

This guide is for whoever puts the app online. You don't need to know the code.

**The result:** a permanent public link such as **https://heat-health.onrender.com/?replay=may2024**, hosted on **Render's free plan**. No credit or debit card is needed; you sign in with GitHub.

**How it works:** the app is **one Docker container**, a Python server that also serves the web map. The May 2024 demo is built into the container image, so the site starts in seconds. Render builds the image straight from the GitHub repository.

**Time:** about 30 minutes, most of it waiting for the first build.

---

## What the free plan means

| | Free plan |
|---|---|
| Link | Permanent: `https://<name>.onrender.com` |
| Card | Not needed |
| Sleep | After **15 minutes with no visitors** the site sleeps; the next visitor waits about 1 minute while it wakes. Step 4 below keeps it awake |
| Memory | 512 MB. The app uses about 200–300 MB (measured) |
| Saved changes | Alert approvals, reports and saved scenarios **reset whenever the site restarts** (redeploy or wake-up). The May 2024 demo always comes back fresh, with the 17 May Red alert as a draft, which is what a demo needs |
| Live forecast | Refreshed every hour. The 122-run probability ensemble is **switched off** (`HEAT_ENSEMBLE=0`) because the free CPU is too small. The **May 2024 demo still shows its probabilities**, which are built in |

---

## 0. Before you start

1. **The code is ready on GitHub.** Open https://github.com/janhavitupe/Heat-Health-Warning-SIH/actions and check that the latest **docker** run is green. It builds the same image Render will build, starts it, and tests the pages.
2. **Nothing needs to be copied from the project owner's laptop.** Render reads the repository directly.
   - **Never ask for their `.env`:** it holds their personal Twilio token.
   - **Never ask for `data/manual/test_recipients.csv`:** it holds their phone number.
3. **Make a password for officers.** Use any password generator and pick 30+ random characters. This is `HEAT_API_TOKEN`. Keep it somewhere safe: officers type it in the app before approving alerts.

## 1. Create a Render account

1. **Sign up:** go to https://render.com → **Get Started** → **GitHub**, and sign in with your GitHub account.
2. **Allow access to the repository:**
   - **If the repository belongs to someone else** (e.g. `janhavitupe`), the owner adds you as a collaborator: GitHub → repository → **Settings → Collaborators → Add people**. The owner can also create the Render service themselves in their own Render account.
   - **Otherwise**, when Render asks, allow it to see that repository (**Configure GitHub App → Only select repositories → Heat-Health-Warning-SIH**).

## 2. Create the web service

1. **Start:** in the Render dashboard, click **+ New → Web Service**.
2. **Pick the repository:** choose **Heat-Health-Warning-SIH**. Or, under **Public Git Repository**, paste `https://github.com/janhavitupe/Heat-Health-Warning-SIH`.
3. **Fill in the form:**
   - **Name:** `heat-health`. This becomes the link: `heat-health.onrender.com`. If the name is taken, pick another.
   - **Language / Runtime:** **Docker**. Render detects the `Dockerfile` itself.
   - **Branch:** `master`
   - **Region:** **Singapore**, the closest to India.
   - **Instance type:** **Free**
4. **Environment variables:** under **Environment Variables**, click **Add** for each:

   | Key | Value |
   |---|---|
   | `HEAT_API_TOKEN` | the password from step 0.3 |
   | `HEAT_DEMO` | `1` |
   | `HEAT_ENSEMBLE` | `0` |
   | `HEAT_DEMO_RESET` | `1` |

5. **Health check:** open **Advanced** and set **Health Check Path** to `/status`.
6. **Create:** click **Create Web Service**.

## 3. Wait for the first build

- **Build:** Render shows the build log. The first build takes **10–20 minutes**: it builds the map, installs Python packages and builds the May 2024 demo into the image.
- **Start:** when the log shows `[start] serving on port 10000` and the page says **Live**, it's running.
- **Open the demo:** **https://heat-health.onrender.com/?replay=may2024**, using your service name.

That's the permanent link. Every time someone pushes to `master` on GitHub, Render rebuilds and redeploys automatically.

## 4. Keep it awake (recommended, free, no card)

Without visitors the site sleeps after 15 minutes. A free uptime monitor visits it every 5 minutes:

1. **Sign up** at https://uptimerobot.com (free plan, no card).
2. **Add a monitor:** **+ New monitor** → type **HTTP(s)**.
3. **Point it at the site:** URL `https://heat-health.onrender.com/status`, interval **5 minutes**, then **Create monitor**.

Render's free plan gives 750 hours a month, enough for one service running all month. As a bonus, UptimeRobot emails you if the site goes down.

---

## Before presenting

- **Open the link 2 minutes early.** If it was asleep, the first load takes about a minute.
- **Reset the demo:** to have the 17 May Red alert back as a draft, go to Render → the service → **Manual Deploy → Restart service**. With `HEAT_DEMO_RESET=1`, every restart gives a fresh demo.
- **Give the password to the approving officer.** Officers type the password once in **Alerts → API token**; without it, Approve shows **401**.

## Everyday tasks (in the Render dashboard)

| Task | Where |
|---|---|
| Update to the latest code | Automatic on every push to `master`; or **Manual Deploy → Deploy latest commit** |
| See logs | Service → **Logs** |
| Restart / fresh demo | **Manual Deploy → Restart service** |
| Change the password | **Environment** → edit `HEAT_API_TOKEN` → **Save, rebuild and deploy** |
| Take it offline | **Settings → Suspend Web Service** |

## Security

- **`HEAT_API_TOKEN` is required on a public site.** Without it, anyone can approve alerts and submit health reports; the app prints a warning in the logs if it's empty.
- **Alert delivery stays simulated** unless Twilio variables are added, so the public site can't text anyone.

## Settings reference

| Variable | Render value | Meaning |
|---|---|---|
| `HEAT_API_TOKEN` | your password | **Required.** Password for write actions (approve, dispatch, reports, saving scenarios) |
| `HEAT_DEMO` | `1` | Serve the demo copy (May 2024 replay, labelled synthetic reports, simulated approvals, 17 May Red alert left as a draft) |
| `HEAT_DEMO_RESET` | `1` | Rebuild the demo copy at every start |
| `HEAT_ENSEMBLE` | `0` | `0` = skip the 122-run live ensemble (too slow for the free CPU). Use `1` on a bigger server |
| `HEAT_DISPATCH_MODE`, `TWILIO_*` | not set | Real SMS / WhatsApp / voice; see `docs/alerts_phase7.md` |

## If something goes wrong

| Symptom | Likely cause and fix |
|---|---|
| Build fails | Open the build log in Render and compare with GitHub **Actions → docker**, which runs the same build. Send the last 40 lines to the project owner |
| "Exited with status 137" or "Out of memory" | Over the 512 MB limit. Check `HEAT_ENSEMBLE` is `0`, then restart |
| First load takes about a minute | The site was asleep. Set up step 4 |
| Page says "replay 'may2024' not built" | The image build skipped the demo. Check the build log for errors in the `api.cli replay` step |
| Approve button says 401 | Enter the `HEAT_API_TOKEN` value in **Alerts → API token** |
| Approvals / reports disappeared | Expected on the free plan: they reset on restart (see "What the free plan means") |
| Anything else | Service → **Logs**, then send the last 60 lines to the project owner |

---

## Running it on your own computer instead

With Docker Desktop installed: clone the repository, then run `cp .env.deploy.example .env`, set `HEAT_API_TOKEN` in `.env`, and run `docker compose up -d --build`. Open http://localhost:8000/?replay=may2024.

To share it temporarily from your computer: run `cloudflared tunnel --url http://localhost:8000` (install with `winget install Cloudflare.cloudflared`). It prints a public link that works while your computer is on.

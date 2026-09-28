# Deploying the Heat-Health Early Warning Platform on Oracle Cloud (free)

This guide is for whoever puts the app online. You don't need to know the code.

**The result:** a permanent, always-on link such as **https://heatwatch.duckdns.org/?replay=may2024**, hosted on Oracle Cloud's **Always Free** tier.

**How the app runs:** it's **one Docker container**, a Python server that also serves the web map, with a SQLite database stored in a Docker volume. On first start it builds the May 2024 demo from files in the repository (no internet needed for that part), fetches today's forecast, and serves everything.

**Time:** about 1 hour the first time, most of it waiting.

---

## 0. Before you start

1. **The code is ready on GitHub.** Open https://github.com/janhavitupe/Heat-Health-Warning-SIH/actions and check that the latest **docker** run is green. It builds and tests the app for both normal (x86) and ARM processors. Oracle's free server is ARM.
2. **Nothing needs to be copied from the project owner's laptop.** Cloning the repository gives you everything.
   - **Never ask for their `.env`:** it holds their personal Twilio token.
   - **Never ask for `data/manual/test_recipients.csv`:** it holds their phone number.
3. **You need:**
   - an email address;
   - a **debit or credit card** for Oracle's identity check. Oracle places a small temporary hold and refunds it. The Always Free resources below are never charged;
   - a laptop with a terminal. Windows PowerShell has `ssh` built in.

---

## 1. Create the Oracle account

1. **Sign up:** go to https://www.oracle.com/cloud/free/ → **Start for free**.
2. **Choose the home region carefully.** Pick **India West (Mumbai)** or **India South (Hyderabad)**; it **can't be changed later**, and Always Free resources exist only there.
3. **Verify:** finish the email and card checks. Account activation can take from a few minutes to a few hours.
4. **Log in** at https://cloud.oracle.com.

## 2. Create the server (free ARM VM)

1. **Start:** ☰ menu → **Compute → Instances → Create instance**.
2. **Name:** `heat-health`.
3. **Image:** click **Edit** next to *Image and shape* → **Change image** → **Ubuntu** → **Canonical Ubuntu 24.04** → Select.
4. **Shape:** click **Change shape** → **Ampere** → **VM.Standard.A1.Flex**. Set **OCPUs = 2** and **Memory = 12 GB**. It must show the **"Always Free-eligible"** label.
5. **Networking:** keep **Create new virtual cloud network** and **Create new public subnet**, and make sure **Assign a public IPv4 address** is **on**.
6. **SSH keys:** choose **Generate a key pair for me** and click **Save private key**. Keep this `.key` file safe: it's the only way into the server.
7. **Boot volume:** keep the default (about 47 GB, free).
8. Click **Create**. After 1–2 minutes the state turns **RUNNING**. Copy the **Public IP address** from the instance page.

> **"Out of capacity for shape VM.Standard.A1.Flex"** is common. Try a different **Availability domain** (AD-1 / AD-2 / AD-3) in the placement section, try **1 OCPU / 6 GB**, or try again a few hours later.

## 3. Open the web ports in Oracle's firewall

Oracle blocks everything except SSH by default. There are **two** firewalls, and both must allow the web ports.

**a. The cloud firewall (security list):**
1. On the instance page, click the **subnet** link → **Security Lists** → **Default Security List** → **Add Ingress Rules**.
2. Add three rules, each with **Source CIDR** `0.0.0.0/0`, **IP Protocol** TCP, and **Destination Port Range**:
   - `80` (web)
   - `443` (secure web)
   - `8000` (the app directly, for testing before HTTPS)

**b. The firewall inside Ubuntu:** done in step 4 below.

## 4. Connect to the server

On your laptop:

**Windows (PowerShell)** — first make the key private, or ssh refuses it:
```
icacls "C:\path\to\ssh-key.key" /inheritance:r /grant:r "$($env:USERNAME):(R)"
ssh -i "C:\path\to\ssh-key.key" ubuntu@<PUBLIC-IP>
```

**macOS / Linux:**
```
chmod 600 ~/Downloads/ssh-key.key
ssh -i ~/Downloads/ssh-key.key ubuntu@<PUBLIC-IP>
```
Type `yes` the first time. You're in when the prompt looks like `ubuntu@heat-health:~$`.

**Now open the ports inside Ubuntu.** Oracle's Ubuntu image has its own firewall rules, and this step is easy to miss. Paste these lines into the server:
```
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 8000 -j ACCEPT
sudo netfilter-persistent save
```

## 5. Install Docker and start the app

Paste into the server:
```
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu
exit
```
Connect again with the same `ssh` command, so the Docker permission applies, then run:
```
git clone https://github.com/janhavitupe/Heat-Health-Warning-SIH.git heat
cd heat
cp .env.deploy.example .env
python3 -c "import secrets; print(secrets.token_urlsafe(24))"
```
The last line prints a random password.
1. **Copy the password.** Keep it somewhere safe: this is `HEAT_API_TOKEN`.
2. **Edit the settings:** run `nano .env`. After `HEAT_API_TOKEN=`, paste the password, and leave `HEAT_DEMO=1`.
3. **Save:** press **Ctrl+O**, **Enter**, then **Ctrl+X**.

Start the app:
```
docker compose up -d --build
docker compose logs -f
```
The first build takes **10–15 minutes** on the ARM server; it compiles the web map and installs Python packages. Then start-up takes about 2 minutes. It's ready when the log shows:
```
[start] serving on port 8000
```
Press **Ctrl+C** to leave the log. The app keeps running.

**Test it:** open **http://\<PUBLIC-IP\>:8000/?replay=may2024** in your browser. You should see the Ahmedabad map with the May 2024 heatwave.

## 6. Permanent HTTPS link (free domain)

1. **Get a free name:** go to https://www.duckdns.org, sign in (e.g. with GitHub), type a name such as `heatwatch` and click **add domain**.
2. **Point it at the server:** in the **current ip** box next to it, paste the server's **Public IP** and click **update ip**.
3. **Tell the app the domain.** On the server, run `nano .env` and set:
   ```
   HEAT_DOMAIN=heatwatch.duckdns.org
   ```
   Save.
4. **Restart with HTTPS:**
   ```
   docker compose -f docker-compose.yml -f docker-compose.https.yml up -d --build
   ```
   Caddy gets the certificate automatically, usually within a minute.
5. **Share:** **https://heatwatch.duckdns.org/?replay=may2024** (with your chosen name). That's the permanent link.

From now on, use `-f docker-compose.yml -f docker-compose.https.yml` in every `docker compose` command (see the table below). You can then remove the port `8000` rule from the security list; the app is reached through HTTPS only.

## 7. Keep it permanent

- **It restarts itself.** The container is set to `restart: unless-stopped`, so it comes back after a server reboot.
- **Oracle may reclaim "idle" free servers.** Always Free instances can be stopped if CPU, network and memory use all stay below 20% for 7 days, and this app is quiet most of the time. There are two ways to avoid it:
  1. **Open the site regularly.** The app also refreshes the forecast every hour and the ensemble every morning, which helps but may not be enough.
  2. **Upgrade the account** to **Pay As You Go** (☰ → Billing → Upgrade and manage payment). Idle reclamation doesn't apply to such accounts, and **Always Free resources stay free**. Only create resources marked "Always Free-eligible", and set a budget alert (☰ → Billing → Budgets) at ₹100 so you're warned of any charge.
- **The IP stays the same** as long as the instance isn't deleted, so the DuckDNS name keeps working.

---

## Everyday commands

Run these on the server, in the `heat` folder. With HTTPS, write `docker compose -f docker-compose.yml -f docker-compose.https.yml` wherever the table says `docker compose`.

| Task | Command |
|---|---|
| Update to the latest code from GitHub | `git pull && docker compose up -d --build` |
| See logs | `docker compose logs -f heat` |
| Restart | `docker compose restart heat` |
| Fresh demo (17 May Red alert back to draft) | `docker compose exec heat python scripts/demo_setup.py --no-pdf`, then `docker compose restart heat` |
| Back up the database | `docker compose cp heat:/app/data/api ./backup-$(date +%F)` |
| Stop | `docker compose down` (data stays in the Docker volume) |

## Security

- **`HEAT_API_TOKEN` is required on a public server.** Without it, anyone can approve alerts and submit health reports. The app prints a warning at start-up if it's empty.
  - **Officers** type it once in **Alerts → API token** before approving.
  - **Health workers** need it to submit reports.
- **Alert delivery stays simulated** unless Twilio variables are added to `.env`, so the public site can't text anyone.
- **Only the project team gets the SSH key file.** Never commit it.

## Settings reference (`.env`)

| Variable | Default | Meaning |
|---|---|---|
| `HEAT_API_TOKEN` | *(empty)* | **Set this.** Password for write actions (approve, dispatch, reports, saving scenarios) |
| `HEAT_DEMO` | `1` | `1` = serve the demo copy (May 2024 replay, labelled synthetic reports, simulated approvals, 17 May Red alert left as a draft) |
| `HEAT_DEMO_RESET` | `0` | `1` = rebuild the demo copy at every start |
| `HEAT_DOMAIN` | — | Your domain, for HTTPS (step 6) |
| `HEAT_DISPATCH_MODE`, `TWILIO_*` | simulated | Real SMS / WhatsApp / voice; see `docs/alerts_phase7.md` |

## If something goes wrong

| Symptom | Likely cause and fix |
|---|---|
| Browser can't reach `http://<IP>:8000` | A port is still closed. Check **both** step 3 (security list) and the `iptables` lines in step 4 |
| `permission denied ... docker.sock` | You didn't reconnect after `usermod`. Type `exit` and `ssh` in again |
| `ssh: ... UNPROTECTED PRIVATE KEY FILE` / `bad permissions` | Run the `icacls` (Windows) or `chmod 600` (macOS/Linux) line from step 4 |
| "Out of capacity" when creating the instance | Try another availability domain, a smaller shape (1 OCPU / 6 GB), or later |
| Build stops at `npm ci` or `pip install` with "Killed" | Not enough memory. Use at least 6 GB, or add swap: `sudo fallocate -l 4G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile` |
| Page says "replay 'may2024' not built" | Check `docker compose logs heat` for `WARNING: replay build failed` and send the lines to the project owner |
| HTTPS certificate not issued | The DuckDNS IP doesn't match the server, or port 80/443 is closed (step 3 and step 4) |
| Approve button says 401 | Enter the `HEAT_API_TOKEN` value in **Alerts → API token** |
| Site stopped after a quiet week | Oracle reclaimed the idle instance: start it again in the console, and see step 7 |
| Anything else | `docker compose logs --tail 60 heat`, then send the output to the project owner |

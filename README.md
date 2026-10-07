# Government Jobs India – auto-updating site (no server, free)

Shows latest Indian government jobs with details and an **Apply** button that goes to the **official website**.
Updated automatically 3 times a day by GitHub Actions. Hosted free on GitHub Pages / Cloudflare Pages / Netlify.

## How it works
1. `fetcher/fetch_jobs.py` reads RSS feeds from `fetcher/feeds.json`.
2. For each new post it opens the page and finds the official link (gov.in, nic.in, upsc, ssc, railway, bank sites…).
3. It saves everything to `data/jobs.json` (title, category, state, vacancies, last date, apply link, notification PDF).
4. `index.html` + `app.js` read that file and show search, category and state filters.

## Setup (10 minutes)
1. Create a new GitHub repo and upload ALL these files (keep the `.github` folder).
2. Repo → **Settings → Actions → General → Workflow permissions → Read and write permissions → Save**.
3. Repo → **Actions** tab → "Update government jobs daily" → **Run workflow**. Wait 1-2 minutes. `data/jobs.json` fills up.
4. Host it:
   - **GitHub Pages:** Settings → Pages → Deploy from branch → `main` / root.
   - **Cloudflare Pages / Netlify:** connect the repo, build command empty, output folder `/`.
5. To add this to technojobs.online, either link to this site, or copy `index.html`, `style.css`, `app.js`, `data/` into it.

## Add or change sources
Edit `fetcher/feeds.json`. Open each feed URL in your browser first to confirm it shows XML.
Good sources to add: official RSS from state PSC / board websites when available.

## Run locally (optional)
```
python fetcher/fetch_jobs.py
python -m http.server 8000     # then open http://localhost:8000
```

## Important
- Only a short summary and links are stored, not full articles. Keep it that way (copyright).
- "Official link not found" means the post had no gov link. Check the source before trusting it.
- Keep the disclaimer on the page: not a government website, never pay for applying.
- Some blogs may block bots or change their feed. If a feed stops working, replace it in `feeds.json`.

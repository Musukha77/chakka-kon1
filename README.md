# CHAKKA KON deployment package

This package turns the Flask server from the Colab notebook into a Render web service.

## Files
- `app.py` — Flask API and game server.
- `requirements.txt` — Python dependencies.
- `index.html` — game webpage. It supports being served from Render and from the existing Netlify site.

## Important frontend setting
After Render gives you your service URL, open `index.html` and replace:

`https://YOUR-RENDER-SERVICE.onrender.com`

with your actual Render URL. Then commit the updated `index.html` to GitHub and redeploy the same updated HTML to Netlify (or connect Netlify to this GitHub repo).

When opened directly on the Render service URL, the page automatically uses the same origin for its API.

## GitHub repository files
Upload these files to the top/root level of your `chakka-kon` repository:
- `app.py`
- `requirements.txt`
- `index.html`
- `README.md`

## Render settings
- Runtime: Python 3
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn --workers 1 --threads 8 --bind 0.0.0.0:$PORT app:app`
- Environment variable (optional): `ALLOWED_ORIGINS=https://chakkagamecuj.netlify.app`

The backend also serves `index.html` at `/` and a health check at `/health`.

## Existing game behavior retained
- Five players per room.
- One hidden Chakka and four Chee Chakkas.
- Host starts the game after all five players join.
- Host manually starts each 10-second voting period.
- A unanimous completed set of votes resolves early; otherwise it resolves when the 10-second deadline is noticed by a player polling `/api/state`.
- Room chat and manual PeerJS voice-ID exchange remain in the webpage.

## Prototype limitations
- Rooms and chat are held in server memory. They are lost if the service restarts, redeploys, or sleeps and spins down.
- Render Free web services spin down after 15 minutes without inbound traffic and can take about a minute to wake up. Use a paid always-on service for a continuously available game server.
- The current voice chat is an optional manual Voice ID exchange, not automatic room-wide voice. Use microphone permissions carefully and share Voice IDs only with people in your room.
- This is a casual prototype and does not include accounts, durable storage, abuse prevention, or production-grade anti-cheat.

# Building and vendoring the front-end (SPA)

The web UI is built in the separate control-plane frontend repo and committed into this repo
as a static bundle under `web/`. The device serves that bundle directly — it never builds the
front-end itself.

The SPA talks to the device on the same origin using relative URLs, so it is built with an
empty `VITE_API_BASE_URL`.

Commands below are PowerShell (Windows). Example paths:
- frontend repo: `D:\diplom\app\control_plane\frontend`
- device repo:   `D:\diplom\app\kvm_engine_py`

## 1. Build

```powershell
cd D:\diplom\app\control_plane\frontend
$env:VITE_API_BASE_URL=""
npm install        # first time only
npm run build      # outputs to .\dist
```

## 2. Copy the bundle into the device repo

```powershell
Remove-Item -Recurse -Force D:\diplom\app\kvm_engine_py\web -ErrorAction SilentlyContinue
New-Item -ItemType Directory D:\diplom\app\kvm_engine_py\web | Out-Null
Copy-Item -Recurse D:\diplom\app\control_plane\frontend\dist\* D:\diplom\app\kvm_engine_py\web\
```

## 3. Commit and push

```powershell
cd D:\diplom\app\kvm_engine_py
git add web
git commit -m "web: update vendored SPA bundle"
git push
```

## 4. Deploy on the device

```bash
cd ~/kvm_engine_py
git pull
```

Caddy serves `web/` as static files, so no restart is needed; refresh the browser to load the
new bundle.

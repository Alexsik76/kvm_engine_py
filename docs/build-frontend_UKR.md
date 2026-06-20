# Збірка й вкладання фронту (SPA)

Веб-інтерфейс збирається в окремому репозиторії фронту control-plane і комітиться в цей
репозиторій як статичний бандл у `web/`. Пристрій роздає цей бандл напряму — сам фронт він не
збирає.

SPA звертається до пристрою на тому ж походженні відносними URL, тож збирається з порожнім
`VITE_API_BASE_URL`.

Команди нижче — PowerShell (Windows). Приклади шляхів:
- репозиторій фронту:    `D:\diplom\app\control_plane\frontend`
- репозиторій пристрою:  `D:\diplom\app\kvm_engine_py`

## 1. Збірка

```powershell
cd D:\diplom\app\control_plane\frontend
$env:VITE_API_BASE_URL=""
npm install        # лише першого разу
npm run build      # результат у .\dist
```

## 2. Копіювання бандла в репозиторій пристрою

```powershell
Remove-Item -Recurse -Force D:\diplom\app\kvm_engine_py\web -ErrorAction SilentlyContinue
New-Item -ItemType Directory D:\diplom\app\kvm_engine_py\web | Out-Null
Copy-Item -Recurse D:\diplom\app\control_plane\frontend\dist\* D:\diplom\app\kvm_engine_py\web\
```

## 3. Коміт і пуш

```powershell
cd D:\diplom\app\kvm_engine_py
git add web
git commit -m "web: update vendored SPA bundle"
git push
```

## 4. Розгортання на пристрої

```bash
cd ~/kvm_engine_py
git pull
```

Caddy роздає `web/` як статику, тож перезапуск не потрібен; онови сторінку в браузері, щоб
підвантажити новий бандл.

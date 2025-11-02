# deploy.ps1 – script aggiornato per Windows + GitHub + Render

Write-Host "🔄 Avvio deploy..."

# 1. Aggiunge tutti i file modificati
git add .

# 2. Crea commit con data/ora
$time = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
git commit -m "auto-deploy $time"

# 3. Si assicura di essere sulla branch main
$branch = git branch --show-current
if (-not $branch) {
    Write-Host "⚙️  Non sei su nessuna branch, passo a main..."
    git switch main
}

# 4. Effettua il push su GitHub
git push origin main

Write-Host "✅ Deploy completato con successo!"

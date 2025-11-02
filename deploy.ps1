# =============================
# ✅ DEPLOY SCRIPT per prenotazioni-ai
# =============================

Write-Host "🚀 Avvio deploy..."

# Forza sulla branch main
git switch main | Out-Null

# Aggiunge tutto e crea commit automatico
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
git add .
git commit -m "auto-deploy $timestamp"

# Aggiorna con eventuali modifiche remote
git pull origin main --rebase

# Esegue il push effettivo
git push origin main

Write-Host "`n✅ Deploy completato con successo! 🎉"

#!/bin/bash
# ============================================================
# NAHRÁT ZMĚNY NA WEB — stačí poklepat na tento soubor.
# Vezme všechny změněné soubory ve složce, uloží je do gitu
# a odešle na GitHub. (Web se přegeneruje ráno v 8:30, nebo
# hned přes Actions -> Run workflow.)
# ============================================================
cd "$(dirname "$0")" || exit 1

# úklid po případném přerušeném běhu
rm -f .git/index.lock

# jednorázově: přestat sledovat generované soubory (neškodné opakovat)
git rm -r --cached --quiet index.html data.html data.json hledani.json 2>/dev/null

git add -A

if git diff --cached --quiet; then
  echo "Žádné změny k nahrání — vše už je na GitHubu."
else
  git commit -m "Aktualizace $(date '+%-d. %-m. %Y %H:%M')"
  if git push origin main; then
    echo ""
    echo "✅ HOTOVO — změny jsou na GitHubu."
    echo "   Web se přegeneruje ráno v 8:30, nebo spusť Actions -> Run workflow."
  else
    echo ""
    echo "❌ Odeslání se nepovedlo. Při prvním spuštění tě git požádá"
    echo "   o přihlášení: Username = zasiik, Password = tvůj token"
    echo "   (návod na token je v chatu). Pak spusť tento soubor znovu."
  fi
fi
echo ""
read -p "Stiskni Enter pro zavření..."

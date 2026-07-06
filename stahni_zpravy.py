# ============================================================
# Krok 1: Stažení zpráv z RSS kanálů.
# Tenhle soubor upravovat nemusíš — nastavení je v config.py.
# ============================================================

import calendar
import re
import time
import feedparser
from config import ZDROJE, MAX_Z_KAZDEHO_ZDROJE, MAX_VYJIMKY, MAX_STARI_HODIN


def _vycisti_text(text, max_delka=400):
    """Odstraní HTML značky a zkrátí text na rozumnou délku."""
    text = re.sub(r"<[^>]+>", " ", text)          # pryč s HTML značkami
    text = re.sub(r"\s+", " ", text).strip()      # sjednotit mezery
    if len(text) > max_delka:
        text = text[:max_delka].rsplit(" ", 1)[0] + "…"
    return text


def stahni_vsechny_zpravy():
    """Projde všechny zdroje z config.py a vrátí seznam zpráv."""
    zpravy = []
    for nazev_zdroje, url in ZDROJE.items():
        print(f"Stahuji: {nazev_zdroje} ...", end=" ")
        feed = feedparser.parse(url)

        if feed.bozo and not feed.entries:
            print(f"CHYBA – nepodařilo se načíst ({feed.bozo_exception})")
            continue

        nejstarsi = time.time() - MAX_STARI_HODIN * 3600
        limit = MAX_VYJIMKY.get(nazev_zdroje, MAX_Z_KAZDEHO_ZDROJE)
        pocet = 0
        for polozka in feed.entries:
            if pocet >= limit:
                break
            # Přeskočit staré zprávy (bez data necháme projít)
            cas = polozka.get("published_parsed") or polozka.get("updated_parsed")
            if cas and calendar.timegm(cas) < nejstarsi:
                continue
            zprava = {
                "zdroj": nazev_zdroje,
                "titulek": polozka.get("title", "").strip(),
                "popis": _vycisti_text(polozka.get("summary", "")),
                "odkaz": polozka.get("link", ""),
                "datum": _datum_jako_text(polozka),
            }
            if zprava["titulek"] and zprava["odkaz"]:
                zpravy.append(zprava)
                pocet += 1
        print(f"OK, {pocet} zpráv")
    return zpravy


def _datum_jako_text(polozka):
    """Převede datum zprávy na text ve formátu RRRR-MM-DD HH:MM."""
    cas = polozka.get("published_parsed") or polozka.get("updated_parsed")
    if cas:
        return time.strftime("%Y-%m-%d %H:%M", cas)
    return ""


# Když spustíš tenhle soubor přímo (python3 stahni_zpravy.py),
# stáhne zprávy a vypíše je na obrazovku — na vyzkoušení.
if __name__ == "__main__":
    zpravy = stahni_vsechny_zpravy()
    print(f"\nCelkem staženo: {len(zpravy)} zpráv\n")
    for z in zpravy:
        print(f"[{z['zdroj']}] {z['datum']}")
        print(f"  {z['titulek']}")
        print(f"  {z['odkaz']}\n")

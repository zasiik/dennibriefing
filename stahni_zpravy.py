# ============================================================
# Krok 1: Stažení zpráv z RSS kanálů (paralelně, 8 najednou).
# Tenhle soubor upravovat nemusíš — nastavení je v config.py.
# ============================================================

import calendar
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import feedparser

from config import ZDROJE, MAX_Z_KAZDEHO_ZDROJE, MAX_VYJIMKY, MAX_STARI_HODIN


def _vycisti_text(text, max_delka=400):
    """Odstraní HTML značky a zkrátí text na rozumnou délku."""
    text = re.sub(r"<[^>]+>", " ", text)          # pryč s HTML značkami
    text = re.sub(r"\s+", " ", text).strip()      # sjednotit mezery
    if len(text) > max_delka:
        text = text[:max_delka].rsplit(" ", 1)[0] + "…"
    return text


def _oprav_a_zparsuj(url):
    """Záchrana vadného XML (např. Kurzy.cz): stáhne, vyčistí, zkusí znovu."""
    try:
        pozadavek = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 dennibriefing.cz"})
        with urllib.request.urlopen(pozadavek, timeout=15) as odpoved:
            text = odpoved.read().decode("utf-8", errors="replace")
        # Pryč s řídicími znaky, které XML nesnese
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
        # Osamocené & (časté u českých webů) -> &amp;
        text = re.sub(r"&(?!#?\w+;)", "&amp;", text)
        feed = feedparser.parse(text)
        return feed if feed.entries else None
    except Exception:
        return None


def _zpracuj_zdroj(nazev_zdroje, url):
    """Stáhne jeden kanál a vrátí (název, seznam zpráv, text chyby | None)."""
    feed = feedparser.parse(url)
    if feed.bozo and not feed.entries:
        oprava = _oprav_a_zparsuj(url)
        if oprava is None:
            return nazev_zdroje, [], str(feed.bozo_exception)
        feed = oprava

    nejstarsi = time.time() - MAX_STARI_HODIN * 3600
    limit = MAX_VYJIMKY.get(nazev_zdroje, MAX_Z_KAZDEHO_ZDROJE)
    zpravy = []
    for polozka in feed.entries:
        if len(zpravy) >= limit:
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
    return nazev_zdroje, zpravy, None


def stahni_vsechny_zpravy():
    """Projde všechny zdroje z config.py paralelně a vrátí seznam zpráv."""
    polozky = list(ZDROJE.items())
    with ThreadPoolExecutor(max_workers=8) as bazen:
        vysledky = list(bazen.map(lambda p: _zpracuj_zdroj(*p), polozky))

    vsechny = []
    for nazev, zpravy, chyba in vysledky:   # výpis v pořadí z config.py
        if chyba is not None:
            print(f"Zdroj {nazev}: CHYBA – nepodařilo se načíst ({chyba})")
        else:
            print(f"Zdroj {nazev}: OK, {len(zpravy)} zpráv")
            vsechny.extend(zpravy)
    return vsechny


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

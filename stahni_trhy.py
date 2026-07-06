# ============================================================
# Klíčová čísla — aktuální hodnoty + 5 let historie pro grafy.
#
# Primární zdroj: Yahoo Finance (zdarma, bez klíče).
# Záloha:         stooq.com (kdyby Yahoo nefungovalo).
# Navíc:          repo sazba z webu ČNB (bez grafu).
#
# Každý ukazatel je chráněný: když selže, ostatní jedou dál.
# ============================================================

import csv
import io
import json
import re
import urllib.request
from datetime import date, datetime, timedelta

from config import TRZNI_UKAZATELE

_HLAVICKY = {"User-Agent": "Mozilla/5.0 (Macintosh) osobni-zpravodajsky-web"}


def _stahni(url):
    pozadavek = urllib.request.Request(url, headers=_HLAVICKY)
    with urllib.request.urlopen(pozadavek, timeout=20) as odpoved:
        return odpoved.read().decode("utf-8", errors="replace")


def _formatuj(cislo):
    """1234.56 -> '1 235'; 21.13 -> '21,13' (české formátování)."""
    if abs(cislo) >= 1000:
        return f"{cislo:,.0f}".replace(",", " ")
    return f"{cislo:.2f}".replace(".", ",")


def _zabal(nazev, dny, hodnoty):
    """Z historie (datum, hodnota) vyrobí záznam pro stránku."""
    if len(hodnoty) < 2:
        return None
    # Zředit dlouhou historii, ať data.json zbytečně neroste
    if len(hodnoty) > 1300:
        krok = len(hodnoty) / 1300
        vyber = [hodnoty[int(i * krok)] for i in range(1300)]
        vyber[-1] = hodnoty[-1]
        hodnoty = vyber
        dny = [dny[int(i * krok)] for i in range(1300)]
        dny[-1] = dny[-1]
    posledni, predposledni = hodnoty[-1], hodnoty[-2]
    return {
        "nazev": nazev,
        "hodnota": _formatuj(posledni),
        "zmena_pct": (posledni / predposledni - 1) * 100 if predposledni else None,
        "historie": [[d, round(h, 4)] for d, h in zip(dny, hodnoty)],
    }


def _yahoo(nazev, symbol):
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
           f"?range=5y&interval=1d")
    data = json.loads(_stahni(url))
    vysledek = data["chart"]["result"][0]
    casy = vysledek["timestamp"]
    zavery = vysledek["indicators"]["quote"][0]["close"]
    dny, hodnoty = [], []
    for cas, zaver in zip(casy, zavery):
        if zaver is not None:
            dny.append(datetime.fromtimestamp(cas).strftime("%Y-%m-%d"))
            hodnoty.append(zaver)
    return _zabal(nazev, dny, hodnoty)


def _stooq(nazev, symbol):
    d2 = date.today()
    d1 = d2 - timedelta(days=5 * 365)
    url = (f"https://stooq.com/q/d/l/?s={symbol}&i=d"
           f"&d1={d1:%Y%m%d}&d2={d2:%Y%m%d}")
    radky = list(csv.DictReader(io.StringIO(_stahni(url))))
    dny = [r["Date"] for r in radky if r.get("Close")]
    hodnoty = [float(r["Close"]) for r in radky if r.get("Close")]
    return _zabal(nazev, dny, hodnoty)


def _repo_sazba_cnb():
    """Aktuální dvoutýdenní repo sazba z webu ČNB (bez historie)."""
    text = _stahni(
        "https://www.cnb.cz/cs/casto-kladene-dotazy/"
        "Jak-se-vyvijela-dvoutydenni-repo-sazba-CNB/"
    )
    shoda = re.search(r"(\d+[.,]\d+)\s*(?:%|&nbsp;%)", text)
    if not shoda:
        return None
    return {"nazev": "Repo sazba ČNB",
            "hodnota": shoda.group(1).replace(".", ",") + " %",
            "zmena_pct": None, "historie": []}


def stahni_klicova_cisla():
    """Vrátí seznam ukazatelů s historií. Chyby jen vypíše a jede dál."""
    cisla = []
    for nazev, yahoo_symbol, stooq_symbol in TRZNI_UKAZATELE:
        zaznam, chyby = None, []
        if yahoo_symbol:
            try:
                zaznam = _yahoo(nazev, yahoo_symbol)
            except Exception as chyba:
                chyby.append(f"Yahoo: {chyba}")
        if zaznam is None and stooq_symbol:
            try:
                zaznam = _stooq(nazev, stooq_symbol)
            except Exception as chyba:
                chyby.append(f"stooq: {chyba}")
        if zaznam:
            cisla.append(zaznam)
        else:
            print(f"  Ukazatel {nazev}: nedostupný ({'; '.join(chyby) or 'bez zdroje'})")
    try:
        repo = _repo_sazba_cnb()
        if repo:
            cisla.append(repo)
    except Exception as chyba:
        print(f"  Repo sazba ČNB: nedostupná ({chyba})")
    print(f"  Načteno {len(cisla)} ukazatelů.")
    return cisla


if __name__ == "__main__":
    print("Stahuji klíčová čísla...")
    for c in stahni_klicova_cisla():
        zmena = (f"  ({c['zmena_pct']:+.2f} %)".replace(".", ",")
                 if c.get("zmena_pct") is not None else "")
        print(f"  {c['nazev']}: {c['hodnota']}{zmena}"
              f"  [historie: {len(c.get('historie', []))} dní]")

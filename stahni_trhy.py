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

# ------------------------------------------------------------
# KATALOG „na přání" — návštěvník si tituly přidává vyhledáváním
# přímo na webu. Vše se stáhne při generování (Yahoo symboly).
# ------------------------------------------------------------
_US_AKCIE = """AAPL MSFT NVDA GOOGL AMZN META TSLA BRK-B AVGO JPM LLY V UNH XOM
MA COST HD PG JNJ WMT NFLX ABBV BAC CRM ORCL CVX WFC KO MRK CSCO ADBE AMD PEP
ACN LIN TMO MCD ABT PM IBM GE ISRG CAT QCOM TXN VZ INTU DIS AMGN PFE GS SPGI
RTX NEE UBER T CMCSA BKNG AXP MS UNP LOW HON COP PANW SYK BLK ETN BX VRTX TJX
PLTR SCHW C BSX ADP MU GILD LRCX DE MMC ADI AMAT REGN KLAC CB SO MDLZ MO ICE
DUK SHW EMR PGR APH PYPL SBUX NKE INTC BA""".split()

_SVETOVE_AKCIE = ["ASML", "SAP", "TM", "NVO", "AZN", "SHEL", "TTE", "UL",
                  "SONY", "BABA", "TSM", "HSBC", "SAN", "SIEGY", "MC.PA",
                  "NESN.SW", "AIR.PA"]

_PRAZSKE_AKCIE = ["CEZ.PR", "KOMB.PR", "MONET.PR", "ERBAG.PR", "VIG.PR"]

_KRYPTO = ["ETH-USD", "SOL-USD", "XRP-USD", "BNB-USD", "ADA-USD",
           "DOGE-USD", "DOT-USD", "LINK-USD", "AVAX-USD", "LTC-USD"]

_KURZY = ["EURUSD=X", "GBPUSD=X", "JPY=X", "GBPCZK=X", "CHFCZK=X", "PLNCZK=X"]

_KOMODITY = [("Stříbro", "SI=F"), ("Měď", "HG=F"), ("Zemní plyn", "NG=F"),
             ("Ropa WTI", "CL=F"), ("Platina", "PL=F")]

_INDEXY = [("Dow Jones", "^DJI"), ("DAX", "^GDAXI"), ("FTSE 100", "^FTSE"),
           ("CAC 40", "^FCHI"), ("Euro Stoxx 50", "^STOXX50E"),
           ("Nikkei 225", "^N225"), ("Hang Seng", "^HSI"),
           ("VIX", "^VIX"), ("US 10Y výnos", "^TNX")]


def _katalog():
    """Vrátí katalogové tituly jako (nazev, yahoo, stooq, vychozi=False)."""
    polozky = []
    for symbol in _US_AKCIE + _SVETOVE_AKCIE + _PRAZSKE_AKCIE:
        nazev = symbol.replace("-USD", "").split(".")[0].replace("=X", "")
        polozky.append((nazev, symbol, "", False))
    for symbol in _KRYPTO:
        polozky.append((symbol.replace("-USD", "") + " (krypto)", symbol, "", False))
    for symbol in _KURZY:
        nazev = symbol.replace("=X", "")
        if symbol == "JPY=X":
            nazev = "USD/JPY"
        elif "CZK" in nazev:
            nazev = nazev[:3] + "/CZK"
        else:
            nazev = nazev[:3] + "/" + nazev[3:]
        polozky.append((nazev, symbol, "", False))
    for nazev, symbol in _KOMODITY + _INDEXY:
        polozky.append((nazev, symbol, "", False))
    return polozky


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
    """Z historie (datum, hodnota) vyrobí záznam pro stránku.

    Ředění: poslední rok denně, starší data po týdnech —
    grafy zůstanou věrné a stránka rychlá i s desítkami titulů.
    """
    if len(hodnoty) < 2:
        return None
    posledni, predposledni = hodnoty[-1], hodnoty[-2]
    if len(hodnoty) > 320:
        stare_d, stare_h = dny[:-260], hodnoty[:-260]
        dny = stare_d[::5] + dny[-260:]
        hodnoty = stare_h[::5] + hodnoty[-260:]
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
            "zmena_pct": None, "historie": [], "vychozi": True}


def stahni_klicova_cisla():
    """Vrátí seznam ukazatelů s historií. Chyby jen vypíše a jede dál."""
    cisla = []
    # tickery.txt (tvoje sada) + katalog pro návštěvníky, bez duplicit
    vsechny = list(TRZNI_UKAZATELE)
    uz_mame = {u[1] for u in vsechny} | {u[0] for u in vsechny}
    for polozka in _katalog():
        if polozka[0] not in uz_mame and polozka[1] not in uz_mame:
            vsechny.append(polozka)
            uz_mame.add(polozka[0]); uz_mame.add(polozka[1])
    print(f"  Stahuji {len(vsechny)} titulů (může to pár minut trvat)...")
    for nazev, yahoo_symbol, stooq_symbol, vychozi in vsechny:
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
            zaznam["vychozi"] = vychozi
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

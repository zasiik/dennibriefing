# ============================================================
# Česká makrodata z oficiálního API ČSÚ (DataStat).
# Bez klíče, zdarma. Jakmile ČSÚ zveřejní nový měsíc, graf se
# při dalším generování automaticky prodlouží.
#
# Každá řada je chráněná — když selže, ostatní jedou dál.
# (ČNB ARAD lze doplnit později stejným vzorem.)
# ============================================================

import csv
import io
import json
import re
import urllib.request

_API = "https://data.csu.gov.cz/api/dotaz/v1/data/sady/{sada}/vlastni?verzeSady={verze}&format=CSV&kodZvlast=true"

# Definice řad: sada + ukazatel + dimenze (zjištěno z katalogu ČSÚ)
MAKRO_RADY = [
    {
        "nazev": "Inflace ČR (meziroční)",
        "sada": "WCEN01M", "verze": 1,
        "ukazatel": "6134J05",          # přírůstek CPI ke stejnému měsíci předch. roku
        "dimenze": {"CasM": [], "Uz0": []},
        "jednotka": " %",
    },
    {
        "nazev": "Zahájené byty ČR / měsíc",
        "sada": "STA09A2", "verze": 1,
        "ukazatel": "3025",
        "dimenze": {"CasM": [], "Uz0A": [], "TYPUDAJESP": ["0"]},
        "jednotka": "",
    },
    {
        "nazev": "Dokončené byty ČR / měsíc",
        "sada": "STA09B1", "verze": 1,
        "ukazatel": "3103",
        "dimenze": {"CasM": [], "Uz0A": [], "TYPUDAJESP": ["0"]},
        "jednotka": "",
    },
]

_MESIC = re.compile(r"^\d{4}-\d{2}$")


def _posli_dotaz(rada):
    """POST na DataStat API, vrátí text CSV s celou časovou řadou."""
    sloupce = [{"kodDimenze": "IndicatorType",
                "filtr": [{"zobrazitPolozky": [rada["ukazatel"]]}]}]
    for kod, polozky in rada["dimenze"].items():
        filtr = [{"zobrazitPolozky": polozky}] if polozky else []
        sloupce.append({"kodDimenze": kod, "filtr": filtr})
    telo = json.dumps({"sloupce": sloupce, "radky": [], "filtryTabulky": []})
    pozadavek = urllib.request.Request(
        _API.format(sada=rada["sada"], verze=rada["verze"]),
        data=telo.encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Accept-Language": "cs",
                 "User-Agent": "Mozilla/5.0 dennibriefing.cz"},
        method="POST",
    )
    with urllib.request.urlopen(pozadavek, timeout=30) as odpoved:
        return odpoved.read().decode("utf-8-sig", errors="replace")


def _rozparsuj(text_csv):
    """Z CSV vytáhne dvojice (YYYY-MM, hodnota) — robustně podle tvaru buněk."""
    body = {}
    for radek in csv.reader(io.StringIO(text_csv)):
        mesic, hodnota = None, None
        for bunka in radek:
            bunka = bunka.strip()
            if _MESIC.match(bunka):
                mesic = bunka
        if mesic:
            # hodnota = poslední buňka, která je číslo
            for bunka in reversed(radek):
                try:
                    hodnota = float(bunka.replace(",", ".").replace(" ", ""))
                    break
                except ValueError:
                    continue
        if mesic and hodnota is not None:
            body[mesic] = hodnota
    return sorted(body.items())


def _formatuj(cislo, jednotka):
    if jednotka.strip() == "%":
        return f"{cislo:.1f}".replace(".", ",") + " %"
    if abs(cislo) >= 1000:
        return f"{cislo:,.0f}".replace(",", " ") + jednotka
    return f"{cislo:g}".replace(".", ",") + jednotka


def stahni_makro_cisla():
    """Vrátí seznam měsíčních ukazatelů ČSÚ pro stránku Data."""
    cisla = []
    for rada in MAKRO_RADY:
        try:
            body = _rozparsuj(_posli_dotaz(rada))
            if len(body) < 2:
                print(f"  ČSÚ {rada['nazev']}: prázdná řada")
                continue
            posledni_mesic, posledni = body[-1]
            cisla.append({
                "nazev": rada["nazev"],
                "hodnota": _formatuj(posledni, rada["jednotka"]),
                "zmena_pct": None,
                "frekvence": "mesicni",
                "vychozi": True,
                "historie": [[m + "-01", round(h, 2)] for m, h in body],
            })
        except Exception as chyba:
            print(f"  ČSÚ {rada['nazev']}: nedostupné ({chyba})")
    print(f"  ČSÚ: načteno {len(cisla)} makro řad.")
    return cisla


if __name__ == "__main__":
    print("Stahuji makrodata ČSÚ...")
    for c in stahni_makro_cisla():
        h = c["historie"]
        print(f"  {c['nazev']}: {c['hodnota']} "
              f"[{len(h)} měsíců, {h[0][0][:7]} až {h[-1][0][:7]}]")

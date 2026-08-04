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
import os
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
        # Pozn.: tahle sada nemá dimenzi TYPUDAJESP (na rozdíl od zahájených)
        "nazev": "Dokončené byty ČR / měsíc",
        "sada": "STA09B1", "verze": 1,
        "ukazatel": "3103",
        "dimenze": {"CasM": [], "Uz0A": []},
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


# ------------------------------------------------------------
# ČNB ARAD — řady definované v souboru arad.txt, klíč v .env
# (ARAD_API_KEY). Dokumentace: ARAD-REST-API v1.
# ------------------------------------------------------------
_ARAD_API = ("https://www.cnb.cz/aradb/api/v1/data"
             "?indicator_id_list={id}&api_key={klic}"
             "&period_sort=asc&decimal_separator=point")


def _nacti_arad_radky():
    cesta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "arad.txt")
    radky = []
    try:
        with open(cesta, encoding="utf-8") as f:
            for radek in f:
                radek = radek.strip()
                if not radek or radek.startswith("#"):
                    continue
                casti = [c.strip() for c in radek.split("|")]
                if len(casti) >= 2 and casti[0] and casti[1]:
                    radky.append((casti[0], casti[1],
                                  casti[2] if len(casti) > 2 else ""))
    except FileNotFoundError:
        pass
    return radky


def _stahni_arad_radu(nazev, ukazatel_id, jednotka, klic):
    url = _ARAD_API.format(id=ukazatel_id, klic=klic)
    pozadavek = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 dennibriefing.cz"})
    with urllib.request.urlopen(pozadavek, timeout=30) as odpoved:
        text = odpoved.read().decode("cp1250", errors="replace")
    body = []
    for radek in csv.reader(io.StringIO(text), delimiter=";"):
        # sloupce: indicator_id;snapshot_id;period;value
        if len(radek) >= 4 and re.match(r"^\d{8}$", radek[2] or ""):
            try:
                hodnota = float(radek[3])
            except ValueError:
                continue
            datum = f"{radek[2][:4]}-{radek[2][4:6]}-{radek[2][6:]}"
            body.append([datum, round(hodnota, 4)])
    if len(body) < 2:
        return None
    # zředit dlouhé řady
    if len(body) > 1300:
        krok = len(body) / 1300
        body = [body[int(i * krok)] for i in range(1299)] + [body[-1]]
    posledni = body[-1][1]
    pripona = f" {jednotka}" if jednotka else ""
    return {
        "nazev": nazev,
        "hodnota": _formatuj(posledni, jednotka) if jednotka.strip() == "%"
                   else _formatuj(posledni, "") + pripona,
        "zmena_pct": None,
        "frekvence": "mesicni",
        "vychozi": True,
        "historie": body,
        "zdroj_dat": "Zdroj: ČNB ARAD",
    }


def stahni_arad_cisla():
    """Řady z ČNB ARAD podle arad.txt. Bez klíče se tiše přeskočí."""
    radky = _nacti_arad_radky()
    if not radky:
        return []
    klic = os.environ.get("ARAD_API_KEY", "").strip()
    if not klic:
        print("  ČNB ARAD: v arad.txt jsou řady, ale chybí ARAD_API_KEY "
              "v .env — přeskakuji.")
        return []
    cisla = []
    for nazev, ukazatel_id, jednotka in radky:
        try:
            zaznam = _stahni_arad_radu(nazev, ukazatel_id, jednotka, klic)
            if zaznam:
                cisla.append(zaznam)
            else:
                print(f"  ARAD {nazev}: prázdná řada (ID {ukazatel_id})")
        except Exception as chyba:
            print(f"  ARAD {nazev}: nedostupné ({chyba})")
    print(f"  ČNB ARAD: načteno {len(cisla)} řad.")
    return cisla


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

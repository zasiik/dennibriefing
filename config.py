# ============================================================
# NASTAVENÍ — tenhle soubor můžeš klidně upravovat.
# ============================================================

# --- Načtení API klíče ze souboru .env (pokud existuje) ---
# Do souboru .env v této složce napiš řádek:
#   ANTHROPIC_API_KEY=tvůj-klíč
# a už nikdy nemusíš psát "export" v Terminálu.
import os as _os
_env = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".env")
if _os.path.exists(_env):
    with open(_env, encoding="utf-8") as _f:
        for _radek in _f:
            _radek = _radek.strip()
            if _radek and not _radek.startswith("#") and "=" in _radek:
                _klic, _hodnota = _radek.split("=", 1)
                _os.environ.setdefault(_klic.strip(), _hodnota.strip().strip("'\""))

# RSS zdroje. Formát: "Název zdroje": "adresa RSS kanálu"
# Řádek smažeš = zdroj se přestane používat. Přidáš řádek = přibude zdroj.
ZDROJE = {
    # ---- Světové: hlavní dění ----
    "BBC World": "https://feeds.bbci.co.uk/news/world/rss.xml",
    "The Guardian World": "https://www.theguardian.com/world/rss",
    "WSJ World": "https://feeds.content.dowjones.io/public/rss/RSSWorldNews",
    "Al Jazeera": "https://www.aljazeera.com/xml/rss/all.xml",
    # Neověřené (můj sandbox je blokuje, u tebe nejspíš pojedou) —
    # odstraň # na začátku řádku a otestuj:
    # "NYT World": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    # "Politico Europe": "https://www.politico.eu/feed/",
    # "DW English": "https://rss.dw.com/rdf/rss-en-world",

    # ---- Světové: byznys a ekonomika ----
    "BBC Business": "https://feeds.bbci.co.uk/news/business/rss.xml",
    "The Guardian Business": "https://www.theguardian.com/uk/business/rss",
    "WSJ Markets": "https://feeds.content.dowjones.io/public/rss/RSSMarketsMain",
    "MarketWatch": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
    "Yahoo Finance": "https://finance.yahoo.com/news/rssindex",
    "CNBC": "https://www.cnbc.com/id/100003114/device/rss/rss.html",

    # ---- Světové: technologie a AI ----
    "BBC Technology": "https://feeds.bbci.co.uk/news/technology/rss.xml",
    "TechCrunch AI": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "The Verge AI": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "WSJ Tech": "https://feeds.content.dowjones.io/public/rss/RSSWSJD",
    "MIT Tech Review": "https://www.technologyreview.com/feed/",

    # ---- České: finance a ekonomika ----
    "Patria": "https://www.patria.cz/rss.html",
    "HN Byznys": "https://byznys.hn.cz/?m=rss",
    "E15": "https://www.e15.cz/rss",

    # ---- České: obecné dění (menší váha) ----
    "Seznam Zprávy": "https://www.seznamzpravy.cz/rss",
    "ČTK hlavní zprávy": "https://www.ceskenoviny.cz/sluzby/rss/zpravy.php",
    "ČTK domácí": "https://www.ceskenoviny.cz/sluzby/rss/cr.php",

    # ---- Oficiální data: ČNB a ČSÚ ----
    "ČNB tiskové zprávy": "https://www.cnb.cz/cs/.content/rss-feed/rss-feed_tz.rss",
    "ČSÚ rychlé informace": "https://csu.gov.cz/rss/produkty?kodVlastnostiVystupu=RI&jazyk=CS",
}

# Moje témata. Pořadí zde = pořadí rubrik na stránce.
# Obecné dění pokrývá sekce Aktuality — tady jsou jen odborná témata.
TEMATA = ["akcie", "AI", "ekonomika", "česká ekonomika"]

# Kolik zpráv smí mít každá rubrika (min–max podle nabídky dne)
MIN_NA_TEMA = 4
MAX_NA_TEMA = 7

# Co mě zajímá nejvíc — Claude to použije při hodnocení důležitosti
PRIORITY = (
    "Nejvíc mě zajímají akcie a AI, potom ekonomika (včetně české). "
    "Klíčová slova, která mají dostat vyšší důležitost: Fed, ČNB, sazby, "
    "inflace, NVIDIA, OpenAI, Anthropic. "
    "Sport, celebrity a bulvár mě nezajímají — dávej jim nízkou důležitost."
)

# Kolik nejnovějších zpráv maximálně vzít z každého zdroje
MAX_Z_KAZDEHO_ZDROJE = 8

# Výjimky: obecné zpravodajské zdroje dodávají víc materiálu,
# aby aktuality opravdu pokryly celé dění dne
MAX_VYJIMKY = {
    "BBC World": 15,
    "ČTK hlavní zprávy": 15,
    "ČTK domácí": 12,
    "Seznam Zprávy": 12,
    "The Guardian World": 10,
    "Al Jazeera": 10,
}

# Ignorovat zprávy starší než tolik hodin.
# Při generování 1–2× denně je 36 hodin rozumná rezerva —
# nic ti neuteče a stará čísla se nevrací.
MAX_STARI_HODIN = 36

# Který model Claude použít
MODEL = "claude-sonnet-5"

# Klíčová čísla — seznam se čte ze souboru tickery.txt (snadná úprava).
# Formát řádku: Název | symbol Yahoo | symbol stooq (nepovinný)
def _nacti_tickery():
    soubor = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                           "tickery.txt")
    ukazatele = []
    try:
        with open(soubor, encoding="utf-8") as f:
            for radek in f:
                radek = radek.strip()
                if not radek or radek.startswith("#"):
                    continue
                casti = [c.strip() for c in radek.split("|")]
                if len(casti) >= 2 and casti[0]:
                    ukazatele.append(
                        (casti[0], casti[1],
                         casti[2] if len(casti) > 2 else ""))
    except FileNotFoundError:
        pass
    return ukazatele

TRZNI_UKAZATELE = _nacti_tickery() or [
    ("S&P 500", "^GSPC", "^spx"),   # záloha, kdyby tickery.txt chyběl
]

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

    # ---- Světové: agentury přes Google News (Reuters/Bloomberg nemají
    #      veřejné RSS; tohle je oficiální cesta, jak jejich titulky odebírat) ----
    "Reuters": "https://news.google.com/rss/search?q=site:reuters.com%20when:1d&hl=en-US&gl=US&ceid=US:en",
    "Bloomberg": "https://news.google.com/rss/search?q=site:bloomberg.com%20when:1d&hl=en-US&gl=US&ceid=US:en",
    "Financial Times": "https://news.google.com/rss/search?q=site:ft.com%20when:1d&hl=en-US&gl=US&ceid=US:en",

    # ---- Světové: byznys a ekonomika ----
    "BBC Business": "https://feeds.bbci.co.uk/news/business/rss.xml",
    "WSJ Business": "https://feeds.content.dowjones.io/public/rss/WSJcomUSBusiness",
    "ECB": "https://www.ecb.europa.eu/rss/press.html",
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
    "Kurzy.cz": "https://rss.kurzy.cz/kurzy_zpravy.xml",
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

# Podcast FT News Briefing — samostatný blok pod aktualitami
FT_BRIEFING_FEED = "https://rss.acast.com/ftnewsbriefing"

# Ignorovat zprávy starší než tolik hodin.
# Při generování 1–2× denně je 36 hodin rozumná rezerva —
# nic ti neuteče a stará čísla se nevrací.
MAX_STARI_HODIN = 36

# Který model Claude použít
MODEL = "claude-sonnet-5"

# ============================================================
# PODCAST – audio verze briefingu (podcast.py)
# Když cokoli selže, podcast se přeskočí a web jede dál.
# ============================================================
PODCAST_ZAPNUTY = True

# Hlas:
#   "pocket"     – výchozí: Pocket TTS s českým modelem (natrénován na ~1000
#                  hodinách české řeči) mluví hlasem Kasandry. Open source,
#                  zdarma, běží přímo na GitHubu (~3 min). Když selže,
#                  automaticky naskočí Piper.
#   "piper"      – starší, robotičtější open-source hlas (taky zdarma)
#   "azure" / "elevenlabs" – placené; klíč do GitHub secrets
#                  (AZURE_SPEECH_KEY / ELEVENLABS_API_KEY)
PODCAST_HLAS_SLUZBA = "pocket"

# Pocket TTS: český model (připnutý na konkrétní verzi) a krátká nahrávka,
# jejíž barvu hlasu model napodobí (Kasandra, CC BY 4.0)
PODCAST_POCKET_MODEL = ("hf://vvolhejn/pocket-tts-czech/czech.yaml"
                        "@7c1fbd0acba765617749dd17f3dbddc2be791cc7")
PODCAST_POCKET_VZOR = "podcast-hlas-vzor.wav"

# Piper (záloha): hlas Kasandra a tempo řeči (menší číslo = rychleji)
PODCAST_PIPER_HLAS = "cs_CZ-kasandra-medium"
PODCAST_PIPER_RYCHLOST = 1.0

# Výslovnost cizích slov (open-source hlasy čtou všechno po česky).
# Vlevo začátek slova v textu, vpravo jak ho vyslovit – "Trump" tak
# pokryje i "Trumpa", "Trumpovi"… Klidně doplňuj.
PODCAST_VYSLOVNOST = {
    "briefing": "brífink",
    "Briefing": "Brífink",
    "Trump": "Tramp",
    "Microsoft": "Majkrosoft",
    "Googl": "Gúgl",
    "Appl": "Epl",
    "Nvidi": "Envidi",
    "NVIDI": "Envidi",
    "OpenAI": "Oupn ej áj",
    "Anthropic": "Entropik",
    "Bloomberg": "Blúmberk",
    "Reuters": "Rojtrs",
    "Wall Street": "Vól strít",
    "Financial Times": "Fajnenšl tajms",
    "Bank of England": "Benk of Ingland",
    "futures": "fjůčrs",
    "S&P 500": "es end pí pět set",
    "S&P": "es end pí",
    "Nasdaq": "Nezdek",
    "JP Morgan": "Džej Pí Morgn",
}

# Azure: český hlas a region, ve kterém sis službu Speech založil
PODCAST_AZURE_HLAS = "cs-CZ-AntoninNeural"    # ženský: cs-CZ-VlastaNeural
PODCAST_AZURE_REGION = "westeurope"
PODCAST_AZURE_RYCHLOST = "+0%"               # např. "+8%" = o něco rychleji

# ElevenLabs: ID hlasu z Voice Library (Voices → ⋯ → Copy voice ID)
PODCAST_ELEVENLABS_HLAS = ""
PODCAST_ELEVENLABS_MODEL = "eleven_multilingual_v2"

# Délka scénáře ve slovech (600–700 slov ≈ 5 minut poslechu)
PODCAST_DELKA_SLOV = (600, 700)

# Kolik posledních epizod nechat ve feedu a na webu
PODCAST_POCET_EPIZOD = 30

# Údaje pořadu pro Apple Podcasts / Spotify
PODCAST_NAZEV = "Denní briefing"
PODCAST_AUTOR = "Denní briefing"
PODCAST_POPIS = ""   # prázdné = výchozí popis
# E-mail vlastníka – Spotify na něj pošle ověřovací kód. Ve feedu je
# veřejně vidět, klidně použij samostatnou adresu.
PODCAST_EMAIL = ""
# Až bude podcast schválený, vlož sem odkazy – objeví se u přehrávače
PODCAST_ODKAZ_APPLE = ""
PODCAST_ODKAZ_SPOTIFY = ""

# ============================================================
# MĚŘENÍ NÁVŠTĚVNOSTI – GoatCounter (zdarma, bez cookies)
# Kód z adresy tvého účtu: https://KOD.goatcounter.com
# Prázdné = měření vypnuté.
# ============================================================
GOATCOUNTER_KOD = "dennibriefing"

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
                    vychozi = (casti[3].lower() != "ne") if len(casti) > 3 else True
                    ukazatele.append(
                        (casti[0], casti[1],
                         casti[2] if len(casti) > 2 else "", vychozi))
    except FileNotFoundError:
        pass
    return ukazatele

TRZNI_UKAZATELE = _nacti_tickery() or [
    ("S&P 500", "^GSPC", "^spx", True),   # záloha, kdyby tickery.txt chyběl
]

# ============================================================
# PODCAST – audio verze denního briefingu.
#
#   1. Claude napíše z dnešních aktualit ~5minutový mluvený text
#   2. Hlasová služba (Azure nebo ElevenLabs) z něj udělá MP3
#   3. Epizoda se uloží do složky podcast/ a přidá do podcast.xml
#      (RSS feed, který jde přidat do Apple Podcasts i Spotify)
#
# Nastavení je v config.py (sekce PODCAST). Klíče se čtou z .env
# nebo z GitHub secrets:  AZURE_SPEECH_KEY  /  ELEVENLABS_API_KEY
# Když klíč chybí, podcast se tiše přeskočí a web se vytvoří normálně.
#
# Vyzkoušení na vlastním počítači (ve složce projektu):
#   python3 podcast.py --ukazka       namluví jednu větu do ukazka.mp3
#   python3 podcast.py --jen-scenar   napíše a vypíše text (volá Clauda)
#   python3 podcast.py                celá epizoda z aktuálního data.json
# ============================================================

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime
from email.utils import format_datetime
from html import escape as _attr
from xml.sax.saxutils import escape as _xml

import config

try:
    from zoneinfo import ZoneInfo
    _PRAHA = ZoneInfo("Europe/Prague")
except Exception:
    _PRAHA = None


def _nastaveni(nazev, vychozi):
    """Hodnota z config.py, nebo výchozí (kdyby v config.py chyběla)."""
    return getattr(config, nazev, vychozi)


ZAPNUTO = _nastaveni("PODCAST_ZAPNUTY", True)
SLUZBA = _nastaveni("PODCAST_HLAS_SLUZBA", "azure").strip().lower()
AZURE_HLAS = _nastaveni("PODCAST_AZURE_HLAS", "cs-CZ-AntoninNeural")
AZURE_REGION = _nastaveni("PODCAST_AZURE_REGION", "westeurope")
AZURE_RYCHLOST = _nastaveni("PODCAST_AZURE_RYCHLOST", "+0%")
ELEVEN_HLAS = _nastaveni("PODCAST_ELEVENLABS_HLAS", "")
ELEVEN_MODEL = _nastaveni("PODCAST_ELEVENLABS_MODEL", "eleven_multilingual_v2")
DELKA_SLOV = _nastaveni("PODCAST_DELKA_SLOV", (650, 800))
POCET_EPIZOD = _nastaveni("PODCAST_POCET_EPIZOD", 30)
NAZEV = _nastaveni("PODCAST_NAZEV", "Denní briefing")
POPIS = _nastaveni("PODCAST_POPIS", "")
AUTOR = _nastaveni("PODCAST_AUTOR", "Denní briefing")
EMAIL = _nastaveni("PODCAST_EMAIL", "").strip()
ODKAZ_APPLE = _nastaveni("PODCAST_ODKAZ_APPLE", "").strip()
ODKAZ_SPOTIFY = _nastaveni("PODCAST_ODKAZ_SPOTIFY", "").strip()

WEB = "https://dennibriefing.cz/"
SLOZKA = "podcast"
SEZNAM = SLOZKA + "/epizody.json"
FEED = "podcast.xml"
OBAL = "podcast-obal.jpg"
_PLATNY_SOUBOR = re.compile(r"^podcast/\d{4}-\d{2}-\d{2}\.(mp3|txt)$")

# Formáty zvuku: (formát pro službu, datový tok v bitech/s pro výpočet délky)
_AZURE_FORMAT = ("audio-24khz-48kbitrate-mono-mp3", 48000)
_ELEVEN_FORMAT = ("mp3_44100_64", 64000)

DNY = ["pondělí", "úterý", "středa", "čtvrtek", "pátek", "sobota", "neděle"]
MESICE_2P = ["", "ledna", "února", "března", "dubna", "května", "června",
             "července", "srpna", "září", "října", "listopadu", "prosince"]
_RADOVE = ["", "prvního", "druhého", "třetího", "čtvrtého", "pátého",
           "šestého", "sedmého", "osmého", "devátého", "desátého",
           "jedenáctého", "dvanáctého", "třináctého", "čtrnáctého",
           "patnáctého", "šestnáctého", "sedmnáctého", "osmnáctého",
           "devatenáctého", "dvacátého"]


def _den_slovy(d):
    """date(2026, 11, 4) -> 'čtvrtého listopadu'."""
    if d.day <= 20:
        radova = _RADOVE[d.day]
    elif d.day < 30:
        radova = "dvacátého " + _RADOVE[d.day - 20]
    else:
        radova = "třicátého" + ("" if d.day == 30 else " prvního")
    return f"{radova} {MESICE_2P[d.month]}"


def _datum_vydani(data):
    """'4. 11. 2026 08:43' -> aware datetime (český čas)."""
    shoda = re.search(r"(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})(?:\s+(\d{1,2}):(\d{2}))?",
                      str(data.get("vygenerovano", "")))
    if shoda:
        d, m, r, h, mi = shoda.groups()
        cas = datetime(int(r), int(m), int(d), int(h or 8), int(mi or 0))
    else:
        cas = datetime.now()
    return cas.replace(tzinfo=_PRAHA) if _PRAHA else cas


# ------------------------------------------------------------
# Seznam epizod (podcast/epizody.json) a jeho obnova z webu
# ------------------------------------------------------------
def nacti_epizody():
    try:
        with open(SEZNAM, encoding="utf-8") as f:
            epizody = json.load(f)
        return [e for e in epizody if _PLATNY_SOUBOR.match(e.get("soubor", ""))]
    except (FileNotFoundError, json.JSONDecodeError, AttributeError):
        return []


def _uloz_epizody(epizody):
    os.makedirs(SLOZKA, exist_ok=True)
    with open(SEZNAM, "w", encoding="utf-8") as f:
        json.dump(epizody, f, ensure_ascii=False, indent=1)


def _stahni(url, timeout=60):
    pozadavek = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 dennibriefing.cz"})
    with urllib.request.urlopen(pozadavek, timeout=timeout) as odpoved:
        return odpoved.read()


def obnov_z_webu():
    """Když chybí místní seznam epizod (např. vypršela cache na GitHubu),
    stáhne dosavadní epizody zpět z živého webu – ať se archiv neztratí."""
    if os.path.exists(SEZNAM):
        return
    try:
        epizody = json.loads(_stahni(WEB + SEZNAM, timeout=20).decode("utf-8"))
    except Exception:
        return   # na webu zatím žádný podcast není – nic se neděje
    os.makedirs(SLOZKA, exist_ok=True)
    obnovene = []
    for ep in epizody:
        soubory = [ep.get("soubor", "")]
        if ep.get("prepis"):
            soubory.append(ep["prepis"])
        try:
            for s in soubory:
                if not _PLATNY_SOUBOR.match(s):
                    raise ValueError(f"neplatný název souboru {s!r}")
                if not os.path.exists(s):
                    with open(s, "wb") as f:
                        f.write(_stahni(WEB + s))
            obnovene.append(ep)
        except Exception as chyba:
            print(f"  Podcast: epizodu {ep.get('datum')} se nepodařilo obnovit ({chyba})")
    _uloz_epizody(obnovene)
    print(f"  Podcast: obnoveno {len(obnovene)} epizod z živého webu.")


# ------------------------------------------------------------
# Krok 1: scénář (Claude)
# ------------------------------------------------------------
def _podklady(data, dnes):
    aktuality = []
    for a in data.get("aktuality", []):
        oblast = "SVĚT" if a.get("oblast") == "svet" else "ČESKO"
        radek = (f"- [{oblast}, důležitost {a.get('dulezitost', 3)}] "
                 f"{a['titulek']} – {a['shrnuti']}")
        if a.get("kauza_shrnuti"):
            radek += f" (Kontext pokračující kauzy: {a['kauza_shrnuti']})"
        aktuality.append(radek)

    karty = sorted((z for z in data.get("zpravy", [])
                    if z.get("dulezitost", 0) >= 4),
                   key=lambda z: z.get("dulezitost", 0), reverse=True)[:8]
    zpravy = [f"- [{z['tema']}] {z['titulek']} – {z['shrnuti']}" for z in karty]

    # Co sledovat: jen dnešní a budoucí termíny, seřazené od nejbližšího
    terminy = []
    for s in data.get("sledovat", []):
        try:
            d = date.fromisoformat(s.get("datum", ""))
        except ValueError:
            terminy.append((date.max, s.get("datum", ""), s.get("nazev", "")))
            continue
        if d >= dnes:
            terminy.append((d, f"{DNY[d.weekday()]} {d.day}. {d.month}.",
                            s.get("nazev", "")))
    terminy.sort(key=lambda t: t[0])
    sledovat = [f"- {kdy}: {co}" for _, kdy, co in terminy if co][:4]

    return ("AKTUALITY (seřazené od nejdůležitější):\n" + "\n".join(aktuality)
            + "\n\nZPRÁVY Z RUBRIK (trhy, AI, ekonomika):\n"
            + ("\n".join(zpravy) or "(nic)")
            + "\n\nCO SLEDOVAT:\n" + ("\n".join(sledovat) or "(nic)"))


def _prompt_scenare(data, vydano):
    dnes = vydano.date()
    od, do = DELKA_SLOV
    den = DNY[dnes.weekday()]
    return f"""Jsi moderátor ranního zpravodajského podcastu „Denní briefing".
Z podkladů níže napiš text, který namluví syntetický hlas (text to speech).
Posluchač poslouchá cestou do práce. Po pěti minutách musí vědět, co
podstatného se stalo ve světě a v Česku.

Dnes je {den} {dnes.day}. {dnes.month}. {dnes.year} – vyslov „{den} {_den_slovy(dnes)}".

STAVBA:
1. Úvod (1–2 věty): pozdrav, den a datum, „tohle je Denní briefing".
   Hned potom jednou větou to nejdůležitější z dneška.
2. Svět: 3–5 nejdůležitějších událostí, od nejzávažnější.
3. Česko: 3–4 nejdůležitější události.
4. Trhy, ekonomika a umělá inteligence: 2–3 krátké zprávy z oddílu ZPRÁVY
   Z RUBRIK – jen to podstatné, co ještě nezaznělo.
5. Co nás čeká: 1–3 nejbližší termíny z oddílu CO SLEDOVAT (pokud nějaké jsou).
6. Krátké rozloučení: celý briefing s odkazy na zdroje je na webu
   „denní briefing tečka cé zet".

DÉLKA: {od}–{do} slov celkem (zhruba pět minut poslechu). Raději vynech
méně důležitou zprávu, než abys všechny odbyl jednou větou.

PSANÍ PRO UCHO:
- Spisovná mluvená čeština jako ve zprávách veřejnoprávního rozhlasu.
  Krátké věty, jedna myšlenka na větu, žádné dlouhé vedlejší věty.
- Mezi zprávami plynulé přechody („V Česku…", „Ze světa ještě…"),
  ale žádné vatové fráze.
- Každá zpráva je jeden odstavec. Odstavce odděl prázdným řádkem.
- Žádné nadpisy, odrážky, závorky, uvozovky, lomítka, emoji ani formátování.
- Čísla piš tak, jak se mají přečíst: procenta a desetinná čísla slovy
  („o tři desetiny procenta", „dvě celé pět procenta"); velká čísla
  zaokrouhli a napiš slovy („přes sedm a půl tisíce bodů", „sedm miliard
  dolarů"). Žádné znaky %, $, €, Kč – vždy slovy. Letopočty mohou zůstat
  číslicemi.
- Data slovy („ve čtvrtek pátého listopadu").
- Zkratky rozepiš: Česká národní banka, Evropská centrální banka, Český
  statistický úřad, Spojené státy… Zkratky, které se čtou jako slovo (NATO,
  Fed), můžeš nechat.
- Cizí jména a názvy firem ponech v původní podobě.

FAKTICKÁ KÁZEŇ: Používej VÝHRADNĚ informace z podkladů. Nic nedomýšlej –
žádná čísla, jména ani souvislosti navíc. Když si nejsi jistý, zprávu vynech.

FORMÁT ODPOVĚDI (přesně takto, nic dalšího):
TITULEK: název epizody, max 8 slov, vystihuje hlavní téma dne
TÉMATA: heslo 1 | heslo 2 | heslo 3 | … (5–10 krátkých hesel o obsahu epizody)
---
samotný text k namluvení

PODKLADY
{_podklady(data, dnes)}"""


def _rozparsuj_scenar(text):
    casti = re.split(r"^\s*-{3,}\s*$", text, maxsplit=1, flags=re.M)
    hlava, telo = (casti[0], casti[1]) if len(casti) == 2 else ("", text)
    titulek, temata = "", []
    for radek in hlava.splitlines():
        klic, _, hodnota = radek.partition(":")
        klic = klic.strip().upper()
        if klic == "TITULEK":
            titulek = hodnota.strip().strip('"„“')
        elif klic in ("TÉMATA", "TEMATA"):
            temata = [t.strip() for t in hodnota.split("|") if t.strip()]
    # Pojistka: pryč s nadpisy, kdyby je model přesto napsal
    telo = "\n".join(r for r in telo.splitlines()
                     if not r.strip().startswith("#"))
    odstavce = []
    for o in re.split(r"\n\s*\n", telo):
        o = re.sub(r"[*#_`]", "", o)              # zbytky formátování
        o = re.sub(r"\s+", " ", o).strip()
        if o:
            odstavce.append(o)
    return {"titulek": titulek, "temata": temata, "odstavce": odstavce}


def napis_scenar(data, vydano):
    import anthropic
    from preloz_zpravy import _surove_volani, _SPOTREBA

    pred = dict(_SPOTREBA)
    client = anthropic.Anthropic()
    text = _surove_volani(client, _prompt_scenare(data, vydano), 16000)
    scenar = _rozparsuj_scenar(text)
    slov = sum(len(o.split()) for o in scenar["odstavce"])
    if slov < 200:
        raise RuntimeError(f"scénář je podezřele krátký ({slov} slov)")
    vstup = _SPOTREBA["vstup"] - pred["vstup"]
    vystup = _SPOTREBA["vystup"] - pred["vystup"]
    print(f"  Scénář: {slov} slov, {len(scenar['odstavce'])} odstavců "
          f"(≈ ${vstup / 1e6 * 3 + vystup / 1e6 * 15:.2f})")
    return scenar


# ------------------------------------------------------------
# Krok 2: namluvení (Azure nebo ElevenLabs)
# ------------------------------------------------------------
def _klic():
    if SLUZBA == "elevenlabs":
        return os.environ.get("ELEVENLABS_API_KEY", "").strip()
    return os.environ.get("AZURE_SPEECH_KEY", "").strip()


def _useky(odstavce, max_znaku=2500):
    """Rozdělí odstavce do bloků, které služba zpracuje najednou."""
    useky, aktualni = [], []
    for o in odstavce:
        if aktualni and sum(len(x) for x in aktualni) + len(o) > max_znaku:
            useky.append(aktualni)
            aktualni = []
        aktualni.append(o)
    if aktualni:
        useky.append(aktualni)
    return useky


def _posli(pozadavek, popis, pokusu=3):
    """Odešle požadavek; při přetížení služby to zkusí znovu."""
    for pokus in range(1, pokusu + 1):
        try:
            with urllib.request.urlopen(pozadavek, timeout=120) as odpoved:
                return odpoved.read()
        except urllib.error.HTTPError as chyba:
            telo = chyba.read().decode("utf-8", errors="replace")[:300]
            if chyba.code in (429, 500, 502, 503, 504) and pokus < pokusu:
                print(f"  {popis}: služba vrátila {chyba.code}, zkouším znovu…")
                time.sleep(8 * pokus)
                continue
            raise RuntimeError(f"{popis}: HTTP {chyba.code} {telo}") from None
        except urllib.error.URLError as chyba:
            if pokus < pokusu:
                time.sleep(8 * pokus)
                continue
            raise RuntimeError(f"{popis}: {chyba}") from None


def _ssml(odstavce, posledni):
    pauza = '<break time="700ms"/>'
    vnitrek = pauza.join(_xml(o) for o in odstavce) + ("" if posledni else pauza)
    return ("<speak version='1.0' xml:lang='cs-CZ'>"
            f"<voice xml:lang='cs-CZ' name='{_xml(AZURE_HLAS)}'>"
            f"<prosody rate='{_xml(AZURE_RYCHLOST)}'>{vnitrek}</prosody>"
            "</voice></speak>")


def _namluv_azure(odstavce, klic):
    region = (os.environ.get("AZURE_SPEECH_REGION") or AZURE_REGION).strip()
    token = _posli(urllib.request.Request(
        f"https://{region}.api.cognitive.microsoft.com/sts/v1.0/issueToken",
        data=b"", method="POST",
        headers={"Ocp-Apim-Subscription-Key": klic}), "Azure (přihlášení)").decode()
    useky = _useky(odstavce)
    zvuk = b""
    for i, usek in enumerate(useky):
        zvuk += _posli(urllib.request.Request(
            f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1",
            data=_ssml(usek, i == len(useky) - 1).encode("utf-8"), method="POST",
            headers={"Authorization": "Bearer " + token,
                     "Content-Type": "application/ssml+xml",
                     "X-Microsoft-OutputFormat": _AZURE_FORMAT[0],
                     "User-Agent": "dennibriefing.cz"}),
            f"Azure (část {i + 1}/{len(useky)})")
    return zvuk, _AZURE_FORMAT[1]


def _namluv_elevenlabs(odstavce, klic):
    if not ELEVEN_HLAS:
        raise RuntimeError("v config.py chybí PODCAST_ELEVENLABS_HLAS (voice_id)")
    texty = ["\n\n".join(u) for u in _useky(odstavce)]
    zvuk = b""
    for i, text in enumerate(texty):
        telo = {"text": text, "model_id": ELEVEN_MODEL}
        if i > 0:
            telo["previous_text"] = texty[i - 1][-1000:]
        if i < len(texty) - 1:
            telo["next_text"] = texty[i + 1][:1000]
        zvuk += _posli(urllib.request.Request(
            f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVEN_HLAS}"
            f"?output_format={_ELEVEN_FORMAT[0]}",
            data=json.dumps(telo).encode("utf-8"), method="POST",
            headers={"xi-api-key": klic, "Content-Type": "application/json",
                     "Accept": "audio/mpeg"}),
            f"ElevenLabs (část {i + 1}/{len(texty)})")
    return zvuk, _ELEVEN_FORMAT[1]


def namluv(odstavce):
    """Vrátí (MP3 bajty, datový tok). Služba podle config.py."""
    klic = _klic()
    if SLUZBA == "elevenlabs":
        return _namluv_elevenlabs(odstavce, klic)
    return _namluv_azure(odstavce, klic)


# ------------------------------------------------------------
# Celá epizoda
# ------------------------------------------------------------
def vytvor_epizodu(soubor_dat="data.json"):
    """Z data.json vyrobí dnešní epizodu. Vrací True/False (nikdy nespadne
    tak, aby shodila web – chyby jen vypíše)."""
    if not ZAPNUTO:
        print("Podcast: vypnutý v config.py.")
        return False
    if not _klic():
        jmeno = "ELEVENLABS_API_KEY" if SLUZBA == "elevenlabs" else "AZURE_SPEECH_KEY"
        print(f"Podcast: chybí klíč {jmeno} – přeskakuji (web se vytvoří normálně).")
        return False
    try:
        obnov_z_webu()
        with open(soubor_dat, encoding="utf-8") as f:
            data = json.load(f)
        if not data.get("aktuality"):
            print("Podcast: dnes nejsou aktuality – epizoda se nevytvoří.")
            return False
        vydano = _datum_vydani(data)
        iso = vydano.strftime("%Y-%m-%d")

        print("Podcast 1/2: píšu scénář…", flush=True)
        scenar = napis_scenar(data, vydano)
        znaku = sum(len(o) for o in scenar["odstavce"])
        hlas = ELEVEN_HLAS if SLUZBA == "elevenlabs" else AZURE_HLAS
        print(f"Podcast 2/2: namlouvám ({SLUZBA}, {hlas}, {znaku} znaků)…", flush=True)
        zvuk, tok = namluv(scenar["odstavce"])
        if len(zvuk) < 50_000:
            raise RuntimeError(f"zvuk je podezřele malý ({len(zvuk)} B)")

        os.makedirs(SLOZKA, exist_ok=True)
        mp3, prepis = f"{SLOZKA}/{iso}.mp3", f"{SLOZKA}/{iso}.txt"
        with open(mp3, "wb") as f:
            f.write(zvuk)
        with open(prepis, "w", encoding="utf-8") as f:
            f.write("\n\n".join(scenar["odstavce"]) + "\n")

        titulek = scenar["titulek"] or data["aktuality"][0]["titulek"]
        epizoda = {
            "datum": iso,
            "vydano": vydano.isoformat(),
            "titulek": titulek,
            "temata": scenar["temata"],
            "soubor": mp3,
            "prepis": prepis,
            "velikost": len(zvuk),
            "delka_s": round(len(zvuk) * 8 / tok),
        }
        epizody = [e for e in nacti_epizody() if e.get("datum") != iso]
        epizody.append(epizoda)
        epizody.sort(key=lambda e: e["datum"])
        for stara in epizody[:-POCET_EPIZOD]:
            for s in (stara.get("soubor"), stara.get("prepis")):
                if s and _PLATNY_SOUBOR.match(s) and os.path.exists(s):
                    os.remove(s)
        _uloz_epizody(epizody[-POCET_EPIZOD:])
        minuty, sekundy = divmod(epizoda["delka_s"], 60)
        print(f"  Epizoda hotová: {mp3} ({minuty}:{sekundy:02d}, "
              f"{len(zvuk) / 1e6:.1f} MB) – „{titulek}\"")
        return True
    except (Exception, SystemExit) as chyba:
        print(f"  !! Podcast se nepovedl: {chyba}")
        print("  Web se vytvoří normálně, jen dnes bez nové epizody.")
        return False


# ------------------------------------------------------------
# RSS feed podcastu (podcast.xml) – pro Apple Podcasts, Spotify atd.
# ------------------------------------------------------------
def _popis_epizody(ep):
    temata = " · ".join(ep.get("temata", []))
    radky = []
    if temata:
        radky.append(f"V dnešním vydání: {temata}.")
    radky.append(f"Celý briefing s odkazy na zdroje najdete na {WEB}")
    radky.append("Text připravuje umělá inteligence ze zpravodajských "
                 "zdrojů, čte ho syntetický hlas.")
    return "\n\n".join(radky)


def _nazev_epizody(ep):
    d = date.fromisoformat(ep["datum"])
    return f"{DNY[d.weekday()].capitalize()} {d.day}. {d.month}.: {ep['titulek']}"


def uloz_feed():
    """Z podcast/epizody.json vytvoří podcast.xml. Vrací počet epizod."""
    obnov_z_webu()
    epizody = nacti_epizody()
    if not epizody:
        return 0
    popis_poradu = POPIS or (
        "Vše podstatné ze světa i Česka za pět minut. Každé pracovní ráno "
        "nejdůležitější zprávy, dění na trzích a v umělé inteligenci. Text "
        "připravuje umělá inteligence, čte ho syntetický hlas.")
    ted = datetime.now(_PRAHA) if _PRAHA else datetime.now()
    vlastnik = ""
    if EMAIL:
        vlastnik = (f"\n  <itunes:owner><itunes:name>{_xml(AUTOR)}</itunes:name>"
                    f"<itunes:email>{_xml(EMAIL)}</itunes:email></itunes:owner>")
    polozky = []
    for ep in reversed(epizody):
        vydano = datetime.fromisoformat(ep["vydano"])
        prepis = ""
        if ep.get("prepis"):
            prepis = (f'\n    <podcast:transcript url="{WEB}{ep["prepis"]}" '
                      'type="text/plain" language="cs"/>')
        polozky.append(f"""  <item>
    <title>{_xml(_nazev_epizody(ep))}</title>
    <description>{_xml(_popis_epizody(ep))}</description>
    <link>{WEB}</link>
    <guid isPermaLink="false">dennibriefing-{ep['datum']}</guid>
    <pubDate>{format_datetime(vydano)}</pubDate>
    <enclosure url="{WEB}{ep['soubor']}" length="{ep['velikost']}" type="audio/mpeg"/>
    <itunes:duration>{ep['delka_s']}</itunes:duration>
    <itunes:episodeType>full</itunes:episodeType>
    <itunes:explicit>false</itunes:explicit>{prepis}
  </item>""")
    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:podcast="https://podcastindex.org/namespace/1.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
  <title>{_xml(NAZEV)}</title>
  <link>{WEB}</link>
  <atom:link href="{WEB}{FEED}" rel="self" type="application/rss+xml"/>
  <language>cs</language>
  <description>{_xml(popis_poradu)}</description>
  <itunes:author>{_xml(AUTOR)}</itunes:author>{vlastnik}
  <itunes:image href="{WEB}{OBAL}"/>
  <image><url>{WEB}{OBAL}</url><title>{_xml(NAZEV)}</title><link>{WEB}</link></image>
  <itunes:category text="News"><itunes:category text="Daily News"/></itunes:category>
  <itunes:explicit>false</itunes:explicit>
  <itunes:type>episodic</itunes:type>
  <lastBuildDate>{format_datetime(ted)}</lastBuildDate>
{chr(10).join(polozky)}
</channel>
</rss>
"""
    with open(FEED, "w", encoding="utf-8") as f:
        f.write(feed)
    return len(epizody)


# ------------------------------------------------------------
# Přehrávač na webu (HTML; styl a ovládání jsou v generuj_web.py)
# ------------------------------------------------------------
def html_prehravace(data, zaklad=""):
    """Přehrávač epizody, která patří k tomuto vydání (jinak prázdný text)."""
    iso = _datum_vydani(data).strftime("%Y-%m-%d")
    ep = next((e for e in nacti_epizody() if e.get("datum") == iso), None)
    if not ep or not os.path.exists(ep["soubor"]):
        return ""
    minut = max(1, round(ep["delka_s"] / 60))
    odkazy = []
    if ODKAZ_APPLE:
        odkazy.append(f'<a href="{_attr(ODKAZ_APPLE)}" target="_blank" rel="noopener">Apple Podcasts</a>')
    if ODKAZ_SPOTIFY:
        odkazy.append(f'<a href="{_attr(ODKAZ_SPOTIFY)}" target="_blank" rel="noopener">Spotify</a>')
    odkazy.append(f'<a href="{zaklad}{FEED}" target="_blank" rel="noopener">RSS</a>')
    return f"""
  <section class="podcast" data-epizoda="{iso}" data-delka="{ep['delka_s']}" data-titulek="{_attr(_nazev_epizody(ep))}" data-obal="{zaklad}{OBAL}">
    <button class="pod-play" aria-label="Přehrát / Play">
      <svg class="ikona-play" viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5.5v13l11-6.5z"/></svg>
      <svg class="ikona-pauza" viewBox="0 0 24 24" aria-hidden="true"><path d="M7 5h4v14H7zM13 5h4v14h-4z"/></svg>
    </button>
    <div class="pod-telo">
      <div class="pod-titul"><span class="l-cs">Poslechni si dnešní briefing</span><span class="l-en">Listen to today's briefing (in Czech)</span><span class="pod-delka">{minut} min</span></div>
      <div class="pod-lista" role="slider" aria-label="Posun v epizodě / Seek"><div class="pod-postup"></div></div>
      <div class="pod-spodek">
        <span class="pod-cas">0:00 / {ep['delka_s'] // 60}:{ep['delka_s'] % 60:02d}</span>
        <button class="pod-rychlost" title="Rychlost přehrávání / Playback speed">1×</button>
        <span class="pod-odber"><span class="l-cs">Odebírat:</span><span class="l-en">Subscribe:</span> {" · ".join(odkazy)}</span>
      </div>
    </div>
    <audio preload="none" src="{zaklad}{ep['soubor']}"></audio>
  </section>"""


# ------------------------------------------------------------
# Spuštění napřímo – na vyzkoušení
# ------------------------------------------------------------
if __name__ == "__main__":
    if "--ukazka" in sys.argv:
        if not _klic():
            sys.exit("Chybí klíč hlasové služby (AZURE_SPEECH_KEY nebo "
                     "ELEVENLABS_API_KEY v souboru .env).")
        zvuk, _ = namluv([
            "Dobré ráno, tohle je ukázka hlasu pro podcast Denní briefing.",
            "Takhle bude znít každé ranní vydání: zprávy ze světa, z Česka "
            "a z trhů za pět minut."])
        with open("ukazka.mp3", "wb") as f:
            f.write(zvuk)
        print(f"Uloženo ukazka.mp3 ({len(zvuk) / 1000:.0f} kB) – pusť si ho.")
    elif "--jen-scenar" in sys.argv:
        with open("data.json", encoding="utf-8") as f:
            data = json.load(f)
        s = napis_scenar(data, _datum_vydani(data))
        print(f"\nTITULEK: {s['titulek']}\nTÉMATA: {' | '.join(s['temata'])}\n")
        print("\n\n".join(s["odstavce"]))
    else:
        if vytvor_epizodu():
            print(f"Feed: {uloz_feed()} epizod v {FEED}")

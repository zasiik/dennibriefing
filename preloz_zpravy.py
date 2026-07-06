# ============================================================
# Krok 2: Výběr, překlad a shrnutí zpráv přes Claude API.
#
# Dvě samostatná (menší) volání Clauda — spolehlivější než jedno velké:
#   1. "zpravy"    — výběr ~25 zpráv pro karty (CZ + EN verze)
#   2. "aktuality" — hlavní události 24 hodin potvrzené více zdroji,
#                    rozdělené na svět / ČR, řazené podle dopadu
#
# API klíč se čte z proměnné prostředí ANTHROPIC_API_KEY.
# ============================================================

import json
import os
import sys
from datetime import datetime, timedelta

import anthropic

from config import TEMATA, PRIORITY, MIN_NA_TEMA, MAX_NA_TEMA, MODEL
from stahni_zpravy import stahni_vsechny_zpravy

MAX_TOKENS = 64000  # maximum modelu; s rozdělenými voláními velká rezerva

# Překladová cache: co už Claude jednou přeložil, se znovu neposílá
CACHE_SOUBOR = "preklady_cache.json"
CACHE_DNU = 4  # jak dlouho držet staré překlady


def _nacti_cache():
    try:
        with open(CACHE_SOUBOR, encoding="utf-8") as f:
            cache = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    # Vyhodit záznamy starší než CACHE_DNU
    hranice = (datetime.now() - timedelta(days=CACHE_DNU)).strftime("%Y-%m-%d")
    return {odkaz: karta for odkaz, karta in cache.items()
            if karta.get("ulozeno", "") >= hranice}


def _uloz_cache(cache):
    with open(CACHE_SOUBOR, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)

ZASADY_JAZYKA = """DŮLEŽITÉ ZÁSADY:
- Kvalita jazyka je priorita číslo 1. Piš jako novinář — česky bez anglicismů
  a kostrbatých doslovných překladů, anglicky idiomaticky. České zprávy
  v češtině jen uhlaď, nepřekládej; do angličtiny je přelož."""


def _vytahni_text(odpoved):
    """Z odpovědi vezme jen textové bloky a odstraní případné ```json obaly."""
    text = "".join(
        blok.text for blok in odpoved.content if blok.type == "text"
    ).strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    return text


def _surove_volani(client, prompt):
    with client.messages.stream(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        odpoved = stream.get_final_message()
    if odpoved.stop_reason == "max_tokens":
        sys.exit(
            "CHYBA: Odpověď Clauda se nevešla do limitu délky (to by se\n"
            "u rozdělených volání nemělo stávat). Sniž v config.py\n"
            "MAX_NA_TEMA nebo MAX_Z_KAZDEHO_ZDROJE."
        )
    return _vytahni_text(odpoved)


def _zavolej_clauda(client, prompt):
    """Volání Clauda s automatickou opravou/opakováním při vadném JSON.

    1. pokus: normální volání
    2. při vadném JSON: pošle se modelu zpět k syntaktické opravě
    3. kdyby ani to nevyšlo: celé volání se jednou zopakuje
    """
    posledni_chyba = None
    for pokus in (1, 2):
        text = _surove_volani(client, prompt)
        try:
            return json.loads(text)
        except json.JSONDecodeError as chyba:
            posledni_chyba = chyba
            print(f"  ...JSON má chybu ({chyba}), nechávám ho opravit.")
            oprava = _surove_volani(
                client,
                "Následující JSON je syntakticky vadný (chyba: "
                f"{chyba}). Vrať PŘESNĚ tentýž obsah s opravenou syntaxí — "
                "zejména escapuj uvozovky uvnitř textů. Odpověz POUZE "
                f"platným JSON, žádný jiný text.\n\n{text}",
            )
            try:
                return json.loads(oprava)
            except json.JSONDecodeError as chyba2:
                posledni_chyba = chyba2
                if pokus == 1:
                    print("  ...oprava nepomohla, generuji celé znovu.")
    sys.exit(f"CHYBA: Ani po opakování se nepodařilo získat platný JSON "
             f"({posledni_chyba}).")


def vyber_a_preloz(zpravy):
    """Vrátí {"zpravy": [...], "aktuality": [...]}."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit(
            "CHYBA: Není nastavený API klíč.\n"
            "V Terminálu spusť:  export ANTHROPIC_API_KEY='tvůj-klíč'\n"
            "a pak skript spusť znovu."
        )

    client = anthropic.Anthropic()

    seznam = "\n".join(
        f"[{i}] ({z['zdroj']}, {z['datum'] or 'bez data'}) {z['titulek']}\n    {z['popis']}"
        for i, z in enumerate(zpravy)
    )
    ted = datetime.now().strftime("%Y-%m-%d %H:%M")
    hlavicka = (
        f"Jsi redaktor osobního zpravodajského přehledu pro českého čtenáře.\n"
        f"Aktuální čas: {ted}\n\n"
        f"ČTENÁŘOVA TÉMATA: {', '.join(TEMATA)}\n"
        f"PRIORITY ČTENÁŘE: {PRIORITY}\n\n"
        f"Níže je seznam zpráv z různých zdrojů."
    )

    # ---------- Volání 1: karty podle témat (jen nepřeložené zprávy) ----------
    cache = _nacti_cache()
    nove = [z for z in zpravy if z["odkaz"] not in cache]
    z_cache = len(zpravy) - len(nove)
    if z_cache:
        print(f"Z překladové cache: {z_cache} zpráv (neposílají se znovu).")

    seznam_novych = "\n".join(
        f"[{i}] ({z['zdroj']}, {z['datum'] or 'bez data'}) {z['titulek']}\n    {z['popis']}"
        for i, z in enumerate(nove)
    )

    prompt_karty = f"""{hlavicka}

Vyber zprávy do tematických rubrik: pro KAŽDÉ z témat ({", ".join(TEMATA)})
vyber {MIN_NA_TEMA} až {MAX_NA_TEMA} zpráv — podle toho, kolik kvalitních
ten den je. Rubriky mají být vyvážené; žádná nesmí zůstat prázdná, pokud
k ní v seznamu nějaká rozumná zpráva existuje.
Pro každou vybranou zprávu vytvoř objekt:
   - "id": číslo zprávy ze seznamu (celé číslo)
   - "titulek": český titulek — přirozený, novinářský, ne doslovný překlad
   - "shrnuti": shrnutí ve 2–3 větách přirozenou češtinou
   - "titulek_en": tentýž titulek přirozenou angličtinou
   - "shrnuti_en": totéž shrnutí přirozenou angličtinou
   - "tema": právě jedno z témat: {", ".join(TEMATA)}
   - "dulezitost": celé číslo 1–5 (5 = nejdůležitější)

{ZASADY_JAZYKA}
- FAKTICKÁ KÁZEŇ: Piš výhradně to, co plyne z titulku a popisu zprávy.
  Nic nedomýšlej — žádné entity, produkty ani souvislosti navíc. Když je
  popis chudý, drž se titulku a napiš méně, ale pravdivě.
- TEST VÝBĚRU: Změní tato informace manažerovi rozhodování nebo obraz
  o trzích, AI či ekonomice? Pokud ne, nevybírej. Raději méně zpráv
  než balast.
- VYŘAĎ: rozhovory a osobní názory bez konkrétního dopadu ("investor si
  myslí", "šéf firmy doporučuje"), osobní příběhy, lifestyle, souhrnné
  přehledy míchající více nesouvisejících témat (roundupy), PR texty.
- Pokud dvě či více zpráv popisují tutéž událost, nejlepší z nich dej
  normální důležitost a ostatním důležitost 1, ať se přehled neopakuje.
- Sportu, celebritám a bulváru dávej důležitost 1, pokud vůbec vybereš.

Odpověz POUZE platným JSON polem objektů, bez jakéhokoli dalšího textu.
Pozor na validitu JSON: uvozovky uvnitř textů escapuj jako \\" a nepoužívej
nezakončené řetězce.

SEZNAM ZPRÁV:
{seznam_novych}"""

    if nove:
        print(f"Volání 1/4: výběr a překlad {len(nove)} nových zpráv ({MODEL})...")
        surove_karty = _zavolej_clauda(client, prompt_karty)
        dnes = datetime.now().strftime("%Y-%m-%d")
        for v in surove_karty:
            original = nove[v["id"]]
            cache[original["odkaz"]] = {
                "titulek": v["titulek"],
                "shrnuti": v["shrnuti"],
                "titulek_en": v.get("titulek_en", v["titulek"]),
                "shrnuti_en": v.get("shrnuti_en", v["shrnuti"]),
                "tema": v["tema"],
                "dulezitost": v["dulezitost"],
                "zdroj": original["zdroj"],
                "odkaz": original["odkaz"],
                "datum": original["datum"],
                "ulozeno": dnes,
            }
        _uloz_cache(cache)
    else:
        print("Volání 1/4: přeskočeno — všechny zprávy už jsou přeložené v cache.")

    # Karty = přeložené verze aktuálně stažených zpráv,
    # seskupené do rubrik podle TEMATA, max MAX_NA_TEMA na rubriku
    podle_temat = {}
    for z in zpravy:
        if z["odkaz"] in cache:
            karta = {k: v for k, v in cache[z["odkaz"]].items() if k != "ulozeno"}
            podle_temat.setdefault(karta["tema"], []).append(karta)
    vysledek = []
    for tema in list(TEMATA) + [t for t in podle_temat if t not in TEMATA]:
        rubrika = podle_temat.get(tema, [])
        rubrika.sort(key=lambda z: (z["dulezitost"], z["datum"]), reverse=True)
        vysledek.extend(rubrika[:MAX_NA_TEMA])

    # ---------- Volání 2: aktuality za 24 hodin ----------
    prompt_aktuality = f"""{hlavicka}

TVOJE ROLE: Jsi šéfredaktor, který sestavuje JEDINÝ denní briefing pro
vytíženého manažera. Tento briefing je jeho jediný zdroj informací o dění —
po přečtení musí být zorientovaný stejně dobře jako člověk, který celý den
sleduje zpravodajství. Cokoli zásadního vynecháš, manažer se nedozví vůbec.

POSTUP (dodrž přesně):

KROK 1 — Projdi celý seznam a seskup zprávy do UDÁLOSTÍ. Dílčí zprávy
o téže věci (např. útok + reakce politiků + dopad na trhy) sluč do jedné
události a shrň dohromady. Každá událost se v briefingu objeví jen jednou.

KROK 2 — Zkontroluj pokrytí oblastí. Kompletní briefing musí pokrýt vše
z tohoto, co se za posledních 24 hodin skutečně stalo:
  SVĚT: geopolitika a konflikty · politika velmocí (USA, Čína, Rusko) ·
  Evropa a EU · centrální banky a makroekonomika · výrazné pohyby trhů
  (akcie, měny, komodity, krypto) · technologie a AI · energetika ·
  velké katastrofy či společenské události s širokým dopadem
  ČESKO: vláda a politika · ekonomika, ČNB, rozpočet · velké firmy
  a byznys · legislativa s dopadem na lidi a firmy · zásadní společenské
  události
Pokud v některé oblasti nic podstatného není, nevymýšlej — ale žádnou
skutečnou událost z těchto oblastí nesmíš vynechat kvůli méně důležité.

KROK 3 — Vyber PŘESNĚ 12 světových a PŘESNĚ 12 českých událostí (méně jen
tehdy, když jich v seznamu tolik reálně není). Pravidla výběru:
  - Test titulků: vybral bys to jako hlavní zprávy televizního dne?
  - Maximálně 2–3 události k jednomu makrotématu (např. jedna válka nesmí
    zabrat půl briefingu) — raději slučuj do větších celků.
  - Přednost událostem potvrzeným více redakcemi; doplň jednozdrojovými,
    jen pokud jsou opravdu důležité.
  - Vyřaď: sport, celebrity, kuriozity, PR a komerční sdělení, názorové
    sloupky, spekulace bez faktů.

KROK 4 — Napiš shrnutí. Každé shrnutí (2–3 věty) musí zvládnout tři věci:
  CO se stalo (konkrétně: čísla, jména, místa) · PROČ na tom záleží
  (dopad na svět/ČR/trhy/čtenáře) · CO BUDE DÁL, pokud je to známo
  (další jednání, termín, očekávaná reakce). U pokračující kauzy připomeň
  půlvětou kontext. Žádná vata typu "situace se vyvíjí" — jen fakta.
  FAKTICKÁ KÁZEŇ: používej výhradně informace ze zpráv v seznamu —
  nikdy nedomýšlej detaily, jména ani souvislosti, které tam nejsou.

DŮLEŽITOST (pole "dulezitost"):
  5 = mění situaci globálně nebo zásadně pro ČR (válka/mír, rozhodnutí
      centrálních bank, pád vlády, krach velké firmy)
  4 = hlavní zpráva dne ve své oblasti, výrazný dopad
  3 = důležitý vývoj, který se manažerovi hodí vědět
  2–1 = doplňkové (používej výjimečně, briefing má být samá váha)
Řaď od nejdůležitější.

Pro každou událost objekt:
   - "titulek": český titulek — věcný, informativní, novinářský
   - "shrnuti": 2–3 věty podle KROKU 4, syntetizuj ze VŠECH zdrojů události
   - "titulek_en", "shrnuti_en": totéž přirozenou angličtinou
   - "oblast": "svet" nebo "cr" (české domácí dění = "cr")
   - "dulezitost": celé číslo 1–5 podle stupnice výše
   - "zdroje": pole čísel [id, id, ...] všech zpráv ze seznamu, které
     o události informují (ideálně 2+ různé redakce, minimálně 1)

{ZASADY_JAZYKA}

Odpověz POUZE platným JSON polem objektů, bez jakéhokoli dalšího textu.
Pozor na validitu JSON: uvozovky uvnitř textů escapuj jako \\" a nepoužívej
nezakončené řetězce.

SEZNAM ZPRÁV:
{seznam}"""

    print(f"Volání 2/4: aktuality za 24 hodin ({MODEL})...")
    surove_aktuality = _zavolej_clauda(client, prompt_aktuality)

    aktuality = []
    for a in surove_aktuality:
        zdroje, videne = [], set()
        for cislo in a.get("zdroje", []):
            if isinstance(cislo, int) and 0 <= cislo < len(zpravy):
                z = zpravy[cislo]
                if z["zdroj"] not in videne:
                    videne.add(z["zdroj"])
                    zdroje.append({"nazev": z["zdroj"], "odkaz": z["odkaz"]})
        if not zdroje:
            continue  # pojistka: událost musí mít aspoň jeden dohledatelný zdroj
        aktuality.append({
            "titulek": a["titulek"],
            "shrnuti": a["shrnuti"],
            "titulek_en": a.get("titulek_en", a["titulek"]),
            "shrnuti_en": a.get("shrnuti_en", a["shrnuti"]),
            "oblast": "cr" if a.get("oblast") == "cr" else "svet",
            "dulezitost": a.get("dulezitost", 3),
            "zdroje": zdroje,
        })
    aktuality.sort(key=lambda a: a["dulezitost"], reverse=True)

    # ---------- Volání 3: co sledovat dnes / tento týden ----------
    prompt_sledovat = f"""{hlavicka}

Vytvoř krátký kalendář "Co sledovat" pro manažera: 5–8 NADCHÁZEJÍCÍCH
událostí (ode dneška zhruba na týden dopředu), které mohou hýbat trhy,
ekonomikou nebo českým děním — zasedání centrálních bank (Fed, ECB, ČNB),
zveřejnění makrodat (inflace, HDP, trh práce od ČSÚ/Eurostatu), výsledky
velkých firem, důležitá politická jednání a summity.

Pro každou událost objekt:
   - "datum": konkrétní datum "YYYY-MM-DD", nebo orientační text
     ("tento týden", "příští týden"), pokud si přesným datem nejsi jistý
   - "nazev": stručný český popis (max 10 slov)
   - "nazev_en": totéž anglicky

DŮLEŽITÉ: Uváděj jen události, které vyplývají ze zpráv v seznamu níže,
nebo pravidelné termíny, kterými si jsi opravdu jistý. Nevymýšlej si
konkrétní data — raději napiš orientační text. Seřaď od nejbližší.

Odpověz POUZE platným JSON polem objektů, bez jakéhokoli dalšího textu.

SEZNAM ZPRÁV:
{seznam}"""

    print(f"Volání 3/4: kalendář Co sledovat ({MODEL})...")
    surove_sledovat = _zavolej_clauda(client, prompt_sledovat)
    sledovat = [
        {"datum": s.get("datum", ""), "nazev": s.get("nazev", ""),
         "nazev_en": s.get("nazev_en", s.get("nazev", ""))}
        for s in surove_sledovat if s.get("nazev")
    ][:8]

    # ---------- Volání 4: kontrola faktů proti originálům ----------
    try:
        vysledek, aktuality = _zkontroluj_fakta(
            client, vysledek, aktuality, zpravy, cache)
    except (Exception, SystemExit) as chyba:
        print(f"  Kontrola faktů se nepovedla ({chyba}) — používám neověřenou verzi.")

    return {"zpravy": vysledek, "aktuality": aktuality, "sledovat": sledovat}


def _zkontroluj_fakta(client, vysledek, aktuality, zpravy, cache):
    """Porovná každé shrnutí s originálem; chyby opraví, nesmysly vyhodí."""
    mapa = {z["odkaz"]: z for z in zpravy}
    polozky = []
    for i, k in enumerate(vysledek):
        original = mapa.get(k["odkaz"])
        if not original:
            continue
        polozky.append(
            f"[K{i}] ORIGINÁL: {original['titulek']} — {original['popis']}\n"
            f"  CS: {k['titulek']} | {k['shrnuti']}\n"
            f"  EN: {k['titulek_en']} | {k['shrnuti_en']}"
        )
    for i, a in enumerate(aktuality):
        originaly = []
        for z in a["zdroje"]:
            puvodni = mapa.get(z["odkaz"])
            if puvodni:
                originaly.append(f"{puvodni['titulek']} — {puvodni['popis']}")
        polozky.append(
            f"[A{i}] ORIGINÁLY: " + " ||| ".join(originaly) + "\n"
            f"  CS: {a['titulek']} | {a['shrnuti']}\n"
            f"  EN: {a['titulek_en']} | {a['shrnuti_en']}"
        )

    prompt = f"""Jsi přísný fact-checker zpravodajského přehledu. Níže jsou položky:
vždy ORIGINÁL(Y) (titulek a popis původní zprávy) a k nim české (CS)
a anglické (EN) znění pro čtenáře.

Pro KAŽDOU položku ověř:
1. Každé tvrzení v CS i EN musí být doložitelné v originálu. Žádná
   domyšlená jména, produkty, čísla ani souvislosti (např. z názvu firmy
   nedovozuj neexistující produkty).
2. Jména firem, osob a produktů odpovídají originálu.
3. Pokud je originál souhrn více nesouvisejících témat, CS/EN se musí
   držet hlavního tématu titulku — ne vyjmenovávat směs.

Odpověz JSON polem, pro každou položku právě jeden objekt:
- vše v pořádku:            {{"id": "K3", "ok": true}}
- obsahuje chybu:           {{"id": "K3", "titulek": "...", "shrnuti": "...",
                             "titulek_en": "...", "shrnuti_en": "..."}}
                            (opravené znění založené VÝHRADNĚ na originálu)
- neopravitelné/bezobsažné: {{"id": "K3", "smazat": true}}

Odpověz POUZE platným JSON polem, escapuj uvozovky uvnitř textů.

POLOŽKY:
{chr(10).join(polozky)}"""

    print(f"Volání 4/4: kontrola faktů ({MODEL})...")
    kontrola = _zavolej_clauda(client, prompt)

    opravy, smazano = 0, 0
    smazat_karty, smazat_akt = set(), set()
    for polozka in kontrola:
        id_ = str(polozka.get("id", ""))
        if not id_ or polozka.get("ok"):
            continue
        typ, cislo = id_[0], id_[1:]
        if not cislo.isdigit():
            continue
        i = int(cislo)
        if polozka.get("smazat"):
            (smazat_karty if typ == "K" else smazat_akt).add(i)
            smazano += 1
            continue
        cil = None
        if typ == "K" and i < len(vysledek):
            cil = vysledek[i]
        elif typ == "A" and i < len(aktuality):
            cil = aktuality[i]
        if cil:
            for pole in ("titulek", "shrnuti", "titulek_en", "shrnuti_en"):
                if polozka.get(pole):
                    cil[pole] = polozka[pole]
            opravy += 1
            # Opravu propsat i do překladové cache
            if typ == "K" and cil["odkaz"] in cache:
                cache[cil["odkaz"]].update(
                    {p: cil[p] for p in ("titulek", "shrnuti",
                                         "titulek_en", "shrnuti_en")})

    vysledek = [k for i, k in enumerate(vysledek) if i not in smazat_karty]
    aktuality = [a for i, a in enumerate(aktuality) if i not in smazat_akt]
    if opravy or smazano:
        _uloz_cache(cache)
        print(f"  Fact-check: {opravy} opraveno, {smazano} vyřazeno.")
    else:
        print("  Fact-check: vše v pořádku.")
    return vysledek, aktuality


def uloz_data(vysledek, soubor="data.json"):
    # Klíčová čísla dne (stooq + ČNB) — bez API klíče, chráněné proti výpadku
    print("Stahuji klíčová čísla dne...")
    try:
        from stahni_trhy import stahni_klicova_cisla
        trhy = stahni_klicova_cisla()
    except Exception as chyba:
        print(f"  Klíčová čísla nedostupná ({chyba}) — stránka bude bez pruhu.")
        trhy = []

    data = {
        "vygenerovano": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "zpravy": vysledek["zpravy"],
        "aktuality": vysledek.get("aktuality", []),
        "sledovat": vysledek.get("sledovat", []),
        "trhy": trhy,
    }
    with open(soubor, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Uloženo do {soubor} ({len(data['zpravy'])} zpráv, "
          f"{len(data['aktuality'])} aktualit, {len(data['sledovat'])} událostí, "
          f"{len(data['trhy'])} ukazatelů).")


# Spuštění napřímo: stáhne zprávy, přeloží a uloží data.json
if __name__ == "__main__":
    zpravy = stahni_vsechny_zpravy()
    print(f"\nCelkem staženo: {len(zpravy)} zpráv")
    vysledek = vyber_a_preloz(zpravy)
    uloz_data(vysledek)
    print()
    for z in vysledek["zpravy"][:10]:
        print(f"  [{z['dulezitost']}] ({z['tema']}) {z['titulek']}")
    print("  ...")
    for a in vysledek["aktuality"]:
        print(f"  AKTUALITA ({a['oblast']}, dopad {a['dulezitost']}): "
              f"{a['titulek']} [{len(a['zdroje'])} zdrojů]")

# Nasazení webu dennibriefing.cz — návod krok za krokem

Cílem je, aby se web **generoval sám 1× denně** a byl dostupný na adrese
**dennibriefing.cz**. Hosting je zdarma (GitHub Pages), platíš jen doménu.

Jak to funguje: kód poběží na GitHubu, který každé ráno spustí tvůj generátor
(stáhne zprávy → Claude je vybere a přeloží → vytvoří stránky) a výsledek
sám vystaví na web. Ty už nemusíš dělat nic.

---

## Co budeš potřebovat

- Účet na **GitHub.com** (zdarma). Když ho nemáš, založ si ho.
- Svůj **Anthropic API klíč** (ten, co máš v souboru `.env` za `ANTHROPIC_API_KEY=`).

---

## Krok 1 — Založ repozitář (úložiště kódu)

1. Přihlas se na github.com a vpravo nahoře klikni na **+** → **New repository**.
2. **Repository name:** napiš třeba `dennibriefing`.
3. Nech vybrané **Public** (u účtu zdarma musí být veřejné, aby fungoval
   hosting zdarma). Neboj — žádné heslo ani API klíč v kódu není, ten se
   vkládá odděleně (viz Krok 3), a soubor `.env` se nahrávat NEBUDE.
4. Klikni **Create repository**.

---

## Krok 2 — Nahraj soubory projektu

1. Na stránce nového repozitáře klikni na odkaz **uploading an existing file**
   (nebo **Add file → Upload files**).
2. V Finderu otevři složku **projekt web**.
3. Stiskni **Cmd + Shift + tečka** — zobrazí se skryté soubory (ty, co začínají
   tečkou, včetně složky `.github`).
4. Označ a přetáhni do GitHubu **všechno KROMĚ souboru `.env`**.
   - **Musí** tam být: `.github` (složka s automatizací), `generuj_web.py`,
     `stahni_zpravy.py`, `stahni_trhy.py`, `preloz_zpravy.py`, `config.py`,
     `requirements.txt`.
   - **NIKDY nenahrávej `.env`** — je v něm tvůj tajný API klíč.
   - Přeskočit můžeš i `__pycache__`, `.DS_Store`, `preklady_cache.json`,
     `env-vzor.txt` (nejsou potřeba).
5. Dole klikni **Commit changes**.

> Ověř, že v repozitáři vidíš složku `.github/workflows/` se souborem
> `deploy.yml`. To je motor celé automatizace.

---

## Krok 3 — Vlož API klíč jako „secret"

Aby GitHub mohl volat Claude, potřebuje tvůj API klíč — uloží se bezpečně,
nikdo ho neuvidí.

1. V repozitáři nahoře **Settings**.
2. Vlevo **Secrets and variables → Actions**.
3. **New repository secret**.
4. **Name:** `ANTHROPIC_API_KEY` (přesně takto).
5. **Secret:** vlož hodnotu svého klíče (to, co je v `.env` za `=`).
6. **Add secret**.

---

## Krok 4 — Zapni GitHub Pages

1. V repozitáři **Settings → Pages**.
2. U **Source** vyber **GitHub Actions**.

---

## Krok 5 — První spuštění (test)

1. V repozitáři nahoře **Actions**.
2. Vlevo klikni na workflow **„Build a nasazení webu"**.
3. Vpravo **Run workflow → Run workflow** (spustí se ručně, ať nečekáš na ráno).
4. Počkej pár minut. Až bude u běhu zelená fajfka, hotovo.
   - Adresa webu je zatím `https://TVOJE-JMENO.github.io/dennibriefing/`
     (uvidíš ji taky v Settings → Pages). Zkontroluj, že se stránka načte.

> Když běh spadne (červený křížek), klikni na něj a pošli mi, co je ve výpisu
> červeně — poradím.

---

## Krok 6 — Napoj doménu dennibriefing.cz

**Část A — v GitHubu:**
1. **Settings → Pages → Custom domain** → napiš `dennibriefing.cz` → **Save**.

**Část B — u WEDOSu (nastavení DNS):**
1. Přihlas se do administrace WEDOS, otevři **DNS záznamy** domény
   dennibriefing.cz (sekce DNS / správa DNS).
2. Přidej **čtyři A záznamy** pro kořen domény (jméno nech prázdné nebo `@`):

   | Typ | Jméno | Hodnota |
   |-----|-------|-----------------|
   | A   | @     | 185.199.108.153 |
   | A   | @     | 185.199.109.153 |
   | A   | @     | 185.199.110.153 |
   | A   | @     | 185.199.111.153 |

3. (Volitelné, doporučené) Přidej pro `www` jeden CNAME záznam:

   | Typ   | Jméno | Hodnota                  |
   |-------|-------|--------------------------|
   | CNAME | www   | TVOJE-JMENO.github.io.   |

4. Ulož změny.

---

## Krok 7 — Počkej a zkontroluj HTTPS

- Rozšíření DNS trvá od pár minut po několik hodin.
- Až doména začne fungovat, vrať se do **Settings → Pages** a zaškrtni
  **Enforce HTTPS** (může chvíli trvat, než se volba zpřístupní — GitHub si
  sám vystaví certifikát zdarma).
- Hotovo: web běží na **https://dennibriefing.cz** a aktualizuje se sám každé ráno.

---

## Jak to potom používat

- **Nic nemusíš dělat** — web se přegeneruje každý den sám (v ~07:00).
- **Chceš aktualizaci hned:** Actions → workflow → Run workflow.
- **Chceš změnit čas:** v `.github/workflows/deploy.yml` uprav řádek `cron`
  (čas je v UTC, tj. o 1–2 hodiny méně než v ČR).
- **Chceš změnit zdroje/témata:** uprav `config.py` v repozitáři
  (Edit tužtičkou → Commit). Při dalším běhu se to promítne.
- **Změníš-li API klíč:** přepiš secret `ANTHROPIC_API_KEY` (Krok 3).

> Poznámka: naplánované spouštění GitHub uspí, pokud je repozitář 60 dní bez
> jakékoli aktivity. Když web běží dál, nevadí; kdyby se zastavil, stačí jednou
> ručně spustit workflow.

---

# Podcast – audio verze briefingu

Každé ráno po vygenerování webu napíše Claude z aktualit ~5minutový mluvený
text a open-source model **Pocket TTS** ho přímo na GitHubu namluví hlasem
**Kasandry**. Na webu se nad aktualitami objeví přehrávač a vznikne podcastový
feed **https://dennibriefing.cz/podcast.xml**. Kód je v `podcast.py`,
nastavení v `config.py` (sekce PODCAST).

## Krok 1 – Nic, běží to samo a zdarma

Bez účtu, bez klíče, bez placení. Jak to funguje:

- **Model:** český Pocket TTS (Kyutai), natrénovaný na ~1000 hodinách české
  řeči z Poslanecké sněmovny. Barvu hlasu přebírá z krátké nahrávky
  `podcast-hlas-vzor.wav` (hlas Kasandra, CC BY 4.0). Namluvení trvá pár minut.
- **Hlídač:** každou větu namlouvá zvlášť a když je zvuk podezřele krátký nebo
  dlouhý (model větu zkrátil či „ujel"), vygeneruje ji znovu.
- **Záloha:** kdyby Pocket selhal, epizodu namluví starší hlas Piper (taky Kasandra).
- **Výslovnost:** hlas čte všechno po česky, takže anglická jména se přepisují
  podle slovníku `PODCAST_VYSLOVNOST` (Microsoft → Majkrosoft) a zbylé číslice
  se převedou na slova. Když nějaké jméno zní špatně, dopiš ho do slovníku.
- **Jiný hlas:** stačí nahradit `podcast-hlas-vzor.wav` jinou čistou nahrávkou
  (10–20 s, jeden mluvčí, bez hudby) – model převezme její barvu hlasu.
  Používej jen nahrávku, ke které máš práva.
- Chceš epizodu hned, ne až ráno? **Actions → Run workflow.**

> Placené hlasy (volitelné): v `config.py` přepni `PODCAST_HLAS_SLUZBA` na
> `"azure"` / `"elevenlabs"` a na GitHub přidej secret `AZURE_SPEECH_KEY` /
> `ELEVENLABS_API_KEY`.

## Krok 2 – Apple Podcasts a Spotify (až vyjde první epizoda)

1. V `config.py` vyplň `PODCAST_EMAIL` (je ve feedu veřejně vidět –
   klidně samostatná adresa). Spotify na ni pošle ověřovací kód.
2. **Spotify:** creators.spotify.com → přidat existující podcast přes RSS →
   vlož `https://dennibriefing.cz/podcast.xml` → ověř kódem z e-mailu.
3. **Apple:** podcastsconnect.apple.com → **+ → New Show** → přidat přes RSS
   feed → vlož stejnou adresu. Schválení obvykle trvá pár dní.
4. Po schválení vlož odkazy na pořad do `PODCAST_ODKAZ_APPLE`
   a `PODCAST_ODKAZ_SPOTIFY` – objeví se u přehrávače vedle RSS.

Uchovává se posledních 30 epizod (`PODCAST_POCET_EPIZOD`). Přepis každé
epizody leží vedle MP3 jako `.txt`.

---

# Návštěvnost – GoatCounter

Měření bez cookies (žádná cookie lišta není potřeba), zdarma pro osobní
weby. Skript se do stránek vkládá sám, když je v `config.py` vyplněný
`GOATCOUNTER_KOD` (nastaveno na `dennibriefing`).

1. Na **goatcounter.com** klikni **Sign up** a jako **Code** zadej
   `dennibriefing` (musí se shodovat s `GOATCOUNTER_KOD`; když je obsazený,
   zvol jiný a přepiš ho v `config.py`).
2. Statistiky pak najdeš na **https://dennibriefing.goatcounter.com**.
3. Ať se nepočítají tvoje vlastní návštěvy: na každém svém zařízení
   jednou otevři **https://dennibriefing.cz/#toggle-goatcounter**.
4. Potvrď e-mail odkazem, který ti GoatCounter poslal (kvůli obnově hesla).

Kromě návštěv stránek se zaznamenává, co lidé rozklikávají (v přehledu
jsou to položky označené jako události):

| Událost | Co znamená |
|---|---|
| `klik/<rubrika>: titulek` | otevřel zprávu z rubriky (akcie, AI…) |
| `klik/aktualita: titulek` | otevřel zdroj u aktuality |
| `kauza: titulek` | rozbalil shrnutí kauzy |
| `podcast/přehrání`, `podcast/dohráno` | pustil / dohrál epizodu na webu |
| `podcast/odběr: …` | klikl na Apple Podcasts / Spotify / RSS |
| `hledání: dotaz` | co hledal (zapíše se po kliknutí na výsledek) |
| `ui/…` | přepnul jazyk, tmavý režim, záložku Svět/Česko, rubriku |

Poslechy v aplikacích (Apple Podcasts, Spotify) GoatCounter nevidí –
ty ukazují jejich vlastní statistiky pro autory.

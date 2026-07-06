# ============================================================
# HLAVNÍ SKRIPT — spustí celý řetězec:
#   1. stáhne zprávy z RSS (stahni_zpravy.py)
#   2. vybere, přeloží a shrne přes Claude (preloz_zpravy.py)
#   3. uloží data.json (včetně tržních dat a kalendáře)
#   4. vygeneruje DVĚ stránky:
#        index.html — aktuality + zprávy podle témat
#        data.html  — kalendář Co sledovat + klíčová čísla s grafy
#
# Spuštění:            python3 generuj_web.py
# Jen přegenerovat
# stránky z data.json
# (bez volání API):    python3 generuj_web.py --jen-html
# ============================================================

import html as html_mod
import json
import sys
from datetime import datetime

from preloz_zpravy import vyber_a_preloz, uloz_data
from stahni_zpravy import stahni_vsechny_zpravy

# Barvy štítků jednotlivých témat (klidně změň)
BARVY_TEMAT = {
    "akcie":            "#1d5c4d",   # lahvově zelená (burza, peníze)
    "ekonomika":        "#2c4a6e",   # námořnická modř
    "česká ekonomika":  "#7d3c46",   # burgundská
    "AI":               "#5d4870",   # tmavý lilek
}
VYCHOZI_BARVA = "#8d8371"

# Anglické názvy témat pro přepínač jazyka
TEMATA_EN = {
    "akcie":            "Stocks",
    "ekonomika":        "Economy",
    "česká ekonomika":  "Czech economy",
    "AI":               "AI",
}

MESICE_EN = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
             "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


# ------------------------------------------------------------
# Společné CSS pro obě stránky (obyčejný string — žádné {{ }})
# ------------------------------------------------------------
CSS = """
  :root {
    --pozadi: #f7f5f1; --karta: #ffffff; --text: #191919;
    --seda: #8a8578; --okraj: #e7e2d8; --odstavec: #44413a;
    --linka: #d8d2c4; --graf: #2c4a6e;
  }
  body.tmavy {
    --pozadi: #121217; --karta: #1c1c24; --text: #ededf2;
    --seda: #8f8f9c; --okraj: #2c2c37; --odstavec: #c6c6d0;
    --linka: #34343f; --graf: #7fa3d0;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  html { scroll-behavior: smooth; }
  body {
    font-family: -apple-system, "Segoe UI", Roboto, sans-serif;
    background: var(--pozadi); color: var(--text);
    line-height: 1.55; padding: 0 20px 70px;
    transition: background-color .45s ease, color .45s ease;
    position: relative; min-height: 100vh;
  }
  body::before {
    content: ""; position: absolute; inset: 0; pointer-events: none;
    background:
      radial-gradient(900px 380px at 30% -80px,
        color-mix(in srgb, #1d5c4d 7%, transparent), transparent 70%),
      radial-gradient(900px 380px at 70% -80px,
        color-mix(in srgb, #5d4870 6%, transparent), transparent 70%);
  }
  .obal {
    max-width: 1080px; margin: 0 auto; position: relative; z-index: 1;
    transition: opacity .22s ease;
  }
  .obal.prolinani { opacity: 0; }

  /* ---------- Hlavička ---------- */
  header.hlavicka { padding: 58px 0 10px; text-align: center; }
  .nadtitulek {
    font-size: 0.72rem; font-weight: 700; letter-spacing: 0.32em;
    text-transform: uppercase; color: var(--seda); margin-bottom: 10px;
  }
  header.hlavicka h1 {
    font-family: Georgia, "Times New Roman", serif;
    font-size: clamp(2.1rem, 5vw, 3rem);
    font-weight: 700; letter-spacing: -0.015em;
  }
  header.hlavicka .cas { color: var(--seda); font-size: 0.9rem; margin-top: 10px; }

  /* ---------- Přepínač stránek Zprávy | Data ---------- */
  nav.stranky {
    display: flex; justify-content: center; margin: 20px 0 30px;
  }
  .stranky-vnitrek {
    display: inline-flex; border: 1px solid var(--okraj);
    border-radius: 999px; padding: 3px; background: var(--karta);
    transition: background-color .45s ease, border-color .45s ease;
  }
  a.stranka {
    text-decoration: none; color: var(--seda);
    border-radius: 999px; padding: 7px 22px; font-size: 0.9rem;
    font-weight: 600;
    transition: background-color .25s ease, color .25s ease;
  }
  a.stranka.aktivni { background: var(--text); color: var(--pozadi); }
  a.stranka:not(.aktivni):hover { color: var(--text); }

  /* ---------- Přepínače vpravo nahoře ---------- */
  .prepinace { position: absolute; top: 20px; right: 0; display: flex; gap: 8px; }
  .prepinac {
    border: 1px solid var(--okraj); background: var(--karta); color: var(--text);
    border-radius: 999px; padding: 7px 14px; font-size: 0.85rem; cursor: pointer;
    transition: background-color .45s ease, color .45s ease,
                border-color .45s ease, transform .15s ease;
  }
  .prepinac:hover { transform: translateY(-1px); border-color: var(--seda); }
  .prepinac:active { transform: scale(0.94); }

  /* ---------- Filtry témat ---------- */
  nav.filtry {
    display: flex; flex-wrap: wrap; gap: 8px;
    justify-content: center; margin: 26px 0 28px;
  }
  .filtr {
    border: 1px solid var(--okraj); background: var(--karta);
    border-radius: 999px; padding: 7px 15px; font-size: 0.85rem;
    cursor: pointer; color: var(--text);
    display: inline-flex; align-items: center; gap: 7px;
    transition: background-color .3s ease, color .3s ease,
                border-color .3s ease, transform .15s ease;
  }
  .filtr:hover { transform: translateY(-1px); border-color: var(--seda); }
  .filtr .tecka {
    width: 8px; height: 8px; border-radius: 50%;
    background: var(--barva); display: inline-block;
  }
  .filtr.aktivni { background: var(--text); color: var(--pozadi); border-color: var(--text); }
  .filtr.aktivni .tecka { background: var(--pozadi); }

  /* ---------- Rubriky a mřížka karet ---------- */
  .rubrika { margin: 0 0 38px; }
  .rubrika-titul {
    font-family: Georgia, "Times New Roman", serif;
    font-size: 1.25rem; font-weight: 700;
    display: flex; align-items: center; gap: 10px;
    margin: 0 0 14px; padding-bottom: 8px;
    border-bottom: 1px solid var(--linka);
    transition: border-color .45s ease;
  }
  .rubrika-titul .tecka {
    width: 10px; height: 10px; border-radius: 50%;
    background: var(--barva); display: inline-block; flex-shrink: 0;
  }
  .rubrika-pocet {
    font-family: -apple-system, "Segoe UI", Roboto, sans-serif;
    font-size: 0.75rem; font-weight: 700; color: var(--seda);
    border: 1px solid var(--okraj); border-radius: 999px;
    padding: 1px 9px; margin-left: 2px;
  }
  .mrizka {
    display: grid; gap: 20px;
    grid-template-columns: repeat(auto-fill, minmax(310px, 1fr));
  }
  .karta {
    background: var(--karta); border: 1px solid var(--okraj);
    border-radius: 16px; padding: 24px;
    display: flex; flex-direction: column; gap: 11px;
    transition: background-color .45s ease, border-color .45s ease,
                box-shadow .2s ease, transform .2s ease, opacity .3s ease;
  }
  .karta:hover {
    box-shadow: 0 10px 30px rgba(0,0,0,.10);
    transform: translateY(-3px);
    border-color: color-mix(in srgb, var(--barva) 45%, var(--okraj));
  }
  body.tmavy .karta:hover { box-shadow: 0 10px 30px rgba(0,0,0,.45); }
  .karta--top { position: relative; overflow: hidden; }
  .karta--top::before {
    content: ""; position: absolute; top: 0; left: 0; right: 0; height: 3px;
    background: linear-gradient(90deg, var(--barva),
      color-mix(in srgb, var(--barva) 25%, transparent));
  }
  .stitek {
    align-self: flex-start; font-size: 0.72rem; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.07em;
    color: color-mix(in srgb, var(--barva) 85%, var(--text));
    background: linear-gradient(135deg,
      color-mix(in srgb, var(--barva) 16%, var(--karta)),
      color-mix(in srgb, var(--barva) 7%, var(--karta)));
    border: 1px solid color-mix(in srgb, var(--barva) 22%, var(--karta));
    border-radius: 999px; padding: 3px 11px;
    transition: background-color .45s ease, color .45s ease, border-color .45s ease;
  }
  body.tmavy .stitek { color: color-mix(in srgb, var(--barva) 55%, white); }
  .karta h2 { font-size: 1.08rem; line-height: 1.35; letter-spacing: -0.01em; }
  .karta h2 a { color: inherit; text-decoration: none; }
  .karta h2 a:hover { text-decoration: underline; text-underline-offset: 3px; }
  .karta p { font-size: 0.92rem; color: var(--odstavec); flex-grow: 1;
             transition: color .45s ease; }
  .karta footer {
    font-size: 0.8rem; color: var(--seda);
    display: flex; justify-content: space-between; align-items: center;
    border-top: 1px solid var(--linka); padding-top: 10px;
    transition: border-color .45s ease, color .45s ease;
  }
  .karta footer .zdroj { font-weight: 600; }
  .skryta { display: none; }

  /* ---------- Aktuality ---------- */
  .aktuality, .panel {
    background: var(--karta); border: 1px solid var(--okraj);
    border-radius: 16px; padding: 26px 28px; margin: 0 0 34px;
    transition: background-color .45s ease, border-color .45s ease;
  }
  .akt-hlava {
    display: flex; align-items: center; justify-content: space-between;
    flex-wrap: wrap; gap: 12px; margin-bottom: 6px;
  }
  .akt-titul {
    font-family: Georgia, "Times New Roman", serif;
    font-size: 1.25rem; font-weight: 700;
    display: flex; align-items: center; gap: 10px;
  }
  .puls {
    width: 9px; height: 9px; border-radius: 50%;
    background: #b0413e; flex-shrink: 0;
    animation: pulzovani 2.2s ease-in-out infinite;
  }
  @keyframes pulzovani {
    0%, 100% { box-shadow: 0 0 0 0 rgba(176,65,62,.35); }
    50%      { box-shadow: 0 0 0 6px rgba(176,65,62,0); }
  }
  .akt-taby {
    display: inline-flex; border: 1px solid var(--okraj);
    border-radius: 999px; padding: 3px; background: var(--pozadi);
    transition: background-color .45s ease, border-color .45s ease;
  }
  .akt-tab {
    border: 0; background: transparent; color: var(--seda);
    border-radius: 999px; padding: 6px 16px; font-size: 0.85rem;
    font-weight: 600; cursor: pointer;
    transition: background-color .25s ease, color .25s ease;
  }
  .akt-tab.aktivni { background: var(--text); color: var(--pozadi); }
  .akt {
    padding: 16px 0; border-bottom: 1px solid var(--linka);
    transition: border-color .45s ease;
  }
  .akt:last-of-type { border-bottom: 0; }
  .akt h3 { font-size: 1.02rem; line-height: 1.4; letter-spacing: -0.01em; }
  .akt p { font-size: 0.92rem; color: var(--odstavec); margin-top: 5px;
           transition: color .45s ease; }
  .akt-zdroje {
    display: flex; flex-wrap: wrap; align-items: center;
    gap: 6px; margin-top: 10px;
  }
  .akt-popisek {
    font-size: 0.72rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.07em; color: var(--seda); margin-right: 4px;
  }
  .zdroj-chip {
    font-size: 0.78rem; color: var(--odstavec); text-decoration: none;
    border: 1px solid var(--okraj); background: var(--pozadi);
    border-radius: 999px; padding: 3px 10px;
    transition: background-color .25s ease, color .25s ease,
                border-color .25s ease, transform .15s ease;
  }
  .zdroj-chip:hover { border-color: var(--seda); transform: translateY(-1px); }
  .akt-pager {
    display: flex; align-items: center; justify-content: center;
    gap: 14px; padding-top: 14px;
  }
  .akt-sipka {
    border: 1px solid var(--okraj); background: var(--pozadi); color: var(--text);
    width: 32px; height: 32px; border-radius: 50%; font-size: 1.05rem;
    cursor: pointer; line-height: 1;
    transition: background-color .25s ease, border-color .25s ease,
                opacity .25s ease, transform .15s ease;
  }
  .akt-sipka:hover:not(:disabled) { transform: translateY(-1px); border-color: var(--seda); }
  .akt-sipka:disabled { opacity: .35; cursor: default; }
  .akt-stranka { font-size: 0.82rem; color: var(--seda); min-width: 44px; text-align: center; }

  /* ---------- Stránka Data: kalendář ---------- */
  .udalost {
    display: flex; align-items: flex-start; gap: 16px;
    padding: 13px 0; border-bottom: 1px solid var(--linka);
    transition: border-color .45s ease;
  }
  .udalost:last-child { border-bottom: 0; }
  .udalost-datum {
    flex-shrink: 0; width: 110px; text-align: right;
    font-size: 0.78rem; font-weight: 700; color: var(--seda);
    text-transform: uppercase; letter-spacing: 0.04em;
    padding-top: 3px; font-variant-numeric: tabular-nums;
  }
  .udalost-nazev { font-size: 0.95rem; }

  /* ---------- Stránka Data: ukazatele s grafy ---------- */
  .sekce-titul {
    font-family: Georgia, "Times New Roman", serif;
    font-size: 1.25rem; font-weight: 700; margin: 0 0 16px;
    display: flex; align-items: center; gap: 10px;
  }
  .ukazatele {
    display: grid; gap: 20px;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    margin-bottom: 34px;
  }
  .ukazatel {
    background: var(--karta); border: 1px solid var(--okraj);
    border-radius: 16px; padding: 20px 22px 16px;
    transition: background-color .45s ease, border-color .45s ease,
                box-shadow .2s ease, transform .2s ease;
  }
  .ukazatel:hover { box-shadow: 0 10px 30px rgba(0,0,0,.08); transform: translateY(-2px); }
  body.tmavy .ukazatel:hover { box-shadow: 0 10px 30px rgba(0,0,0,.4); }
  .ukazatel-nazev {
    font-size: 0.76rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.07em; color: var(--seda); margin-bottom: 6px;
  }
  .ukazatel-radek { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
  .ukazatel-hodnota {
    font-size: 1.7rem; font-weight: 800; letter-spacing: -0.02em;
    font-variant-numeric: tabular-nums;
  }
  .zmena { font-size: 0.85rem; font-weight: 700; font-variant-numeric: tabular-nums; }
  .zmena.nahoru { color: #1d7a4f; }
  .zmena.dolu { color: #b0413e; }
  body.tmavy .zmena.nahoru { color: #4cc38a; }
  body.tmavy .zmena.dolu { color: #e5726f; }
  .graf-obal { position: relative; margin-top: 12px; }
  .graf { width: 100%; height: 84px; display: block; color: var(--graf); }
  .graf-tip {
    position: absolute; pointer-events: none; display: none; z-index: 2;
    background: var(--text); color: var(--pozadi);
    font-size: 0.72rem; font-weight: 600; font-variant-numeric: tabular-nums;
    padding: 3px 9px; border-radius: 6px; white-space: nowrap;
    transform: translate(-50%, -135%);
    box-shadow: 0 2px 10px rgba(0,0,0,.18);
  }
  .graf-svisla {
    position: absolute; top: 0; bottom: 0; width: 1px;
    background: var(--seda); opacity: .55; display: none; pointer-events: none;
  }
  .graf-tecka {
    position: absolute; width: 9px; height: 9px; border-radius: 50%;
    background: var(--graf); border: 2px solid var(--karta);
    transform: translate(-50%, -50%); display: none; pointer-events: none;
  }
  .graf-cara { fill: none; stroke: currentColor; stroke-width: 2; }
  .graf-plocha { fill: currentColor; opacity: .10; }
  .graf-popisky {
    display: flex; justify-content: space-between;
    font-size: 0.72rem; color: var(--seda); margin-top: 4px;
    font-variant-numeric: tabular-nums;
  }
  .rozsahy { display: flex; gap: 6px; margin-top: 12px; }
  .rozsah {
    border: 1px solid var(--okraj); background: transparent; color: var(--seda);
    border-radius: 8px; padding: 3px 10px; font-size: 0.75rem;
    font-weight: 600; cursor: pointer;
    transition: background-color .2s ease, color .2s ease, border-color .2s ease;
  }
  .rozsah.aktivni { background: var(--text); color: var(--pozadi); border-color: var(--text); }
  .rozsah:not(.aktivni):hover { color: var(--text); border-color: var(--seda); }
  .ukazatel { position: relative; }
  .skryj {
    position: absolute; top: 10px; right: 12px;
    border: 0; background: transparent; color: var(--seda);
    font-size: 1.1rem; line-height: 1; cursor: pointer;
    opacity: 0; transition: opacity .2s ease, color .2s ease;
  }
  .ukazatel:hover .skryj { opacity: .7; }
  .skryj:hover { opacity: 1 !important; color: #b0413e; }
  .skryte-obal {
    display: flex; flex-wrap: wrap; align-items: center; gap: 8px;
    margin: -14px 0 20px;
  }
  .skryty-chip {
    border: 1px dashed var(--okraj); background: transparent;
    color: var(--seda); border-radius: 999px; padding: 4px 12px;
    font-size: 0.8rem; cursor: pointer;
    transition: color .2s ease, border-color .2s ease;
  }
  .skryty-chip:hover { color: var(--text); border-color: var(--seda); }
  .tip-pridani { font-size: 0.8rem; color: var(--seda); margin: -8px 0 26px; }

  /* ---------- Jazykové verze ---------- */
  .l-en { display: none; }
  body.anglicky .l-en { display: inline; }
  body.anglicky .l-cs { display: none; }

  @media (max-width: 560px) {
    header.hlavicka { padding-top: 84px; }
    .prepinace { top: 16px; right: 0; }
    .udalost-datum { width: 84px; }
  }
"""

# ------------------------------------------------------------
# Společný JavaScript (vše ošetřeno, ať funguje na obou stránkách)
# ------------------------------------------------------------
JS = """
  // ---- Filtrování rubrik podle tématu (jen stránka Zprávy) ----
  document.querySelectorAll(".filtr").forEach(function (btn) {
    btn.addEventListener("click", function () {
      document.querySelectorAll(".filtr").forEach(b => b.classList.remove("aktivni"));
      btn.classList.add("aktivni");
      var tema = btn.dataset.tema;
      document.querySelectorAll(".rubrika").forEach(function (r) {
        r.classList.toggle("skryta", tema !== "vse" && r.dataset.tema !== tema);
      });
    });
  });

  // ---- Aktuality: záložky Svět/Česko + stránkování po 4 ----
  (function () {
    var NA_STRANKU = 4;
    var aktivniTab = document.querySelector(".akt-tab.aktivni");
    if (!aktivniTab) return;
    var stav = { oblast: aktivniTab.dataset.oblast, strana: 0 };
    var pager = document.getElementById("akt-pager");
    var popisek = document.getElementById("akt-stranka");
    var zpet = document.getElementById("akt-zpet");
    var dal = document.getElementById("akt-dal");

    function prekresli() {
      var vTabu = Array.from(document.querySelectorAll(".akt"))
        .filter(a => a.dataset.oblast === stav.oblast);
      var stran = Math.max(1, Math.ceil(vTabu.length / NA_STRANKU));
      if (stav.strana >= stran) stav.strana = stran - 1;
      document.querySelectorAll(".akt").forEach(a => a.classList.add("skryta"));
      vTabu.slice(stav.strana * NA_STRANKU, (stav.strana + 1) * NA_STRANKU)
        .forEach(a => a.classList.remove("skryta"));
      popisek.textContent = (stav.strana + 1) + " / " + stran;
      zpet.disabled = stav.strana === 0;
      dal.disabled = stav.strana >= stran - 1;
      pager.style.display = stran > 1 ? "flex" : "none";
    }
    document.querySelectorAll(".akt-tab").forEach(function (btn) {
      btn.addEventListener("click", function () {
        document.querySelectorAll(".akt-tab").forEach(b => b.classList.remove("aktivni"));
        btn.classList.add("aktivni");
        stav.oblast = btn.dataset.oblast;
        stav.strana = 0;
        prekresli();
      });
    });
    zpet.addEventListener("click", function () { stav.strana--; prekresli(); });
    dal.addEventListener("click", function () { stav.strana++; prekresli(); });
    prekresli();
  })();

  // ---- Grafy ukazatelů (jen stránka Data) ----
  (function () {
    var zdrojDat = document.getElementById("trhy-data");
    if (!zdrojDat) return;
    var TRHY = JSON.parse(zdrojDat.textContent);
    var SIRKA = 320, VYSKA = 90, OKRAJ = 6;

    function hezkeDatum(iso) {
      var c = iso.split("-");
      return c[2].replace(/^0/, "") + ". " + c[1].replace(/^0/, "") + ". " + c[0];
    }

    function vykresli(karta) {
      var i = +karta.dataset.i;
      var aktivni = karta.querySelector(".rozsah.aktivni");
      var dny = aktivni ? +aktivni.dataset.dny : 66;
      var body = (TRHY[i].historie || []);
      if (dny > 0) body = body.slice(-dny);
      var svg = karta.querySelector(".graf");
      if (!svg || body.length < 2) return;

      var hodnoty = body.map(b => b[1]);
      var min = Math.min.apply(null, hodnoty), max = Math.max.apply(null, hodnoty);
      if (max === min) { max += 1; min -= 1; }
      var body_svg = body.map(function (b, j) {
        var x = OKRAJ + (j / (body.length - 1)) * (SIRKA - 2 * OKRAJ);
        var y = VYSKA - OKRAJ - ((b[1] - min) / (max - min)) * (VYSKA - 2 * OKRAJ);
        return x.toFixed(1) + "," + y.toFixed(1);
      });
      var cara = "M" + body_svg.join(" L");
      var plocha = cara + " L" + (SIRKA - OKRAJ) + "," + (VYSKA - OKRAJ)
                 + " L" + OKRAJ + "," + (VYSKA - OKRAJ) + " Z";
      svg.innerHTML = '<path class="graf-plocha" d="' + plocha + '"/>'
                    + '<path class="graf-cara" d="' + cara + '"/>';
      var od = karta.querySelector(".g-od"), doo = karta.querySelector(".g-do");
      if (od) od.textContent = hezkeDatum(body[0][0]);
      if (doo) doo.textContent = hezkeDatum(body[body.length - 1][0]);
      // Uložíme si data pro čtení hodnot myší
      karta._graf = { body: body, min: min, max: max };
    }

    function formatCena(v) {
      if (Math.abs(v) >= 1000)
        return Math.round(v).toString().replace(/\\B(?=(\\d{3})+(?!\\d))/g, "\\u00a0");
      return v.toFixed(2).replace(".", ",");
    }

    function zapniCteniMysi(karta) {
      var obal = karta.querySelector(".graf-obal");
      if (!obal) return;
      var svg = obal.querySelector(".graf");
      var tip = obal.querySelector(".graf-tip");
      var svisla = obal.querySelector(".graf-svisla");
      var tecka = obal.querySelector(".graf-tecka");

      obal.addEventListener("mousemove", function (e) {
        var g = karta._graf;
        if (!g || g.body.length < 2) return;
        var rect = svg.getBoundingClientRect();
        var fx = (e.clientX - rect.left) / rect.width * SIRKA;
        var n = g.body.length;
        var idx = Math.round((fx - OKRAJ) / (SIRKA - 2 * OKRAJ) * (n - 1));
        idx = Math.max(0, Math.min(n - 1, idx));
        var bod = g.body[idx];
        var xSvg = OKRAJ + (idx / (n - 1)) * (SIRKA - 2 * OKRAJ);
        var ySvg = VYSKA - OKRAJ - ((bod[1] - g.min) / (g.max - g.min)) * (VYSKA - 2 * OKRAJ);
        var xPx = xSvg / SIRKA * rect.width;
        var yPx = ySvg / VYSKA * rect.height;

        svisla.style.left = xPx + "px";
        tecka.style.left = xPx + "px";
        tecka.style.top = yPx + "px";
        tip.style.left = Math.max(38, Math.min(rect.width - 38, xPx)) + "px";
        tip.style.top = yPx + "px";
        tip.textContent = formatCena(bod[1]) + " \\u00b7 " + hezkeDatum(bod[0]);
        svisla.style.display = tecka.style.display = tip.style.display = "block";
      });
      obal.addEventListener("mouseleave", function () {
        svisla.style.display = tecka.style.display = tip.style.display = "none";
      });
    }

    document.querySelectorAll(".ukazatel").forEach(function (karta) {
      karta.querySelectorAll(".rozsah").forEach(function (btn) {
        btn.addEventListener("click", function () {
          karta.querySelectorAll(".rozsah").forEach(b => b.classList.remove("aktivni"));
          btn.classList.add("aktivni");
          vykresli(karta);
        });
      });
      vykresli(karta);
      zapniCteniMysi(karta);
    });
  })();

  // ---- Skrývání ukazatelů (pamatuje se v prohlížeči) ----
  (function () {
    var karty = document.querySelectorAll(".ukazatel");
    if (!karty.length) return;
    var obal = document.getElementById("skryte-obal");
    var radek = document.getElementById("skryte-radek");

    function nactiSkryte() {
      try { return JSON.parse(localStorage.getItem("skryteUkazatele") || "[]"); }
      catch (e) { return []; }
    }
    function ulozSkryte(s) { localStorage.setItem("skryteUkazatele", JSON.stringify(s)); }

    function prekresliSkryte() {
      var skryte = nactiSkryte();
      karty.forEach(function (k) {
        k.classList.toggle("skryta", skryte.indexOf(k.dataset.nazev) !== -1);
      });
      radek.innerHTML = "";
      skryte.forEach(function (nazev) {
        var chip = document.createElement("button");
        chip.className = "skryty-chip";
        chip.textContent = "+ " + nazev;
        chip.addEventListener("click", function () {
          ulozSkryte(nactiSkryte().filter(n => n !== nazev));
          prekresliSkryte();
        });
        radek.appendChild(chip);
      });
      obal.style.display = skryte.length ? "flex" : "none";
    }

    karty.forEach(function (k) {
      var btn = k.querySelector(".skryj");
      if (btn) btn.addEventListener("click", function () {
        var s = nactiSkryte();
        if (s.indexOf(k.dataset.nazev) === -1) s.push(k.dataset.nazev);
        ulozSkryte(s);
        prekresliSkryte();
      });
    });
    prekresliSkryte();
  })();

  // ---- Tmavý režim a jazyk (pamatují se, platí pro obě stránky) ----
  var telo = document.body;
  var obal = document.getElementById("obal");
  var btnRezim = document.getElementById("rezim");
  var btnJazyk = document.getElementById("jazyk");

  function nastavRezim(tmavy) {
    telo.classList.toggle("tmavy", tmavy);
    btnRezim.textContent = tmavy ? "\\u2600\\uFE0F" : "\\uD83C\\uDF19";
    localStorage.setItem("rezim", tmavy ? "tmavy" : "svetly");
  }
  function nastavJazyk(en) {
    telo.classList.toggle("anglicky", en);
    btnJazyk.textContent = en ? "CZ" : "EN";
    document.documentElement.lang = en ? "en" : "cs";
    localStorage.setItem("jazyk", en ? "en" : "cs");
  }
  btnRezim.addEventListener("click", function () {
    nastavRezim(!telo.classList.contains("tmavy"));
  });
  btnJazyk.addEventListener("click", function () {
    obal.classList.add("prolinani");
    setTimeout(function () {
      nastavJazyk(!telo.classList.contains("anglicky"));
      obal.classList.remove("prolinani");
    }, 220);
  });
  var ulozenyRezim = localStorage.getItem("rezim");
  nastavRezim(ulozenyRezim ? ulozenyRezim === "tmavy"
    : window.matchMedia("(prefers-color-scheme: dark)").matches);
  nastavJazyk(localStorage.getItem("jazyk") === "en");
"""


def _kostra(data, aktivni_stranka, obsah):
    """Společná kostra stránky: hlavička, přepínače, obsah, JS."""
    zpravy_akt = ' aktivni' if aktivni_stranka == 'zpravy' else ''
    data_akt = ' aktivni' if aktivni_stranka == 'data' else ''
    return f"""<!DOCTYPE html>
<html lang="cs">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Můj přehled zpráv</title>
<style>{CSS}</style>
</head>
<body>
<div class="obal" id="obal">
  <div class="prepinace">
    <button class="prepinac" id="jazyk" title="Switch language">EN</button>
    <button class="prepinac" id="rezim" title="Tmavý/světlý režim">🌙</button>
  </div>
  <header class="hlavicka">
    <div class="nadtitulek"><span class="l-cs">Osobní výběr</span><span class="l-en">Personal briefing</span></div>
    <h1><span class="l-cs">Můj přehled zpráv</span><span class="l-en">My News Digest</span></h1>
    <div class="cas"><span class="l-cs">Vygenerováno</span><span class="l-en">Generated</span> {data["vygenerovano"]}</div>
  </header>
  <nav class="stranky">
    <div class="stranky-vnitrek">
      <a class="stranka{zpravy_akt}" href="index.html"><span class="l-cs">Zprávy</span><span class="l-en">News</span></a>
      <a class="stranka{data_akt}" href="data.html"><span class="l-cs">Data</span><span class="l-en">Data</span></a>
    </div>
  </nav>
{obsah}
</div>
<script>{JS}</script>
</body>
</html>
"""


def _hezke_datum(text):
    """'2026-07-08' -> ('8. 7.', 'Jul 8'); jiný text zůstane, jak je."""
    try:
        d = datetime.strptime(text, "%Y-%m-%d")
        return f"{d.day}. {d.month}.", f"{MESICE_EN[d.month]} {d.day}"
    except ValueError:
        return text, text


# ------------------------------------------------------------
# Stránka 1: Zprávy (aktuality + karty podle témat)
# ------------------------------------------------------------
def vytvor_html(data):
    zpravy = data["zpravy"]
    e = html_mod.escape

    # Zprávy seskupené do rubrik (pořadí podle prvního výskytu,
    # což odpovídá pořadí TEMATA z config.py)
    rubriky_poradi, rubriky = [], {}
    for z in zpravy:
        if z["tema"] not in rubriky:
            rubriky_poradi.append(z["tema"])
            rubriky[z["tema"]] = []
        rubriky[z["tema"]].append(z)

    sekce_rubrik = []
    for tema in rubriky_poradi:
        barva = BARVY_TEMAT.get(tema, VYCHOZI_BARVA)
        tema_en = TEMATA_EN.get(tema, tema)
        karty = []
        for z in rubriky[tema]:
            dulezita = " karta--top" if z["dulezitost"] >= 5 else ""
            datum = z["datum"][:10] if z["datum"] else ""
            tit_en = z.get("titulek_en", z["titulek"])
            shr_en = z.get("shrnuti_en", z["shrnuti"])
            karty.append(f"""\
      <article class="karta{dulezita}" data-tema="{e(tema)}" style="--barva:{barva}">
        <h2><a href="{e(z['odkaz'])}" target="_blank" rel="noopener"><span class="l-cs">{e(z['titulek'])}</span><span class="l-en">{e(tit_en)}</span></a></h2>
        <p><span class="l-cs">{e(z['shrnuti'])}</span><span class="l-en">{e(shr_en)}</span></p>
        <footer><span class="zdroj">{e(z['zdroj'])}</span><span class="datum">{datum}</span></footer>
      </article>""")
        sekce_rubrik.append(f"""\
  <section class="rubrika" data-tema="{e(tema)}" style="--barva:{barva}">
    <h2 class="rubrika-titul"><span class="tecka"></span><span class="l-cs">{e(tema)}</span><span class="l-en">{e(tema_en)}</span><span class="rubrika-pocet">{len(karty)}</span></h2>
    <div class="mrizka">
{chr(10).join(karty)}
    </div>
  </section>""")

    tlacitka = ['<button class="filtr aktivni" data-tema="vse"><span class="l-cs">Vše</span><span class="l-en">All</span></button>']
    for t in rubriky_poradi:
        barva = BARVY_TEMAT.get(t, VYCHOZI_BARVA)
        t_en = TEMATA_EN.get(t, t)
        tlacitka.append(
            f'<button class="filtr" data-tema="{e(t)}" style="--barva:{barva}">'
            f'<span class="tecka"></span><span class="l-cs">{e(t)}</span><span class="l-en">{e(t_en)}</span></button>'
        )

    aktuality = data.get("aktuality", [])
    sekce_aktualit = ""
    if aktuality:
        vychozi = "svet" if any(a["oblast"] == "svet" for a in aktuality) else "cr"
        polozky = []
        for a in aktuality:
            chipy = "".join(
                f'<a class="zdroj-chip" href="{e(z["odkaz"])}" target="_blank" '
                f'rel="noopener">{e(z["nazev"])}</a>'
                for z in a["zdroje"]
            )
            skryta = "" if a["oblast"] == vychozi else " skryta"
            polozky.append(f"""\
      <div class="akt{skryta}" data-oblast="{a['oblast']}">
        <h3><span class="l-cs">{e(a['titulek'])}</span><span class="l-en">{e(a.get('titulek_en', a['titulek']))}</span></h3>
        <p><span class="l-cs">{e(a['shrnuti'])}</span><span class="l-en">{e(a.get('shrnuti_en', a['shrnuti']))}</span></p>
        <div class="akt-zdroje"><span class="akt-popisek"><span class="l-cs">Zdroje</span><span class="l-en">Sources</span></span>{chipy}</div>
      </div>""")
        aktivni_svet = " aktivni" if vychozi == "svet" else ""
        aktivni_cr = " aktivni" if vychozi == "cr" else ""
        sekce_aktualit = f"""
  <section class="aktuality">
    <div class="akt-hlava">
      <h2 class="akt-titul"><span class="puls"></span><span class="l-cs">Aktuality · posledních 24 hodin</span><span class="l-en">Breaking · last 24 hours</span></h2>
      <div class="akt-taby">
        <button class="akt-tab{aktivni_svet}" data-oblast="svet"><span class="l-cs">Svět</span><span class="l-en">World</span></button>
        <button class="akt-tab{aktivni_cr}" data-oblast="cr"><span class="l-cs">Česko</span><span class="l-en">Czechia</span></button>
      </div>
    </div>
{chr(10).join(polozky)}
    <div class="akt-pager" id="akt-pager">
      <button class="akt-sipka" id="akt-zpet" aria-label="Předchozí">‹</button>
      <span class="akt-stranka" id="akt-stranka">1 / 1</span>
      <button class="akt-sipka" id="akt-dal" aria-label="Další">›</button>
    </div>
  </section>"""

    obsah = f"""{sekce_aktualit}
  <nav class="filtry">
{chr(10).join("    " + t for t in tlacitka)}
  </nav>
{chr(10).join(sekce_rubrik)}"""
    return _kostra(data, "zpravy", obsah)


# ------------------------------------------------------------
# Stránka 2: Data (kalendář Co sledovat + ukazatele s grafy)
# ------------------------------------------------------------
def vytvor_data_html(data):
    e = html_mod.escape

    # Kalendář
    sledovat = data.get("sledovat", [])
    sekce_kalendar = ""
    if sledovat:
        radky = []
        for s in sledovat:
            datum_cs, datum_en = _hezke_datum(s["datum"])
            radky.append(f"""\
      <div class="udalost">
        <span class="udalost-datum"><span class="l-cs">{e(datum_cs)}</span><span class="l-en">{e(datum_en)}</span></span>
        <span class="udalost-nazev"><span class="l-cs">{e(s['nazev'])}</span><span class="l-en">{e(s['nazev_en'])}</span></span>
      </div>""")
        sekce_kalendar = f"""
  <section class="panel">
    <h2 class="sekce-titul">📅 <span class="l-cs">Co sledovat</span><span class="l-en">What to watch</span></h2>
{chr(10).join(radky)}
  </section>"""

    # Ukazatele s grafy
    trhy = data.get("trhy", [])
    sekce_trhy = ""
    if trhy:
        karty_ukazatelu = []
        for i, t in enumerate(trhy):
            zmena = ""
            if t.get("zmena_pct") is not None:
                smer = "nahoru" if t["zmena_pct"] >= 0 else "dolu"
                znak = "▲" if t["zmena_pct"] >= 0 else "▼"
                procenta = f"{abs(t['zmena_pct']):.2f}".replace(".", ",")
                zmena = f'<span class="zmena {smer}">{znak} {procenta} %</span>'
            graf = ""
            if t.get("historie"):
                graf = """
      <div class="graf-obal">
        <svg class="graf" viewBox="0 0 320 90" preserveAspectRatio="none" aria-hidden="true"></svg>
        <div class="graf-svisla"></div>
        <div class="graf-tecka"></div>
        <div class="graf-tip"></div>
      </div>
      <div class="graf-popisky"><span class="g-od"></span><span class="g-do"></span></div>
      <div class="rozsahy">
        <button class="rozsah" data-dny="22">1M</button>
        <button class="rozsah aktivni" data-dny="66">3M</button>
        <button class="rozsah" data-dny="252">1R</button>
        <button class="rozsah" data-dny="0">5R</button>
      </div>"""
            karty_ukazatelu.append(f"""\
    <article class="ukazatel" data-i="{i}" data-nazev="{e(t['nazev'])}">
      <button class="skryj" title="Skrýt ukazatel / Hide">×</button>
      <div class="ukazatel-nazev">{e(t['nazev'])}</div>
      <div class="ukazatel-radek"><span class="ukazatel-hodnota">{e(t['hodnota'])}</span>{zmena}</div>{graf}
    </article>""")
        # Historii vložíme na stránku jako JSON pro vykreslování grafů
        json_trhy = json.dumps(
            [{"historie": t.get("historie", [])} for t in trhy],
            ensure_ascii=False, separators=(",", ":"),
        ).replace("</", "<\\/")
        sekce_trhy = f"""
  <h2 class="sekce-titul">📈 <span class="l-cs">Klíčová čísla</span><span class="l-en">Key figures</span></h2>
  <main class="ukazatele">
{chr(10).join(karty_ukazatelu)}
  </main>
  <div class="skryte-obal" id="skryte-obal" style="display:none">
    <span class="akt-popisek"><span class="l-cs">Skryté (klikni pro vrácení):</span><span class="l-en">Hidden (click to restore):</span></span>
    <span id="skryte-radek"></span>
  </div>
  <p class="tip-pridani"><span class="l-cs">Nový titul přidáš řádkem v souboru
  tickery.txt a spuštěním generování.</span><span class="l-en">Add a new ticker
  by editing tickery.txt and re-running the generator.</span></p>
  <script id="trhy-data" type="application/json">{json_trhy}</script>"""

    if not sekce_kalendar and not sekce_trhy:
        sekce_kalendar = """
  <section class="panel"><p><span class="l-cs">Zatím žádná data — spusť plné generování
  (python3 generuj_web.py).</span><span class="l-en">No data yet — run the full
  generation (python3 generuj_web.py).</span></p></section>"""

    return _kostra(data, "data", sekce_kalendar + sekce_trhy)


def uloz_html(data):
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(vytvor_html(data))
    with open("data.html", "w", encoding="utf-8") as f:
        f.write(vytvor_data_html(data))
    print("Stránky uloženy: index.html (zprávy) + data.html (data a kalendář).")


if __name__ == "__main__":
    if "--jen-html" not in sys.argv:
        zpravy = stahni_vsechny_zpravy()
        print(f"\nCelkem staženo: {len(zpravy)} zpráv")
        vysledek = vyber_a_preloz(zpravy)
        uloz_data(vysledek)

    # Stránky se vždy staví z data.json
    with open("data.json", encoding="utf-8") as f:
        data = json.load(f)
    uloz_html(data)
    print("\nHotovo! Otevři index.html v prohlížeči.")

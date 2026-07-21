#!/usr/bin/env python3
"""Kronika Świata (#1520) — wire generated illustrations into swiat.html.

Idempotent: an entry that already carries a <figure class="gaz-fig"> is skipped, so
this can be re-run after regenerating a subset of the art.

  python3 scripts/embed_kronika_illus.py            # apply
  python3 scripts/embed_kronika_illus.py --dry-run  # report only
"""
import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "frontend" / "showcase" / "swiat.html"
IMG_DIR = ROOT / "frontend" / "showcase" / "assets" / "img"

# nagłówek wpisu (h4) → (plik, alt, podpis)
ENTRIES = {
    "Wolfsmark": ("loc-wolfsmark",
        "Wolfsmark — wioska górnicza pod szarymi górami",
        "Wolfsmark żyje z tego, co wyciągnie spod ziemi — i z tego, że nie schodzi za głęboko."),
    "Most Czarnej Rzeki": ("loc-most",
        "Most Czarnej Rzeki — kamienny most z komorą celną nad czarną wodą",
        "Kto chce przejść suchą nogą, płaci. Pius zapisuje każdy przejazd — i pamięta ci, których nie zapisał."),
    "Cieszburg": ("loc-cieszburg",
        "Cieszburg — spokojna wieś z kapliczką i starą studnią na placu",
        "Najspokojniejsza wieś Kresów. Albo była nią do niedawna."),
    "Zgliszcza": ("loc-zgliszcza",
        "Zgliszcza — spalona wieś, czarne kominy i masowy grób",
        "Zostały kominy jak czarne zęby i czterdzieści jeden krzyży. Nikt nie mówi głośno, co spaliło Zgliszcza."),
    "Karczma Pod Trzema Krukami": ("loc-kruki",
        "Karczma Pod Trzema Krukami — samotny zajazd na rozstajach nocą",
        "Trzy kruki na kalenicy i światło w oknach. Na Kresach to wystarczy, żeby zjechać z traktu."),
    "Pustelnia Świętego Marcina": ("loc-pustelnia",
        "Pustelnia Świętego Marcina — kapliczka, ogród ziołowy i święte źródło",
        "Jeden pustelnik, jeden ogród, jedno źródło. Najbliższa pomoc duchowa na wiele mil."),
    "Vilnograd": ("loc-vilnograd",
        "Vilnograd — stolica świata widziana zza rzeki o zmierzchu",
        "Największe miasto świata. Wszystko tu działa — pytanie tylko, dla kogo."),
    "Volhynia": ("loc-volhynia",
        "Volhynia — miasto kupieckie na skrzyżowaniu czterech traktów",
        "Cztery trakty schodzą się w jednym placu targowym. Co nie przejdzie przez Volhynię, nie przejdzie wcale."),
    "Klasztor Iskry": ("loc-iskry",
        "Klasztor Iskry — warowny klasztor Światła z wiecznym płomieniem",
        "Stąd wychodzą misje na krańce świata — i stąd patrzy inkwizycja."),
    "Bór Zmarłych / Las Czarnych Drzew": ("loc-bor-zmarlych",
        "Bór Zmarłych — las smolistoczarnych pni bez runa",
        "Granica czerni jest widoczna gołym okiem. Co roku leży dalej niż rok temu."),
    "Trzęsawiska Mgieł i Bagienna Knieja": ("loc-trzesawiska",
        "Trzęsawiska Mgieł — czarna woda, utopione drzewa i mgła",
        "Mgła leży na wodzie jak koc. To, co się pod nią rusza, nie zawsze wypływa."),
    "Step Wilków": ("loc-step-wilkow",
        "Step Wilków — bezkresna trawa, wataha na grzbiecie i kurhan",
        "Trawa po horyzont, jeden kurhan i wilki, które nigdy do niego nie wchodzą."),
    "Wyrobisko Srebrnej Żyły": ("loc-wyrobisko",
        "Wyrobisko Srebrnej Żyły — czynna kopalnia srebra na zboczu",
        "Kopalnia, która wciąż pracuje — bo trzyma się nad Linią Soli. Stukanie słychać coraz wyraźniej."),
    "Kopalnia Czarnego Hutmana": ("loc-hutman",
        "Kopalnia Czarnego Hutmana — zapieczętowany kompleks kopalniany pod śniegiem",
        "Zamknięta na łańcuch i sól dwadzieścia lat temu. Żadnych śladów w śniegu — ani do środka, ani na zewnątrz."),
    "Krzyż Gór i Lodowy Pas": ("loc-krzyz-gor",
        "Krzyż Gór — granitowe szczyty i jęzor lodowca między nimi",
        "Najwyższe pasmo świata. Wyżej jest już tylko lód — i zakaz, którego nikt nie pamięta, kto wydał."),
    "Czarne Skały": ("loc-czarne-skaly",
        "Czarne Skały — wulkaniczny stożek nad polem obsydianu i popiołu",
        "Szkło, popiół i czerwony blask w szczelinach. Nic tu nie rośnie i nic tu nie mieszka."),
    "Gorące Źródła i Karawanseraj": ("loc-gorace-zrodla",
        "Gorące Źródła — parujące baseny i karawanseraj w śnieżnej kotlinie",
        "Jedyne ciepłe miejsce w Graniach. Karawany zatrzymują się tu nawet wtedy, gdy nie muszą."),
    "Obóz Wygnańców Lodu": ("loc-wygnancy",
        "Obóz Wygnańców Lodu — koczowisko na zamarzniętej tundrze",
        "Ani murów, ani dachów. Ród, który złamał zakaz lodowca, koczuje w jego cieniu."),
    "Czarnogród": ("loc-czarnograd",
        "Czarnogród — smolisty port przy ujściu rzeki nocą",
        "Drugie miasto świata. Prawo Korony kończy się tu na linii przyboju."),
    "Zatoka Topielców": ("loc-zatoka",
        "Zatoka Topielców — piracka twierdza na skalistej wyspie",
        "Miasto-twierdza bez prawa. Cztery fotele zajęte, piąty czeka."),
    "Świątynia Pradawnych": ("loc-swiatynia",
        "Świątynia Pradawnych — wnętrze o niemożliwej geometrii nad świecącą szczeliną",
        "Wnętrze martwego boga. Pod posadzką pęknięcie sięga samego Rdzenia."),
    "Krypta Krwawego Hrabiego": ("loc-krypta",
        "Krypta Krwawego Hrabiego — grobowiec rycerza w czarnym marmurze",
        "Był rycerzem Korony, nim potargował się z Rdzeniem. Ktoś wciąż zostawia tu świece."),
    "Twierdza Bezimiennego": ("loc-twierdza",
        "Twierdza Bezimiennego — czarna forteca z otwartą bramą na popielnej równinie",
        "Brama stoi otworem. Nikt z tych, co weszli, nie wrócił."),
}

FIG = ('    <figure class="gaz-fig">\n'
       '      <img src="assets/img/{img}.webp" loading="lazy" alt="{alt}">\n'
       '      <figcaption>{cap}</figcaption>\n'
       '    </figure>\n')

# kotwica rozdziału ludu → plik banera tła nagłówka
LUDY = ["lud-ludzie", "lud-krasnoludy", "lud-elfy", "lud-pietnowani", "lud-wyspiarze"]

# tytuł nazwanej rany → (plik, alt)
RANY = {
    "Schizma elfów": ("rana-schizma",
        "Elfy w chwili rozłamu na polanie, gdzie trawa rośnie czarna"),
    "Dwieście lat wojen granicznych": ("rana-wojny",
        "Mury Strzegwachtu o świcie i uchodźcy nadciągający ze wschodu"),
    "Głębokie Bicie": ("rana-bicie",
        "Zapieczętowany wlot Kopalni Czarnego Hutmana pod śniegiem"),
    "Sztorm Wieczny": ("rana-sztorm",
        "Ściana Sztormu Wiecznego i ostatni statek uchodźców"),
}

# tytuł karty frakcji → (plik, alt)
HERBY = {
    "Korona": ("herb-korona", "Godło Korony: żelazna korona nad mieczem"),
    "Rada Czterech": ("herb-rada", "Godło Rady Czterech: cztery bezimienne maski"),
    "Świątynia Światła": ("herb-swiatlo", "Godło Świątyni Światła: promienista latarnia"),
    "Kulty Rdzenia": ("herb-kulty", "Godło kultów: pęknięty krąg, z którego sączy się mrok"),
    "Gildie kupieckie": ("herb-gildie", "Godło gildii: waga kupiecka nad monetą"),
    "Dzielnica złodziei": ("herb-zlodzieje", "Godło dzielnicy złodziei: sygnet i wytrych"),
    "Rada Piracka": ("herb-piraci", "Godło Rady Pirackiej: koło sterowe i pusty fotel"),
    "Rody krasnoludzkie": ("herb-rody", "Godło rodów: młot i kilof nad szczytem góry"),
    "Krąg Starszych i zwiadowcy": ("herb-elfy",
        "Godło Czarnoboru: drzewo w połowie żywe, w połowie zwęglone"),
    "Nieumarli i dzicz": ("herb-dzicz", "Godło dziczy: wilcza czaszka i złamane ostrze"),
}


def have(img: str) -> bool:
    return (IMG_DIR / f"{img}.webp").exists()


def wire_ludy(html: str, added: list, missing: list) -> str:
    for anchor in LUDY:
        if f'id="{anchor}" style="--lud-img' in html:
            continue
        if not have(anchor):
            missing.append(f"lud {anchor}")
            continue
        html = html.replace(
            f'<details class="lud" id="{anchor}"',
            # UWAGA: ścieżka w custom property rozwija się względem ARKUSZA CSS,
            # nie dokumentu — musi być ../img/, inaczej wychodzi assets/css/assets/img/
            f'<details class="lud" id="{anchor}" style="--lud-img:url(\'../img/{anchor}.webp\')"',
            1)
        added.append(f"baner {anchor}")
    return html


def wire_rany(html: str, added: list, missing: list) -> str:
    for tytul, (img, alt) in RANY.items():
        old = f'<div class="rana"><h4>{tytul}</h4>'
        if old not in html:
            continue  # już opakowana
        if not have(img):
            missing.append(f"rana {img}")
            continue
        new = (f'<div class="rana"><img class="rana-img" loading="lazy" '
               f'src="assets/img/{img}.webp" alt="{alt}"><div class="rana-body">'
               f'<h4>{tytul}</h4>')
        html = html.replace(old, new, 1)
        added.append(f"rana {tytul}")
    # domknięcie .rana-body dla świeżo opakowanych bloków
    html = re.sub(r'(<div class="rana"><img(?:(?!</div></div>).)*?)</p></div>(?!</div>)',
                  r'\1</p></div></div>', html, flags=re.S)
    return html


def wire_herby(html: str, added: list, missing: list) -> str:
    for tytul, (img, alt) in HERBY.items():
        old = f'<div class="codex-card"><h4>{tytul}</h4>'
        if old not in html:
            continue
        if not have(img):
            missing.append(f"herb {img}")
            continue
        new = (f'<div class="codex-card z-herb"><img class="herb" loading="lazy" '
               f'src="assets/img/{img}.webp" alt="{alt}"><div><h4>{tytul}</h4>')
        html = html.replace(old, new, 1)
        added.append(f"herb {tytul}")
    html = re.sub(r'(<div class="codex-card z-herb"><img(?:(?!</div></div>).)*?)</p></div>(?!</div>)',
                  r'\1</p></div></div>', html, flags=re.S)
    return html


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    html = PAGE.read_text(encoding="utf-8")
    added, skipped, missing = [], [], []

    html = wire_ludy(html, added, missing)
    html = wire_rany(html, added, missing)
    html = wire_herby(html, added, missing)

    # OD KOŃCA: każda wstawka wydłuża dokument, więc pozycje dopasowań policzone
    # na wejściowym HTML przestają być aktualne dla wpisów LEŻĄCYCH DALEJ. Idąc
    # wstecz modyfikujemy zawsze fragment za już przetworzonymi — offsety trzymają.
    for m in reversed(list(re.finditer(r'<article class="gaz-entry[^"]*">\s*<h4>([^<]+)', html))):
        title = re.sub(r'\s*<span.*', '', m.group(1)).strip()
        spec = ENTRIES.get(title)
        if not spec:
            continue
        img, alt, cap = spec
        start = m.start()
        end = html.find("</article>", start)
        if "gaz-fig" in html[start:end]:
            skipped.append(title)
            continue
        if not have(img):
            missing.append(f"{title} → {img}.webp")
            continue
        # figura idzie tuż przed blokiem haków, a gdy go nie ma — na koniec wpisu
        hooks = html.find('<div class="gaz-hooks">', start, end)
        pos = hooks if hooks != -1 else end
        block = FIG.format(img=img, alt=alt, cap=cap)
        html = html[:pos] + block + html[pos:]
        added.append(title)

    if added and not args.dry_run:
        PAGE.write_text(html, encoding="utf-8")

    print(f"osadzono: {len(added)}")
    for t in added:
        print(f"   + {t}")
    if skipped:
        print(f"pominięto (mają już figurę): {len(skipped)}")
    if missing:
        print(f"BRAK PLIKU: {len(missing)}")
        for t in missing:
            print(f"   ! {t}")
    if args.dry_run:
        print("(dry-run — nic nie zapisano)")


if __name__ == "__main__":
    main()

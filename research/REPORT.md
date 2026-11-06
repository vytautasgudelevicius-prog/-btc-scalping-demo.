# BTC/EUR tyrimo ataskaita — 2026-11-06

**Sprendimas: naujos strategijos nediegti.** Pelningumas nepatvirtintas. Šis darbas pateikia žvakių modelį, ne tikslų 15 sekundžių prekybos atkūrimą. Nė viena alternatyva nepasiekė iš anksto nustatyto 30 validavimo sandorių minimumo. `risk_size` palikta kaip iš anksto numatyta diagnostinė alternatyva, ne atrinkta laimėtoja. Galutinis laikotarpis po jo peržiūros nebėra nepanaudotas testas būsimiems pakeitimams.

## Kas palikta nepakeista

- `bot.py` baitų turinys sutampa su veikiančiu `39e57375c91c314809656279e846fc12f1144560`.
- Pradiniai tyrimų failai iš `e3aec9bca75e8c1a775076d580a465b759cc0f5b` palikti. Senasis `backtest.py` yra supaprastintas prototipas, šios ataskaitos skaičiavimams nenaudojamas.
- Railway diegimas, nustatymai ir SQLite failas neliesti. Nauji tyrimai yra atskiroje šakoje.
- Jokių privačių biržos raktų, pavedimų ar LIVE prekybos.

## Duomenys ir vientisumas

Oficialus šaltinis: https://support.kraken.com/articles/360047124832-downloadable-historical-ohlcvt-open-high-low-close-volume-trades-data

Oficialus `Kraken_OHLCVT_Full.zip.part00`–`part04` iš `assets.kraken.com/marketing/institutions/`. Pasirinkti tik `XBTEUR_1.csv`, `XBTEUR_240.csv`, `MANIFEST.json`, naudojant HTTP Range ir ZIP centrinį katalogą. ZIP CRC patikrinti išpakuojant; viso kelių GB archyvo SHA256 netikrintas, nes nepersiųsti kiti instrumentai. Pasirinktų pilnų CSV SHA256 yra `results.json`.

Analizės laikotarpis: **2024-10-01 00:00 UTC – 2026-09-30 23:59 UTC**, 24 mėnesiai. 1 043 812 minutinių ir 4 379 keturių valandų žvakės. Minutinių įrašų trūksta 7 388 per 5 702 tarpus; 4h intervalų trūksta vieno. Dublikatų nėra. Patikrinti didėjantys UTC epoch laikai, intervalų tinklelis, baigtinės reikšmės, OHLC ribos ir neneigiamos apimtys. Sintetinių žvakių: 0.

Kraken nurodo, kad archyvas neturi žvakių intervalams be sandorių. Tai nėra įrodymas, kad kiekvieną tarpą galima saugiai užpildyti. Modelis po tarpo reikalauja 90 ištisinių minučių naujam įėjimui; esamą poziciją uždaro pirmo kito stebėto atidarymo kaina. Tai sąmoningas konservatyvus skirtumas nuo gyvo roboto. Mokymo ir vertinimo duomenys nepermaišomi. Pakete papildomai paliktas 120 dienų indikatorių apšilimas; jis nėra įskaičiuotas į nurodytą 24 mėnesių apimtį.

## Atitikimas veikiančiam robotui

| Taisyklė | Tyrimo įgyvendinimas / riba |
|---|---|
| EMA 9/21 | 719 paskutinių užbaigtų žvakių langas; skaičiavimas patikrintas prieš bot.ema ir bot.signal |
| EMA 50/200 4h | BULL/BEAR ±0,5 % slenkstis; žvakė prieinama tik pasibaigus 4h; >=210 istorinių žvakių |
| ATR, apimtis, įėjimo kokybė | Formulės palygintos automatiniu testu su bot.py |
| Pozicijos | Iki 3, viena kryptimi, 30 % bruto ekspozicija, iki 8 įėjimų per UTC dieną |
| Kapitalas | LONG ir hipotetinio SHORT pinigų srautai, abu komisiniai, MTM kapitalas |
| Dienos riba | Nauji įėjimai stabdomi žemiau 97 % dienos pradžios kapitalo; tai negarantuoja maksimaliai 3 % nuostolio |
| Stop / tikslas / laikas | 1,2 %, 3 %, 45 min pagal laiką, ne turimų žvakių skaičių |
| Sąnaudos | 0,8 % kiekvienoje pusėje, bendras spredas 5 bps, praslydimas 2 bps kiekvienoje pusėje |
| Išėjimai | Modeliuojami minutės OHLC; jei paliesti abu lygiai, pirma stop. Atidarymo spragos vykdomos atidarymo, ne geresne stop kaina |
| Rizikos palyginimas | Kapitalo kritimas matuojamas žvakių pabaigoje, todėl neapima visų intraminutinių ekstremumų |

**Tikslus vykdymo atitikimas nepatvirtintas:** istorinių 15 sekundžių bid/ask, order book, vėlavimų ir tikro praslydimo nėra. Gyvas robotas dėl plataus spredo ar pasenusių duomenų praleidžia ir pozicijų uždarymo patikrą; to rizikos iš OHLC pilnai atkurti negalima. SHORT hipotetinis, finansavimo/skolinimo sąnaudos nepridėtos. Nėra pagrindo šį tyrimą vadinti pilnu profesionalios vykdymo sistemos patvirtinimu.

## Atskiri laikotarpiai ir variantai

Kiekvienas laikotarpis pradedamas su 1 000 € ir be pozicijų; indikatoriai apšildomi tik ankstesniais duomenimis. Mokymas 2024-10-01–2025-09-30; validavimas 2025-10-01–2026-03-31; galutinis testas 2026-04-01–2026-09-30.

Variantai nėra sudedami į vieną optimizuotą strategiją. `portfolio_risk` papildomai prie rizikinio dydžio įveda bendrą limitą; kiti pakeitimai vertinami prieš bazinį variantą. Rizika pozicijai 0,25 % kapitalo, bendra rizika 0,5 %, į skaičiavimą įtrauktos sąnaudos. ATR stop: 3×ATR, ribos 0,3–2 %; ATR tikslas max(3 %,6×ATR). Tendencijos slenkstis 1 %, likvidumas >=1× vidurkio, grynasis reward/risk >=1,5, cooldown 30 min, nepalankios dienos pauzė nuo -1,5 %. Tai fiksuoti tyrimo variantai, ne pažadas, kad jie optimalūs.

| Variantas | Mokymo pelnas € / sandoriai | Validavimo pelnas € / sandoriai |
|---|---:|---:|
| baseline | -12.619 / 12 | -14.553 / 10 |
| risk_size | -10.923 / 12 | -12.600 / 10 |
| portfolio_risk | -10.923 / 12 | -12.600 / 10 |
| atr_stop | -12.393 / 12 | -16.129 / 10 |
| atr_target | -12.619 / 12 | -14.553 / 10 |
| trend_strength | -12.207 / 11 | -14.553 / 10 |
| liquidity | -9.097 / 8 | -7.768 / 6 |
| net_reward_risk | 0.000 / 0 | 0.000 / 0 |
| cooldown | -12.619 / 12 | -14.553 / 10 |
| adverse_pause | -12.619 / 12 | -14.553 / 10 |

## Galutinis nepriklausomas testas

| Rodiklis | Bazinis modelis | Rizikinis dydis |
|---|---:|---:|
| Sandorių skaičius | 2.0000 | 2.0000 |
| Laimėjimai % | 50.0000 | 50.0000 |
| Grynasis pelnas € | -1.3236 | -1.1449 |
| Pelno faktorius | 0.0622 | 0.0622 |
| Vid. pelningas € | 0.0878 | 0.0759 |
| Vid. nuostolingas € | -1.4113 | -1.2209 |
| Didžiausias kapitalo kritimas % | 0.2346 | 0.2029 |
| Komisiniai € | 3.1852 | 2.7554 |
| Spredas ir praslydimas € | 0.1792 | 0.1550 |

Mažesnės rizikos variantas prarado mažiau dėl mažesnės ekspozicijos. Pelno faktorius iš esmės nepasikeitė. Abiejų rezultatas neigiamas ir tik po 2 sandorius: statistiškai patikimo pagerėjimo nėra. Nulinis sandorių skaičius reward/risk variante nėra pelninga strategija.

| Sąnaudų scenarijus | Bazinis neto € | Rizikinis neto € |
|---|---:|---:|
| low | -0.4280 | -0.4280 |
| base | -1.3236 | -1.1449 |
| stress | -2.4392 | -1.7678 |

Low: 0,6 % komisiniai/pusė, 2 bps spredas, 1 bps praslydimas/pusė. Base: 0,8 %, 5 bps, 2 bps. Stress: 1 %, 15 bps, 5 bps. Tai prielaidos, ne patvirtinti istoriniai tarifai ar spredai. Sąnaudų jautrumui įėjimo kokybės slenkstis paliktas toks, koks yra bot.py.

## Testai, stebėsena ir Railway

27 automatiniai testai praėjo, 0 nepraėjo. Įtraukti 4 ankstesni testai, LONG/SHORT komisinių ir kapitalo skaičiavimai, stop/target, stop-first, 45 min laikymas, priverstinis laikotarpio uždarymas, duomenų spragos, EMA atitikimas, būsimų duomenų poveikio ir neužbaigtos 4h žvakės neprieinamumo testai. SQLite migracija išbandyta tik atskiroje atminties DB: sena istorija ir nežinomi mokesčiai išsaugomi, migracija idempotentiška. Tai nėra aktyvios SQLite atsarginė kopija ar pilnas atkūrimo bandymas.

Ankstesnis GitHub Actions paleidimas `42189601075` prie `e3aec9b` sėkmingas, blokavimo nėra. Nauja CI konfigūracija tikrina ir bot.py, naują tyrimų modulį bei visus testus. Rezultatai įrašyti `tests.txt`.

Railway `62e01b01-fe0b-4776-9896-acde935bafde`: SUCCESS, versija `39e5737`, diskas `paper-state` prie `/data`. Patikros metu gauti 2026-11-06 08:51:52 UTC žurnalai: equity 998,74 €, pozicijų 0, naujoje uždarytų pozicijų statistikoje closed=0, net_pnl=0, max_drawdown=0,13 %. Tai konkretaus žurnalo momento duomenys, ne dabartinio balanso garantija. Įrašai platformoje pažymėti error, bet pats tekstas INFO — vien šis žymėjimas nėra roboto klaida.

Esama valandinė užduotis `Automation_613b12f78e38819182e35ace269109f4` papildyta naujų sutrikimų, sustojimo požymių, patvirtintos dienos ribos ir statistikos stebėsena. Grafikas nepakeistas, dublikato nesukurta. Pristatymo įrodymų nėra; patvari deduplikacija ir day_start prieinamumas nepatvirtinti. Vien teksto nurodymas nekartoti pranešimų nėra garantuota techninė deduplikacija. Valandinis tikrinimas nėra momentinis perspėjimas.

## Kas lieka ir kodėl nediegiama

1. Trūksta istorinių bid/ask ir 15 s vykdymo duomenų tiksliam atkartojimui; reikalingas atskirai patvirtintas rinkos duomenų rinkimas ir forward DEMO vertinimas.
2. Nei teigiamo nepriklausomo pelno, nei pakankamo sandorių kiekio nėra. Papildomas derinimas pagal šį holdout būtų jo panaudojimas mokymui; vėlesniam kandidatui reikės naujo nepanaudoto laikotarpio.
3. Stebėsenai dar reikia patvarios įvykių būsenos, tikro pristatymo bandymo ir day_start/health telemetrijos. Tam siūlomas vėlesnis atskiras operacinis pakeitimas; aktyvus robotas šio darbo metu nekeistas.
4. Prieš bet kokį būsimą diegimą: SQLite online backup + integrity_check ir atkūrimo bandymas atskiroje vietoje, užfiksuotas senasis diegimas ir schema, tada vartotojo atskiras patvirtinimas. Railway rodo, kad dabartinis diegimas gali būti grąžintas, bet rollback nepaleistas ir nėra DB atsarginės kopijos pakaitalas.

## Atkūrimas

```sh
pip install -r research/requirements.txt
python -m unittest discover -v
python research/download_kraken.py /absolute/path/to/data
python research/study.py /absolute/path/to/data/XBTEUR_1.csv /absolute/path/to/data/XBTEUR_240.csv
```

Dideli duomenys į GitHub neįtraukti. Atskirame duomenų pakete yra 24 mėnesiai su apšilimu, šaltinio manifestas, rezultatų JSON ir ši ataskaita. `results.json` originalių šaltinių SHA256 taikomi pilniems atsisiųstiems CSV, o ne sutrumpintiems paketo CSV.

# Aktyvaus BTC/EUR DEMO skalpinimo patikra — 2026-11-06

Sprendimas: pelningas kandidatas nerastas. Užduotis nėra galutinai užbaigta: gyvi nauji OPEN/CLOSE ir naujos pataisos diegimas nepatvirtinti.

## Istoriniai rezultatai

Kiekviena atkarpa pradedama nuo 1 000 EUR. Toliau 2026-04-01–2026-09-30; laikotarpis jau naudotas ankstesniame tyrime, todėl tai pakartotinis vertinimas, ne naujas nepriklausomas holdout.

| Variantas | Sandoriai | Per dieną | Laimėjimai % | Vid. pelnas EUR | Vid. nuostolis EUR | Neto EUR | Max DD % | PF |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 2 | 0.01 | 50.00 | 0.0878 | -1.4113 | -1.32 | 0.23 | 0.0622 |
| active | 1792 | 9.79 | 0.00 | — | -0.5301 | -950.01 | 95.00 | 0.0000 |
| active_5m | 1795 | 9.81 | 0.00 | — | -0.5293 | -950.07 | 95.01 | 0.0000 |
| active_maker | 1147 | 6.27 | 0.00 | — | -0.6678 | -765.91 | 76.59 | 0.0000 |

Visų trijų atkarpų rezultatai pateikti JSON failuose. Aktyvus variantas: 5 min cooldown, 15 min laikymas, 3 pozicijos, 16 įėjimų per UTC dieną, 10 % vienai pozicijai ir 30 % bruto ekspozicija, 3 % dienos nuostolio įėjimo stabdis. Dienos stabdis negarantuoja bendro nuostolio ribos: jis kasdien perskaičiuojamas. Po ilgo nuostolių periodo pasiekiama 5 EUR minimalaus pozicijos biudžeto riba ir prekyba beveik sustoja.

2023 m. laikotarpis rezervuotas papildomai patikrai prieš jo rezultatų peržiūrą; parametrai jam nederinti. Tai anksčiau šiuose tyrimuose nenaudotas ankstesnis laikotarpis, o ne būsimo laikotarpio forward testas.

- active: 1801 sandoriai, neto -950.03 EUR, DD 95.00 %, PF 0.000000.
- active_5m: 1800 sandoriai, neto -950.08 EUR, DD 95.01 %, PF 0.000000.
- active_maker: 1767 sandoriai, neto -891.77 EUR, DD 89.18 %, PF 0.000035.

## Sąnaudos ir vykdymas

Oficialus tarifas patikrintas 2026-11-06: https://www.kraken.com/pro/fees — spot Tier 1 maker 0,40 %, taker 0,80 % kiekvienoje pusėje. Naudotas dabartinės DEMO programos fiksuotas Tier 1 modelis; istoriniai tarifai ir automatiniai apyvartos tarifų pokyčiai neatkurti. 5 bps bendras spredas ir 2 bps praslydimas pusei yra prielaidos, ne istorinių kotiruočių matavimas.

active_maker: 0,4 % įėjimo mokestis, vienos minutės pasyvus limitas ties numanomu bid/ask, būtinas daugiau nei 1 bp kainos perėjimas per limitą; neįvykęs pavedimas atšaukiamas. Išėjimui 0,8 % taker mokestis ir praslydimas. Tai ribotas OHLC modelis: nėra eilės vietos, dalinių vykdymų, tikrų kotiruočių ar vėlavimo. Nei prisilietimas, nei trade-through realioje biržoje negarantuoja įvykdymo.

SHORT hipotetinis, be skolinimo ir finansavimo. Futures tarifai neperkeliami į BTC/EUR spot žvakes: tai būtų kitas instrumentas. Net limitinio įėjimo proxy pelningumo nepateisino.

## Duomenys ir testai

Oficialūs Kraken OHLCVT CSV: https://support.kraken.com/articles/360047124832-downloadable-historical-ohlcvt-open-high-low-close-volume-trades-data . Duomenų manifestas nurodo iki 2026-09-30. CSV turinys patikrintas dėl baigtinių reikšmių, OHLC ribų, laiko tvarkos ir dublikatų. CRC patikrintas ZIP skaitymo metu; pasirinkti CSV SHA256 pateikti active_quality.json.

1 min signalas naudoja užbaigtą žvakę; vykdymas ne anksčiau kitos žvakės. 5 min patvirtinimas tik iš pilnos penkių realių minučių grupės, prieinamos po jos pabaigos. 4h režimas prieinamas po žvakės užsidarymo. Tarpai neužpildomi; po jų 90 vientisų minučių reikalavimas ir priverstinis kitos stebėtos žvakės išėjimas yra skirtumai nuo gyvo ciklo. Stop-first OHLC modelis neatkuria 15 sekundžių vykdymo tiksliai.

33 tyrimo automatiniai testai praėjo (research/active_tests.txt); atskirai ankstesnė 9025132 operacinė pataisa turi 9 praėjusius testus ir sėkmingą GitHub CI. Testai tikrina abiejų krypčių apskaitą, sąnaudas, stop, laiką, ateities duomenų neprieinamumą 1m/4h, filtrus, limitinio pavedimo neįvykdymą ir SQLite migraciją izoliuotoje DB.

## Railway faktai ir neužbaigti darbai

Veikiantis diegimas 9b6b80da-4ddb-410a-b72b-97f8612de19e: 90eb19d, SUCCESS. Patikrintuose ciklų žurnaluose equity/cash 998,74 EUR, atvirų pozicijų 0. Nuo šio diegimo patikrinto intervalo pradžios nėra patvirtintų naujų OPEN/CLOSE. Šiandienos ankstesniame žurnale 08:21 UTC yra seno LONG uždarymas; jis nėra naujo aktyvaus varianto rezultatas.

Palyginus su 1 000 EUR pradžia bendras balanso skirtumas -1,26 EUR. Naujoje uždarytų pozicijų lentelės statistikoje closed=0/net_pnl=0, todėl šio skirtumo negalima pristatyti kaip naujos strategijos realizuoto PnL.

/data prijungtas prie paper-state patvaraus disko. Balansas matytas toks pats prieš ir po ankstesnio perkrovimo, tačiau tiesioginė SQLite kopija, integrity_check ir atkūrimo bandymas aktyviame diske šiame darbe neatlikti.

9025132 pataisa, leidžianti tikrinti išėjimus net pasenus žvakėms ar išsiplėtus spredui, jau main. Šiame tęstinume diegimo veiksmas grąžino „Cancelled — the user did not approve this action. No changes were made.“ Apėjimų nedaryta. Liko vienas staged main šakos nustatymas; naujos strategijos neruošta diegti.

Veiklos įrodymui dar reikia autorizuoto operacinės pataisos diegimo, tikros SQLite atsarginės kopijos / atkūrimo patikros ir natūralaus signalo OPEN→CLOSE ciklo. Fiktyvių sandorių neįrašyta. Pelningai strategijai reikia kitos ekonomiškai pagrįstos hipotezės ir naujo forward vertinimo; šių nuostolingų kandidatų papildomas filtrų atlaisvinimas nepateisinamas.

## Atkūrimas

python -m unittest discover -v
python -m research.run_active
VARIANTS=active_maker OUTPUT=research/maker_results.json python -m research.run_active
UNSEEN_2023=1 VARIANTS=active,active_5m,active_maker OUTPUT=research/unseen_2023_results.json python -m research.run_active

Duomenų kelias: ../market-data/XBTEUR_1.csv ir ../market-data/XBTEUR_240.csv.

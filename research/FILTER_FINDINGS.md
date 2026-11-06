# Filtrų diagnostika — 2026-11-06

Tęsinys nuo 0fc44a1. Strategijos parametrai nekeisti. Analizuoti tik mokymo
ir validavimo laikotarpiai; galutinis testas neįtrauktas net į indikatorių skaičiavimą.

| Nuosekliai pritaikytas filtras | Mokymas | Validavimas |
|---|---:|---:|
| EMA susikirtimas | 22 198 | 11 727 |
| Sutampa 4h režimas | 6 611 | 3 672 |
| Vientisi duomenys ir kita vykdymo minutė | 5 285 | 3 258 |
| Valandos diapazonas bent 2,14 % | 110 | 62 |
| Kryptinis valandos pokytis bent 0,4 % | 36 | 24 |
| ATR ribos | 36 | 24 |
| Apimtis | 13 | 10 |

Pagal šią filtrų eilę didžiausias sumažėjimas po duomenų vientisumo patikros
yra 2,14 % valandos diapazono reikalavimas: atmetama apie 98 % likusių signalų.
Tai paaiškina mažą aktyvumą, bet neįrodo, kad slenksčio mažinimas pagerintų pelną.
Filtrai priklausomi vienas nuo kito; tai nėra atskirų filtrų priežastinio poveikio testas.
13 ir 10 yra įėjimo kandidatai, ne sandoriai: čia netaikomi portfelio, dienos,
cooldown ir vykdymo apribojimai. Ankstesnis bazinis modelis turėjo 12 ir 10 sandorių.

Kitas pagrįstas tyrimo žingsnis: iš anksto apibrėžti alternatyvią įėjimo hipotezę
ir sąnaudų modelį, tirti tik vystymo duomenis, o galutiniam vertinimui naudoti naują
nepanaudotą laikotarpį arba būsimus DEMO duomenis. Vien mažesnis nuostolis dėl
mažesnės pozicijos nėra strategijos pranašumas. Diegti pelningą strategiją pagrindo nėra.

Atkūrimas iš ankstesnio duomenų paketo, paleidžiant saugyklos šaknyje:

```sh
python -m research.filter_diagnostics /path/BTC_EUR_1m.csv /path/BTC_EUR_4h.csv
python -m unittest discover -v
```

Aktyvus Railway robotas ir jo SQLite istorija šiuo tęsiniu nepakeisti.

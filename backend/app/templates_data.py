"""Predefined maintenance templates, per asset kind.

Each template is a named bundle of components and tasks. Applying a template to
an asset creates the components and tasks in the user's language.
Edit freely: add your own bundles here.

Task tuple: (title_en, title_no, interval_value, interval_unit, component key or None[, "MM-DD"])
The Italian titles are in TASK_TITLES_IT below, keyed by the English title (so the tuples stay short).
Names and components carry all three languages: {"en": …, "no": …, "it": …}.
The optional "MM-DD" pins seasonal jobs (tyres, antifouling, frost) to the next such date
instead of the start date chosen when applying the template.
"""
from .lang import norm

TEMPLATES = {
    "home": [
        {
            "key": "house_basic",
            "name": {"en": "House – basics", "no": "Hus – grunnleggende", "it": "Casa – base"},
            "components": {
                "smoke": {"en": "Smoke detectors", "no": "Røykvarslere", "it": "Rilevatori di fumo"},
                "gutters": {"en": "Gutters & downpipes", "no": "Takrenner og nedløp", "it": "Grondaie e pluviali"},
                "roof": {"en": "Roof", "no": "Tak", "it": "Tetto"},
                "waterheater": {"en": "Water heater", "no": "Varmtvannsbereder", "it": "Scaldabagno"},
                "drains": {"en": "Drains", "no": "Sluk", "it": "Scarichi"},
                "extinguisher": {"en": "Fire extinguisher", "no": "Brannslukker", "it": "Estintore"},
            },
            "tasks": [
                ("Test smoke detectors", "Test røykvarslere", 3, "months", "smoke"),
                ("Replace smoke detector batteries", "Bytt batteri i røykvarslere", 1, "years", "smoke"),
                ("Clean gutters", "Rens takrenner", 6, "months", "gutters", "10-15"),
                ("Clear roof and balcony drains", "Rens sluk på tak og balkong", 6, "months", "gutters", "05-01"),
                ("Spring roof check", "Vårsjekk av taket", 1, "years", "roof", "04-20"),
                ("Autumn roof check before winter", "Høstsjekk av taket før vinteren", 1, "years", "roof", "09-15"),
                ("Check water heater safety valve", "Sjekk sikkerhetsventil på bereder", 1, "years", "waterheater"),
                ("Clean drains", "Rens sluk", 3, "months", "drains"),
                ("Check fire extinguisher pressure", "Sjekk trykk på brannslukker", 1, "years", "extinguisher"),
            ],
        },
        {
            "key": "heat_pump",
            "name": {"en": "Air-to-air heat pump", "no": "Luft-til-luft varmepumpe", "it": "Pompa di calore aria-aria"},
            "components": {"hp": {"en": "Heat pump", "no": "Varmepumpe", "it": "Pompa di calore"}},
            "tasks": [
                ("Clean heat pump indoor filters", "Rens filtre i innedel", 1, "months", "hp"),
                ("Clean outdoor unit and check drain", "Rens utedel og sjekk drenering", 6, "months", "hp", "10-01"),
                ("Professional heat pump service", "Service av varmepumpe (fagperson)", 2, "years", "hp"),
                ("Winter check: ice under the outdoor unit", "Vintersjekk: is under utedelen", 1, "years", "hp", "01-15"),
            ],
        },
        {
            "key": "exterior_check",
            "name": {"en": "Exterior – house check", "no": "Hussjekk ute", "it": "Controllo esterno della casa"},
            "components": {
                "facade": {"en": "Façade & cladding", "no": "Fasade og kledning", "it": "Facciata e rivestimento"},
                "gutters": {"en": "Gutters & downpipes", "no": "Takrenner og nedløp", "it": "Grondaie e pluviali"},
                "foundation": {"en": "Foundation & drainage", "no": "Grunnmur og drenering", "it": "Fondazioni e drenaggio"},
            },
            "tasks": [
                ("Check downpipes and icicles", "Sjekk taknedløp og istapper", 1, "years", "gutters", "01-15"),
                ("Check cladding near the ground", "Sjekk kledningen nær bakken", 1, "years", "facade", "02-15"),
                ("Look for black mould on the walls", "Se etter svertesopp på veggene", 1, "years", "facade", "03-01"),
                ("Wash the façade", "Vask husveggen", 1, "years", "facade", "05-15"),
                ("Check drainage around the house", "Sjekk dreneringen rundt huset", 1, "years", "foundation", "09-01"),
                ("Seal mouse entry points", "Tett åpninger mot mus", 1, "years", "foundation", "09-15"),
            ],
        },
        {
            "key": "crawl_space",
            "name": {"en": "Crawl space", "no": "Krypkjeller", "it": "Vespaio"},
            "components": {"crawl": {"en": "Crawl space", "no": "Krypkjeller", "it": "Vespaio"}},
            "tasks": [
                ("Inspect crawl space – spring", "Inspiser krypkjelleren – vår", 1, "years", "crawl", "04-01"),
                ("Close crawl-space vents for summer", "Steng ventilene i krypkjelleren for sommeren", 1, "years", "crawl", "05-15"),
                ("Open crawl-space vents for winter", "Åpne ventilene i krypkjelleren for vinteren", 1, "years", "crawl", "09-20"),
                ("Inspect crawl space – autumn", "Inspiser krypkjelleren – høst", 1, "years", "crawl", "10-15"),
            ],
        },
        {
            "key": "radon",
            "name": {"en": "Radon", "no": "Radon", "it": "Radon"},
            "components": {},
            "tasks": [
                ("Measure radon (long-term, winter)", "Mål radon (langtidsmåling, vinter)", 5, "years", None, "10-15"),
            ],
        },
        {
            "key": "water_electrical",
            "name": {"en": "Indoors – water & electrical", "no": "Inne – vann og elektrisk", "it": "Interni – acqua ed elettricità"},
            "components": {},
            "tasks": [
                ("Check washing machine and dishwasher hoses", "Sjekk slanger til vaskemaskin og oppvaskmaskin", 1, "years", None, "06-15"),
                ("Close the main water valve before holidays", "Steng hovedstoppekranen før ferien", 1, "years", None, "06-25"),
                ("Look over sockets and switches", "Se over stikkontakter og brytere", 1, "years", None, "07-15"),
            ],
        },
        {
            "key": "fireplace",
            "name": {"en": "Fireplace & wood stove", "no": "Peis og vedovn", "it": "Camino e stufa a legna"},
            "components": {"stove": {"en": "Fireplace / stove", "no": "Peis / vedovn", "it": "Camino / stufa"}},
            "tasks": [
                ("Sweep chimney / check fireplace", "Feie pipe / sjekk ildsted", 1, "years", "stove", "09-01"),
                ("Check draught before the heating season", "Sjekk trekken før fyringssesongen", 1, "years", "stove", "09-15"),
                ("Store firewood dry and ventilated", "Lagre veden tørt og luftig", 1, "years", None, "10-01"),
            ],
        },
        {
            "key": "ventilation",
            "name": {"en": "Balanced ventilation", "no": "Balansert ventilasjon", "it": "Ventilazione meccanica"},
            "components": {"vent": {"en": "Ventilation unit", "no": "Ventilasjonsaggregat", "it": "Unità di ventilazione"}},
            "tasks": [
                ("Replace ventilation filters", "Bytt filter i ventilasjonsanlegg", 6, "months", "vent"),
                ("Clean kitchen hood filter", "Rens filter i kjøkkenvifte", 3, "months", None),
            ],
        },
        {
            "key": "garden",
            "name": {"en": "Garden & outdoors", "no": "Hage og utendørs", "it": "Giardino ed esterni"},
            "components": {},
            "tasks": [
                ("Turn off outdoor water before frost", "Steng utekran før frost", 1, "years", None, "10-20"),
                ("Treat terrace / deck", "Behandle terrasse", 2, "years", None, "06-01"),
                ("Service lawn mower", "Service på gressklipper", 1, "years", None, "04-01"),
            ],
        },
    ],
    "car": [
        {
            "key": "car_ev",
            "name": {"en": "Electric car", "no": "Elbil", "it": "Auto elettrica"},
            "components": {
                "tyres": {"en": "Tyres", "no": "Dekk", "it": "Pneumatici"},
                "cabin": {"en": "Cabin filter", "no": "Kupéfilter", "it": "Filtro abitacolo"},
                "brakes": {"en": "Brakes", "no": "Bremser", "it": "Freni"},
            },
            "tasks": [
                ("Swap to winter tyres", "Bytt til vinterdekk", 1, "years", "tyres", "10-25"),
                ("Swap to summer tyres", "Bytt til sommerdekk", 1, "years", "tyres", "04-15"),
                ("Check tyre pressure", "Sjekk dekktrykk", 1, "months", "tyres"),
                ("Replace cabin filter", "Bytt kupéfilter", 1, "years", "cabin"),
                ("Brake service / brake fluid", "Bremseservice / bremsevæske", 2, "years", "brakes"),
                ("Annual service", "Årlig service", 1, "years", None),
                ("EU inspection (EU-kontroll)", "EU-kontroll", 2, "years", None),
            ],
        },
        {
            "key": "car_ice",
            "name": {"en": "Petrol / diesel car", "no": "Bensin- / dieselbil", "it": "Auto benzina / diesel"},
            "components": {
                "engine": {"en": "Engine", "no": "Motor", "it": "Motore"},
                "tyres": {"en": "Tyres", "no": "Dekk", "it": "Pneumatici"},
            },
            "tasks": [
                ("Oil and oil filter change", "Bytt olje og oljefilter", 1, "years", "engine"),
                ("Replace air filter", "Bytt luftfilter", 2, "years", "engine"),
                ("Swap to winter tyres", "Bytt til vinterdekk", 1, "years", "tyres", "10-25"),
                ("Swap to summer tyres", "Bytt til sommerdekk", 1, "years", "tyres", "04-15"),
                ("EU inspection (EU-kontroll)", "EU-kontroll", 2, "years", None),
            ],
        },
    ],
    "boat": [
        {
            "key": "boat_outboard",
            "name": {"en": "Boat with outboard", "no": "Båt med påhengsmotor", "it": "Barca con fuoribordo"},
            "components": {
                "engine": {"en": "Outboard engine", "no": "Påhengsmotor", "it": "Motore fuoribordo"},
                "hull": {"en": "Hull", "no": "Skrog", "it": "Scafo"},
                "safety": {"en": "Safety equipment", "no": "Sikkerhetsutstyr", "it": "Dotazioni di sicurezza"},
            },
            "tasks": [
                ("Change gear oil", "Bytt girolje", 1, "years", "engine"),
                ("Replace impeller", "Bytt impeller", 2, "years", "engine"),
                ("Winterise engine", "Vinterlagring av motor", 1, "years", "engine", "10-15"),
                ("Antifouling", "Bunnstoff", 1, "years", "hull", "04-15"),
                ("Replace anodes", "Bytt anoder", 1, "years", "hull", "04-15"),
                ("Check life jackets and flares", "Sjekk redningsvester og nødbluss", 1, "years", "safety", "05-01"),
            ],
        },
    ],
    "cabin": [
        {
            "key": "cabin_basic",
            "name": {"en": "Cabin – season", "no": "Hytte – sesong", "it": "Baita – stagione"},
            "components": {},
            "tasks": [
                ("Drain water before winter", "Tøm vann før vinteren", 1, "years", None, "10-15"),
                ("Sweep chimney / check fireplace", "Feie pipe / sjekk ildsted", 1, "years", None),
                ("Check roof after snow season", "Sjekk tak etter snøsesong", 1, "years", None, "04-15"),
            ],
        },
    ],
    "bicycle": [
        {
            "key": "bike_basic",
            "name": {"en": "Bicycle – basics", "no": "Sykkel – grunnleggende", "it": "Bici – base"},
            "components": {
                "chain": {"en": "Chain & gears", "no": "Kjede og gir", "it": "Catena e cambio"},
                "brakes": {"en": "Brakes", "no": "Bremser", "it": "Freni"},
                "tyres": {"en": "Tyres", "no": "Dekk", "it": "Pneumatici"},
            },
            "tasks": [
                ("Clean and lube the chain", "Rens og smør kjedet", 1, "months", "chain"),
                ("Check tyre pressure", "Sjekk dekktrykk", 2, "weeks", "tyres"),
                ("Check brakes and brake pads", "Sjekk bremser og bremseklosser", 3, "months", "brakes"),
                ("Check bolts, quick releases and spokes", "Sjekk skruer, hurtigkoblinger og eiker", 3, "months", None),
                ("Spring service at bike shop", "Vårservice hos sykkelverksted", 1, "years", None, "04-01"),
            ],
        },
        {
            "key": "bike_winter",
            "name": {"en": "Winter cycling", "no": "Vintersykling", "it": "Bici d'inverno"},
            "components": {"tyres": {"en": "Tyres", "no": "Dekk", "it": "Pneumatici"}},
            "tasks": [
                ("Fit studded tyres", "Bytt til piggdekk", 1, "years", "tyres", "11-01"),
                ("Take off studded tyres", "Bytt tilbake til sommerdekk", 1, "years", "tyres", "04-15"),
                ("Rinse off road salt", "Skyll av veisalt", 2, "weeks", None),
            ],
        },
        {
            "key": "bike_electric",
            "name": {"en": "E-bike", "no": "Elsykkel", "it": "Bici elettrica"},
            "components": {"battery": {"en": "Battery & motor", "no": "Batteri og motor", "it": "Batteria e motore"}},
            "tasks": [
                ("Clean and check battery contacts", "Rens og sjekk batterikontakter", 6, "months", "battery"),
                ("Charge battery in winter storage (30–60 %)", "Lad batteriet i vinteropplag (30–60 %)", 1, "months", "battery"),
                ("Software update and motor check", "Programvareoppdatering og sjekk av motor", 1, "years", "battery", "04-01"),
            ],
        },
    ],
    "motorcycle": [
        {
            "key": "mc_basic",
            "name": {"en": "Motorcycle", "no": "Motorsykkel", "it": "Moto"},
            "components": {
                "engine": {"en": "Engine", "no": "Motor", "it": "Motore"},
                "chain": {"en": "Chain & sprockets", "no": "Kjede og tannhjul", "it": "Catena e corone"},
                "tyres": {"en": "Tyres", "no": "Dekk", "it": "Pneumatici"},
                "brakes": {"en": "Brakes", "no": "Bremser", "it": "Freni"},
                "battery": {"en": "Battery", "no": "Batteri", "it": "Batteria"},
            },
            "tasks": [
                ("Spring check before the season", "Vårsjekk før sesongen", 1, "years", None, "04-01"),
                ("Oil and oil filter change", "Bytt olje og oljefilter", 1, "years", "engine", "04-01"),
                ("Clean, lube and tension the chain", "Rens, smør og stram kjedet", 1, "months", "chain"),
                ("Check tyre pressure and tread", "Sjekk dekktrykk og mønsterdybde", 1, "months", "tyres"),
                ("Change brake fluid", "Bytt bremsevæske", 2, "years", "brakes"),
                ("Prepare for winter storage", "Klargjør for vinterlagring", 1, "years", None, "10-15"),
                ("Battery on maintenance charger", "Sett batteriet på vedlikeholdslader", 1, "years", "battery", "10-15"),
                ("EU inspection (EU-kontroll)", "EU-kontroll", 2, "years", None),
            ],
        },
    ],
    "scooter": [
        {
            "key": "scooter_basic",
            "name": {"en": "Electric scooter", "no": "Elsparkesykkel", "it": "Monopattino elettrico"},
            "components": {
                "battery": {"en": "Battery", "no": "Batteri", "it": "Batteria"},
                "tyres": {"en": "Tyres", "no": "Dekk", "it": "Pneumatici"},
                "brakes": {"en": "Brakes", "no": "Bremser", "it": "Freni"},
            },
            "tasks": [
                ("Check tyre pressure", "Sjekk dekktrykk", 2, "weeks", "tyres"),
                ("Check and adjust brakes", "Sjekk og juster bremsene", 1, "months", "brakes"),
                ("Tighten screws and check folding mechanism", "Stram skruer og sjekk sammenleggingen", 1, "months", None),
                ("Clean and check for damage and cracks", "Rengjør og sjekk for skader og sprekker", 3, "months", None),
                ("Check for software updates in the app", "Sjekk programvareoppdatering i appen", 3, "months", None),
                ("Charge battery in winter storage", "Lad batteriet i vinteropplag", 1, "months", "battery"),
                ("Check lights and bell before winter", "Sjekk lys og ringeklokke før vinteren", 1, "years", None, "10-01"),
            ],
        },
    ],
    "other": [],
}

# English task title -> Italian
TASK_TITLES_IT = {
    "Test smoke detectors": "Prova i rilevatori di fumo",
    "Replace smoke detector batteries": "Cambia le batterie dei rilevatori di fumo",
    "Clean gutters": "Pulisci le grondaie",
    "Clear roof and balcony drains": "Pulisci gli scarichi del tetto e del balcone",
    "Spring roof check": "Controllo primaverile del tetto",
    "Autumn roof check before winter": "Controllo autunnale del tetto prima dell'inverno",
    "Winter check: ice under the outdoor unit": "Controllo invernale: ghiaccio sotto l'unità esterna",
    "Check downpipes and icicles": "Controlla pluviali e ghiaccioli",
    "Check cladding near the ground": "Controlla il rivestimento vicino al terreno",
    "Look for black mould on the walls": "Cerca muffa nera sulle pareti esterne",
    "Wash the façade": "Lava la facciata",
    "Check drainage around the house": "Controlla il drenaggio intorno alla casa",
    "Seal mouse entry points": "Chiudi i passaggi dei topi",
    "Inspect crawl space – spring": "Ispeziona il vespaio – primavera",
    "Close crawl-space vents for summer": "Chiudi le prese d'aria del vespaio per l'estate",
    "Open crawl-space vents for winter": "Apri le prese d'aria del vespaio per l'inverno",
    "Inspect crawl space – autumn": "Ispeziona il vespaio – autunno",
    "Measure radon (long-term, winter)": "Misura il radon (lungo periodo, in inverno)",
    "Check washing machine and dishwasher hoses": "Controlla i tubi di lavatrice e lavastoviglie",
    "Close the main water valve before holidays": "Chiudi il rubinetto generale prima delle vacanze",
    "Look over sockets and switches": "Controlla prese e interruttori",
    "Check draught before the heating season": "Controlla il tiraggio prima della stagione di riscaldamento",
    "Store firewood dry and ventilated": "Conserva la legna all'asciutto e ventilata",
    "Check water heater safety valve": "Controlla la valvola di sicurezza dello scaldabagno",
    "Clean drains": "Pulisci gli scarichi",
    "Check fire extinguisher pressure": "Controlla la pressione dell'estintore",
    "Clean heat pump indoor filters": "Pulisci i filtri dell'unità interna",
    "Clean outdoor unit and check drain": "Pulisci l'unità esterna e controlla lo scarico della condensa",
    "Professional heat pump service": "Manutenzione della pompa di calore (tecnico)",
    "Replace ventilation filters": "Cambia i filtri della ventilazione",
    "Clean kitchen hood filter": "Pulisci il filtro della cappa",
    "Turn off outdoor water before frost": "Chiudi l'acqua esterna prima del gelo",
    "Treat terrace / deck": "Tratta la terrazza / il deck",
    "Service lawn mower": "Manutenzione del tosaerba",
    "Swap to winter tyres": "Monta le gomme invernali",
    "Swap to summer tyres": "Monta le gomme estive",
    "Check tyre pressure": "Controlla la pressione delle gomme",
    "Replace cabin filter": "Cambia il filtro abitacolo",
    "Brake service / brake fluid": "Revisione freni / liquido freni",
    "Annual service": "Tagliando annuale",
    "EU inspection (EU-kontroll)": "Revisione (EU-kontroll)",
    "Oil and oil filter change": "Cambio olio e filtro olio",
    "Replace air filter": "Cambia il filtro aria",
    "Change gear oil": "Cambia l'olio del piede",
    "Replace impeller": "Cambia la girante",
    "Winterise engine": "Rimessaggio invernale del motore",
    "Antifouling": "Antivegetativa",
    "Replace anodes": "Cambia gli anodi",
    "Check life jackets and flares": "Controlla giubbotti di salvataggio e razzi",
    "Drain water before winter": "Svuota l'acqua prima dell'inverno",
    "Sweep chimney / check fireplace": "Pulisci la canna fumaria / controlla il camino",
    "Check roof after snow season": "Controlla il tetto dopo la stagione della neve",
    "Clean and lube the chain": "Pulisci e lubrifica la catena",
    "Check brakes and brake pads": "Controlla freni e pastiglie",
    "Check bolts, quick releases and spokes": "Controlla viti, sganci rapidi e raggi",
    "Spring service at bike shop": "Revisione primaverile dal ciclista",
    "Fit studded tyres": "Monta le gomme chiodate",
    "Take off studded tyres": "Togli le gomme chiodate",
    "Rinse off road salt": "Sciacqua via il sale stradale",
    "Clean and check battery contacts": "Pulisci e controlla i contatti della batteria",
    "Charge battery in winter storage (30–60 %)": "Ricarica la batteria durante il rimessaggio (30–60 %)",
    "Software update and motor check": "Aggiornamento software e controllo del motore",
    "Spring check before the season": "Controllo primaverile prima della stagione",
    "Clean, lube and tension the chain": "Pulisci, lubrifica e tendi la catena",
    "Check tyre pressure and tread": "Controlla pressione e battistrada delle gomme",
    "Change brake fluid": "Cambia il liquido dei freni",
    "Prepare for winter storage": "Prepara il rimessaggio invernale",
    "Battery on maintenance charger": "Metti la batteria sul mantenitore di carica",
    "Check and adjust brakes": "Controlla e regola i freni",
    "Tighten screws and check folding mechanism": "Stringi le viti e controlla il meccanismo di chiusura",
    "Clean and check for damage and cracks": "Pulisci e controlla danni e crepe",
    "Check for software updates in the app": "Controlla gli aggiornamenti software nell'app",
    "Charge battery in winter storage": "Ricarica la batteria durante il rimessaggio",
    "Check lights and bell before winter": "Controlla luci e campanello prima dell'inverno",
}


# The crawl-space bundle also fits cabins (same tasks, own key).
TEMPLATES["cabin"].append({**next(t for t in TEMPLATES["home"] if t["key"] == "crawl_space"), "key": "cabin_crawl_space"})


# English task title -> what to check, in en / no / it. Saved as the task's description when applied.
# Written for TotalMaint; the intervals follow common Norwegian advice (Huseierne, DSA for radon).
TASK_DESCRIPTIONS = {
    "Clean gutters": {
        "en": "Clear leaves and debris so rainwater runs off. Twice a year is the minimum; with big trees near the house, add extra rounds while the leaves fall.",
        "no": "Fjern løv og rusk så regnvannet renner unna. Minst to ganger i året; har du store trær nær huset, ta flere runder mens løvet faller.",
        "it": "Togli foglie e detriti perché l'acqua piovana defluisca. Almeno due volte l'anno; con alberi grandi vicino a casa, aggiungi altri giri durante la caduta delle foglie.",
    },
    "Clear roof and balcony drains": {
        "en": "Clean the drains on flat roofs, balconies and roof terraces. Drains can hide under decking or raised tiles: lift them to check and clean underneath.",
        "no": "Rens sluk på flate tak, balkonger og takterrasser. Sluket kan ligge under terrassegulv eller heller: løft dem opp, sjekk og rengjør under.",
        "it": "Pulisci gli scarichi di tetti piani, balconi e terrazze. Lo scarico può essere sotto il pavimento della terrazza o le piastrelle sollevate: alzale, controlla e pulisci sotto.",
    },
    "Spring roof check": {
        "en": "After winter: look for cracked or missing tiles and gaps between sheets, check snow guards and their fixings, flashings along the edges and around the chimney, vents and skylights. Flat roof: water must drain off; clean drains and outlets. Check from the ground (binoculars, drone) if you are not safe at height.",
        "no": "Etter vinteren: se etter sprukne eller manglende takstein og glipper mellom plater, sjekk snøfangere og festene, beslag langs kantene og rundt pipe, lufting og takvindu. Flatt tak: vannet må renne unna; rens sluk og nedløp. Sjekk fra bakken (kikkert, drone) hvis du ikke er trygg i høyden.",
        "it": "Dopo l'inverno: cerca tegole crepate o mancanti e fessure tra le lastre, controlla i paraneve e i loro fissaggi, le lattonerie lungo i bordi e intorno a camino, sfiati e lucernari. Tetto piano: l'acqua deve defluire; pulisci scarichi e bocchettoni. Controlla da terra (binocolo, drone) se non sei sicuro in altezza.",
    },
    "Autumn roof check before winter": {
        "en": "Replace broken tiles, look for gaps in the covering, and on shingle or felt roofs for spots where it has lifted (blisters). Check around all penetrations and flashings for rust or cracks, and that gutters are clear.",
        "no": "Bytt knust takstein, se etter glipper i tekkingen, og på shingel eller takpapp etter områder som har løsnet (blærer). Sjekk rundt alle gjennomføringer og beslag for rust eller sprekker, og at takrennene er rene.",
        "it": "Sostituisci le tegole rotte, cerca fessure nella copertura e, su tegole bituminose o guaina, punti che si sono staccati (bolle). Controlla intorno a tutti gli attraversamenti e le lattonerie per ruggine o crepe, e che le grondaie siano pulite.",
    },
    "Winter check: ice under the outdoor unit": {
        "en": "Defrost water from the outdoor unit must not run down the wall or build an ice mound into the unit. Lead it away, e.g. with a heated drip tray, and check the unit hangs high enough.",
        "no": "Avrimingsvannet fra utedelen skal ikke renne mot veggen eller bygge en issvull opp i utedelen. Led det bort, f.eks. med dryppanne med varmekabel, og sjekk at utedelen henger høyt nok.",
        "it": "L'acqua di sbrinamento dell'unità esterna non deve scorrere sul muro né formare un cumulo di ghiaccio che arriva all'unità. Portala lontano, ad esempio con una vaschetta riscaldata, e controlla che l'unità sia abbastanza in alto.",
    },
    "Clean outdoor unit and check drain": {
        "en": "Remove leaves and dirt from the outdoor unit, check that condensate drains away from the wall, and that the unit stands level.",
        "no": "Fjern løv og skitt fra utedelen, sjekk at kondensvannet ledes bort fra veggen, og at utedelen står i vater.",
        "it": "Togli foglie e sporco dall'unità esterna, controlla che la condensa venga portata lontano dal muro e che l'unità sia in bolla.",
    },
    "Check downpipes and icicles": {
        "en": "Make sure downpipes are not blocked by leaves, snow or ice, or meltwater will cause leaks and frost damage. Many icicles in steady cold weather point to heat loss through the roof: consider more insulation.",
        "no": "Sjekk at nedløpene ikke er tette av løv, snø eller is, ellers gir smeltevannet lekkasjer og frostskader. Mange istapper i stabil kulde tyder på varmetap gjennom taket: vurder etterisolering.",
        "it": "Controlla che i pluviali non siano ostruiti da foglie, neve o ghiaccio, altrimenti l'acqua di disgelo causa infiltrazioni e danni da gelo. Molti ghiaccioli con freddo costante indicano dispersione di calore dal tetto: valuta più isolamento.",
    },
    "Check cladding near the ground": {
        "en": "Look closely at the lowest boards and those not sheltered by the roof overhang. Soft wood (a screwdriver goes in easily) means rot: plan the repair and book a tradesperson early.",
        "no": "Se nøye på de nederste bordene og de som ikke er beskyttet av takutstikket. Mykt treverk (skrutrekkeren går lett inn) betyr råte: planlegg utbedring og bestill håndverker tidlig.",
        "it": "Guarda bene le assi più basse e quelle non protette dallo sporto del tetto. Legno morbido (il cacciavite entra facilmente) vuol dire marciume: pianifica la riparazione e prenota presto un artigiano.",
    },
    "Look for black mould on the walls": {
        "en": "Black spots on light walls and white details are usually black mould. It is not dangerous for the house, but it starts breaking down the wood. Note where it is so you can wash those areas and trim vegetation in spring.",
        "no": "Svarte prikker på lyse vegger og hvite detaljer er som regel svertesopp. Den er ikke farlig for huset, men starter nedbrytningen av treverket. Noter hvor den er, så du kan vaske og beskjære vegetasjon til våren.",
        "it": "Puntini neri su pareti chiare e dettagli bianchi sono di solito muffa nera. Non è pericolosa per la casa, ma avvia il degrado del legno. Annota dove si trova per lavare quelle zone e potare la vegetazione in primavera.",
    },
    "Wash the façade": {
        "en": "Wash the walls with a mould-killing cleaner where needed. While washing, look for flaking or cracked paint and small damage that should be touched up now.",
        "no": "Vask veggene, med soppdrepende middel der det trengs. Se samtidig etter flassende eller sprukken maling og småskader som bør utbedres nå.",
        "it": "Lava le pareti, con un prodotto antimuffa dove serve. Intanto cerca vernice che si sfoglia o crepata e piccoli danni da sistemare subito.",
    },
    "Check drainage around the house": {
        "en": "Ground should slope away from the foundation, and roof water should be led away from the wall. Look for cracks in the foundation and take photos to follow them over time.",
        "no": "Terrenget skal falle bort fra grunnmuren, og takvannet skal ledes bort fra veggen. Se etter sprekker i grunnmuren og ta bilder så du kan følge dem over tid.",
        "it": "Il terreno deve scendere lontano dalle fondazioni e l'acqua del tetto va portata lontano dal muro. Cerca crepe nelle fondazioni e fotografale per seguirle nel tempo.",
    },
    "Seal mouse entry points": {
        "en": "Mice get in through gaps of about 6 mm. Check corner boxes and the joint between foundation and cladding; a phone camera held under the boards helps. Seal with steel wool or a mouse brush.",
        "no": "Mus kommer inn gjennom glipper på ca. 6 mm. Sjekk hjørnekasser og overgangen mellom mur og kledning; mobilkameraet under bordene hjelper. Tett med stålull eller musebørste.",
        "it": "I topi entrano da fessure di circa 6 mm. Controlla gli angoli e il punto tra fondazione e rivestimento; la fotocamera del telefono sotto le assi aiuta. Chiudi con lana d'acciaio o spazzolino antitopo.",
    },
    "Inspect crawl space – spring": {
        "en": "Bring a torch, mask and knife. Look for condensation on the walls, water on the ground, mould on surfaces and a musty smell. Push the knife into the timber: if it goes in easily, there may be rot. Target: wood moisture under 20 %, relative humidity under 70 %.",
        "no": "Ta med lommelykt, maske og kniv. Se etter kondens på muren, vann på grunnen, muggsopp på overflater og mugglukt. Stikk kniven i treverket: går den lett inn, kan det være råte. Mål: fukt i treverk under 20 %, relativ luftfuktighet under 70 %.",
        "it": "Porta torcia, mascherina e coltello. Cerca condensa sui muri, acqua sul terreno, muffa sulle superfici e odore di muffa. Infila il coltello nel legno: se entra facilmente, può esserci marciume. Obiettivo: umidità del legno sotto il 20 %, umidità relativa sotto il 70 %.",
    },
    "Inspect crawl space – autumn": {
        "en": "Same round as in spring, before the snow: condensation, water, mould, smell and soft timber. Remove anything stored down there, and check that the vents are open and clean from the inside.",
        "no": "Samme runde som om våren, før snøen: kondens, vann, mugg, lukt og mykt treverk. Fjern det som er lagret der nede, og sjekk at ventilene er åpne og rene fra innsiden.",
        "it": "Stesso giro della primavera, prima della neve: condensa, acqua, muffa, odore e legno morbido. Togli quello che c'è depositato e controlla dall'interno che le prese d'aria siano aperte e pulite.",
    },
    "Close crawl-space vents for summer": {
        "en": "Warm, humid summer air condenses on the cold walls (summer condensation). Close the vents for the summer half of the year.",
        "no": "Varm og fuktig sommerluft kondenserer på de kalde veggene (sommerkondens). Steng ventilene i sommerhalvåret.",
        "it": "L'aria estiva calda e umida condensa sui muri freddi (condensa estiva). Chiudi le prese d'aria nella metà estiva dell'anno.",
    },
    "Open crawl-space vents for winter": {
        "en": "Open the vents between mid-September and mid-October and keep them open until May: the drier winter air dries out the crawl space. Insulate water pipes if it gets very cold.",
        "no": "Åpne ventilene mellom midten av september og midten av oktober, og la dem stå åpne til mai: den tørrere vinterluften tørker ut krypkjelleren. Isoler vannrørene hvis det blir svært kaldt.",
        "it": "Apri le prese d'aria tra metà settembre e metà ottobre e lasciale aperte fino a maggio: l'aria invernale più secca asciuga il vespaio. Isola i tubi dell'acqua se fa molto freddo.",
    },
    "Measure radon (long-term, winter)": {
        "en": "Measure between October and April, for at least two months, with at least two detectors in the most used rooms, 1–2 m above the floor. Also measure after renovating, insulating or changing ventilation. Under 100 Bq/m³: no action; 100–200: consider measures; over 200: act. Attach the report.",
        "no": "Mål mellom oktober og april, i minst to måneder, med minst to målere i de mest brukte rommene, 1–2 m over gulvet. Mål også etter oppussing, etterisolering eller endret ventilasjon. Under 100 Bq/m³: ingen tiltak; 100–200: vurder tiltak; over 200: gjør tiltak. Legg ved rapporten.",
        "it": "Misura tra ottobre e aprile, per almeno due mesi, con almeno due rilevatori nelle stanze più usate, a 1–2 m dal pavimento. Misura anche dopo ristrutturazioni, isolamento o modifiche alla ventilazione. Sotto 100 Bq/m³: nessun intervento; 100–200: valuta interventi; oltre 200: intervieni. Allega il rapporto.",
    },
    "Check washing machine and dishwasher hoses": {
        "en": "Look for cracks, bulges and drips at the hoses and connections. Replace worn hoses; consider a leak detector with automatic shut-off.",
        "no": "Se etter sprekker, bobler og drypp ved slanger og koblinger. Bytt slitte slanger; vurder vannstopper med automatisk stenging.",
        "it": "Cerca crepe, rigonfiamenti e gocciolamenti su tubi e raccordi. Sostituisci i tubi usurati; valuta un rilevatore di perdite con chiusura automatica.",
    },
    "Close the main water valve before holidays": {
        "en": "Turn off the main water valve when you leave for a longer trip. Check now and then that it still closes properly.",
        "no": "Steng hovedstoppekranen når du reiser bort over tid. Sjekk innimellom at den fortsatt stenger skikkelig.",
        "it": "Chiudi il rubinetto generale dell'acqua quando parti per un periodo lungo. Controlla ogni tanto che chiuda ancora bene.",
    },
    "Look over sockets and switches": {
        "en": "Look for discoloured, warm, loose or damaged sockets, switches and plugs. Any repair must be done by an electrician.",
        "no": "Se etter misfargede, varme, løse eller skadde stikkontakter, brytere og støpsler. Utbedring må gjøres av elektriker.",
        "it": "Cerca prese, interruttori e spine scolorite, calde, allentate o danneggiate. Le riparazioni vanno fatte da un elettricista.",
    },
    "Check draught before the heating season": {
        "en": "If smoke comes into the room when you light the fire, check that the damper is open, the chimney is clear and the room gets enough fresh air.",
        "no": "Slår røyken inn når du fyrer, sjekk at spjeldet er åpent, at pipa er ren og at rommet får nok frisk luft.",
        "it": "Se il fumo entra nella stanza quando accendi il fuoco, controlla che la serranda sia aperta, la canna fumaria libera e che la stanza riceva abbastanza aria.",
    },
    "Store firewood dry and ventilated": {
        "en": "Stack the wood off the ground with air between the logs, covered on top but open on the sides. Bring a few days' supply indoors ahead of use.",
        "no": "Stable veden opp fra bakken med luft mellom kubbene, dekket på toppen men åpen på sidene. Ta inn noen dagers forbruk i forkant.",
        "it": "Impila la legna sollevata da terra, con aria tra i ciocchi, coperta sopra ma aperta ai lati. Porta in casa la scorta di qualche giorno in anticipo.",
    },
}


def task_description(task: tuple, lang: str) -> str | None:
    """The task's checklist text in `lang`, or None when the template has none."""
    d = TASK_DESCRIPTIONS.get(task[0])
    if not d:
        return None
    return d.get(lang) or d["en"]


def task_title(task: tuple, lang: str) -> str:
    """The task's title in `lang` (en / no / it); English when a translation is missing."""
    if lang == "no":
        return task[1]
    if lang == "it":
        return TASK_TITLES_IT.get(task[0], task[0])
    return task[0]


def list_templates(kind: str, lang: str) -> list[dict]:
    lang = norm(lang)
    out = []
    for t in TEMPLATES.get(kind, []):
        out.append({
            "key": t["key"],
            "name": t["name"].get(lang) or t["name"]["en"],
            "task_titles": [task_title(task, lang) for task in t["tasks"]],
        })
    return out


def find_template(key: str) -> dict | None:
    for bundles in TEMPLATES.values():
        for t in bundles:
            if t["key"] == key:
                return t
    return None

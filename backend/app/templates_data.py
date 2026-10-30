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
                ("Inspect roof", "Inspiser taket", 1, "years", "roof", "05-01"),
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
    "Inspect roof": "Controlla il tetto",
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

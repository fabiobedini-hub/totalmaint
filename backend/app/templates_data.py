"""Predefined maintenance templates, per asset kind.

Each template is a named bundle of components and tasks. Applying a template to
an asset creates the components and tasks in the user's language.
Edit freely: add your own bundles here.

Task tuple: (title_en, title_no, interval_value, interval_unit, component key or None[, "MM-DD"])
The optional "MM-DD" pins seasonal jobs (tyres, antifouling, frost) to the next such date
instead of the start date chosen when applying the template.
"""

TEMPLATES = {
    "home": [
        {
            "key": "house_basic",
            "name": {"en": "House – basics", "no": "Hus – grunnleggende"},
            "components": {
                "smoke": {"en": "Smoke detectors", "no": "Røykvarslere"},
                "gutters": {"en": "Gutters & downpipes", "no": "Takrenner og nedløp"},
                "roof": {"en": "Roof", "no": "Tak"},
                "waterheater": {"en": "Water heater", "no": "Varmtvannsbereder"},
                "drains": {"en": "Drains", "no": "Sluk"},
                "extinguisher": {"en": "Fire extinguisher", "no": "Brannslukker"},
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
            "name": {"en": "Air-to-air heat pump", "no": "Luft-til-luft varmepumpe"},
            "components": {"hp": {"en": "Heat pump", "no": "Varmepumpe"}},
            "tasks": [
                ("Clean heat pump indoor filters", "Rens filtre i innedel", 1, "months", "hp"),
                ("Clean outdoor unit and check drain", "Rens utedel og sjekk drenering", 6, "months", "hp", "10-01"),
                ("Professional heat pump service", "Service av varmepumpe (fagperson)", 2, "years", "hp"),
            ],
        },
        {
            "key": "ventilation",
            "name": {"en": "Balanced ventilation", "no": "Balansert ventilasjon"},
            "components": {"vent": {"en": "Ventilation unit", "no": "Ventilasjonsaggregat"}},
            "tasks": [
                ("Replace ventilation filters", "Bytt filter i ventilasjonsanlegg", 6, "months", "vent"),
                ("Clean kitchen hood filter", "Rens filter i kjøkkenvifte", 3, "months", None),
            ],
        },
        {
            "key": "garden",
            "name": {"en": "Garden & outdoors", "no": "Hage og utendørs"},
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
            "name": {"en": "Electric car", "no": "Elbil"},
            "components": {
                "tyres": {"en": "Tyres", "no": "Dekk"},
                "cabin": {"en": "Cabin filter", "no": "Kupéfilter"},
                "brakes": {"en": "Brakes", "no": "Bremser"},
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
            "name": {"en": "Petrol / diesel car", "no": "Bensin- / dieselbil"},
            "components": {
                "engine": {"en": "Engine", "no": "Motor"},
                "tyres": {"en": "Tyres", "no": "Dekk"},
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
            "name": {"en": "Boat with outboard", "no": "Båt med påhengsmotor"},
            "components": {
                "engine": {"en": "Outboard engine", "no": "Påhengsmotor"},
                "hull": {"en": "Hull", "no": "Skrog"},
                "safety": {"en": "Safety equipment", "no": "Sikkerhetsutstyr"},
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
            "name": {"en": "Cabin – season", "no": "Hytte – sesong"},
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
            "name": {"en": "Bicycle – basics", "no": "Sykkel – grunnleggende"},
            "components": {
                "chain": {"en": "Chain & gears", "no": "Kjede og gir"},
                "brakes": {"en": "Brakes", "no": "Bremser"},
                "tyres": {"en": "Tyres", "no": "Dekk"},
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
            "name": {"en": "Winter cycling", "no": "Vintersykling"},
            "components": {"tyres": {"en": "Tyres", "no": "Dekk"}},
            "tasks": [
                ("Fit studded tyres", "Bytt til piggdekk", 1, "years", "tyres", "11-01"),
                ("Take off studded tyres", "Bytt tilbake til sommerdekk", 1, "years", "tyres", "04-15"),
                ("Rinse off road salt", "Skyll av veisalt", 2, "weeks", None),
            ],
        },
        {
            "key": "bike_electric",
            "name": {"en": "E-bike", "no": "Elsykkel"},
            "components": {"battery": {"en": "Battery & motor", "no": "Batteri og motor"}},
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
            "name": {"en": "Motorcycle", "no": "Motorsykkel"},
            "components": {
                "engine": {"en": "Engine", "no": "Motor"},
                "chain": {"en": "Chain & sprockets", "no": "Kjede og tannhjul"},
                "tyres": {"en": "Tyres", "no": "Dekk"},
                "brakes": {"en": "Brakes", "no": "Bremser"},
                "battery": {"en": "Battery", "no": "Batteri"},
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
            "name": {"en": "Electric scooter", "no": "Elsparkesykkel"},
            "components": {
                "battery": {"en": "Battery", "no": "Batteri"},
                "tyres": {"en": "Tyres", "no": "Dekk"},
                "brakes": {"en": "Brakes", "no": "Bremser"},
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


def list_templates(kind: str, lang: str) -> list[dict]:
    lang = lang if lang in ("en", "no") else "en"
    out = []
    for t in TEMPLATES.get(kind, []):
        out.append({
            "key": t["key"],
            "name": t["name"][lang],
            "task_titles": [task[1] if lang == "no" else task[0] for task in t["tasks"]],
        })
    return out


def find_template(key: str) -> dict | None:
    for bundles in TEMPLATES.values():
        for t in bundles:
            if t["key"] == key:
                return t
    return None

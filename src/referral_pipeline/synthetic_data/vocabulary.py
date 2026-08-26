"""Large, deterministic vocabularies for realistic fictitious referral data.

The values are intentionally assembled from independent components.  They are
not copied from patient records and must never be used to contact a person or
make a care decision.
"""

from __future__ import annotations


FIRST_NAMES = (
    "Adriana", "Alejandro", "Alina", "Amara", "Anita", "Armando", "Beatriz", "Bernard",
    "Bianca", "Caleb", "Camille", "Carina", "Carmen", "Cassandra", "Cecilia", "Clara",
    "Dalia", "Damian", "Darius", "Delia", "Desmond", "Diana", "Edgar", "Elena",
    "Elias", "Emilia", "Esteban", "Evelyn", "Farrah", "Felix", "Francis", "Gabriel",
    "Gloria", "Guillermo", "Hector", "Helena", "Imani", "Inez", "Isabel", "Javier",
    "Jerome", "Joanna", "Julian", "Karina", "Kiara", "Leandro", "Leonard", "Leticia",
    "Lucia", "Manuel", "Maribel", "Marina", "Mateo", "Naomi", "Nathaniel", "Nora",
    "Octavia", "Omar", "Opal", "Patricia", "Preston", "Raquel", "Rafael", "Renata",
    "Rochelle", "Ruben", "Samuel", "Selena", "Solomon", "Sonia", "Teresa", "Tomas",
    "Valeria", "Vicente", "Vincent", "Wanda", "Xavier", "Yolanda", "Zenaida", "Zoe",
)

LAST_NAMES = (
    "Abarca", "Acevedo", "Aguilar", "Alvarado", "Barrera", "Benton", "Bishop", "Bradshaw",
    "Cabrera", "Calderon", "Carrillo", "Castillo", "Delaney", "Dominguez", "Duarte", "Estrada",
    "Fletcher", "Fuentes", "Galindo", "Garza", "Givens", "Hawkins", "Hendrix", "Ibarra",
    "Jefferson", "Kimura", "Langston", "Lozano", "Maldonado", "Mendoza", "Montoya", "Navarro",
    "Nguyen", "Okafor", "Ortega", "Paredes", "Pritchard", "Quintero", "Ramirez", "Rasmussen",
    "Renteria", "Salazar", "Sandoval", "Serrano", "Solis", "Townsend", "Trujillo", "Valencia",
    "Vasquez", "Velasco", "Villanueva", "Whitaker", "Wilkins", "Ybarra", "Zamora", "Zuniga",
)

STREET_NAMES = (
    "Alamitos Avenue", "Arlington Place", "Atlantic Avenue", "Banning Street",
    "Bay View Drive", "Bellflower Boulevard", "Cabrillo Avenue", "Carson Street",
    "Catalina Avenue", "Cedar Avenue", "Cherry Avenue", "Cypress Street",
    "Del Amo Boulevard", "Dominguez Way", "Elm Avenue", "Figueroa Street",
    "Gaffey Street", "Harbor View Avenue", "Hawthorne Boulevard", "Junipero Avenue",
    "Lakewood Boulevard", "Linden Avenue", "Lomita Boulevard", "Magnolia Avenue",
    "Main Street", "Mariposa Avenue", "Normandie Avenue", "Orange Avenue",
    "Pacific Coast Highway", "Palos Verdes Drive", "Pine Avenue", "Redondo Beach Boulevard",
    "Sepulveda Boulevard", "Signal Hill Road", "Spring Street", "Temple Avenue",
    "Vermont Avenue", "Victoria Street", "Wardlow Road", "Willow Street",
)

CITIES = (
    ("Long Beach", "CA", "90802"), ("Long Beach", "CA", "90806"),
    ("Torrance", "CA", "90501"), ("Carson", "CA", "90745"),
    ("Inglewood", "CA", "90301"), ("San Pedro", "CA", "90731"),
    ("Lakewood", "CA", "90712"), ("Compton", "CA", "90220"),
    ("Gardena", "CA", "90247"), ("Hawthorne", "CA", "90250"),
    ("Lomita", "CA", "90717"), ("Redondo Beach", "CA", "90277"),
    ("Wilmington", "CA", "90744"), ("Signal Hill", "CA", "90755"),
    ("Bellflower", "CA", "90706"), ("Downey", "CA", "90241"),
    ("Norwalk", "CA", "90650"), ("Paramount", "CA", "90723"),
    ("Los Angeles", "CA", "90044"), ("Los Angeles", "CA", "90047"),
)

FACILITIES = (
    "Harbor Crest Medical Center", "South Bay Regional Hospital", "Pacific Horizon Home Health",
    "Valley Pointe Rehabilitation Center", "Coastal Community Clinic", "MetroCare Medical Group",
    "St. Maren Medical Pavilion", "Los Robles Post-Acute Center", "Cabrillo Family Medicine",
    "Seaside Transitional Care", "Paloma Home Health Services", "Westbridge Community Hospital",
    "Providence Harbor Medical Group", "Magnolia Skilled Nursing Center", "Golden Shore Hospice",
    "Linden Primary Care Associates", "Carson Valley Medical Center", "Arbor Gate Home Health",
    "Pacific Crest Internal Medicine", "San Gabriel Continuity Clinic",
)

INSURERS = (
    "Blue Shield of California", "Anthem Blue Cross", "Health Net", "UnitedHealthcare",
    "Humana Medicare Advantage", "Aetna Medicare", "Alignment Health Plan", "SCAN Health Plan",
    "L.A. Care Health Plan", "Molina Healthcare", "Original Medicare", "Central Health Plan",
)

DIAGNOSES = (
    ("Stage 3 pressure injury of the sacral region.", ("L89.153",)),
    ("Diabetic ulcer of the right heel with fat layer exposed.", ("E11.621", "L97.412")),
    ("Venous stasis ulcer of the left lower leg with edema.", ("I83.023", "L97.321")),
    ("Non-healing surgical wound of the lower abdomen.", ("T81.89XA",)),
    ("Open wound of the left foot following cellulitis admission.", ("S91.302A", "L03.116")),
    ("Unstageable pressure injury of the right hip.", ("L89.210",)),
    ("Stage 2 pressure injury of the left buttock.", ("L89.322",)),
    ("Chronic ulcer of the right ankle with skin breakdown.", ("L97.311",)),
    ("Diabetic ulcer of the left midfoot with fat layer exposed.", ("E11.621", "L97.422")),
    ("Dehisced surgical incision requiring skilled wound management.", ("T81.31XA",)),
    ("Skin tear of the right forearm without foreign body.", ("S51.811A",)),
    ("Stage 4 pressure injury of the coccygeal region.", ("L89.154",)),
    ("Venous ulcer of the right calf with inflammation.", ("I83.212", "L97.212")),
    ("Neuropathic ulcer of the left plantar surface.", ("L97.522", "G62.9")),
    ("Open wound of the right lower leg after traumatic injury.", ("S81.801A",)),
    ("Moisture-associated skin damage of the gluteal cleft.", ("L30.8",)),
    ("Arterial ulcer of the left lateral ankle.", ("I70.243", "L97.322")),
    ("Delayed healing of postoperative wound of the right groin.", ("T81.89XD",)),
    ("Pressure injury of the right heel, deep tissue presentation.", ("L89.616",)),
    ("Chronic ulcer of the left great toe with necrosis of muscle.", ("L97.523",)),
)

NOTE_FRAGMENTS = (
    "Referral received after recent hospitalization for worsening skin breakdown.",
    "Family reports increased drainage during the past several days.",
    "Patient requires assistance with transfers and spends most of the day in a chair.",
    "Home-health nursing has been completing dressing changes between visits.",
    "Wound bed contains mixed granulation and slough with moderate serous drainage.",
    "Periwound skin is fragile with mild maceration and no active bleeding.",
    "Pain is reported primarily during cleansing and repositioning.",
    "No fever or chills were reported during the intake call.",
    "Current treatment includes saline cleanse and bordered foam dressing.",
    "Off-loading and pressure redistribution were reviewed with the caregiver.",
    "Photographs and most recent measurements are included in the fax packet.",
    "Ordering clinician requests evaluation and treatment recommendations.",
    "Medication reconciliation was completed from the discharge list.",
    "Patient is homebound because of limited endurance and impaired mobility.",
    "Follow-up with primary care is scheduled within two weeks.",
    "Skilled assessment is requested for change in wound appearance.",
    "Caregiver is available in the mornings and assists with dressing supplies.",
    "The patient uses a walker for short distances inside the residence.",
    "Vascular studies are pending and will be forwarded when available.",
    "Nutritional intake has been variable since the recent admission.",
)

MEDICATIONS = (
    "Metformin 500 mg tablet", "Lisinopril 10 mg tablet", "Amlodipine 5 mg tablet",
    "Atorvastatin 20 mg tablet", "Gabapentin 300 mg capsule", "Furosemide 20 mg tablet",
    "Apixaban 5 mg tablet", "Insulin glargine 100 unit/mL", "Acetaminophen 500 mg tablet",
    "Clopidogrel 75 mg tablet", "Levothyroxine 50 mcg tablet", "Carvedilol 6.25 mg tablet",
)


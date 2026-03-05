from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from kerykeion import AstrologicalSubject, SynastryAspects
from datetime import datetime

app = FastAPI(title="Orbis Astrology Engine")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory="static"), name="static")


class BirthData(BaseModel):
    name: str
    year: int
    month: int
    day: int
    hour: int
    minute: int
    city: str
    nation: str = "US"

class CompatibilityData(BaseModel):
    person1: BirthData
    person2: BirthData


SIGN_DATA = {
    "Ari": ("Aries","♈","Fire","Cardinal"),
    "Tau": ("Taurus","♉","Earth","Fixed"),
    "Gem": ("Gemini","♊","Air","Mutable"),
    "Can": ("Cancer","♋","Water","Cardinal"),
    "Leo": ("Leo","♌","Fire","Fixed"),
    "Vir": ("Virgo","♍","Earth","Mutable"),
    "Lib": ("Libra","♎","Air","Cardinal"),
    "Sco": ("Scorpio","♏","Water","Fixed"),
    "Sag": ("Sagittarius","♐","Fire","Mutable"),
    "Cap": ("Capricorn","♑","Earth","Cardinal"),
    "Aqu": ("Aquarius","♒","Air","Fixed"),
    "Pis": ("Pisces","♓","Water","Mutable"),
}
SIGN_ORDER = ["Ari","Tau","Gem","Can","Leo","Vir","Lib","Sco","Sag","Cap","Aqu","Pis"]
PLANET_SYMBOLS = {
    "Sun":"☉","Moon":"☽","Mercury":"☿","Venus":"♀","Mars":"♂",
    "Jupiter":"♃","Saturn":"♄","Uranus":"♅","Neptune":"♆","Pluto":"♇",
    "Mean_Node":"☊","Chiron":"⚷",
}
PLANET_MEANINGS = {
    "Sun":"core identity, ego, life purpose","Moon":"emotions, instincts, inner world",
    "Mercury":"communication, intellect, thought","Venus":"love, beauty, values, pleasure",
    "Mars":"drive, passion, action, desire","Jupiter":"expansion, luck, philosophy, growth",
    "Saturn":"discipline, karma, structure, lessons","Uranus":"rebellion, innovation, sudden change",
    "Neptune":"dreams, spirituality, illusion","Pluto":"transformation, power, rebirth",
    "Mean_Node":"karmic path, destiny","Chiron":"wounds and healing",
}
ASPECT_DATA = {
    "conjunction": ("☌", 0,   "#c9a84c", 8),
    "opposition":  ("☍", 180, "#e87070", 8),
    "trine":       ("△", 120, "#6bcb8a", 8),
    "square":      ("□", 90,  "#e87070", 7),
    "sextile":     ("⚹", 60,  "#6bcb8a", 6),
    "quincunx":    ("⚻", 150, "#a8afc0", 5),
}
HOROSCOPES = {
    "Aries": "The ram charges forward today. Mars fuels your ambition — act on instinct, but temper impulsiveness with awareness.",
    "Taurus": "Venus wraps you in earthly pleasures. Financial matters deserve attention. Trust your body's wisdom today.",
    "Gemini": "Mercury dances between ideas. Your words carry unusual power — use them wisely. A conversation shifts something.",
    "Cancer": "The Moon speaks to your depths. Emotional tides run high. Home and family offer comfort and clarity.",
    "Leo": "The Sun illuminates your natural throne. Your presence commands rooms without effort. Share your warmth generously.",
    "Virgo": "Details reveal hidden truths today. Your analytical mind cuts through illusion. Service to others brings unexpected reward.",
    "Libra": "Scales seek equilibrium. A choice you've avoided demands resolution. Beauty and harmony restore your sense of self.",
    "Scorpio": "Depths call to you. Transformation stirs beneath the surface. What you release today creates space for rebirth.",
    "Sagittarius": "The archer draws back for a long shot. Philosophy and adventure beckon. Truth arrives from an unexpected direction.",
    "Capricorn": "Saturn rewards patient effort. Your ambitions are well-founded — trust the slow climb. Authority recognizes your worth.",
    "Aquarius": "Uranus sparks unconventional solutions. Your vision is ahead of its time. Find others who can see what you see.",
    "Pisces": "Neptune dissolves boundaries between worlds. Intuition speaks louder than logic today. Dreams carry messages worth decoding.",
}

HOUSE_ROMAN = ['I','II','III','IV','V','VI','VII','VIII','IX','X','XI','XII']


def house_from_cusps(abs_deg, cusps):
    """Given a planet's absolute degree (0-360) and list of 12 cusp abs_degrees, return roman numeral."""
    if not cusps:
        return ""
    abs_deg = abs_deg % 360
    for i in range(12):
        c1 = cusps[i] % 360
        c2 = cusps[(i + 1) % 12] % 360
        if c1 < c2:
            if c1 <= abs_deg < c2:
                return HOUSE_ROMAN[i]
        else:  # wraps around 0
            if abs_deg >= c1 or abs_deg < c2:
                return HOUSE_ROMAN[i]
    return HOUSE_ROMAN[0]


def get_sign(sign_str):
    key = sign_str[:3].capitalize()
    return SIGN_DATA.get(key, (sign_str, "?", "?", "?"))

def abs_pos(sign_str, degree):
    key = sign_str[:3].capitalize()
    try:
        return SIGN_ORDER.index(key) * 30 + degree
    except ValueError:
        return degree

def extract_planet(subject, attr, cusp_abs=None):
    try:
        p = getattr(subject, attr)
        si = get_sign(p.sign)
        abs_d = round(abs_pos(p.sign, p.position), 4)
        house = house_from_cusps(abs_d, cusp_abs) if cusp_abs else ""
        return {
            "name": p.name, "attr": attr,
            "symbol": PLANET_SYMBOLS.get(p.name, p.name[:2]),
            "sign": si[0], "sign_symbol": si[1],
            "sign_key": p.sign[:3].capitalize(),
            "element": si[2], "modality": si[3],
            "degree": round(p.position, 4),
            "abs_degree": abs_d,
            "house": house,
            "retrograde": getattr(p, 'retrograde', False),
            "meaning": PLANET_MEANINGS.get(p.name, ""),
        }
    except Exception:
        return None

def compute_aspects(planets):
    aspects = []
    pl = [p for p in planets if p]
    for i in range(len(pl)):
        for j in range(i+1, len(pl)):
            diff = abs(pl[i]["abs_degree"] - pl[j]["abs_degree"])
            if diff > 180: diff = 360 - diff
            for name, (sym, angle, color, orb) in ASPECT_DATA.items():
                if abs(diff - angle) <= orb:
                    aspects.append({
                        "planet1": pl[i]["name"], "planet1_symbol": pl[i]["symbol"],
                        "planet2": pl[j]["name"], "planet2_symbol": pl[j]["symbol"],
                        "aspect": name, "aspect_symbol": sym, "color": color,
                        "orb": round(abs(diff - angle), 2),
                        "p1_abs": pl[i]["abs_degree"], "p2_abs": pl[j]["abs_degree"],
                    })
                    break
    return aspects

def compute_houses(subject):
    attrs = ["first_house","second_house","third_house","fourth_house","fifth_house","sixth_house",
             "seventh_house","eighth_house","ninth_house","tenth_house","eleventh_house","twelfth_house"]
    nums = ["I","II","III","IV","V","VI","VII","VIII","IX","X","XI","XII"]
    houses = []
    for i, attr in enumerate(attrs):
        try:
            h = getattr(subject, attr)
            si = get_sign(h.sign)
            houses.append({"number": nums[i], "sign": si[0], "sign_symbol": si[1],
                           "degree": round(h.position, 2), "abs_degree": round(abs_pos(h.sign, h.position), 4)})
        except Exception:
            continue
    return houses


@app.get("/")
async def root():
    return FileResponse("static/index.html")


# Debug endpoint — call /api/debug with birth data to see raw planet attrs
@app.post("/api/debug")
async def debug_chart(data: BirthData):
    try:
        s = AstrologicalSubject(
            name=data.name, year=data.year, month=data.month, day=data.day,
            hour=data.hour, minute=data.minute, city=data.city, nation=data.nation, online=True,
        )
        p = s.sun
        attrs = {a: str(getattr(p, a, 'N/A')) for a in dir(p) if not a.startswith('_')}
        return {"sun_attrs": attrs}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/chart")
async def get_chart(data: BirthData):
    try:
        is_cosmogram = (data.hour == 12 and data.minute == 0)

        s = AstrologicalSubject(
            name=data.name, year=data.year, month=data.month, day=data.day,
            hour=data.hour, minute=data.minute, city=data.city, nation=data.nation, online=True,
        )

        # compute house cusps first so we can assign planets to houses
        houses = compute_houses(s) if not is_cosmogram else []
        cusp_abs = [h["abs_degree"] for h in houses] if houses else None

        planet_attrs = ["sun","moon","mercury","venus","mars","jupiter","saturn","uranus","neptune","pluto","mean_node","chiron"]
        planets = [p for p in [extract_planet(s, a, cusp_abs) for a in planet_attrs] if p]

        if not is_cosmogram:
            for name, attr, sym, meaning in [("Asc","first_house","AC","rising sign, outer self"),("MC","tenth_house","MC","career, public life, destiny")]:
                try:
                    h = getattr(s, attr)
                    si = get_sign(h.sign)
                    planets.append({"name": name, "attr": attr, "symbol": sym,
                        "sign": si[0], "sign_symbol": si[1], "sign_key": h.sign[:3].capitalize(),
                        "element": si[2], "modality": si[3], "degree": round(h.position, 2),
                        "abs_degree": round(abs_pos(h.sign, h.position), 4),
                        "house": "I" if name=="Asc" else "X", "retrograde": False, "meaning": meaning})
                except Exception:
                    pass

        aspects = compute_aspects([p for p in planets if p["name"] not in ["Asc","MC"]])

        sun_info = get_sign(s.sun.sign)
        moon_info = get_sign(s.moon.sign)
        asc_info = get_sign(s.first_house.sign)
        asc_abs = round(abs_pos(s.first_house.sign, s.first_house.position), 4)

        return {
            "name": data.name,
            "is_cosmogram": is_cosmogram,
            "sun_sign": sun_info[0], "sun_symbol": sun_info[1],
            "moon_sign": moon_info[0], "moon_symbol": moon_info[1],
            "ascendant": asc_info[0] if not is_cosmogram else None,
            "asc_symbol": asc_info[1] if not is_cosmogram else None,
            "asc_abs": asc_abs if not is_cosmogram else 0,
            "planets": planets, "aspects": aspects, "houses": houses,
            "horoscope": HOROSCOPES.get(sun_info[0], "The stars have a unique message for you today."),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/compatibility")
async def get_compatibility(data: CompatibilityData):
    try:
        p1, p2 = data.person1, data.person2
        s1 = AstrologicalSubject(name=p1.name, year=p1.year, month=p1.month, day=p1.day,
            hour=p1.hour, minute=p1.minute, city=p1.city, nation=p1.nation, online=True)
        s2 = AstrologicalSubject(name=p2.name, year=p2.year, month=p2.month, day=p2.day,
            hour=p2.hour, minute=p2.minute, city=p2.city, nation=p2.nation, online=True)

        planet_attrs = ["sun","moon","mercury","venus","mars","jupiter","saturn","uranus","neptune","pluto","mean_node","chiron"]
        planets1 = [p for p in [extract_planet(s1, a) for a in planet_attrs] if p]
        planets2 = [p for p in [extract_planet(s2, a) for a in planet_attrs] if p]

        # compute cross-aspects manually for consistent field names
        ASPECT_ORBS = {"conjunction":(0,8),"opposition":(180,8),"trine":(120,7),
                       "square":(90,7),"sextile":(60,5),"quincunx":(150,3)}
        aspects = []
        for pp1 in planets1:
            for pp2 in planets2:
                diff = abs(pp1["abs_degree"] - pp2["abs_degree"])
                if diff > 180: diff = 360 - diff
                for asp_name, (angle, orb) in ASPECT_ORBS.items():
                    if abs(diff - angle) <= orb:
                        sym, _, color, _ = ASPECT_DATA[asp_name]
                        aspects.append({
                            "planet1": pp1["name"], "planet1_symbol": pp1["symbol"],
                            "planet2": pp2["name"], "planet2_symbol": pp2["symbol"],
                            "aspect": asp_name, "aspect_symbol": sym, "color": color,
                            "orb": round(abs(diff - angle), 2),
                            "p1_abs": pp1["abs_degree"], "p2_abs": pp2["abs_degree"],
                        })
                        break

        harmonious = sum(1 for a in aspects if a["aspect"] in ["trine","sextile","conjunction"])
        tense      = sum(1 for a in aspects if a["aspect"] in ["square","opposition"])
        total      = len(aspects) if aspects else 1
        score      = min(100, max(0, int((harmonious/total)*100+20)))

        asc1 = round(abs_pos(s1.first_house.sign, s1.first_house.position), 4)

        return {
            "person1": p1.name, "person2": p2.name, "score": score,
            "score_label": "high" if score>=80 else "medium" if score>=60 else "low" if score>=40 else "challenging",
            "planets1": planets1, "planets2": planets2,
            "asc_abs": asc1,
            "natal_houses": compute_houses(s1),
            "sun1": get_sign(s1.sun.sign)[0], "sun2": get_sign(s2.sun.sign)[0],
            "aspects": aspects,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/sky")
async def get_sky():
    try:
        now = datetime.utcnow()
        sky = AstrologicalSubject(
            name="Sky", year=now.year, month=now.month, day=now.day,
            hour=now.hour, minute=now.minute,
            city="London", nation="GB", online=True,
        )
        planet_attrs = ["sun","moon","mercury","venus","mars","jupiter","saturn","uranus","neptune","pluto","mean_node","chiron"]
        planets = [p for p in [extract_planet(sky, a) for a in planet_attrs] if p]
        aspects = compute_aspects(planets)
        return {
            "planets": planets,
            "aspects": aspects,
            "datetime": now.strftime("%d.%m.%Y %H:%M UTC"),
            "is_cosmogram": True,
            "asc_abs": 0,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/horoscope/{sign}")
async def get_horoscope(sign: str):
    sign = sign.capitalize()
    if sign not in HOROSCOPES:
        raise HTTPException(status_code=404, detail="Sign not found")
    return {"sign": sign, "horoscope": HOROSCOPES[sign], "date": datetime.now().strftime("%B %d, %Y")}


class TransitData(BaseModel):
    natal: BirthData
    transit_date: str = ""   # YYYY-MM-DD, defaults to today
    transit_city: str = ""
    transit_nation: str = "US"

@app.post("/api/transits")
async def get_transits(data: TransitData):
    try:
        now = datetime.utcnow()
        if data.transit_date:
            parts = data.transit_date.split("-")
            ty, tm, td = int(parts[0]), int(parts[1]), int(parts[2])
        else:
            ty, tm, td = now.year, now.month, now.day

        city   = data.transit_city   or data.natal.city
        nation = data.transit_nation or data.natal.nation

        # natal chart
        natal = AstrologicalSubject(
            name=data.natal.name,
            year=data.natal.year, month=data.natal.month, day=data.natal.day,
            hour=data.natal.hour, minute=data.natal.minute,
            city=data.natal.city, nation=data.natal.nation, online=True,
        )

        # transit "person" — current sky at given date, noon
        transit = AstrologicalSubject(
            name="Transit",
            year=ty, month=tm, day=td,
            hour=now.hour, minute=now.minute,
            city=city, nation=nation, online=True,
        )

        planet_attrs = ["sun","moon","mercury","venus","mars","jupiter","saturn","uranus","neptune","pluto","mean_node","chiron"]

        natal_planets   = [p for p in [extract_planet(natal,   a) for a in planet_attrs] if p]
        transit_planets = [p for p in [extract_planet(transit, a) for a in planet_attrs] if p]

        # aspects between transit planets and natal planets
        transit_aspects = []
        ASPECT_ORBS = {"conjunction":(0,8),"opposition":(180,8),"trine":(120,7),
                       "square":(90,7),"sextile":(60,5),"quincunx":(150,3)}
        for tp in transit_planets:
            for np_ in natal_planets:
                diff = abs(tp["abs_degree"] - np_["abs_degree"])
                if diff > 180: diff = 360 - diff
                for asp_name, (angle, orb) in ASPECT_ORBS.items():
                    if abs(diff - angle) <= orb:
                        sym, _, color, _ = ASPECT_DATA[asp_name]
                        transit_aspects.append({
                            "transit_planet": tp["name"],
                            "transit_symbol": tp["symbol"],
                            "natal_planet":   np_["name"],
                            "natal_symbol":   np_["symbol"],
                            "aspect":         asp_name,
                            "aspect_symbol":  sym,
                            "color":          color,
                            "orb":            round(abs(diff - angle), 2),
                            "t_abs":          tp["abs_degree"],
                            "n_abs":          np_["abs_degree"],
                        })
                        break

        natal_info = get_sign(natal.sun.sign)
        asc_info   = get_sign(natal.first_house.sign)

        return {
            "name":           data.natal.name,
            "transit_date":   f"{td:02d}.{tm:02d}.{ty}",
            "natal_planets":  natal_planets,
            "transit_planets": transit_planets,
            "transit_aspects": transit_aspects,
            "natal_houses":   compute_houses(natal),
            "asc_abs":        round(abs_pos(natal.first_house.sign, natal.first_house.position), 4),
            "sun_sign":       natal_info[0],
            "ascendant":      asc_info[0],
            "is_cosmogram":   (data.natal.hour == 12 and data.natal.minute == 0),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

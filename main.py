from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from kerykeion import AstrologicalSubject, NatalAspects, SynastryAspects
from datetime import datetime

app = FastAPI(title="Lumina Astrology Engine")
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


def get_sign(sign_str):
    key = sign_str[:3].capitalize()
    return SIGN_DATA.get(key, (sign_str, "?", "?", "?"))

def abs_pos(sign_str, degree):
    key = sign_str[:3].capitalize()
    try:
        return SIGN_ORDER.index(key) * 30 + degree
    except ValueError:
        return degree

def extract_planet(subject, attr):
    try:
        p = getattr(subject, attr)
        si = get_sign(p.sign)
        return {
            "name": p.name, "attr": attr,
            "symbol": PLANET_SYMBOLS.get(p.name, p.name[:2]),
            "sign": si[0], "sign_symbol": si[1],
            "sign_key": p.sign[:3].capitalize(),
            "element": si[2], "modality": si[3],
            "degree": round(p.position, 4),
            "abs_degree": round(abs_pos(p.sign, p.position), 4),
            "house": getattr(p, 'house_name', '?'),
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

@app.post("/api/chart")
async def get_chart(data: BirthData):
    try:
        s = AstrologicalSubject(
            name=data.name, year=data.year, month=data.month, day=data.day,
            hour=data.hour, minute=data.minute, city=data.city, nation=data.nation, online=True,
        )
        planet_attrs = ["sun","moon","mercury","venus","mars","jupiter","saturn","uranus","neptune","pluto","mean_node","chiron"]
        planets = [p for p in [extract_planet(s, a) for a in planet_attrs] if p]

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
        houses = compute_houses(s)
        sun_info = get_sign(s.sun.sign)
        moon_info = get_sign(s.moon.sign)
        asc_info = get_sign(s.first_house.sign)

        return {
            "name": data.name,
            "sun_sign": sun_info[0], "sun_symbol": sun_info[1],
            "moon_sign": moon_info[0], "moon_symbol": moon_info[1],
            "ascendant": asc_info[0], "asc_symbol": asc_info[1],
            "asc_abs": round(abs_pos(s.first_house.sign, s.first_house.position), 4),
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
        synastry = SynastryAspects(s1, s2)
        aspects = synastry.get_relevant_aspects()
        harmonious = sum(1 for a in aspects if a["aspect"] in ["trine","sextile","conjunction"])
        tense = sum(1 for a in aspects if a["aspect"] in ["square","opposition"])
        total = len(aspects) if aspects else 1
        score = min(100, max(0, int((harmonious/total)*100+20)))
        return {
            "person1": p1.name, "person2": p2.name, "score": score,
            "harmonious_aspects": harmonious, "tense_aspects": tense, "total_aspects": len(aspects),
            "sun1": get_sign(s1.sun.sign)[0], "sun2": get_sign(s2.sun.sign)[0],
            "summary": (
                f"{p1.name} and {p2.name} share a rare cosmic alignment. Your souls recognize each other across lifetimes." if score>=80
                else f"{p1.name} and {p2.name} complement each other beautifully. Growth and harmony intertwine in your connection." if score>=60
                else f"{p1.name} and {p2.name} challenge and transform each other. Tension, when navigated consciously, forges depth." if score>=40
                else f"{p1.name} and {p2.name} walk very different cosmic paths. Understanding requires patience and real effort."
            ),
            "aspects": [{"planet1":a["p1_name"],"planet2":a["p2_name"],"aspect":a["aspect"],"orb":round(a["orbit"],2)} for a in aspects[:15]],
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/horoscope/{sign}")
async def get_horoscope(sign: str):
    sign = sign.capitalize()
    if sign not in HOROSCOPES:
        raise HTTPException(status_code=404, detail="Sign not found")
    return {"sign": sign, "horoscope": HOROSCOPES[sign], "date": datetime.now().strftime("%B %d, %Y")}

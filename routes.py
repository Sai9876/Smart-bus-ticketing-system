# 38 TN districts (shortlist)
DISTRICTS = [
 "Ariyalur","Chengalpattu","Chennai","Coimbatore","Cuddalore","Dharmapuri","Dindigul",
 "Erode","Kallakurichi","Kanchipuram","Kanyakumari","Karur","Krishnagiri","Madurai",
 "Mayiladuthurai","Nagapattinam","Namakkal","Nilgiris","Perambalur","Pudukkottai",
 "Ramanathapuram","Ranipet","Salem","Sivagangai","Tenkasi","Thanjavur","Theni",
 "Thoothukudi","Tiruchirappalli","Tirunelveli","Tirupathur","Tiruppur","Tiruvallur",
 "Tiruvannamalai","Tiruvarur","Vellore","Viluppuram","Virudhunagar"
]

# Sample major routes (expand later)
ROUTES = [
 ("Coimbatore","Chennai"),
 ("Chennai","Madurai"),
 ("Madurai","Coimbatore"),
 ("Coimbatore","Tiruppur"),
 ("Salem","Chennai"),
]

ROUTE_FARES = {
 ("Coimbatore","Chennai"): 599,
 ("Chennai","Madurai"):   499,
 ("Madurai","Coimbatore"):429,
 ("Coimbatore","Tiruppur"):149,
 ("Salem","Chennai"):     379,
}





# --- District HQ approx coords (lat, lon). Enough for fare calc; not for navigation. ---
COORDS = {
 "Ariyalur":(11.14,79.08),"Chengalpattu":(12.69,79.98),"Chennai":(13.08,80.27),"Coimbatore":(11.02,76.96),
 "Cuddalore":(11.75,79.77),"Dharmapuri":(12.13,78.16),"Dindigul":(10.36,77.97),"Erode":(11.34,77.72),
 "Kallakurichi":(11.74,78.96),"Kanchipuram":(12.84,79.70),"Kanyakumari":(8.08,77.55),"Karur":(10.96,78.08),
 "Krishnagiri":(12.53,78.21),"Madurai":(9.93,78.12),"Mayiladuthurai":(11.10,79.65),"Nagapattinam":(10.77,79.84),
 "Namakkal":(11.22,78.17),"Nilgiris":(11.41,76.70),"Perambalur":(11.24,78.88),"Pudukkottai":(10.38,78.82),
 "Ramanathapuram":(9.37,78.83),"Ranipet":(12.95,79.33),"Salem":(11.65,78.15),"Sivagangai":(9.85,78.48),
 "Tenkasi":(8.96,77.31),"Thanjavur":(10.79,79.14),"Theni":(10.01,77.48),"Thoothukudi":(8.81,78.15),
 "Tiruchirappalli":(10.80,78.69),"Tirunelveli":(8.73,77.70),"Tirupathur":(12.49,78.57),"Tiruppur":(11.11,77.35),
 "Tiruvallur":(13.14,79.91),"Tiruvannamalai":(12.23,79.07),"Tiruvarur":(10.77,79.64),"Vellore":(12.92,79.13),
 "Viluppuram":(11.94,79.49),"Virudhunagar":(9.59,77.95)
}

# Optional manual overrides (exact km or fare) if you need:
MANUAL_KM = {  # ("From","To"): km
    # ("Chennai","Coimbatore"): 510,
}
FARE_OVERRIDES = {  # ("From","To"): fare_rs
    # ("Chennai","Coimbatore"): 599,
}

# --- Core helpers ---
import math
def _norm(c): return (c or "").strip().title()

def _haversine_km(a, b):
    (lat1,lon1),(lat2,lon2) = a, b
    R=6371.0
    p1=math.radians(lat1); p2=math.radians(lat2)
    dlat=math.radians(lat2-lat1); dlon=math.radians(lon2-lon1)
    h=math.sin(dlat/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dlon/2)**2
    return 2*R*math.asin(math.sqrt(h))

def km_between(c1, c2, default_km=250):
    b, d = _norm(c1), _norm(c2)
    if (b,d) in MANUAL_KM: return float(MANUAL_KM[(b,d)])
    if (d,b) in MANUAL_KM: return float(MANUAL_KM[(d,b)])
    if b in COORDS and d in COORDS:
        return round(_haversine_km(COORDS[b], COORDS[d]))
    return float(default_km)

# Fare policy: per_km + min fare + round to nearest 5
def fare_by_km(b, d, per_km=1.8, min_rs=99, round_to=5):
    b, d = _norm(b), _norm(d)
    if (b,d) in FARE_OVERRIDES: return float(FARE_OVERRIDES[(b,d)])
    if (d,b) in FARE_OVERRIDES: return float(FARE_OVERRIDES[(d,b)])
    km = km_between(b, d)
    raw = max(min_rs, km * float(per_km))
    # round to nearest `round_to`
    return float(int((raw + round_to/2)//round_to) * round_to)

def is_available(b, d):
    # any two valid districts = available
    return _norm(b) in DISTRICTS and _norm(d) in DISTRICTS and _norm(b)!=_norm(d)


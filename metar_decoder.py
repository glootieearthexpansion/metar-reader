"""Decode raw METAR weather reports into plain-English summaries."""
import re

COMPASS_POINTS = [
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
]

WX_DESCRIPTOR = {
    "MI": "shallow", "PR": "partial", "BC": "patchy", "DR": "drifting",
    "BL": "blowing", "SH": "showery", "TS": "thunderstorm with", "FZ": "freezing",
}
WX_PHENOMENON = {
    "DZ": "drizzle", "RA": "rain", "SN": "snow", "SG": "snow grains",
    "IC": "ice crystals", "PL": "ice pellets", "GR": "hail",
    "GS": "small hail / snow pellets", "UP": "unknown precipitation",
    "BR": "mist", "FG": "fog", "FU": "smoke", "VA": "volcanic ash",
    "DU": "dust", "SA": "sand", "HZ": "haze", "PY": "spray",
    "PO": "dust whirls", "SQ": "squall", "FC": "funnel cloud",
    "SS": "sandstorm", "DS": "duststorm",
}
SKY_COVER = {
    "SKC": "Sky clear", "CLR": "Clear skies", "NSC": "No significant cloud",
    "NCD": "No cloud detected", "FEW": "A few clouds", "SCT": "Scattered clouds",
    "BKN": "Broken clouds", "OVC": "Overcast",
}
COVER_RANK = {"FEW": 1, "SCT": 2, "BKN": 3, "OVC": 4, "VV": 5}

DATETIME_RE = re.compile(r"^(\d{2})(\d{2})(\d{2})Z$")
WIND_RE = re.compile(r"^(VRB|\d{3})(\d{2,3})(?:G(\d{2,3}))?(KT|MPS|KMH)$")
WIND_VAR_RE = re.compile(r"^\d{3}V\d{3}$")
VIS_SM_RE = re.compile(r"^(M)?(\d+(?:/\d+)?)SM$")
CLOUD_RE = re.compile(r"^(FEW|SCT|BKN|OVC|VV)(\d{3}|///)(CB|TCU)?$")
TEMP_RE = re.compile(r"^(M?\d{2})/(M?\d{2})?$")
ALTIM_IN_RE = re.compile(r"^A(\d{4})$")
ALTIM_HPA_RE = re.compile(r"^Q(\d{4})$")
WX_RE = re.compile(
    r"^(?P<int>-|\+|VC)?"
    r"(?P<desc>(?:MI|PR|BC|DR|BL|SH|TS|FZ){0,2})"
    r"(?P<phen>(?:DZ|RA|SN|SG|IC|PL|GR|GS|UP|BR|FG|FU|VA|DU|SA|HZ|PY|PO|SQ|FC|SS|DS)+)$"
)


def _compass(deg):
    return COMPASS_POINTS[int((deg + 11.25) // 22.5) % 16]


def _temp_token_to_c(token):
    return -int(token[1:]) if token.startswith("M") else int(token)


def _c_to_f(c):
    return round(c * 9 / 5 + 32)


def _kt_to_mph(kt):
    return round(kt * 1.15078)


def _split_wx_phenomena(phen):
    """Split a run of 2-letter phenomenon codes, e.g. 'RASN' -> ['RA', 'SN']."""
    return [phen[i:i + 2] for i in range(0, len(phen), 2)]


def _decode_wx_token(tok):
    m = WX_RE.match(tok)
    if not m or not m["phen"]:
        return None, []
    words = []
    if m["int"] == "+":
        words.append("Heavy")
    elif m["int"] == "-":
        words.append("Light")
    elif m["int"] == "VC":
        words.append("Nearby")
    codes = []
    if m["desc"]:
        for i in range(0, len(m["desc"]), 2):
            code = m["desc"][i:i + 2]
            codes.append(code)
            if code in WX_DESCRIPTOR:
                words.append(WX_DESCRIPTOR[code])
    phen_codes = _split_wx_phenomena(m["phen"])
    codes.extend(phen_codes)
    phen_words = [WX_PHENOMENON.get(code, code) for code in phen_codes]
    words.append(" and ".join(phen_words))
    return " ".join(words), codes


def _parse_visibility(tok):
    m = VIS_SM_RE.match(tok)
    if not m:
        return None
    prefix = "Less than " if m[1] else ""
    num = m[2]
    label = "statute mile" if num == "1" else "statute miles"
    return f"{prefix}{num} {label}"


def _merge_fraction_visibility(tokens):
    """Merge whole-number + fraction visibility groups, e.g. ['1', '1/2SM'] -> ['1 1/2SM']."""
    merged = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        nxt = tokens[i + 1] if i + 1 < len(tokens) else ""
        if re.match(r"^\d+$", tok) and re.match(r"^\d+/\d+SM$", nxt):
            merged.append(f"{tok} {nxt}")
            i += 2
        else:
            merged.append(tok)
            i += 1
    return merged


def _parse_merged_visibility(tok):
    """Handle a pre-merged 'WHOLE NUM/DENSM' token, e.g. '1 1/2SM'."""
    m = re.match(r"^(\d+) (\d+)/(\d+)SM$", tok)
    if not m:
        return None
    whole, num, den = m.groups()
    return f"{whole} {num}/{den} statute miles"


def _weather_icon(cloud_layers, wx_codes):
    if "TS" in wx_codes:
        return "⛈️"
    if any(c in wx_codes for c in ("RA", "DZ", "SH")):
        return "🌧️"
    if any(c in wx_codes for c in ("SN", "SG", "PL", "GR", "GS")):
        return "❄️"
    if any(c in wx_codes for c in ("FG", "BR", "HZ")):
        return "🌫️"
    if not cloud_layers:
        return "☀️"
    top_cover = max((layer["rank"] for layer in cloud_layers), default=0)
    if top_cover == 0:
        return "☀️"
    if top_cover <= 2:
        return "🌤️"
    if top_cover == 3:
        return "⛅"
    return "☁️"


def decode_metar(raw):
    """Parse a raw METAR string into a friendly summary plus a structured detail list."""
    text = raw.strip()
    tokens = text.split()
    if tokens and tokens[0] in ("METAR", "SPECI"):
        tokens = tokens[1:]
    if not tokens:
        raise ValueError("Empty METAR report")

    tokens = _merge_fraction_visibility(tokens)

    station = tokens[0]
    details = [("Station", station)]

    observed = None
    auto_station = False
    wind_desc = None
    vis_desc = None
    wx_words = []
    wx_codes = []
    cloud_layers = []
    temp_c = dew_c = None
    altim_desc = None

    for tok in tokens[1:]:
        if tok == "RMK":
            break
        if tok in ("AUTO", "COR"):
            auto_station = tok == "AUTO"
            continue
        if tok == "CAVOK":
            vis_desc = "10+ statute miles (CAVOK)"
            continue
        if WIND_VAR_RE.match(tok):
            continue

        m = DATETIME_RE.match(tok)
        if m:
            observed = f"Day {m[1]} of the month, {m[2]}:{m[3]} UTC"
            continue

        m = WIND_RE.match(tok)
        if m:
            direction, speed, gust, unit = m.groups()
            speed = int(speed)
            gust = int(gust) if gust else None
            if unit == "KT":
                to_mph = _kt_to_mph
            elif unit == "KMH":
                to_mph = lambda v: round(v * 0.621371)
            else:  # MPS
                to_mph = lambda v: round(v * 2.23694)
            if speed == 0:
                wind_desc = "calm"
            else:
                if direction == "VRB":
                    dir_phrase = "variable directions"
                else:
                    deg = int(direction)
                    dir_phrase = f"the {_compass(deg)} ({deg}°)"
                wind_desc = f"from {dir_phrase} at {to_mph(speed)} mph"
                if gust:
                    wind_desc += f", gusting to {to_mph(gust)} mph"
            continue

        merged_vis = _parse_merged_visibility(tok)
        if merged_vis:
            vis_desc = merged_vis
            continue

        vis = _parse_visibility(tok)
        if vis:
            vis_desc = vis
            continue

        if vis_desc is None and re.match(r"^\d{4}$", tok):
            meters = int(tok)
            if meters == 9999:
                vis_desc = "10+ km (6.2+ miles)"
            else:
                vis_desc = f"{meters:,} m ({meters / 1609.34:.1f} miles)"
            continue

        m = CLOUD_RE.match(tok)
        if m:
            cover, height, cloud_type = m.groups()
            if cover == "VV":
                if height == "///":
                    cloud_layers.append({"text": "Indefinite ceiling, height unknown", "rank": COVER_RANK["VV"]})
                else:
                    feet = int(height) * 100
                    cloud_layers.append({"text": f"Indefinite ceiling (vertical visibility) at {feet:,} ft",
                                          "rank": COVER_RANK["VV"]})
            else:
                label = SKY_COVER[cover]
                if height == "///":
                    cloud_layers.append({"text": f"{label}, height unknown", "rank": COVER_RANK[cover]})
                else:
                    feet = int(height) * 100
                    extra = " (cumulonimbus)" if cloud_type == "CB" else " (towering cumulus)" if cloud_type == "TCU" else ""
                    cloud_layers.append({"text": f"{label} at {feet:,} ft{extra}", "rank": COVER_RANK[cover]})
            continue

        if tok in ("SKC", "CLR", "NSC", "NCD"):
            cloud_layers.append({"text": SKY_COVER[tok], "rank": 0})
            continue

        m = TEMP_RE.match(tok)
        if m and (m[1] or m[2]):
            temp_c = _temp_token_to_c(m[1])
            dew_c = _temp_token_to_c(m[2]) if m[2] else None
            continue

        m = ALTIM_IN_RE.match(tok)
        if m:
            altim_desc = f"{int(m[1]) / 100:.2f} inHg"
            continue

        m = ALTIM_HPA_RE.match(tok)
        if m:
            altim_desc = f"{int(m[1])} hPa"
            continue

        wx_word, codes = _decode_wx_token(tok)
        if wx_word:
            wx_words.append(wx_word)
            wx_codes.extend(codes)
            continue
        # Unrecognized token (e.g. an unusual remark group): ignore gracefully.

    def _cap(s):
        return s[0].upper() + s[1:]

    if observed:
        details.append(("Observed", observed))
    details.append(("Wind", _cap(wind_desc) if wind_desc else "Not reported"))
    details.append(("Visibility", vis_desc or "Not reported"))
    details.append(("Weather", "; ".join(wx_words) if wx_words else "None reported"))
    details.append(("Sky condition", "; ".join(layer["text"] for layer in cloud_layers) if cloud_layers else "Not reported"))
    if temp_c is not None:
        details.append(("Temperature", f"{_c_to_f(temp_c)}°F ({temp_c}°C)"))
    if dew_c is not None:
        details.append(("Dew point", f"{_c_to_f(dew_c)}°F ({dew_c}°C)"))
    details.append(("Altimeter", altim_desc or "Not reported"))
    if auto_station:
        details.append(("Station type", "Automated"))

    sky_phrase = max(cloud_layers, key=lambda l: l["rank"])["text"] if cloud_layers else "Clear skies"

    sentence_parts = []
    if wx_words:
        sentence_parts.append(", ".join(wx_words))
        sentence_parts.append(sky_phrase[0].lower() + sky_phrase[1:])
    else:
        sentence_parts.append(sky_phrase)
    if temp_c is not None:
        sentence_parts.append(f"{_c_to_f(temp_c)}°F")
    sentence_parts.append(f"wind {wind_desc if wind_desc else 'not reported'}")
    if vis_desc:
        sentence_parts.append(f"visibility {vis_desc.lower()}")
    summary = ", ".join(sentence_parts) + "."
    summary = summary[0].upper() + summary[1:]

    icon = _weather_icon(cloud_layers, wx_codes)

    return {"summary": summary, "details": details, "icon": icon}

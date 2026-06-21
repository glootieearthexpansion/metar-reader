import pytest

from metar_decoder import decode_metar


def detail_dict(result):
    return dict(result["details"])


def test_typical_clear_report():
    raw = "METAR KJFK 190951Z 30011KT 10SM SCT170 BKN250 23/11 A2968 RMK AO2 PK WND 31030/0853"
    result = decode_metar(raw)
    details = detail_dict(result)

    assert details["Station"] == "KJFK"
    assert details["Wind"] == "From the WNW (300°) at 13 mph"
    assert details["Visibility"] == "10 statute miles"
    assert details["Weather"] == "None reported"
    assert "Scattered clouds at 17,000 ft" in details["Sky condition"]
    assert "Broken clouds at 25,000 ft" in details["Sky condition"]
    assert details["Temperature"] == "73°F (23°C)"
    assert details["Dew point"] == "52°F (11°C)"
    assert details["Altimeter"] == "29.68 inHg"
    assert "Station type" not in details  # no AUTO token present
    assert "WNW" in result["summary"]  # compass point keeps its casing in the summary too


def test_auto_station_flag():
    raw = "KDEN 191751Z AUTO 27015KT 10SM CLR 28/18 A2995"
    details = detail_dict(decode_metar(raw))
    assert details["Station type"] == "Automated"


def test_rmk_section_is_not_parsed():
    raw = "KJFK 190951Z 30011KT 10SM SKC 23/11 A2968 RMK AO2 +RA SLP049"
    details = detail_dict(decode_metar(raw))
    # +RA appears only after RMK, so it must not be picked up as real weather.
    assert details["Weather"] == "None reported"


@pytest.mark.parametrize(
    "token, expected_substring",
    [
        ("00000KT", "Calm"),
        ("VRB03KT", "variable directions"),
        ("18006KT", "the S (180°)"),
        ("27015G25KT", "gusting to 29 mph"),
    ],
)
def test_wind_variants(token, expected_substring):
    raw = f"KTST 191751Z {token} 10SM CLR 20/10 A3000"
    details = detail_dict(decode_metar(raw))
    assert expected_substring in details["Wind"]


@pytest.mark.parametrize(
    "unit_token, expected_mph",
    [
        ("18010MPS", 22),  # 10 m/s ~= 22 mph
        ("18020KMH", 12),  # 20 km/h ~= 12 mph
    ],
)
def test_wind_unit_conversion(unit_token, expected_mph):
    raw = f"KTST 191751Z {unit_token} 10SM CLR 20/10 A3000"
    details = detail_dict(decode_metar(raw))
    assert f"{expected_mph} mph" in details["Wind"]


@pytest.mark.parametrize(
    "vis_token, expected",
    [
        ("10SM", "10 statute miles"),
        ("1SM", "1 statute mile"),
        ("1/2SM", "1/2 statute miles"),
        ("M1/4SM", "Less than 1/4 statute miles"),
    ],
)
def test_visibility_statute_miles(vis_token, expected):
    raw = f"KTST 191751Z 00000KT {vis_token} CLR 20/10 A3000"
    details = detail_dict(decode_metar(raw))
    assert details["Visibility"] == expected


def test_visibility_mixed_whole_and_fraction():
    raw = "KDEN 191751Z 27015G25KT 1 1/2SM +TSRA BKN030CB 28/18 A2995"
    details = detail_dict(decode_metar(raw))
    assert details["Visibility"] == "1 1/2 statute miles"


def test_visibility_meters():
    raw = "EGLL 191750Z VRB03KT 0800 FEW020 18/10 Q1015"
    details = detail_dict(decode_metar(raw))
    assert "800" in details["Visibility"]
    assert "m" in details["Visibility"]


def test_visibility_meters_cavok_equivalent():
    raw = "EGLL 191750Z VRB03KT 9999 FEW020 18/10 Q1015"
    details = detail_dict(decode_metar(raw))
    assert "10+ km" in details["Visibility"]


def test_weather_phenomena_heavy_thunderstorm():
    raw = "KDEN 191751Z 27015G25KT 1 1/2SM +TSRA BKN030CB 28/18 A2995"
    details = detail_dict(decode_metar(raw))
    assert details["Weather"] == "Heavy thunderstorm with rain"
    assert "(cumulonimbus)" in details["Sky condition"]


def test_weather_phenomena_combined_codes():
    raw = "KBOS 191754Z 18006KT 1/2SM -RASN BR BKN008 OVC015 M02/M05 A2980"
    details = detail_dict(decode_metar(raw))
    assert details["Weather"] == "Light rain and snow; mist"


def test_sky_cover_clear_tokens():
    for token in ("SKC", "CLR", "NSC", "NCD"):
        raw = f"KTST 191751Z 00000KT 10SM {token} 20/10 A3000"
        details = detail_dict(decode_metar(raw))
        assert details["Sky condition"] != "Not reported"


def test_sky_cover_indefinite_ceiling():
    raw = "KORD 191751Z 00000KT M1/4SM FG VV002 05/05 A3001"
    details = detail_dict(decode_metar(raw))
    assert "Indefinite ceiling" in details["Sky condition"]
    assert "200 ft" in details["Sky condition"]


def test_negative_temperature_and_dewpoint():
    raw = "KBOS 191754Z 18006KT 1/2SM RASN BR BKN008 OVC015 M02/M05 A2980"
    details = detail_dict(decode_metar(raw))
    assert details["Temperature"] == "28°F (-2°C)"
    assert details["Dew point"] == "23°F (-5°C)"


def test_altimeter_hpa():
    raw = "EGLL 191750Z VRB03KT 9999 FEW020 18/10 Q1015"
    details = detail_dict(decode_metar(raw))
    assert details["Altimeter"] == "1015 hPa"


def test_metar_prefix_is_stripped():
    raw = "METAR KJFK 190951Z 30011KT 10SM SCT170 23/11 A2968"
    details = detail_dict(decode_metar(raw))
    assert details["Station"] == "KJFK"


def test_empty_report_raises():
    with pytest.raises(ValueError):
        decode_metar("   ")


@pytest.mark.parametrize(
    "raw, expected_icon",
    [
        ("KTST 191751Z 00000KT 10SM CLR 20/10 A3000", "☀️"),
        ("KTST 191751Z 00000KT 10SM OVC050 20/10 A3000", "☁️"),
        ("KDEN 191751Z 27015G25KT 1 1/2SM +TSRA BKN030CB 28/18 A2995", "⛈️"),
        ("KTST 191751Z 00000KT 10SM -RA BKN020 20/10 A3000", "🌧️"),
        ("KTST 191751Z 00000KT 10SM -SN BKN020 M05/M10 A3000", "❄️"),
        ("KORD 191751Z 00000KT M1/4SM FG VV002 05/05 A3001", "🌫️"),
    ],
)
def test_icon_selection(raw, expected_icon):
    result = decode_metar(raw)
    assert result["icon"] == expected_icon

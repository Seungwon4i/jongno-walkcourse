"""
make_map.py — 도달성 + A→B→C 동선 folium 지도 (v1.0 데모 시각화)

경복궁 출발, 120분 예산으로:
  - 도달 가능 후보(상위 N)를 카테고리별 색 CircleMarker 로 표시
  - reachable 을 매 단계 상위 1곳 선택해 A→B→C… 체이닝한 동선을 PolyLine 으로 연결
  - 출발점(A)·동선 노드는 강조 마커
  - 마커 팝업: 이름·카테고리·도보시간·hotspot_score
결과 HTML 저장 → outputs/reachability_map.html

사용:
    python scripts/make_map.py
필요:
    conda install -c conda-forge folium   (또는 pip install folium)
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

try:
    import folium
except ImportError:
    sys.exit("folium 이 필요합니다:\n  conda install -c conda-forge folium\n  (또는 pip install folium)")

from backend.reachability import _load, reachable  # noqa: E402

# ──────────────────────────────────────────────────────────────────────────
# 설정
# ──────────────────────────────────────────────────────────────────────────

START_KEYWORD = "경복궁"
BUDGET_MIN = 120.0
DISPLAY_N = 120          # 후보 마커는 hotspot 상위 N 개만(가독성)
OUTPUT_PATH = REPO_ROOT / "outputs" / "reachability_map.html"

# 카테고리별 색
CATEGORY_COLORS = {
    "음식점": "red",
    "카페": "blue",
    "관광명소": "green",
}
DEFAULT_COLOR = "gray"


def _popup_html(name, category, od_min, hotspot, prefix=""):
    return folium.Popup(
        f"<b>{prefix}{name}</b><br>"
        f"카테고리: {category}<br>"
        f"도보시간: {od_min:.1f}분<br>"
        f"hotspot: {hotspot:.3f}",
        max_width=250,
    )


def main() -> None:
    pois, _ = _load()
    start = pois[(pois["name"].str.contains(START_KEYWORD, na=False)) &
                 (pois["category_main"] == "관광명소")]
    if start.empty:
        sys.exit(f"출발점 '{START_KEYWORD}' 을 찾지 못했습니다.")
    sid = start.index[0]
    s_lat, s_lon = float(start.loc[sid, "lat"]), float(start.loc[sid, "lon"])
    s_name = start.loc[sid, "name"]

    # 도달 가능 후보(출발점 기준)
    field = reachable(sid, BUDGET_MIN)
    shown = field[:DISPLAY_N]

    # A→B→C… 체이닝
    chain = []
    current, budget, visited = sid, BUDGET_MIN, [sid]
    while True:
        res = reachable(current, budget, visited=visited)
        if not res:
            break
        pick = res[0]
        chain.append(pick)
        current, budget = pick["place_id"], pick["remaining_min"]
        visited.append(pick["place_id"])

    # 지도
    m = folium.Map(location=[s_lat, s_lon], zoom_start=14, tiles="OpenStreetMap")

    # 후보 색 마커 (CircleMarker, 가벼움)
    field_layer = folium.FeatureGroup(name=f"도달가능 후보 상위 {len(shown)}")
    for r in shown:
        folium.CircleMarker(
            location=[r["lat"], r["lon"]], radius=5,
            color=CATEGORY_COLORS.get(r["category_main"], DEFAULT_COLOR),
            fill=True, fill_opacity=0.7,
            popup=_popup_html(r["name"], r["category_main"], r["od_min"], r["hotspot_score"]),
        ).add_to(field_layer)
    field_layer.add_to(m)

    # 출발점 A 강조
    folium.Marker(
        [s_lat, s_lon], popup=folium.Popup(f"<b>A. {s_name} (출발)</b>", max_width=250),
        icon=folium.Icon(color="green", icon="star", prefix="fa"),
        tooltip="A (출발)",
    ).add_to(m)

    # 동선 노드 + 연결선
    chain_layer = folium.FeatureGroup(name=f"A→B→C 동선 ({len(chain)}단계)")
    coords = [[s_lat, s_lon]]
    for i, p in enumerate(chain):
        letter = chr(ord("B") + i)
        coords.append([p["lat"], p["lon"]])
        folium.Marker(
            [p["lat"], p["lon"]],
            popup=_popup_html(p["name"], p["category_main"], p["od_min"],
                              p["hotspot_score"], prefix=f"{letter}. "),
            icon=folium.Icon(color="purple", icon="flag", prefix="fa"),
            tooltip=f"{letter}. {p['name']}",
        ).add_to(chain_layer)
    folium.PolyLine(coords, color="purple", weight=4, opacity=0.8).add_to(chain_layer)
    chain_layer.add_to(m)

    folium.LayerControl().add_to(m)

    # 범례
    legend = (
        '<div style="position:fixed; bottom:24px; left:24px; z-index:9999; '
        'background:white; padding:10px 12px; border:1px solid #888; border-radius:6px; '
        'font-size:13px; line-height:1.6;">'
        f'<b>경복궁 {BUDGET_MIN:.0f}분 도달권</b><br>'
        '<span style="color:red;">●</span> 음식점 &nbsp;'
        '<span style="color:blue;">●</span> 카페 &nbsp;'
        '<span style="color:green;">●</span> 관광명소<br>'
        '<span style="color:purple;">▬</span> A→B→C 동선'
        '</div>'
    )
    m.get_root().html.add_child(folium.Element(legend))

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    m.save(str(OUTPUT_PATH))

    print(f"도달 후보: {len(field)}곳 (지도 표시 {len(shown)})")
    print(f"동선: {' → '.join([s_name] + [p['name'] for p in chain])}")
    print(f"저장 완료 → {OUTPUT_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()

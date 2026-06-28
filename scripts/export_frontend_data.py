import json
from pathlib import Path
import numpy as np
import pandas as pd

DATA = Path("data/processed")
OUT = Path("frontend/public/data")
OUT.mkdir(parents=True, exist_ok=True)

MAX_BUDGET = 180  # 분. 이보다 먼 단일 구간은 도달 불가 → null 처리

# ⚠️ backend/reachability.py 의 STAY_MINUTES 와 정확히 동일.
#    (reachability.py:32-37 확인 — 음식점40/카페20/관광명소30, DEFAULT_STAY=30)
STAY_MINUTES = {
    "음식점": 40,
    "카페": 20,
    "관광명소": 30,
}
DEFAULT_STAY = 30

pois = pd.read_parquet(DATA / "pois_final.parquet")
od = pd.read_parquet(DATA / "od_matrix.parquet")

print("POI 수:", len(pois))
print("컬럼:", list(pois.columns))
print("category_main 분포:\n", pois["category_main"].value_counts())
print("STAY_MINUTES:", STAY_MINUTES, "DEFAULT_STAY:", DEFAULT_STAY)

place_ids = pois["place_id"].astype(str).tolist()

# OD행렬을 pois 순서로 양축 reindex (행=출발, 열=도착)
# od_matrix.parquet 은 place_id 를 '컬럼'으로 저장(build_graph reset_index) → 인덱스로 복원
if "place_id" in od.columns:
    od = od.set_index("place_id")
od.index = od.index.astype(str)
od.columns = od.columns.astype(str)
od = od.reindex(index=place_ids, columns=place_ids)

times = od.to_numpy(dtype=float)
nan_before = np.isnan(times).mean()
times = np.round(times, 1)
times = np.where(times > MAX_BUDGET, np.nan, times)  # 가지치기
nan_after = np.isnan(times).mean()
print(f"OD shape: {times.shape}, NaN 비율: 전 {nan_before:.1%} → 후 {nan_after:.1%}")

def stay_for(cat):
    return int(STAY_MINUTES.get(cat, DEFAULT_STAY))

def classify(row):
    cn = str(row.get("category_name", ""))
    parts = [p.strip() for p in cn.split(">")]
    main = row["category_main"]
    # 음식점 세분
    if main == "음식점":
        t = parts[1] if len(parts) > 1 else ""
        if t == "한식": return "한식"
        if t == "술집": return "술집"
        return "식당(기타)"   # 일식·중식·양식·분식·아시아 등
    if main == "카페":
        return "카페"
    # 관광 세분 (TourAPI 평면은 parts 길이가 짧음)
    if main == "관광명소":
        # 카카오 AT4: "여행 > 관광,명소 > 3번째토큰"
        t3 = parts[2] if len(parts) > 2 else ""
        유적 = {"문화유적", "고궁,궁", "관광,명소"}
        자연거리 = {"테마거리", "도보여행", "전망대", "산", "계곡", "수목원,식물원", "숲", "드라이브코스", "저수지", "도자기,도예촌", "테마파크"}
        if t3 in 유적: return "명소·유적"
        if t3 in 자연거리: return "거리·자연"
        # TourAPI 평면("관광명소"만 있고 계층 없음) 또는 미매칭
        return "기타관광"
    return "기타"

pois_out = []
for _, r in pois.iterrows():
    pois_out.append({
        "id": str(r["place_id"]),
        "name": str(r["name"]),
        "cat": str(r["category_main"]),
        "cat2": classify(r),
        "gu": str(r["gu"]),
        "lon": round(float(r["lon"]), 6),
        "lat": round(float(r["lat"]), 6),
        "score": round(float(r["hotspot_score"]), 4),
        "stay": stay_for(r["category_main"]),
    })

from collections import Counter
print("cat2 분포:")
for k, v in Counter(p["cat2"] for p in pois_out).most_common():
    print(f"  {k}: {v}")

times_list = [[None if np.isnan(v) else float(v) for v in row] for row in times]

with open(OUT / "pois.json", "w", encoding="utf-8") as f:
    json.dump(pois_out, f, ensure_ascii=False)
with open(OUT / "od.json", "w", encoding="utf-8") as f:
    json.dump({"ids": place_ids, "times": times_list}, f)

for fn in ["pois.json", "od.json"]:
    mb = (OUT / fn).stat().st_size / 1e6
    print(f"{fn}: {mb:.2f} MB")

# 스팟체크: 경복궁 60분 도달 후보 수 (v1.0 검증값 ~467)
start_idx = next((i for i, p in enumerate(pois_out) if "경복궁" in p["name"]), None)
if start_idx is not None:
    budget, cnt = 60, 0
    for j, p in enumerate(pois_out):
        if j == start_idx:
            continue
        t = times_list[start_idx][j]
        if t is not None and t + p["stay"] <= budget:
            cnt += 1
    print(f"스팟체크: 경복궁(idx={start_idx}) 60분 도달 후보 = {cnt}곳 (v1.0 ~467 비교)")
else:
    print("스팟체크: '경복궁' 이름 노드를 못 찾음 — 출발점 이름 확인 필요")

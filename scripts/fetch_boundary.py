"""
fetch_boundary.py — 종로구 행정경계 GeoJSON 다운로드 (VWorld 2D데이터 API)

frontend/.env 의 VITE_VWORLD_KEY 를 재사용. 키 값은 출력하지 않는다.
출력 → frontend/public/data/jongno_boundary.geojson
"""

from pathlib import Path
import json
import sys
import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = REPO_ROOT / "frontend" / ".env"
OUT = REPO_ROOT / "frontend" / "public" / "data" / "jongno_boundary.geojson"

# .env 에서 키 읽기 (출력 금지)
key = ""
for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line.startswith("VITE_VWORLD_KEY="):
        key = line.split("=", 1)[1].strip()
if not key:
    sys.exit("frontend/.env 에 VITE_VWORLD_KEY 가 비어 있습니다.")

def mask(s):
    return s.replace(key, "***KEY***") if key else s

URL = "https://api.vworld.kr/req/data"
params = {
    "service": "data",
    "request": "GetFeature",
    "data": "LT_C_ADSIGG_INFO",
    "key": key,
    "domain": "http://localhost:5173",
    "format": "json",
    "geometry": "true",
    "attrFilter": "sig_kor_nm:like:종로구",
    "size": "10",
    "crs": "EPSG:4326",
}

resp = requests.get(URL, params=params, timeout=30)
print("HTTP", resp.status_code)

try:
    data = resp.json()
except ValueError:
    sys.exit(f"JSON 파싱 실패. 본문:\n{mask(resp.text[:600])}")

# VWorld 응답 구조: response.status / response.result.featureCollection
res = data.get("response", {})
status = res.get("status")
print("response.status:", status)

if status != "OK":
    err = res.get("error") or res
    sys.exit(f"VWorld 오류: {mask(json.dumps(err, ensure_ascii=False))[:600]}")

fc = res.get("result", {}).get("featureCollection")
if not fc or not fc.get("features"):
    sys.exit(f"피처 없음. 응답 일부:\n{mask(json.dumps(res, ensure_ascii=False))[:600]}")

feats = fc["features"]

def count_coords(geom):
    n = 0
    def walk(x):
        nonlocal n
        if isinstance(x, (list, tuple)):
            if x and isinstance(x[0], (int, float)):
                n += 1
            else:
                for e in x:
                    walk(e)
    walk(geom.get("coordinates", []))
    return n

total_coords = sum(count_coords(f.get("geometry", {})) for f in feats)
names = [f.get("properties", {}).get("sig_kor_nm") for f in feats]

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(fc, ensure_ascii=False), encoding="utf-8")

print(f"피처 수: {len(feats)} | 이름: {names}")
print(f"좌표(점) 개수: {total_coords}")
print(f"geometry type: {[f.get('geometry', {}).get('type') for f in feats]}")
print(f"저장 완료 → {OUT.relative_to(REPO_ROOT)} ({OUT.stat().st_size/1024:.1f} KB)")

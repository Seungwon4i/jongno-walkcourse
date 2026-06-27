"""
preprocess_pois.py — 수집한 종로 POI 전처리 (경계 클리핑 + 구 라벨 + 카테고리 정리)

입력 : data/raw/jongno_pois.parquet           (collect_pois.py 산출물)
출력 : data/processed/pois_clean.parquet

하는 일
  1) 행정구역 경계(GeoJSON)로 종로구 + 인접 버퍼(중·서대문·성북·은평) 안의 POI만 남김
     - 수집은 사각형 bbox 라 구 경계 밖 POI 가 섞여 있음 → 실제 구 폴리곤으로 클리핑
  2) 각 POI 에 소속 구(gu) 컬럼 추가 (point-in-polygon)
  3) 카테고리 라벨 정돈 (category_main 정규화 + 세부 category_sub 추출)
  4) data/processed/pois_clean.parquet 저장

⚠️ 노드 캡(500~800)은 여기서 하지 않는다 — 언급량 피처를 붙인 뒤 별도 단계에서.

경계 데이터 출처 (공개):
  southkorea/seoul-maps  (서울 25개 자치구 GeoJSON, 통계청 2013 기준, 단순화 버전)
  https://github.com/southkorea/seoul-maps
  파일: kostat/2013/json/seoul_municipalities_geo_simple.json
  ※ '서울 전용' 파일이라 properties.name 의 '중구' 가 타 시도 중구와 혼동되지 않음.

사용:
    python scripts/preprocess_pois.py
필요:
    pip install geopandas shapely requests pandas pyarrow
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _ensure_gdal_data() -> None:
    """GDAL_DATA/PROJ 데이터 경로를 conda 환경에서 자동 탐지해 설정.

    geopandas(pyogrio) 임포트 *전에* 호출해야 한다. 이미 설정돼 있으면 건드리지 않음.
    Anaconda(win): <prefix>/Library/share/{gdal,proj}, 그 외: <prefix>/share/{gdal,proj}.
    """
    prefix = Path(sys.prefix)
    for env_var, sub in (("GDAL_DATA", "gdal"), ("PROJ_DATA", "proj")):
        if os.environ.get(env_var):
            continue  # 사용자가 이미 지정했으면 존중
        for cand in (prefix / "Library" / "share" / sub, prefix / "share" / sub):
            if cand.is_dir():
                os.environ[env_var] = str(cand)
                break


_ensure_gdal_data()

try:
    import pandas as pd
except ImportError:
    sys.exit("pandas 가 필요합니다:  pip install pandas pyarrow")

try:
    import geopandas as gpd
except ImportError:
    sys.exit("geopandas 가 필요합니다:  pip install geopandas shapely")

import requests


# ──────────────────────────────────────────────────────────────────────────
# 설정
# ──────────────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent
INPUT_PATH = REPO_ROOT / "data" / "raw" / "jongno_pois.parquet"
OUTPUT_PATH = REPO_ROOT / "data" / "processed" / "pois_clean.parquet"

# 경계 GeoJSON (없으면 받아서 캐시)
BOUNDARY_URL = (
    "https://raw.githubusercontent.com/southkorea/seoul-maps/master/"
    "kostat/2013/json/seoul_municipalities_geo_simple.json"
)
BOUNDARY_CACHE = REPO_ROOT / "data" / "raw" / "seoul_municipalities.geojson"

# 남길 구: 종로 + 인접 버퍼
TARGET_GUS = ["종로구", "중구", "서대문구", "성북구", "은평구"]

# 카카오 category_group_code → 표준 라벨 (라벨 정돈의 기준)
CATEGORY_LABELS = {"FD6": "음식점", "CE7": "카페", "AT4": "관광명소"}

CRS_WGS84 = "EPSG:4326"


# ──────────────────────────────────────────────────────────────────────────
# 단계별 함수
# ──────────────────────────────────────────────────────────────────────────

def load_boundaries() -> gpd.GeoDataFrame:
    """서울 자치구 경계 로드(캐시 우선) → 대상 구만 필터."""
    if not BOUNDARY_CACHE.exists():
        print(f"경계 GeoJSON 내려받는 중...\n  {BOUNDARY_URL}")
        resp = requests.get(BOUNDARY_URL, timeout=30)
        resp.raise_for_status()
        BOUNDARY_CACHE.parent.mkdir(parents=True, exist_ok=True)
        BOUNDARY_CACHE.write_bytes(resp.content)
        print(f"  캐시 저장 → {BOUNDARY_CACHE.relative_to(REPO_ROOT)}")
    else:
        print(f"경계 GeoJSON 캐시 사용 → {BOUNDARY_CACHE.relative_to(REPO_ROOT)}")

    gdf = gpd.read_file(BOUNDARY_CACHE)
    if gdf.crs is None:
        gdf = gdf.set_crs(CRS_WGS84)
    else:
        gdf = gdf.to_crs(CRS_WGS84)

    # properties.name 에 자치구 한글명이 들어 있음
    if "name" not in gdf.columns:
        sys.exit(f"경계 데이터에 'name' 컬럼이 없습니다. 실제 컬럼: {list(gdf.columns)}")

    target = gdf[gdf["name"].isin(TARGET_GUS)][["name", "geometry"]].copy()
    target = target.rename(columns={"name": "gu"})
    found = sorted(target["gu"].unique())
    missing = [g for g in TARGET_GUS if g not in found]
    print(f"  대상 구 폴리곤: {found}" + (f"  ⚠️ 누락: {missing}" if missing else ""))
    return target


def clip_and_label(df: pd.DataFrame, boundaries: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """POI 를 점 지오메트리로 만들고, 대상 구 폴리곤 안에 드는 것만 남기며 gu 라벨 부여."""
    pts = gpd.GeoDataFrame(
        df.copy(),
        geometry=gpd.points_from_xy(df["lon"], df["lat"]),
        crs=CRS_WGS84,
    )
    # point-in-polygon: 폴리곤 안에 든 점만 (구 경계 밖은 자동 탈락 = 클리핑)
    joined = gpd.sjoin(pts, boundaries, how="inner", predicate="within")
    joined = joined.drop(columns=["index_right"])
    # 경계가 겹치는 극소수 점이 중복될 수 있어 place_id 기준 1개만
    joined = joined.drop_duplicates(subset="place_id", keep="first")
    return joined


def tidy_categories(df: pd.DataFrame) -> pd.DataFrame:
    """카테고리 라벨 정돈: main 정규화 + 세부(sub) 추출 + 문자열 공백 정리."""
    df = df.copy()

    # main 라벨을 코드 기준으로 표준화 (수집 단계 값이 있어도 코드를 진실로)
    df["category_main"] = df["category_group_code"].map(CATEGORY_LABELS)

    # category_name 예: "음식점 > 한식 > 육류,고기" → 가장 구체적인 끝 항목을 sub 로
    def last_segment(s: str) -> str:
        if not isinstance(s, str) or not s.strip():
            return ""
        return s.split(">")[-1].strip()

    df["category_sub"] = df["category_name"].map(last_segment)

    # 이름/주소 공백 정리
    for col in ["name", "address_name", "road_address_name", "category_name"]:
        df[col] = df[col].fillna("").astype(str).str.strip()

    return df


# ──────────────────────────────────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────────────────────────────────

def main() -> None:
    if not INPUT_PATH.exists():
        sys.exit(f"입력 파일이 없습니다: {INPUT_PATH}\n  먼저 collect_pois.py 를 실행하세요.")

    print("=" * 60)
    print("POI 전처리 시작")
    print("=" * 60)

    raw = pd.read_parquet(INPUT_PATH)
    print(f"입력: {len(raw):,} POI  ({INPUT_PATH.relative_to(REPO_ROOT)})")

    boundaries = load_boundaries()

    print("\n경계 클리핑 + 구 라벨링 중...")
    clipped = clip_and_label(raw, boundaries)
    dropped = len(raw) - len(clipped)
    print(f"  남은 POI: {len(clipped):,}  (구 경계 밖 제거: {dropped:,})")

    print("\n카테고리 라벨 정돈 중...")
    clean = tidy_categories(clipped)

    # 저장 (지오메트리는 빼고 평범한 테이블로 — lon/lat 로 충분)
    out_cols = [
        "place_id", "name", "gu",
        "category_main", "category_sub", "category_group_code", "category_name",
        "phone", "address_name", "road_address_name",
        "lon", "lat", "place_url",
    ]
    out = pd.DataFrame(clean[out_cols])
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUTPUT_PATH, index=False)
    print(f"\n저장 완료 → {OUTPUT_PATH.relative_to(REPO_ROOT)}  ({len(out):,} rows)")

    # 요약
    print("\n구별 집계:")
    for gu, cnt in out["gu"].value_counts().items():
        print(f"  - {gu}: {cnt:,}")
    print("\n카테고리별 집계:")
    for cat, cnt in out["category_main"].value_counts().items():
        print(f"  - {cat}: {cnt:,}")


if __name__ == "__main__":
    main()

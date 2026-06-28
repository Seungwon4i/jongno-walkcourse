"""
build_graph.py — 보행 네트워크(로컬 PBF) + 946 노드 OD(도보시간) 행렬 사전계산

레이어 (A) 의 마지막 산출물. 레이어 (B) 도달성 엔진이 쓸 OD 행렬을 만든다.

※ Overpass 공개 서버가 큰 보행망 쿼리에 불안정해, pyrosm + Geofabrik/BBBike
   .pbf 추출본을 '한 번만' 내려받아 로컬에서 네트워크를 만든다(서버 의존 제거).

입력 : data/processed/pois_final.parquet   (946 노드)
출력 :
  data/processed/walk_graph.gpickle   보행망 그래프(pickle, 경로 폴리라인 그리기용)
  data/processed/od_matrix.parquet    N×N 도보시간(분) 행렬 (행/열 = place_id)
  data/processed/node_snap.parquet    각 POI → 도로망 노드 매핑 + 스냅 거리(m)

방식
  1) pyrosm 으로 서울 .pbf 다운로드/캐시 (data/raw/osm_pbf/)
  2) 종로+버퍼 bbox 로 클립해 보행(walking) 네트워크 → networkx 그래프
  3) 엣지에 travel_time(분) 부여 (보행속도 WALK_SPEED_KMH)
  4) 각 POI 를 가장 가까운 도로망 노드에 스냅
  5) 스냅 노드별 Dijkstra 로 N×N 최단 도보시간 행렬 (CHECKPOINT 마다 중간 저장)

사용:
    python -u scripts/build_graph.py
필요:
    conda install -c conda-forge pyrosm   (또는 pip install pyrosm)
    (networkx, osmnx[스냅용], pandas, pyarrow 는 이미 설치됨)
"""

from __future__ import annotations

import os
import pickle
import sys
import time
from pathlib import Path


def _ensure_geo_data() -> None:
    """GDAL_DATA/PROJ 경로 자동 설정."""
    prefix = Path(sys.prefix)
    for env_var, sub in (("GDAL_DATA", "gdal"), ("PROJ_DATA", "proj")):
        if os.environ.get(env_var):
            continue
        for cand in (prefix / "Library" / "share" / sub, prefix / "share" / sub):
            if cand.is_dir():
                os.environ[env_var] = str(cand)
                break


_ensure_geo_data()

try:
    import numpy as np
    import pandas as pd
except ImportError:
    sys.exit("numpy/pandas 가 필요합니다:  pip install numpy pandas pyarrow")

try:
    import networkx as nx
except ImportError:
    sys.exit("networkx 가 필요합니다:  pip install networkx")

try:
    from pyrosm import OSM, get_data
except ImportError:
    sys.exit("pyrosm 가 필요합니다 (로컬 PBF 보행망):\n"
             "  conda install -c conda-forge pyrosm\n  (또는 pip install pyrosm)")

try:
    import osmnx as ox  # 스냅(nearest_nodes)용
except ImportError:
    ox = None


# ──────────────────────────────────────────────────────────────────────────
# 설정
# ──────────────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent
INPUT_PATH = REPO_ROOT / "data" / "processed" / "pois_final.parquet"
GRAPH_PATH = REPO_ROOT / "data" / "processed" / "walk_graph.gpickle"
OD_PATH = REPO_ROOT / "data" / "processed" / "od_matrix.parquet"
SNAP_PATH = REPO_ROOT / "data" / "processed" / "node_snap.parquet"
PBF_DIR = REPO_ROOT / "data" / "raw" / "osm_pbf"

# pyrosm 데이터셋 후보 (앞에서부터 시도). Seoul=BBBike 시 추출(작음), SouthKorea=Geofabrik.
PBF_DATASETS = ["Seoul", "SouthKorea"]

WALK_SPEED_KMH = 4.5
MARGIN_DEG = 0.01             # bbox 여유 버퍼(약 1.1km)
CHECKPOINT = 200             # 이 행마다 부분 OD 중간 저장

# 좌표 유효성 범위 (서울 대략). 이상 좌표 방어.
LON_MIN, LON_MAX = 126.6, 127.3
LAT_MIN, LAT_MAX = 37.3, 37.9

# 보행은 양방향 통행 가능 → force_bidirectional 로 일방통행성 제거(불필요한 NaN 방지)
FORCE_BIDIRECTIONAL = True

_METERS_PER_MIN = WALK_SPEED_KMH * 1000 / 60


# ──────────────────────────────────────────────────────────────────────────
# 보행망 (로컬 PBF)
# ──────────────────────────────────────────────────────────────────────────

def get_pbf_path() -> str:
    """서울 .pbf 를 캐시(없으면 다운로드)하고 경로 반환."""
    PBF_DIR.mkdir(parents=True, exist_ok=True)
    last = None
    for name in PBF_DATASETS:
        try:
            print(f"  · PBF 확보 시도: {name} (캐시 {PBF_DIR})", flush=True)
            fp = get_data(name, directory=str(PBF_DIR))
            print(f"    OK → {fp}", flush=True)
            return fp
        except Exception as e:
            last = e
            print(f"    실패: {e}", flush=True)
    sys.exit(f"PBF 다운로드 실패. pyrosm 데이터셋명 확인 필요(pyrosm.data.available).\n  {last}")


def build_walk_graph(fp: str, bbox: tuple) -> "nx.MultiDiGraph":
    """PBF → bbox 클립 → 보행 networkx 그래프."""
    west, south, east, north = bbox
    osm = OSM(fp, bounding_box=[west, south, east, north])
    nodes, edges = osm.get_network(network_type="walking", nodes=True)
    if nodes is None or edges is None or len(edges) == 0:
        sys.exit("bbox 내 보행망이 비었습니다. bbox/데이터셋 확인 필요.")
    G = osm.to_graph(
        nodes, edges, graph_type="networkx",
        force_bidirectional=FORCE_BIDIRECTIONAL, retain_all=True,
        osmnx_compatible=True,
    )
    if "crs" not in G.graph:
        G.graph["crs"] = "EPSG:4326"
    return G


def add_walk_traveltime(G: "nx.MultiDiGraph") -> None:
    """엣지 length(m) → travel_time(분). length 없으면 0 처리(드묾)."""
    for _u, _v, data in G.edges(data=True):
        length = data.get("length")
        data["travel_time"] = (length / _METERS_PER_MIN) if length else 0.0


# ──────────────────────────────────────────────────────────────────────────
# 스냅 / OD
# ──────────────────────────────────────────────────────────────────────────

def snap_pois(G, pois: pd.DataFrame):
    """각 POI → 가장 가까운 도로망 노드. (node_ids, snap_dist_m)."""
    if ox is not None:
        nodes, dists = ox.distance.nearest_nodes(
            G, X=pois["lon"].to_numpy(), Y=pois["lat"].to_numpy(), return_dist=True
        )
        return list(nodes), list(dists)
    # osmnx 없으면 직접 최근접 (haversine 근사)
    node_ids = list(G.nodes)
    nx_arr = np.array([G.nodes[n]["x"] for n in node_ids])
    ny_arr = np.array([G.nodes[n]["y"] for n in node_ids])
    snapped, dists = [], []
    for lon, lat in zip(pois["lon"], pois["lat"]):
        dlon = (nx_arr - lon) * 111000 * np.cos(np.radians(lat))
        dlat = (ny_arr - lat) * 111000
        d = np.hypot(dlon, dlat)
        i = int(d.argmin())
        snapped.append(node_ids[i]); dists.append(float(d[i]))
    return snapped, dists


def build_od_matrix(G, snap_nodes, place_ids):
    """스냅 노드별 Dijkstra 로 N×N 도보시간(분) 행렬. CHECKPOINT 마다 부분 저장."""
    n = len(place_ids)
    mat = np.full((n, n), np.nan, dtype=float)
    cache: dict = {}
    t0 = time.time()
    for i in range(n):
        src = snap_nodes[i]
        if src not in cache:
            cache[src] = nx.single_source_dijkstra_path_length(G, src, weight="travel_time")
        lengths = cache[src]
        mat[i, :] = [lengths.get(snap_nodes[j], np.nan) for j in range(n)]
        if (i + 1) % 50 == 0 or i + 1 == n:
            print(f"  OD {i + 1:>4}/{n} | 캐시 {len(cache)} | {time.time() - t0:5.1f}s", flush=True)
        if (i + 1) % CHECKPOINT == 0:
            save_matrix(mat, place_ids)
            print(f"  · 중간 저장 ({i + 1}/{n} 행)", flush=True)
    return mat


def save_matrix(mat: np.ndarray, place_ids: list) -> None:
    df = pd.DataFrame(mat, index=place_ids, columns=[str(p) for p in place_ids])
    df.index.name = "place_id"
    OD_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.reset_index().to_parquet(OD_PATH, index=False)


# ──────────────────────────────────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────────────────────────────────

def main() -> None:
    if not INPUT_PATH.exists():
        sys.exit(f"입력 파일이 없습니다: {INPUT_PATH}\n  먼저 collect_tourapi.py 를 실행하세요.")

    pois = pd.read_parquet(INPUT_PATH).reset_index(drop=True)

    # 방어적 좌표 필터
    valid = pois["lon"].between(LON_MIN, LON_MAX) & pois["lat"].between(LAT_MIN, LAT_MAX)
    if (~valid).any():
        bad = pois[~valid]
        print(f"⚠️ 좌표 이상 {len(bad)}건 제외:")
        for _, r in bad.iterrows():
            print(f"   - {r['name']} ({r['gu']}) lon={r['lon']:.4f} lat={r['lat']:.4f}")
        pois = pois[valid].reset_index(drop=True)

    place_ids = pois["place_id"].tolist()
    n = len(pois)

    west = pois["lon"].min() - MARGIN_DEG
    east = pois["lon"].max() + MARGIN_DEG
    south = pois["lat"].min() - MARGIN_DEG
    north = pois["lat"].max() + MARGIN_DEG

    print("=" * 60)
    print("보행망(로컬 PBF) + OD 행렬 빌드")
    print(f"  노드(POI): {n}")
    print(f"  bbox: W{west:.4f} S{south:.4f} E{east:.4f} N{north:.4f}")
    print(f"  보행속도: {WALK_SPEED_KMH} km/h | 양방향: {FORCE_BIDIRECTIONAL}")
    print("=" * 60)

    print("\n[1/4] 서울 PBF 확보 (최초 1회 다운로드)")
    fp = get_pbf_path()

    print("\n[2/4] bbox 클립 → 보행 네트워크 구축")
    G = build_walk_graph(fp, (west, south, east, north))
    print(f"  그래프: 노드 {G.number_of_nodes():,} / 엣지 {G.number_of_edges():,}")
    add_walk_traveltime(G)

    print("\n[3/4] POI → 도로망 노드 스냅")
    snap_nodes, snap_dists = snap_pois(G, pois)
    pd.DataFrame({
        "place_id": place_ids, "osmid": snap_nodes,
        "snap_dist_m": np.round(snap_dists, 1),
    }).to_parquet(SNAP_PATH, index=False)
    print(f"  스냅 거리(m): 중앙값 {np.median(snap_dists):.1f}, 최대 {np.max(snap_dists):.1f}")
    far = int((np.array(snap_dists) > 100).sum())
    if far:
        print(f"  ⚠️ 도로에서 100m 넘게 떨어진 POI {far}건")

    print("\n[4/4] OD 행렬 계산 (Dijkstra)")
    mat = build_od_matrix(G, snap_nodes, place_ids)

    # 저장
    with open(GRAPH_PATH, "wb") as f:
        pickle.dump(G, f)
    save_matrix(mat, place_ids)

    # 리포트
    total = n * n
    finite = mat[np.isfinite(mat)]
    print("\n저장 완료:")
    print(f"  {GRAPH_PATH.relative_to(REPO_ROOT)}")
    print(f"  {OD_PATH.relative_to(REPO_ROOT)}  ({n}×{n})")
    print(f"  {SNAP_PATH.relative_to(REPO_ROOT)}")
    print(f"\n도달 불가 쌍(NaN): {int(np.isnan(mat).sum()):,} / {total:,} "
          f"({np.isnan(mat).sum() / total * 100:.1f}%)")
    if finite.size:
        print(f"도보시간(분) 분포: 중앙값 {np.median(finite):.1f}, "
              f"평균 {finite.mean():.1f}, 최대 {finite.max():.1f}")


if __name__ == "__main__":
    main()

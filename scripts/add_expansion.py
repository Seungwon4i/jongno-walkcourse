"""
add_expansion.py — 데이터 확장(B): 확정 서점·문화시설·쇼핑 노드를 OD 행렬에 일괄 증분 편입.

add_kyobo.py 의 "1곳 편입"을 "여러 노드 일괄"로 일반화. 안전장치:
원본은 .bak2 백업됨. 기본 실행은 '쓰기 없이' 선별·중복제거 후 최종 대상 목록만 보고.
값 확인 뒤 `--write` 로 실제 OD 편입·저장.

  python scripts/add_expansion.py            # 1·2 (선별 + 중복제거 + 목록 보고, 캐시 저장)
  python scripts/add_expansion.py --write    # 3·4 (OD 증분 편입 + pois_final 갱신)

⚠️ 신규 노드는 보행그래프 '최대 연결 컴포넌트(giant component)'에 스냅 (고립 섬 방지 — 교보문고 교훈).
   보행망 대칭이라 OD 행=열. 정찰 캐시(candidates_scored.json)에서 확정 이름만 매칭.
"""
from __future__ import annotations
import os, sys, json, pickle, argparse
from pathlib import Path


def _ensure_geo():
    pre = Path(sys.prefix)
    for ev, sub in (("GDAL_DATA", "gdal"), ("PROJ_DATA", "proj")):
        if os.environ.get(ev):
            continue
        for c in (pre / "Library" / "share" / sub, pre / "share" / sub):
            if c.is_dir():
                os.environ[ev] = str(c); break


_ensure_geo()
import numpy as np, pandas as pd, networkx as nx, osmnx as ox

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data" / "processed"
POIS, OD = DATA / "pois_final.parquet", DATA / "od_matrix.parquet"
GRAPH, SNAP = DATA / "walk_graph.gpickle", DATA / "node_snap.parquet"
SELECTED_OUT = DATA / "_expansion_selected.json"
# 정찰 점수 캐시 (scout_score.py 산출). 세션 스크래치패드.
CACHE_IN = Path(r"C:\Users\USER\AppData\Local\Temp\claude\C--Users-USER-----Admin-05-Research-Agentic-AI-jongno-walkcourse\25383273-9650-4e22-9d4a-6eb15ecf69e2\scratchpad\candidates_scored.json")

DEDUP_M = 50
STAY = 30  # 서점/문화시설/쇼핑 모두 30분

# 확정 목록: (표시이름, 매칭키). 키는 후보 이름(공백제거)에서 찾을 구분 문자열.
TARGETS = {
    "서점": [
        ("책방오늘", "책방오늘"), ("이라선", "이라선"), ("보안책방", "보안책방"),
        ("서촌그책방", "서촌그책방"), ("동양서림", "동양서림"), ("영풍문고 종각점", "영풍문고"),
        ("북살롱 텍스트북", "북살롱"), ("위트앤시니컬", "위트앤시니컬"),
        ("알라딘중고 종로점", "알라딘중고서점 종로"), ("청계천서점", "청계천서점"),
        ("영광서점", "영광서점"), ("서가는", "서가는"), ("북커스", "북커스"),
        ("불일서점", "불일서점"), ("오프투얼론", "오프투얼론"),
    ],
    "문화시설": [
        ("서울공예박물관", "서울공예박물관"), ("국립현대미술관 서울", "국립현대미술관 서울"),
        ("대림미술관", "대림미술관"), ("국제갤러리", "국제갤러리"), ("서울역사박물관", "서울역사박물관"),
        ("국립고궁박물관", "국립고궁박물관"), ("성곡미술관", "성곡미술관"), ("갤러리현대", "갤러리현대"),
        ("학고재", "학고재"), ("금호미술관", "금호미술관"), ("떡박물관", "떡박물관"),
        ("서울교육박물관", "서울교육박물관"), ("PKM갤러리", "PKM갤러리"), ("서울옥션", "서울옥션"),
        ("국립민속박물관 어린이박물관", "국립민속박물관 어린이박물관"), ("아트센터 나비", "아트센터 나비"),
        ("전통주갤러리", "전통주갤러리"), ("한벽원미술관", "한벽원미술관"), ("탑골미술관", "탑골미술관"),
        ("정독도서관", "정독도서관"), ("서울도서관", "서울도서관"), ("청운문학도서관", "청운문학도서관"),
    ],
    "쇼핑": [
        ("동대문종합시장", "동대문종합시장"), ("동대문 문구완구시장", "문구완구시장"),
        ("동묘시장", "동묘시장"), ("동묘벼룩시장", "동묘벼룩시장"),
    ],
}
EXCLUDE_SUB = ["주차장"]  # 부속/출입구 분할 제외


def norm(s): return "".join(str(s).split())


def match_one(key, cands):
    nk = norm(key)
    # 1) 정확 일치 우선
    ex = [c for c in cands if norm(c["name"]) == nk]
    if ex:
        return max(ex, key=lambda c: c["score"])
    # 2) 부분 포함 (부속 제외)
    sub = [c for c in cands if nk in norm(c["name"]) and not any(x in c["name"] for x in EXCLUDE_SUB)]
    if sub:
        return max(sub, key=lambda c: c["score"])
    # 3) 역포함 (후보명이 키에 포함)
    rev = [c for c in cands if len(norm(c["name"])) >= 2 and norm(c["name"]) in nk]
    if rev:
        return max(rev, key=lambda c: c["score"])
    return None


def select():
    if not CACHE_IN.exists():
        sys.exit(f"정찰 캐시 없음: {CACHE_IN}\n  먼저 scout_score 실행 필요")
    cache = json.loads(CACHE_IN.read_text(encoding="utf-8"))
    pois = pd.read_parquet(POIS)
    exist_ids = set(pois["place_id"].astype(str))
    exy = pois[["lon", "lat"]].to_numpy()

    def near(lon, lat):
        d = np.hypot((exy[:, 0] - lon) * 88800, (exy[:, 1] - lat) * 111000)
        return bool((d < DEDUP_M).any())

    selected, notfound, dup = [], [], []
    for cat, items in TARGETS.items():
        for disp, key in items:
            m = match_one(key, cache.get(cat, []))
            if m is None:
                notfound.append((cat, disp)); continue
            if str(m["id"]) in exist_ids or near(m["lon"], m["lat"]):
                dup.append((cat, disp, m["name"])); continue
            selected.append({"place_id": str(m["id"]), "name": m["name"], "cat": cat,
                             "lon": m["lon"], "lat": m["lat"], "score": m["score"]})
    return selected, notfound, dup


def report():
    selected, notfound, dup = select()
    SELECTED_OUT.write_text(json.dumps(selected, ensure_ascii=False), encoding="utf-8")
    by = {}
    for s in selected:
        by.setdefault(s["cat"], []).append(s)
    print("=" * 60)
    print(f"최종 편입 대상: {len(selected)}개")
    for cat in TARGETS:
        lst = by.get(cat, [])
        print(f"\n[{cat}] {len(lst)}개")
        for s in lst:
            print(f"  {s['score']:.3f} | {s['name']}  ({s['lon']:.5f},{s['lat']:.5f})")
    if notfound:
        print(f"\n⚠️ 캐시에서 못 찾음 {len(notfound)}개:")
        for cat, disp in notfound:
            print(f"  - [{cat}] {disp}")
    if dup:
        print(f"\nℹ️ 기존 947과 중복으로 제외 {len(dup)}개:")
        for cat, disp, nm in dup:
            print(f"  - [{cat}] {disp} (매칭: {nm})")
    print(f"\n선별 캐시 저장 → {SELECTED_OUT.relative_to(REPO)}")
    print("값 확인 후:  python scripts/add_expansion.py --write")


def write_run():
    if not SELECTED_OUT.exists():
        sys.exit("선별 캐시 없음 — 먼저 기본 실행으로 목록 확정")
    selected = json.loads(SELECTED_OUT.read_text(encoding="utf-8"))
    if not selected:
        sys.exit("선별 0개 — 중단")

    print(f"보행 그래프 로드(140MB)... 신규 {len(selected)}개 편입")
    with open(GRAPH, "rb") as f:
        G = pickle.load(f)
    if "crs" not in G.graph:
        G.graph["crs"] = "EPSG:4326"
    comps = (nx.weakly_connected_components(G) if G.is_directed() else nx.connected_components(G))
    G = G.subgraph(max(comps, key=len)).copy()  # 최대 연결 컴포넌트
    print(f"  giant component 노드 {G.number_of_nodes():,}")

    # 신규 노드 스냅 + dijkstra
    new_snap, lengths = {}, {}
    for s in selected:
        node = ox.distance.nearest_nodes(G, X=s["lon"], Y=s["lat"])
        new_snap[s["place_id"]] = node
        lengths[s["place_id"]] = nx.single_source_dijkstra_path_length(G, node, weight="travel_time")
    snapdf = pd.read_parquet(SNAP)
    exist_snap = {str(r.place_id): r.osmid for r in snapdf.itertuples(index=False)}

    def od_min(nid, target_osmid):
        v = lengths[nid].get(target_osmid)
        return None if v is None else round(float(v), 1)

    # OD 행렬 확장
    od = pd.read_parquet(OD).set_index("place_id")
    od.index = od.index.astype(str); od.columns = od.columns.astype(str)
    new_ids = [s["place_id"] for s in selected]
    for nid in new_ids:
        if nid in od.index:
            sys.exit(f"이미 존재 place_id={nid} — 중단")
    # 열 추가 (기존행 → 신규, 대칭이라 신규→기존과 동일)
    for nid in new_ids:
        od[nid] = [od_min(nid, exist_snap.get(idx)) for idx in od.index]
    # 행 추가
    for nid in new_ids:
        row = {}
        for col in od.columns:
            if col in new_snap:
                row[col] = od_min(nid, new_snap[col])
            else:
                row[col] = od_min(nid, exist_snap.get(col))
        row[nid] = 0.0
        od.loc[nid] = pd.Series(row)
    od.index.name = "place_id"
    od.reset_index().to_parquet(OD, index=False)
    print(f"OD 갱신 → {od.shape[0]}×{od.shape[1]}")

    # pois_final 갱신
    pois = pd.read_parquet(POIS)
    rows = []
    for s in selected:
        r = {c: np.nan for c in pois.columns}
        r.update({"place_id": s["place_id"], "name": s["name"], "gu": "종로구",
                  "category_main": s["cat"], "category_sub": s["cat"],
                  "category_group_code": "EXP", "category_name": s["cat"],
                  "phone": "", "address_name": "", "road_address_name": "",
                  "lon": s["lon"], "lat": s["lat"], "place_url": "",
                  "mention_count": 0, "hotspot_score": round(s["score"], 4), "source": "expansion"})
        rows.append(r)
    pois = pd.concat([pois, pd.DataFrame(rows)[pois.columns]], ignore_index=True)
    pois.to_parquet(POIS, index=False)
    print(f"pois_final 갱신 → {len(pois)} 행")
    print("완료. (검증·export 는 별도 단계)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    write_run() if a.write else report()

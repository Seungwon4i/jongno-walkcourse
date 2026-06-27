"""
cap_nodes.py — 노드 캡 (OD 행렬이 다룰 만한 규모로 POI 추리기)

입력 : data/processed/pois_features.parquet  (핫스팟 점수까지 붙은 전체 POI)
출력 : data/processed/pois_capped.parquet     (피처 컬럼 그대로, 행만 축소)

방식
  카테고리별 쿼터 안에서 hotspot_score 상위를 뽑되, '종로 위주 + 버퍼 일부'를
  보장하려고 각 쿼터의 비(非)종로(버퍼) 노드 비율에 상한(BUFFER_MAX_SHARE)을 둔다.

쿼터 근거
  - 관광명소(AT4): 187개로 희소하고 동선의 핵심 앵커 → 전부 유지 (quota=None)
  - 음식점(FD6) : 도보 동선의 1차 목적지 → 최대 쿼터(400)
  - 카페(CE7)   : 쉬어가는 2차 목적지 → 중간 쿼터(200)
  → 총 ~787개. OD 행렬 787×787 ≈ 62만 쌍으로 사전계산·저장이 현실적.

사용:
    python scripts/cap_nodes.py
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    sys.exit("pandas 가 필요합니다:  pip install pandas pyarrow")


# ──────────────────────────────────────────────────────────────────────────
# 설정 (조정 포인트)
# ──────────────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent
INPUT_PATH = REPO_ROOT / "data" / "processed" / "pois_features.parquet"
OUTPUT_PATH = REPO_ROOT / "data" / "processed" / "pois_capped.parquet"

# 카테고리별 쿼터 (category_main 라벨 기준). None = 전부 유지.
CATEGORY_QUOTAS = {
    "관광명소": None,   # 희소(187) + 동선 앵커 → 전부 유지
    "음식점": 400,     # 1차 목적지 → 최대
    "카페": 200,       # 2차 목적지 → 중간
}

PRIMARY_GU = "종로구"        # 주 대상 구
BUFFER_MAX_SHARE = 0.20      # 각 카테고리 쿼터 중 버퍼(비종로) 최대 비율


# ──────────────────────────────────────────────────────────────────────────
# 선택 로직
# ──────────────────────────────────────────────────────────────────────────

def select_category(sub: pd.DataFrame, quota, primary_gu: str,
                    buffer_share: float) -> pd.DataFrame:
    """카테고리 하나에서 hotspot_score 상위를 쿼터만큼 선택 (버퍼 비율 상한 적용)."""
    sub = sub.sort_values("hotspot_score", ascending=False)

    if quota is None or quota >= len(sub):
        return sub  # 전부 유지

    buffer_cap = int(quota * buffer_share)
    chosen: list = []
    chosen_set: set = set()
    buf = 0

    # 1차: 상위부터, 종로는 자유롭게 / 버퍼는 상한까지
    for idx, gu in zip(sub.index, sub["gu"]):
        if len(chosen) >= quota:
            break
        if gu == primary_gu:
            chosen.append(idx); chosen_set.add(idx)
        elif buf < buffer_cap:
            chosen.append(idx); chosen_set.add(idx); buf += 1

    # 2차(안전장치): 종로 물량 부족으로 쿼터 미달이면 남은 자리를 상위 버퍼로 보충
    if len(chosen) < quota:
        for idx in sub.index:
            if idx not in chosen_set:
                chosen.append(idx); chosen_set.add(idx)
                if len(chosen) >= quota:
                    break

    return sub.loc[chosen]


# ──────────────────────────────────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────────────────────────────────

def main() -> None:
    if not INPUT_PATH.exists():
        sys.exit(f"입력 파일이 없습니다: {INPUT_PATH}\n  먼저 build_hotspot.py 를 실행하세요.")

    df = pd.read_parquet(INPUT_PATH)

    print("=" * 60)
    print("노드 캡")
    print(f"  입력: {len(df):,} POI")
    print(f"  쿼터: {CATEGORY_QUOTAS}")
    print(f"  주 대상 구: {PRIMARY_GU}, 버퍼 상한: {BUFFER_MAX_SHARE:.0%}")
    print("=" * 60)

    parts = []
    buffer_report = {}
    for label, quota in CATEGORY_QUOTAS.items():
        sub = df[df["category_main"] == label]
        picked = select_category(sub, quota, PRIMARY_GU, BUFFER_MAX_SHARE)
        parts.append(picked)
        n_buffer = int((picked["gu"] != PRIMARY_GU).sum())
        buffer_report[label] = (len(picked), n_buffer)

    capped = pd.concat(parts, ignore_index=True)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    capped.to_parquet(OUTPUT_PATH, index=False)

    print(f"\n저장 완료 → {OUTPUT_PATH.relative_to(REPO_ROOT)}  ({len(capped):,} nodes)")

    print(f"\n총 노드 수: {len(capped):,}")
    print("\n카테고리별 (총 / 버퍼 포함):")
    for label, (tot, nbuf) in buffer_report.items():
        print(f"  - {label}: {tot}  (버퍼 {nbuf})")

    print("\n구별 집계:")
    for gu, cnt in capped["gu"].value_counts().items():
        print(f"  - {gu}: {cnt}")


if __name__ == "__main__":
    main()

"""
collect_mentions.py — POI 언급량(인기) 수집 (네이버 블로그 검색 API)

각 POI 이름으로 네이버 블로그 검색을 호출해 결과 total 수를 mention_count 로 기록.
검색어는 이름을 따옴표로 묶은 정확구 + 구 형태: `"이름" 구`  (예: '"토속촌삼계탕" 종로구')
  → 따옴표가 없으면 긴 상호가 형태소로 토큰화돼(함께/있어/좋은/사람) 무관한 글까지
     대량 매칭되는 문제가 있어, 정확구 일치로 막는다. 구를 덧붙여 지역도 한정.
  ※ 단, '집'·'안녕' 같은 1~2글자 일반어 상호는 이 방식으로도 과대계상될 수 있어
     하류의 hotspot 점수 단계에서 윈저라이즈(상한 캡)로 2차 방어를 권장.

입력 : data/processed/pois_clean.parquet   (preprocess_pois.py 산출물)
출력 : data/processed/pois_mentions.parquet (place_id 기준 누적)

특징
  - 이어하기: 이미 처리한 place_id 는 건너뜀. 중간 저장(SAVE_EVERY)으로 끊겨도 진행분 보존.
  - 한도 보호: 네이버 일일 한도(25,000) 고려해 호출 사이 딜레이.
    429/한도초과면 멈추되, 그때까지 모은 결과는 저장하고 종료.
  - 진행상황 print (n/총건).

사용:
    python scripts/collect_mentions.py     # 처음 또는 이어서 실행(자동 판별)
필요:
    .env 의 NAVER_CLIENT_ID / NAVER_CLIENT_SECRET
    pip install requests pandas pyarrow python-dotenv
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import requests

try:
    import pandas as pd
except ImportError:
    sys.exit("pandas 가 필요합니다:  pip install pandas pyarrow")

try:
    from dotenv import load_dotenv
except ImportError:
    sys.exit("python-dotenv 가 필요합니다:  pip install python-dotenv")


# ──────────────────────────────────────────────────────────────────────────
# 설정
# ──────────────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent
INPUT_PATH = REPO_ROOT / "data" / "processed" / "pois_clean.parquet"
OUTPUT_PATH = REPO_ROOT / "data" / "processed" / "pois_mentions.parquet"

NAVER_URL = "https://openapi.naver.com/v1/search/blog.json"

# total 만 필요하므로 display 는 최소(1) 로
DISPLAY = 1

# 호출 사이 딜레이(초). 네이버 검색은 일 25,000건 한도 → 여유 있게.
REQUEST_DELAY = 0.12

# 중간 저장 주기 (신규 N건마다 parquet 갱신)
SAVE_EVERY = 200

# 일시 오류(5xx/네트워크) 재시도
MAX_RETRIES = 3
RETRY_WAIT = 1.5

# 출력 컬럼 (place_id 로 나중에 pois_clean 과 머지)
OUT_COLS = ["place_id", "name", "gu", "mention_query", "mention_count"]


class QuotaStop(Exception):
    """한도 초과/지속 오류 → 진행분 저장 후 정상 종료를 위한 신호."""


# ──────────────────────────────────────────────────────────────────────────
# 네이버 호출
# ──────────────────────────────────────────────────────────────────────────

def fetch_total(session: requests.Session, headers: dict, query: str) -> int:
    """블로그 검색 total 반환. 인증 오류는 즉시 종료, 한도/지속오류는 QuotaStop."""
    params = {"query": query, "display": DISPLAY, "sort": "sim"}
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.get(NAVER_URL, headers=headers, params=params, timeout=10)
        except requests.RequestException as e:
            print(f"    · 네트워크 오류({e}) — 재시도 {attempt}/{MAX_RETRIES}")
            time.sleep(RETRY_WAIT)
            continue

        if resp.status_code == 200:
            return int(resp.json().get("total", 0))

        if resp.status_code == 401:
            sys.exit(f"네이버 인증 실패(401): NAVER_CLIENT_ID/SECRET 확인.\n  본문: {resp.text}")
        if resp.status_code == 403:
            sys.exit("네이버 권한 오류(403): 앱에 '검색' API 사용 설정이 켜져 있는지 확인.\n"
                     f"  본문: {resp.text}")
        if resp.status_code == 429:
            # 호출 한도 초과(일일/초당). 진행분 저장 위해 신호 발생.
            raise QuotaStop(f"429 한도 초과 — 본문: {resp.text[:200]}")

        # 그 밖의 4xx/5xx: 잠시 후 재시도
        print(f"    · HTTP {resp.status_code} | {resp.text[:200]} — 재시도 {attempt}/{MAX_RETRIES}")
        time.sleep(RETRY_WAIT)

    # 재시도 모두 실패 → 멈추되 진행분 저장
    raise QuotaStop(f"재시도 초과: query={query!r}")


# ──────────────────────────────────────────────────────────────────────────
# 저장/로드
# ──────────────────────────────────────────────────────────────────────────

def load_existing() -> dict:
    """기존 출력(있으면) 로드 → place_id→record dict."""
    results: dict = {}
    if OUTPUT_PATH.exists():
        prev = pd.read_parquet(OUTPUT_PATH)
        for rec in prev.to_dict("records"):
            results[rec["place_id"]] = rec
        print(f"이어하기: 기존 결과 {len(results):,}건 로드 ({OUTPUT_PATH.relative_to(REPO_ROOT)})")
    return results


def save_results(results: dict) -> None:
    df = pd.DataFrame(list(results.values()), columns=OUT_COLS)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUTPUT_PATH, index=False)


# ──────────────────────────────────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────────────────────────────────

def main() -> None:
    load_dotenv(REPO_ROOT / ".env")
    cid = os.getenv("NAVER_CLIENT_ID", "").strip()
    secret = os.getenv("NAVER_CLIENT_SECRET", "").strip()
    if not cid or not secret:
        sys.exit(".env 에 NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 가 비어 있습니다.")

    if not INPUT_PATH.exists():
        sys.exit(f"입력 파일이 없습니다: {INPUT_PATH}\n  먼저 preprocess_pois.py 를 실행하세요.")

    headers = {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": secret}
    session = requests.Session()

    pois = pd.read_parquet(INPUT_PATH)
    results = load_existing()

    todo = pois[~pois["place_id"].isin(results.keys())]
    total_n = len(pois)
    done_n = len(results)
    todo_n = len(todo)

    print("=" * 60)
    print("언급량 수집 시작 (네이버 블로그 검색)")
    print(f"  전체 POI : {total_n:,}")
    print(f"  완료     : {done_n:,}")
    print(f"  남은 작업 : {todo_n:,}")
    print("=" * 60)

    if todo_n == 0:
        print("모든 POI 처리 완료 — 새로 할 작업이 없습니다.")
        return

    new_count = 0
    stopped = False
    try:
        for i, row in enumerate(todo.itertuples(index=False), 1):
            query = f'"{row.name}" {row.gu}'.strip()
            total = fetch_total(session, headers, query)
            results[row.place_id] = {
                "place_id": row.place_id,
                "name": row.name,
                "gu": row.gu,
                "mention_query": query,
                "mention_count": total,
            }
            new_count += 1
            time.sleep(REQUEST_DELAY)

            if new_count % 50 == 0 or i == todo_n:
                print(f"  {done_n + new_count:,}/{total_n:,} 처리 "
                      f"| 최근: {row.name} → {total}", end="\r")
            if new_count % SAVE_EVERY == 0:
                save_results(results)
                print(f"\n  · 중간 저장 ({len(results):,}건)")

    except QuotaStop as e:
        stopped = True
        print(f"\n⏸ 한도/오류로 중단: {e}")
    except KeyboardInterrupt:
        stopped = True
        print("\n⏸ 사용자 중단(Ctrl+C)")

    save_results(results)
    print(f"\n저장 완료 → {OUTPUT_PATH.relative_to(REPO_ROOT)}  ({len(results):,}건)")
    print(f"이번 실행 신규: {new_count:,}건")
    if stopped:
        remaining = total_n - len(results)
        print(f"남은 작업 {remaining:,}건 — 다시 실행하면 이어서 진행합니다.")
    else:
        print("전체 완료 🎉")


if __name__ == "__main__":
    main()

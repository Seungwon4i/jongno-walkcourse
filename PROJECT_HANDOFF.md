# 종로 도보 동선 추천 (가칭: Jongno Walk-Course Recommender) — 프로젝트 핸드오프 문서 **v5**

> **이 문서의 목적**
> 채팅(claude.ai 상담 대화)이 길어져 새 창에서 다시 시작할 때, **이 문서 전체를 새 채팅에 붙여넣으면 맥락이 그대로 복원**되도록 만든 단일 진실 소스(single source of truth).
> 새 채팅 첫 메시지 예시: *"아래는 진행 중인 학교 과제의 핸드오프 문서야. 이걸 기준으로 이어가자. 현재 상태는 13번 섹션을 봐줘."* + (이 문서 붙여넣기)
>
> **참고:** Claude Code(데스크톱 Code 탭)는 새 채팅이 불필요 — 기존 `jongno-walkcourse` 세션 그대로. Colab(NN 트랙)도 노트북 다시 열어 "모두 실행"하면 복원(데이터 CSV 재업로드 필요). "새 세션"은 이 claude.ai 상담 대화에만 해당.
>
> **v5 변경 요지:** **NN 트랙 1차(L1·L2) 완료.** Foursquare NYC 공개 체크인으로 next-POI 추천을 학습·평가 → **NN L2(MLP + 사용자 이력 임베딩)가 전 지표에서 베이스라인 초과**(Recall@1 0.524 / Recall@10 0.648 / NDCG@10 0.590). "고전 대비 NN 우위 수치 증명"(6번 서사) 달성. 노트북·결과 레포 박제. GitHub username = **urbsn4i-sw** 확정. 데이터 출처·gitignore 정책 갱신. 다음: L3(LSTM/Transformer) · 출발점 스냅(D21) · 데이터 확장(B).

---

## 1. 프로젝트 한 줄 정의
**종로구 지도 위에서, 내 출발점으로부터 도보 예산(30분/1h/2h/3h) 안에 닿는 스팟(맛집·관광지·핫스팟)을 우선순위로 추천하고, 하나를 고르면 다음 후보가 다시 떠서 A→B→C 동선이 완성되는 무료 웹앱.**

- 핵심 상호작용: `A 선택 → B-1…B-n 우선순위 표시 → B-5 선택 → C-5-1…C-5-n …` (예산 소진까지, 가변 깊이) — **React 앱에서 작동 확인됨**
- **학습 목표(중요):** NN을 *직접 짜고 학습시키는* 경험이 이 과제의 중심. 추천·랭킹 = NN/ML, 시간/도달성 = 결정론. → **L1·L2 실제 구축·학습 완료(아래 6번).**
- 학술 프레이밍(선택): 보행 접근성(walkability) · 시간지리학의 time-space prism

---

## 2. 절대 제약 (Hard Constraints)
1. **전부 무료.** 유료 API·유료 빌링 금지. 무료 등록(키 발급)은 허용. (Claude Code는 **Claude Max 플랜 포함** → 제약 위반 아님.) ⚠️ "무료 제약"의 실제 대상은 **앱이 의존하는 외부 서비스/호스팅**이지 개발 도구(Claude Max)가 아님 — 백엔드 *제작*은 비용·제약 없고, **24시간 공개 호스팅**만 무료 티어 제약(콜드스타트 등) 대상.
2. **배움 중심.** 결과물보다 학습 경험·재현 가능성 우선. 특히 **NN을 적극적으로 구축·학습** — L1·L2 완료.
3. **지도에 경로와 추천이 반드시 보여야 함.** (텍스트 리스트만으로는 불가) — ✅ React 앱에서 충족.
4. **경계 침범 허용·안내.** 도보 예산이 크면 종로구를 벗어나 **중구·서대문·성북·은평**으로 넘어갈 수 있음 → 데이터·네트워크가 버퍼 포함, UI는 다른 구로 넘어감을 표시. (종로구 경계선 표시 = D20)
5. 식당 폐점 여부 검증은 **사용자가 직접 처리**(앱 범위 밖).

---

## 3. 확정된 설계 결정 (Decision Log)
| # | 결정 | 값 |
|---|---|---|
| D1 | 형태 | 웹앱(앱 아님) |
| D2 | 대상 지역 | 종로구 + 인접 버퍼(중·서대문·성북·은평) |
| D3 | 이동 수단 | 도보 |
| D4 | 시간 예산 | 30분 / 1시간 / 2시간 / 3시간 (사용자 선택) |
| D5 | "1시간"의 정의 | 이동시간 + 체류시간 누적 |
| D6 | 분기 | A→B→C… 예산 소진까지 반복(**가변 깊이**) |
| D7 | 경계 | 인접 구 침범 허용 + 표시 |
| D8 | NN/ML의 역할 | **후보 추천·랭킹(직접 구축·학습)**. 시간/도달성은 결정론. → L1·L2 완료 |
| D9 | 핫스팟 정의 | 블로그 언급량 + 군집(밀집). 고평점은 무료 평점 소스 부재로 언급량 대체 |
| D10 | 성·연령 | **인기도 조건화(집계)**만. 학습된 개인화는 future work |
| D11 | 개발 도구 | Claude Code(레포·코드, Max 포함) + Colab(NN 학습) |
| D12 | 프론트엔드 | **React + Leaflet** (Streamlit 제외) — ✅ 구현 완료 |
| D13 | 배포 | **GitHub Pages**(정적) — 데이터 사전계산 → JSON 내보내 브라우저 처리. ⚠️ 백엔드 도입 시 재검토(D22) |
| D14 | 강화학습(RL) | **v2/advanced**로 연기 |
| D15 | 언어 | **v1은 한국어만.** 다국어 UI·README 영어화는 마무리 단계 |
| D16 | 지도 타일 | **VWorld `white` 한글 일반지도**(무료 키). Leaflet TileLayer URL 한 줄. ⚠️ 레이어명은 `Base`/`white`/`midnight`/`Hybrid`만 유효(`gray`는 무효 — 시행착오로 확인) |
| D17 | 보행 시간 모델 | travel_time = 거리 ÷ **4.5km/h**(검증 통과). 신호·계단 미반영(가정) |
| D18 | 랜덤포레스트 | 후보 랭킹 베이스라인. (NN 트랙에선 인기순·개인이력 베이스라인을 사용 — 아래 6번) |
| D19 | 카테고리 세분(cat2) | **cat2 7종**: 한식·술집·식당(기타)·카페·명소·유적·거리·자연·기타관광. `category_name`(카카오 계층) 매핑. TourAPI 159개는 평면→"기타관광" |
| D20 | 종로구 경계 표시 | VWorld 2D데이터 API(`LT_C_ADSIGG_INFO`) → MultiPolygon(2,332점) `jongno_boundary.geojson` → `<GeoJSON>` 파란 점선 |
| D21 | 출발점 선택 | 임의 점(GPS/지도클릭) → **종로 최근접 POI 노드로 스냅**. GPS는 좌표 획득 보조수단. 현재 앱은 경복궁 **임시 고정**(스냅 UI 미구현). 도보거리 스냅은 백엔드(D22) 필요 / 직선거리는 폴백 |
| D22 | 백엔드(FastAPI) — 검토 중 | 도보거리 스냅·라우팅·NN 서버추론용. 로컬 우선 제작, 공개 배포는 마지막 결정. 정적 GitHub Pages(D13)와 충돌 → (가)정적+로컬보조 vs (나)분리배포 미정 |
| **D23** | **NN 학습 데이터** | 종로 데이터엔 사용자 선택 로그가 없음 → **Foursquare NYC 공개 체크인**(Dingqi Yang 2014)으로 *방법을 학습·검증*, 구조를 종로에 적용(데모). 6번 방침 실제 수행 |

---

## 4. 아키텍처 (4 레이어)
```
(A) 데이터 레이어   : 종로+버퍼 POI 테이블(피처) + 도보 OD행렬   [완성]
(B) 도달성 엔진     : OD[현재][후보]+체류[후보] ≤ 남은예산 인 후보만 통과  [완성, 결정론적]
(C) 점수·추천 레이어 : 통과 후보 정렬  ← ★ NN/ML이 사는 곳 (앱은 hotspot_score 순 임시 / NN 랭커는 Colab에서 L1·L2 학습 완료, 앱 연결은 미정)
(D) 화면(웹)        : 지도 + 컨트롤 + 우선순위 마커 + 동선 + 클릭 루프  [React 본 구현 완성]
```
**원칙:** 하드 제약(시간 예산)은 (B)가 정확히 거르고, 그 안에서 (C)의 NN/ML이 순위만 매긴다.
**현 상태:** A·B·D 완성. C는 앱에선 hotspot_score 정렬(임시), NN 랭커는 별도 트랙(Colab)에서 학습 완료 — 앱에 어떻게 연결할지는 future work(가벼운 모델 export 또는 백엔드 추론 D22).

---

## 5. ★ 앱 UX 요구사항 — ✅ A안 구현 완료
1. **지도:** VWorld `white` 한글 일반지도. ✅
2. **상단 컨트롤:** 시간 버튼(30분/1h/2h/3h) + 카테고리 필터(cat2 7종) + 뒤로가기. ✅
3. **시간 선택 시:** 출발점 기준 도달 후보 → 선택 → 다음 후보 → 예산 소진까지(가변 깊이). ✅
4. **뒤로 가기(undo):** 예산 복구 + 후보 재표시(스택 패턴). ✅
5. **카테고리 필터(cat2 7종):** 각 단계에서 필터. ✅
6. **마우스 호버 툴팁:** 이름·cat2·도보분. ✅
7. **종로구 경계 표시.** ✅
- **미구현:** 출발점 사용자 선택(현재 경복궁 고정, D21)

---

## 6. ★ NN/ML 사다리 — ✅ L1·L2 완료 (벤치마크 달성)
> **방침(D23):** Foursquare NYC 공개 체크인으로 next-POI 추천을 학습·검증(정량지표), 구조를 종로에 적용(데모). 각 레벨에서 모델 정의→학습 루프→loss 관찰→평가를 직접 손으로 — **완료.**

**데이터:** Foursquare NYC 체크인 227,428건 / 사용자 1,083명(방문 5회+) / venue ~38,000. userId별 시간순 시퀀스 → train 225,262 샘플, test = leave-one-out(사용자당 마지막 1방문). 후보 POI는 상위 5,000개로 제한, **공정 비교는 동일 test 403개 집합**에서.

**평가(동일 403 집합) — Recall@k / NDCG@k:**
| 모델 | R@1 | R@5 | R@10 | NDCG@10 |
|---|---|---|---|---|
| 인기순(most-popular) | 0.003 | 0.022 | 0.025 | 0.014 |
| 개인 이력(personal history) | 0.273 | 0.593 | 0.635 | 0.464 |
| **NN L1 (MLP)** | 0.442 | 0.519 | 0.541 | 0.493 |
| **NN L2 (MLP + 사용자 이력 임베딩)** | **0.524** | **0.628** | **0.648** | **0.590** |

**결론:** **L2가 전 지표에서 베이스라인 초과.** L1(입력=마지막 방문 POI+카테고리+시간대)은 Recall@1·NDCG에서 강베이스라인(개인 이력)을 이겼으나 Recall@10은 못 넘김 → L2에서 **사용자 이력 POI 임베딩 평균**을 입력에 추가하니 Recall@10까지 추월. "단계적 향상 + 각 향상에 명확한 이유" 서사 완성.

| Level | 모델 | 상태 |
|---|---|---|
| 베이스라인 | 인기순·개인이력 | ✅ 측정 완료 |
| L1 | MLP 랭커 (`nn.Embedding`+ReLU→점수, CrossEntropy) | ✅ 완료 |
| L2 | MLP + 사용자 이력 임베딩 평균 | ✅ 완료(전 지표 1위) |
| L3 | 시퀀스 모델 (LSTM / 소형 Transformer) — 방문 "순서" | ⬜ 다음 |
| L4 *(선택)* | GNN | future work |
| v2 *(연기)* | 강화학습 / 확산 | future work |

**환경:** Colab(CPU로도 L1·L2 학습 가능, 15 epoch loss 7.62→1.80). 노트북 `notebooks/jongno_walkcourse.ipynb`(출력 비워 23KB 커밋), 결과 `notebooks/README.md`. 학습 모델 `.pt`는 미저장(재학습으로 복원 — 노트북 "모두 실행" + CSV 재업로드).

---

## 7. 무료 기술 스택 (FREE)
| 용도 | 도구 | 비고 |
|---|---|---|
| 지도 표시 | Leaflet + VWorld `white` 타일 | 무료 키(frontend/.env). 한글 라벨 |
| 행정경계 | VWorld 2D데이터 API | 종로구 폴리곤 GeoJSON (D20) |
| 보행망·OD행렬 | pyrosm + 로컬 PBF + NetworkX | |
| POI(노드) | 카카오 로컬 + TourAPI | 무료 키 |
| 언급량 | 네이버 블로그 검색 API | 검색어 `"이름" 구` |
| NN 학습 데이터 | **Foursquare NYC 공개 체크인** | next-POI 벤치마크 (D23) |
| NN·ML | **PyTorch / scikit-learn** + Colab | L1·L2 완료 |
| 프론트엔드 | Vite 8 + React 19 + react-leaflet 5 + leaflet 1.9 | Node v24 |
| 배포 | GitHub Pages / HF Spaces | (백엔드 시 재검토 D22) |
| 백엔드(검토 중) | FastAPI | 도보거리 스냅·라우팅 (D22) |
| 개발 | Claude Code(Max) + Colab | |

---

## 8. 데이터 파이프라인 — ✅ 완성 + 프론트 내보내기
**스크립트(11), 커밋·푸시 완료. 원본 데이터는 `.gitignore`(코드만 레포에).**
```
collect_pois.py / preprocess_pois.py / collect_mentions.py / build_hotspot.py /
cap_nodes.py / collect_tourapi.py / build_graph.py /
export_frontend_data.py → pois.json + od.json (cat2 7종 분류) /
fetch_boundary.py → 종로 경계 GeoJSON / make_map.py → folium 검증
```
**원본 산출물 (data/processed/, gitignore):** `pois_final.parquet`(946 POI), `od_matrix.parquet`(946×946 도보분 — ⚠️ place_id를 컬럼 저장 → 읽을 때 `set_index("place_id")` 필요), `walk_graph.gpickle`, `node_snap.parquet`.
**프론트 배포 산출물 (frontend/public/data/, 커밋됨):** `pois.json`(~163KB; id·name·cat·**cat2**·gu·lon·lat·score·stay), `od.json`(~5.06MB; `{ids,times}`, null=도달불가/180분초과), `jongno_boundary.geojson`(~94KB).
**cat2 분포(946):** 한식169 / 술집106 / 식당기타125 / 카페200 / 명소·유적37 / 거리·자연150 / 기타관광159.

---

## 9. 도달성 엔진 (레이어 B) — ✅ 완성 (Python + JS 포팅)
`backend/reachability.py`: `reachable(current, budget, category_filter, visited)` — OD+체류 ≤ 예산, STAY={음식점40,카페20,관광명소30}/기본30, NaN·자기·visited 제외, hotspot_score 정렬, remaining_min 반환.
**JS 포팅** (`frontend/src/App.jsx`): 1:1, cat2 필터. ⚠️ 좌표 필드명 `lon`(`lng` 아님 — `.lng` 쓰면 흰 화면 크래시, 반복 발생·교정). **검증:** 경복궁 60분 → Python 467 / JS 468(반올림 1차 = 동일).

---

## 10. v1.0 데모 (folium) — ✅ 완성
`scripts/make_map.py` → `outputs/reachability_map.html`(커밋, `.gitattributes`로 linguist-generated).

---

## 11. v1.1 React 본 구현 — ✅ A안 완성
`frontend/` (Vite + React 19 + react-leaflet 5 + leaflet 1.9). `src/App.jsx` 전체 앱: 데이터 fetch(pois/od/boundary) → reachable JS → 클릭 체이닝. VWorld `white` 타일, 마커 아이콘 깨짐 수정, 시간버튼 4개, cat2 7색 후보 마커, 호버 툴팁, 클릭→동선추가, 예산 누적차감, undo, 동선 Polyline, 종로 경계.

---

## 12. 레포 구조 / 환경
**레포:** `github.com/urbsn4i-sw/jongno-walkcourse` (공개). **레포 커밋 신원 = Dorothy / urban4i.sw@gmail.com**(git config). 과거 초기 커밋은 옛 `wonlab144` 유지. Co-Authored-By: Claude 트레일러가 일부 커밋에 있음(투명성, 그대로 둠).
**구조:** `scripts/`(11) / `backend/` / `outputs/` / `frontend/` / `notebooks/`(NN: README.md + jongno_walkcourse.ipynb) / `models/`(비어있음, 모델 .pt 미저장) / `archive/`(Foursquare CSV 102MB — **gitignore**) / `cache/`.
`.gitignore` 정책: 원본 parquet·`.env`·`archive/`·`PROJECT_HANDOFF_v*.md`(버전 사본) 무시. 핸드오프 본체는 **`PROJECT_HANDOFF.md` 하나**만 추적(단일 진실 소스).
**환경:** Windows / Anaconda Python 3.12 / **Node v24.17.0** / Claude Code(데스크톱, Max) / Colab.
**API 키(.env, gitignore):** KAKAO✅ NAVER✅ TOURAPI✅ **VITE_VWORLD_KEY**(frontend/.env)✅.
> **학교 PC 메모:** 학교 정책으로 Claude Code 설치 불가 → 발표/시연은 GitHub Pages 배포 후 브라우저 접속(설치 불필요). 개발은 본인 환경.

---

## 13. 현재 상태 / 다음 행동  ← **새 채팅에서 여기부터 확인**
**완료:**
- **v1.0:** 데이터 파이프라인(946 노드 + OD행렬) · 도달성 엔진 · folium 검증.
- **v1.1 (A안):** React+Leaflet 앱 — VWorld 한글 지도, 시간버튼, A→B→C 체이닝+undo, cat2 7색 필터, 호버 툴팁, 종로 경계. push·동기화.
- **NN 트랙 1차 (L1·L2):** Foursquare NYC로 next-POI 학습. **L2(MLP+이력)가 전 지표 베이스라인 초과**(R@1 0.524/R@10 0.648/NDCG@10 0.590). 노트북·결과 레포 박제. (6번 참조)

**미구현 / 다음 후보:**
1. **NN L3 (LSTM / 소형 Transformer)** — 방문 "순서" 모델링, L2 대비 추가 이득 검증. Colab. (L2로 NN 파트는 발표 충분 — L3는 선택 심화)
2. **출발점 선택 (D21)** — 경복궁 고정 해제. GPS/지도클릭 → 최근접 노드 스냅(직선거리 v1 / 도보거리는 백엔드 D22) + 범위밖 폴백.
3. **데이터 확장 (B)** — 문화시설(박물관·도서관, TourAPI contentTypeId=14) 추가 수집 → 노드 재구성 → OD 재계산 → JSON 재생성. ⚠️ v1.0 파이프라인 거의 재실행 = 묵직함.
4. **백엔드 FastAPI (D22)** / **OD 경량화**(od.json 5MB) / **NN 랭커 앱 연결**(C 레이어).

> ⚠️ **Claude Code는 새 채팅 불필요.** Colab은 노트북 "모두 실행" + CSV 재업로드로 복원.
> **작업 방식:** claude.ai(상담/설계)=결정·지시(붙여넣기용 코드블록) / Claude Code(실행)=명령·파일편집 / Colab(NN)=셀 단위. 모든 답변 한국어, 끝에 "2.지금까지 / 3.다음으로" 두 섹션 고정.

---

## 14. Future Work (명시적 보류)
- 다국어 UI / README 영어화 · 보행시간 정밀화(신호·계단) · 출발점 도보거리 스냅(백엔드) · OD 경량화 · 관광 세분 정밀화(TourAPI cat1/2/3) · 데이터 확장(문화시설·쇼핑) · RL·확산 모델 · 성·연령 학습 개인화 · 단계별 카테고리 다양성 · 버퍼 구 수집 확장 · 백엔드 공개 호스팅(D22) · **NN L4(GNN)** · **NN 랭커를 종로 데이터/앱에 실제 연결**(현재는 Foursquare로 방법 검증까지).

---

## 15. 변경 이력
- **v1~v3:** 초기~v1.0 완성(데이터 파이프라인·도달성 엔진·folium, 앱 UX 확정).
- **v4:** v1.1 React 본 구현(A안) 완성 — VWorld 한글 지도, A→B→C 체이닝+undo, cat2 7종(D19), 종로 경계(D20), 호버 툴팁. 프론트 JSON 내보내기. 출발점 스냅(D21)·백엔드(D22) 방향.
- **v5:** **NN 트랙 1차(L1·L2) 완료** — Foursquare NYC next-POI(D23), L2가 전 지표 베이스라인 초과(R@1 0.524/R@10 0.648/NDCG@10 0.590). 노트북·결과 레포 박제(notebooks/), Foursquare CSV·핸드오프 v사본 gitignore. GitHub username `urbsn4i-sw` 확정(12번). 6번 NN 사다리 실제 구현 반영, 13번 다음 후보를 L3·D21·B로 갱신. VWorld 유효 레이어명(D16)·lon 필드 함정(9번) 명시.
- 이후 변경은 여기에 한 줄씩 추가.

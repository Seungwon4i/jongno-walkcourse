# 종로 도보 동선 추천 (가칭: Jongno Walk-Course Recommender) — 프로젝트 핸드오프 문서 **v4**

> **이 문서의 목적**
> 채팅(claude.ai 상담 대화)이 길어져 새 창에서 다시 시작할 때, **이 문서 전체를 새 채팅에 붙여넣으면 맥락이 그대로 복원**되도록 만든 단일 진실 소스(single source of truth).
> 새 채팅 첫 메시지 예시: *"아래는 진행 중인 학교 과제의 핸드오프 문서야. 이걸 기준으로 이어가자. 현재 상태는 13번 섹션을 봐줘."* + (이 문서 붙여넣기)
>
> **참고:** Claude Code(데스크톱 Code 탭)는 새 채팅이 불필요 — 기존 `jongno-walkcourse` 세션 그대로 이어감. "새 세션"은 이 claude.ai 상담 대화에만 해당.
>
> **v4 변경 요지:** **v1.1 React 본 구현(A안) 완성.** Vite+React19+react-leaflet5 앱이 작동: VWorld 한글 지도 · 상단 시간버튼 · A→B→C 클릭 체이닝 · undo · cat2 7종 세분 카테고리 필터(7색 마커) · 마우스 호버 툴팁 · 종로구 경계 표시. 프론트용 JSON 내보내기 파이프라인(`export_frontend_data.py`, `fetch_boundary.py`) 추가. 새 결정 D19~D22 추가. 새 계획: 백엔드(FastAPI) 도입 검토, 데이터 확장(B, 문화시설). 환경·산출물·다음 행동(NN 트랙/출발점 스냅) 갱신.

---

## 1. 프로젝트 한 줄 정의
**종로구 지도 위에서, 내 출발점으로부터 도보 예산(30분/1h/2h/3h) 안에 닿는 스팟(맛집·관광지·핫스팟)을 우선순위로 추천하고, 하나를 고르면 다음 후보가 다시 떠서 A→B→C 동선이 완성되는 무료 웹앱.**

- 핵심 상호작용: `A 선택 → B-1…B-n 우선순위 표시 → B-5 선택 → C-5-1…C-5-n …` (예산 소진까지, 가변 깊이) — **React 앱에서 작동 확인됨**
- **학습 목표(중요):** NN을 *직접 짜고 학습시키는* 경험이 이 과제의 중심. 추천·랭킹 = NN/ML, 시간/도달성 = 결정론.
- 학술 프레이밍(선택): 보행 접근성(walkability) · 시간지리학의 time-space prism

---

## 2. 절대 제약 (Hard Constraints)
1. **전부 무료.** 유료 API·유료 빌링 금지. 무료 등록(키 발급)은 허용. (Claude Code는 **Claude Max 플랜 포함** → 제약 위반 아님.) ⚠️ "무료 제약"의 실제 대상은 **앱이 의존하는 외부 서비스/호스팅**이지 개발 도구(Claude Max)가 아님 — 백엔드 *제작*은 비용·제약 없고, **24시간 공개 호스팅**만 무료 티어 제약(콜드스타트 등) 대상.
2. **배움 중심.** 결과물보다 학습 경험·재현 가능성 우선. 특히 **NN을 적극적으로 구축·학습**.
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
| D6 | 분기 | A→B→C… 예산 소진까지 반복(**가변 깊이** — 시간 예산이 깊이 결정) |
| D7 | 경계 | 인접 구 침범 허용 + 표시 |
| D8 | NN/ML의 역할 | **후보 추천·랭킹(직접 구축·학습)**. 시간/도달성은 결정론, ML 아님 |
| D9 | 핫스팟 정의 | 블로그 언급량 + 군집(밀집). 고평점은 무료 평점 소스 부재로 언급량으로 대체 |
| D10 | 성·연령 | **인기도 조건화(집계)**만. 학습된 개인화는 future work |
| D11 | 개발 도구 | Claude Code(레포·코드, Max 포함) + Colab(NN 학습) |
| D12 | 프론트엔드 | **React + Leaflet** (Streamlit 제외) — ✅ 구현 완료 |
| D13 | 배포 | **GitHub Pages**(정적) — 데이터 오프라인 사전계산 → JSON 내보내 브라우저 처리. (대안: HF Spaces) ⚠️ 백엔드 도입 시 재검토(D22) |
| D14 | 강화학습(RL) | **v2/advanced**로 연기. v1은 지도학습 랭커까지 |
| D15 | 언어 | **v1은 한국어만.** 영어/일본어/중국어 UI는 future work. GitHub README 영어화는 마무리 단계 |
| D16 | 지도 타일 | **VWorld `white` 한글 일반지도**(국토지리정보원 계열, 무료 키). ~~CartoDB Positron~~에서 교체 — 로마자 라벨 문제 해소. Leaflet TileLayer URL 한 줄 |
| D17 | 보행 시간 모델 | travel_time = 거리 ÷ **4.5km/h**(검증 통과). 신호·계단 대기 미반영(가정) |
| D18 | 랜덤포레스트 | **후보 랭킹용**(NN 사다리 베이스라인). 경로 잇기용 아님 |
| **D19** | **카테고리 세분(cat2)** | category_main 3종 위에 **cat2 7종** 추가: 한식·술집·식당(기타)·카페·명소·유적·거리·자연·기타관광. `category_name`(카카오 계층) 매핑으로 생성, 재수집 불필요. ⚠️ TourAPI 159개는 평면("관광명소")이라 "기타관광"으로만 분류됨 |
| **D20** | **종로구 경계 표시** | VWorld 2D데이터 API(`LT_C_ADSIGG_INFO`)로 종로구 폴리곤(MultiPolygon, 2,332점) → `jongno_boundary.geojson` 정적 저장 → react-leaflet `<GeoJSON>` 파란 점선 렌더 |
| **D21** | **출발점 선택** | 임의 점(GPS/지도클릭) → **종로 최근접 POI 노드로 스냅**해서 시작. GPS는 좌표 획득 *보조수단*. 현재 앱은 경복궁 **임시 고정** 상태(스냅 UI 미구현). 스냅 거리계산 방식 = **도보거리 희망**(D22 백엔드 필요) / 직선거리는 폴백 |
| **D22** | **백엔드(FastAPI) 도입 — 검토 중** | 도보거리 스냅·실시간 라우팅·NN 서버추론용. **로컬에서 먼저 제작·검증**, 공개 배포는 마지막에 결정. 정적 GitHub Pages(D13)와 충돌 → (가)정적+로컬보조 vs (나)분리배포(무료티어 콜드스타트 감수) 중 미정 |

---

## 4. 아키텍처 (4 레이어)
```
(A) 데이터 레이어   : 종로+버퍼 POI 테이블(피처) + 도보 OD행렬   [완성]
(B) 도달성 엔진     : OD[현재][후보]+체류[후보] ≤ 남은예산 인 후보만 통과  [완성, 결정론적]
(C) 점수·추천 레이어 : 통과 후보 정렬  ← ★ NN/ML이 사는 곳 (현재 hotspot_score 순 임시)
(D) 화면(웹)        : 지도 + 컨트롤(시간버튼·카테고리·뒤로) + 우선순위 마커 + 동선 + 클릭 루프
                      [React 본 구현 완성 — 아래 13번]
```
**원칙:** 하드 제약(시간 예산)은 (B)가 정확히 거르고, 그 안에서 (C)의 NN/ML이 순위만 매긴다.
**현 상태:** A·B·D 완성. C는 hotspot_score 정렬(임시) — NN/RF로 교체 예정(D8/D18).

---

## 5. ★ 앱 UX 요구사항 — ✅ A안 대부분 구현 완료
1. **지도:** VWorld `white` 한글 일반지도. ✅
2. **상단 컨트롤:** 시간 버튼(30분/1h/2h/3h) + 카테고리 필터(cat2 7종) + 뒤로가기. ✅ ("설정" 버튼은 카테고리 필터로 대체됨)
3. **시간 선택 시:** 출발점 기준 도달 후보 표시 → 하나 선택 → 그 지점 기준 다음 후보 → 예산 소진까지(가변 깊이). ✅
4. **뒤로 가기(undo):** 예산 복구 + 후보 재표시(스택 패턴). ✅
5. **카테고리 필터(cat2 7종):** 각 단계에서 필터. ✅
6. **후보 랭킹:** 현재 hotspot_score 순 → 나중에 RF/NN 랭커로 교체(D18, C 레이어). ⬜
7. **마우스 호버 툴팁:** 후보에 마우스만 올려도 이름·cat2·도보분 표시. ✅ (D19 신규)
8. **종로구 경계 표시.** ✅ (D20 신규)
- **미구현:** 출발점 사용자 선택(현재 경복궁 고정, D21)

---

## 6. ★ NN/ML 사다리 (이 과제의 핵심 — 직접 구축·학습) — ⬜ 미착수
> **방침:** Foursquare 등 공개 체크인으로 *방법을 학습·검증*(정량지표), 구조를 종로 POI에 적용(데모). 각 레벨에서 **모델 정의 → 학습 루프 → loss 관찰 → 평가**를 직접 손으로.

| Level | 모델 | 산출/근거 |
|---|---|---|
| 베이스라인 | 랜덤포레스트·인기순·KNN·로지스틱·결정트리·SVM | Recall@k·NDCG 비교군 |
| L1 | MLP 랭커 (`nn.Linear`+ReLU → 점수) | NN 입문 완주 |
| L2 | 학습된 임베딩 (`nn.Embedding`) | POI 종류별 군집 시각화(UMAP) |
| L3 | 시퀀스 모델 (LSTM / 소형 Transformer) | A→B→C 순서 인코딩, 다음 장소 예측 |
| L4 *(선택)* | GNN | 그래프 표현학습 |
| v2 *(연기)* | 강화학습 / 확산(trajectory) | future work |

**과학적 서사:** 베이스라인(RF 등) vs NN을 **Recall@k·NDCG로 대결** → "고전 대비 NN 우위" 수치 증명.

---

## 7. 무료 기술 스택 (FREE) — 실제 사용 반영
| 용도 | 도구 | 비고 |
|---|---|---|
| 지도 표시 | **Leaflet + VWorld `white` 타일** | 무료 키(`.env`). 한글 라벨 |
| 행정경계 | **VWorld 2D데이터 API** | 종로구 폴리곤 GeoJSON (D20) |
| 보행망·OD행렬 | **pyrosm + 로컬 PBF + NetworkX** | OSMnx Overpass 대신 |
| POI(노드) | **카카오 로컬**(주력) + **TourAPI**(관광 보강) | 무료 키 |
| 언급량(인기) | **네이버 블로그 검색 API** | 검색어 `"이름" 구` 방식 |
| 생활인구·인구통계 | 서울 열린데이터광장 | v1.3 예정 |
| 랭커 학습 신호 | Foursquare 공개 체크인 | 벤치마크용 |
| NN·ML | **PyTorch / scikit-learn** + Colab 무료 GPU | NN은 Colab 트랙 |
| 프론트엔드 | **Vite 8 + React 19 + react-leaflet 5 + leaflet 1.9** | Node v24 |
| 지도 검증(임시) | folium | v1.0 검증 HTML |
| 배포 | **GitHub Pages** / HF Spaces | 무료 (백엔드 시 재검토 D22) |
| 백엔드(검토 중) | **FastAPI**(예정) | 도보거리 스냅·라우팅 (D22) |
| 개발 | Claude Code(로컬, Max 포함) + Colab | |

---

## 8. 데이터 파이프라인 — ✅ 완성 + 프론트 내보내기 추가
**스크립트(11개), 커밋·푸시 완료. 원본 데이터는 `.gitignore`(코드만 레포에).**
```
collect_pois.py        → 카카오 POI 11,801건 (raw)
preprocess_pois.py     → 경계 클리핑·구·카테고리 정리 → 10,357건
collect_mentions.py    → 네이버 블로그 언급량 (검색어 "이름" 구)
build_hotspot.py       → 핫스팟 점수 (윈저라이즈 99%캡 + 일반어 가드 + 0.4/0.6)
cap_nodes.py           → 노드 캡 787 (카테고리 쿼터 + 버퍼 ≤20%)
collect_tourapi.py     → 관광지 앵커 보강 → 946 노드 확정
build_graph.py         → pyrosm 보행망 + 946² OD행렬
export_frontend_data.py→ [신규] pois.json + od.json (cat2 7종 분류 포함)
fetch_boundary.py      → [신규] 종로구 경계 GeoJSON (VWorld 2D데이터 API)
make_map.py            → folium 검증 지도
```
**원본 산출물 (data/processed/, gitignore):**
- `pois_final.parquet` — 946 POI. 컬럼: place_id, name, gu, **category_main**(음식점400/관광명소346/카페200), **category_sub**, **category_name**(카카오 "대분류>중분류>소분류" 99종 보존), category_group_code(FD6/CE7/AT4/TOUR12), lon, lat, mention_count, hotspot_score, source 등
- `od_matrix.parquet` — 946×946 도보시간(분). ⚠️ **place_id를 컬럼으로 저장**(`reset_index()`) → 읽을 때 `set_index("place_id")` 필요 (export 스크립트 버그 원인이었음)
- `walk_graph.gpickle`, `node_snap.parquet`

**프론트 배포 산출물 (frontend/public/data/, 커밋됨):**
- `pois.json` (~163KB) — 각 POI: id, name, cat(대분류), **cat2(세분 7종)**, gu, lon, lat, score, stay
- `od.json` (~5.06MB) — `{ids:[...946], times:[[...]]}`, 도달불가/180분초과 = null. ⚠️ 초기 로드 다소 큼 → future work "OD 경량화"
- `jongno_boundary.geojson` (~94KB) — 종로구 MultiPolygon

### 핫스팟 점수 (전처리, NN 아님)
```
hotspot_score = 0.4·z(log(언급량), 99%윈저라이즈, 일반어가드) + 0.6·(반경100m 밀집도) → 0~1
```

### cat2 세분 분포 (D19, 합계 946, "기타" 0)
한식 169 / 술집 106 / 식당(기타) 125 / 카페 200 / 명소·유적 37 / 거리·자연 150 / 기타관광 159(=TourAPI 평면)

---

## 9. 도달성 엔진 (레이어 B) — ✅ 완성 (Python + JS 포팅)
`backend/reachability.py` (Python, 원본):
```
reachable(current_place_id, remaining_budget, category_filter=None, visited=None)
# 통과: OD[현재][후보] + 체류시간[후보] ≤ 남은예산
# STAY_MINUTES = {"음식점":40, "카페":20, "관광명소":30}, DEFAULT 30
# 제외: NaN·자기자신·visited / 정렬: hotspot_score 내림차순
# 반환에 remaining_min(방문 후 잔여) 포함 → 체이닝 구동
```
**JS 포팅** (`frontend/src/App.jsx` 내 `reachable()`): Python과 1:1. cat2 필터 사용.
**검증:** 경복궁 60분 → Python 467곳 / JS 468곳 (반올림 1곳 차 = 동일). STAY_MINUTES 일치 확인.

---

## 10. v1.0 데모 (folium) — ✅ 완성
`scripts/make_map.py` → `outputs/reachability_map.html` (커밋됨). 데이터 검증용 정적 미리보기. 인터랙티브 버전은 React에서 구현됨(아래 11번).
> ⚠️ 이 HTML은 `.gitattributes`로 `linguist-generated` 처리(언어 통계 제외).

---

## 11. v1.1 React 본 구현 — ✅ A안 완성
`frontend/` (Vite + React 19 + react-leaflet 5 + leaflet 1.9):
- `src/App.jsx` — 전체 앱. 데이터 fetch(pois/od/boundary) → reachable JS → 클릭 체이닝.
- VWorld `white` 타일(`import.meta.env.VITE_VWORLD_KEY`), 마커 아이콘 깨짐 수정 코드 포함.
- **작동 기능:** 시간버튼 4개 / cat2 7색 후보 마커 / 호버 툴팁 / 클릭→동선추가 / 예산 누적차감 / 뒤로(undo) / 동선 Polyline / 종로 경계.
- **데이터 필드 주의:** 좌표 필드명은 `lon`(`lng` 아님) — 코드에서 `.lng` 쓰면 흰 화면 크래시(이미 두 번 발생·교정).

---

## 12. 레포 구조 / 환경
**레포:** `github.com/<USERNAME>/jongno-walkcourse` (공개).
⚠️ **USERNAME 표기 혼선:** 기록상 `urban4i-sw` / `urbsn4i-sw` / `Seungwon4i` 가 섞여 있음 → **GitHub 실제 레포 URL에서 username 재확인 필요.** 확실한 것: **레포 커밋 신원 = Dorothy / urban4i.sw@gmail.com**(이 레포 git config). 과거 초기 커밋은 옛 `wonlab144` 유지(문제 없음). Co-Authored-By: Claude 트레일러가 일부 커밋에 있음(투명성 차원, 그대로 둠).

**구조:**
- `scripts/` 데이터 파이프라인(11) / `backend/` 도달성 엔진 / `outputs/` folium 데모 / `frontend/` React 앱 / `models/`·`notebooks/`·`cache/` (NN 예정·비어있음)
- `frontend/src/`: App.jsx, index.css, main.jsx (App.css 미사용) / `frontend/public/data/`: pois.json, od.json, jongno_boundary.geojson

**환경:** Windows / Anaconda Python 3.12 / **Node v24.17.0, npm 11.13.0** / Claude Code(데스크톱 Code 탭, Max) / Colab.
설치: geopandas, pyrosm 0.7, osmnx 2.1, networkx 3.5, folium 0.20, scikit-learn / (frontend) react 19.2.7, react-dom 19.2.7, leaflet 1.9.4, react-leaflet 5.0.0, vite 8.1.0, @vitejs/plugin-react 6.0.2, oxlint 1.69.
**API 키(.env, gitignore):** KAKAO ✅ / NAVER ✅ / TOURAPI ✅ / **VITE_VWORLD_KEY**(frontend/.env, 한글지도+경계) ✅ / SEOUL_OPENDATA(v1.3 예정).

> **키 관리 교훈:** `.env`는 `code .env`로 직접 편집(다운로드 사본 금지). 키는 채팅에 적지 말고 `.env`에 직접 입력. frontend/.env 는 frontend/.gitignore + 루트 .gitignore 이중 보호.
> **학교 PC 메모:** 학교 정책으로 Claude Code 설치 불가 → 발표/시연은 GitHub Pages 배포 후 **브라우저 접속**으로 해결(설치 불필요). 개발은 본인 환경 유지.

---

## 13. 현재 상태 / 다음 행동  ← **새 채팅에서 여기부터 확인**
**완료:**
- **v1.0:** 데이터 파이프라인(946 노드 + OD행렬) · 도달성 엔진 · folium 검증 지도.
- **v1.1 (A안):** React+Leaflet 앱 작동 — VWorld 한글 지도, 시간버튼, **A→B→C 클릭 체이닝 + undo**, **cat2 7종 세분 카테고리 필터(7색)**, **호버 툴팁**, **종로구 경계 표시**. 데이터 JSON 내보내기 파이프라인 구축. **GitHub push·동기화 완료.**

**미구현 / 다음 후보:**
1. **NN 트랙 착수 (과제 핵심, D8)** — RF 베이스라인 + NN L1(MLP 랭커). Colab에서 React와 병렬. ← **추천 우선**
2. **출발점 선택 (D21)** — 경복궁 고정 해제. GPS/지도클릭 → 최근접 노드 스냅(+범위밖 폴백). 도보거리 스냅 원하면 백엔드(D22) 필요.
3. **데이터 확장 (B)** — 문화시설(박물관·도서관, TourAPI contentTypeId=14) 추가 수집 → 노드 재구성 → **OD 재계산** → JSON 재생성. (프론트는 cat 매핑 있으면 자동 반영) ⚠️ v1.0 파이프라인 거의 재실행 = 묵직함.
4. **백엔드 FastAPI (D22)** — `/snap`(도보거리 최근접) + `/route`(폴리라인). 로컬 우선.
5. **OD 경량화** — od.json 5MB → 정수화/희소/바이너리.

> ⚠️ **Claude Code는 새 채팅 불필요** — 기존 `jongno-walkcourse` 세션 그대로.
> **작업 방식:** claude.ai(상담/설계) = 결정·지시(붙여넣기용 코드블록) / Claude Code(실행) = 명령·파일편집. 모든 답변은 한국어, 끝에 "2.지금까지 / 3.다음으로" 두 섹션 고정.

---

## 14. Future Work (명시적 보류)
- **언어:** 영어/일본어/중국어 UI. README 영어화는 마무리 단계.
- **보행 시간 정밀화:** 횡단보도 신호·계단·육교 페널티 (현재 4.5km/h 거리 근사).
- **출발점 도보거리 스냅:** 현재 직선거리 폴백 / 도보거리는 백엔드(D22) 필요.
- **OD 경량화:** od.json 5MB 초기 로드 축소.
- **관광 세분 정밀화:** TourAPI 159개 평면("기타관광") → cat1/2/3 재수집.
- **데이터 확장:** 문화시설·쇼핑·옷가게 (현재 0건, 추가 수집 필요 = B).
- **강화학습(RL)·확산 모델(diffusion):** 동선 전체 보상 최적화/생성.
- **성·연령 학습 개인화:** v1은 집계 인기도 조건화만.
- **단계별 카테고리 다양성:** 후보가 음식점에 쏠리는 경향 — 단계마다 섞어 보여주기.
- **버퍼 구 수집 확장:** 현재 종로 중심(버퍼 빈약).
- **백엔드 공개 호스팅(D22):** 무료 티어 콜드스타트·관리부담 → 발표 형태 정해지면 결정.

---

## 15. 변경 이력
- **v1:** 초기 핸드오프. 무료 제약, 경계 버퍼.
- **v2:** NN 주인공 격상(사다리 신설). React+Leaflet·GitHub Pages·RL은 v2·Claude Code Max.
- **v3:** v1.0 완성(데이터 파이프라인 946노드+OD행렬+도달성 엔진+folium). 앱 UX 확정. RF=랭킹용(D18). 라우팅 pyrosm. 보행시간 가정(D17). 언어 v1 한국어(D15).
- **v4:** **v1.1 React 본 구현(A안) 완성.** VWorld `white` 한글 지도 전환(D16 갱신). A→B→C 클릭 체이닝+undo, cat2 7종 세분 필터(D19), 종로 경계 표시(D20), 호버 툴팁. 프론트 JSON 내보내기(export_frontend_data·fetch_boundary). 출발점 스냅 방향(D21), 백엔드 FastAPI 검토(D22). 환경(Node24/Vite8/React19/react-leaflet5)·산출물·다음행동(NN/출발점/B확장) 갱신. GitHub username 재확인 플래그. 학교 PC 메모.
- 이후 변경은 여기에 한 줄씩 추가.

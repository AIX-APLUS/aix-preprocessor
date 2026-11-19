# 본조사 밖의 추가 후보

Java 테스트, 그래프, 메시지 처리, 경로 탐색, 데이터 바인딩에서 각각 한 곳을 살펴보았다. **추가 파일럿 우선 후보는 Jackson Databind 한 곳**이다. 각 후보의 고정 기본 브랜치에서 최근순 API 커밋 25개씩을 세 시점에 조회했다. 부모 두 개가 관측된 커밋 수를 표시했다. 시점은 고정 tip, 2025-11-19 00:00 UTC 이전, 2018-11-19 00:00 UTC 이전이다. 각 열의 분모는 저장소당 25이다. 이 표본은 각 프로젝트에서 도달 가능한 전체 이력을 대표할 만큼 무작위로 뽑히지 않았다. 자세한 SHA·GitHub API URL·개별 비교 결과는 [원자료](../../research/repository-audit/evidence/supplementary-screen.json)에 있다.

| 추가 후보 | 고정 SHA | 분야·루트 라이선스 | 최신 | 2025 | 2018 | 파일럿 판단 |
|---|---|---|---:|---:|---:|---|
| [FasterXML/jackson-databind](https://github.com/FasterXML/jackson-databind/tree/2a1dcbcc6d188f271e6360f16d2be3a4bb8eff9f) | `2a1dcbcc6d18` | JSON 데이터 바인딩, Apache-2.0 | 12 | 6 | 4 | 세 시점 모두 두 부모 병합이 있었고 최근 표본에서 양쪽이 같은 Java 파일을 수정한 경로를 확인했다. |
| [mockito/mockito](https://github.com/mockito/mockito/tree/10b31ba2a8252cf340bc154c9e05224802a84691) | `10b31ba2a825` | 단위 테스트 모킹, MIT | 0 | 0 | 4 | 2018년 병합 4건 전부 양쪽 수정 Java 경로 교집합이 비었다. 추가 이력 확인 후 결정한다. |
| [graphhopper/graphhopper](https://github.com/graphhopper/graphhopper/tree/70e8293630cae820a0bd34811f6357b7dc6d5faa) | `70e8293630ca` | 지도 경로 탐색, Apache-2.0 | 0 | 0 | 1 | 경로 탐색이라는 도메인 이점이 있으나 이 표본에서는 병합이 드물었다. |
| [jgrapht/jgrapht](https://github.com/jgrapht/jgrapht/tree/ee3a1084f7373cf2873bcba59ee5c1b6b17ec8ad) | `ee3a1084f737` | 그래프 알고리즘, [EPL-2.0 또는 LGPL 이중 라이선스](https://jgrapht.org/) | 0 | 0 | 1 | 추가 소스 도메인 후보. 샘플에 관측된 병합 1건만으로 학습 수율을 판단하기 어렵다. |
| [apache/kafka](https://github.com/apache/kafka/tree/db02bf715f34b7e998210b12e246973ece611459) | `db02bf715f34` | 분산 이벤트 스트리밍, Apache-2.0 | 0 | 0 | 0 | 조회한 75개 커밋에서는 두 부모 병합을 관측하지 못했다. 대규모 추출 우선순위를 낮출 근거다. |

Jackson의 최신 표본에서 API 순서의 앞쪽 두 부모 병합 5건을 골랐다. 각 병합의 부모 SHA를 순서를 바꿔 양방향으로 비교하고, GitHub가 양쪽 모두 `modified`라고 반환한 동일 `.java` 경로를 세었다. 최소 2개 병합에 3개 경로쌍이 관측됐고 고유 경로는 2개였다. `TypeFactory.java`가 두 번 등장하므로 버전 브랜치 간 반복 병합의 영향을 별도로 점검할 필요가 있다. 최신 `3.x`의 전체 버전 계열 병합도 의도된 배포 동기화에 편중될 수 있으므로, 본 추출에서 기간·경로·브랜치별 비중과 충돌 레이블을 함께 확인한다. [두 경로가 겹친 병합](https://github.com/FasterXML/jackson-databind/commit/338750bf01d3df75be258c9c649b3ef43e5ef30a) · [같은 경로가 반복된 병합](https://github.com/FasterXML/jackson-databind/commit/7e16c8bc18d9a3704878d9ddcdb262eec36c4d43)

GitHub Compare는 하나의 merge base를 반환하며 파일 목록 상한은 300개다. Jackson의 두 비교가 이 상한에 닿아 교집합 수는 하한으로만 썼다. 새 후보의 유일 merge base·Parquet 행 수·충돌률·추출 시간은 미측정이다. Mockito의 관측 구간과 Kafka의 단일 부모 표본에서도 과거 squash 또는 rebase 횟수는 구별할 수 없다. [GitHub Compare API](https://docs.github.com/en/rest/commits/commits#compare-two-commits)

### 재현

1. 원자료의 `repositories[].windows[].evidence`를 호출해 커밋별 `parents` 원소 수를 센다. URL은 기본 브랜치 이름 대신 고정 SHA를 사용한다.
2. `both_parent_path_checks[].compare_urls` 양쪽 응답의 `files`에서 상태가 `modified`이고 이름이 소문자 `.java`로 끝나는 경로의 교집합을 구한다. 파일 수가 300인 응답에서 교집합이 비어도 누락 가능성이 있다.
3. Jackson을 실험할 때는 본조사와 동일한 전처리기 SHA와 통제한 refs로 `extract`와 `stats`를 실행한 뒤 학습 후보로 승격할지 결정한다.

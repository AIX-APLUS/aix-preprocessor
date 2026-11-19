# 본조사 밖의 추가 후보

Java 테스트, 그래프, 메시지 처리, 경로 탐색, 데이터 바인딩에서 각각 한 곳을 살펴보았다. 이 다섯 곳에서는 **Jackson Databind의 버전 브랜치에서 관측한 충돌이 다른 유형의 병합에서도 재현되는지** 먼저 확인할 만하다. 각 후보의 고정 기본 브랜치에서 최근순 API 커밋 25개씩을 세 시점에 조회했다. 부모 두 개가 관측된 커밋 수를 표시했다. 시점은 고정 tip, 2025-11-19 00:00 UTC 이전, 2018-11-19 00:00 UTC 이전이다. 각 열의 분모는 저장소당 25이다. 이 표본은 각 프로젝트에서 도달 가능한 전체 이력을 대표할 만큼 무작위로 뽑히지 않았다. 자세한 SHA·GitHub API URL·개별 비교 결과는 [원자료](../../research/repository-audit/evidence/supplementary-screen.json)에 있다.

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

### 고정 SHA의 규모와 파일 단위 재검사

기존 다섯 추가 후보 가운데 Jackson을 다음 제한 추출에 올릴 근거가 늘었다. 2018년과 2025년 표본에서 서로 다른 세 병합의 Java 파일 세 개가 독립적인 3방향 텍스트 병합에서 충돌했다. 같은 기준으로 검사한 최신 경로 3건은 모두 깨끗하게 병합됐다. 이 다섯 후보에 전처리기 전체를 실행해 얻은 Parquet 행 수·양성 수·시간·RSS는 아직 측정하지 않았다.

| 고정 기본 브랜치 후보 | 도달 가능 커밋 | Java 파일 수 | Java 바이트 | GitHub 저장소 크기(KiB) | 두 부모 / 75커밋 | 양쪽 수정 비교 병합 | 겹친 Java 경로 건수 | 파일 단독 충돌 / 깨끗한 병합 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Jackson Databind | 13,947 | 1,439 | 12,147,326 | 90,669 | 22 | 11 | ≥8 | 3 / 5 |
| Mockito | 6,383 | 1,015 | 3,648,723 | 49,825 | 4 | 4 | 0 | 미검사 |
| GraphHopper | 7,141 | 975 | 6,895,050 | 143,763 | 1 | 1 | 0 | 미검사 |
| JGraphT | 3,586 | 1,011 | 8,836,725 | 351,480 | 1 | 1 | 0 | 미검사 |
| Apache Kafka | 18,732 | 6,309 | 74,281,825 | 327,962 | 0 | 0 | 미측정 | 미검사 |

커밋 수는 고정 SHA부터 GitHub 커밋 목록으로 도달하는 조상 수다. 다른 heads·tags까지 합친 수와 전체 두 부모 병합 수는 미측정이다. Java 규모는 해당 tip의 완전한 재귀 트리에서 일반 파일 모드로 끝이 `.java`인 경로를 세고 각 blob 바이트를 합산했다. 테스트 소스도 포함된다. KiB는 기존 GitHub 메타데이터의 `size` 필드로, 실제 추출 비용은 `extract` 실행 후에 측정해야 한다. Kafka와 JGraphT는 이 값이 크고 75커밋에서 두 부모가 각각 0·1건이었다. 한쪽 부모만 관측되는 커밋은 일반 개발, squash, rebase 등을 구분하기 어렵다. [고정 SHA·Git 트리·마지막 커밋 페이지와 다음 빈 페이지](../../research/repository-audit/evidence/supplementary-followup/inventory.json)

**Jackson에서 검사를 확대한 범위.** 최신 구간에서 이미 조사한 병합 5건을 유지하고 2025년·2018년 각 25커밋에서 순서대로 앞의 두 부모 병합 3건씩을 골랐다. SHA와 양방향 비교를 확인한 11건 중 6개 병합에서 수정 경로 8건을 찾았고, 원본 경로 기준 7개가 서로 달랐다. 비교가 300파일 상한에 닿은 사례가 있어 경로 수는 하한이다. 각 경로에서 GitHub가 선택한 base와 두 부모의 트리를 대조하고 blob SHA와 바이트 수를 확인했다.

| Jackson 관측 구간 | 검사한 두 부모 병합 | 발견한 양쪽 수정 경로 | 파일 단독 충돌 | 파일 단독 비충돌 |
|---|---:|---:|---:|---:|
| 고정 tip 부근 | 5 | 3 | 0 | 3 |
| 2025-11-19 이전 | 3 | 2 | 1 | 1 |
| 2018-11-19 이전 | 3 | 3 | 2 | 1 |

충돌을 재현한 파일은 `InjectableValues.java`, `SerializationConfig.java`, `JsonMapper.java`다. 8개 경로만 골라 검사한 결과이므로 3/8을 Jackson의 충돌률로 사용할 수 없다. 실제 전처리기는 유일 merge base와 전체 트리 병합·이력 통계를 검사하며 `.gitattributes`, 경로 변경, 충돌 유형에 따라 제외할 수 있다. Jackson은 서로 다른 기간을 고정한 소규모 전처리기 파일럿 후보로 권한다. Mockito는 과거 표본을 늘릴 때 재검토한다. GraphHopper·JGraphT는 다른 도메인이 더 필요해질 때 탐색할 수 있고, Kafka는 최신·과거 세 표본 모두 두 부모가 없어 전체 추출은 후순위다. [양방향 부모 비교 및 개별 근거 URL](../../research/repository-audit/evidence/supplementary-followup/additional-comparisons.json) · [8개 경로의 SHA·Git 버전·반환 코드](../../research/repository-audit/evidence/supplementary-followup/jackson-file-probes.json)

**재현 절차.**

1. `inventory.json` 각 항목의 `last_commit_page_url`에서 저장된 SHA 1개, `first_empty_page_url`에서 빈 배열을 확인한다. `git_tree_url`의 `truncated`가 false인지 확인하고 `type == blob`, `mode ∈ {100644, 100755}`, 이름이 소문자 `.java`로 끝나는 항목 수와 `size` 합계를 구한다.
2. 기존 비교와 추가 비교의 `compare_urls` 두 곳에서 파일 상태가 모두 `modified`인 동일 Java 경로를 교차한다. 같은 경로가 다른 병합에서 등장하면 별도 건으로 센다. 300개 상한과 rename 누락은 하한 해석에 반영한다.
3. `jackson-file-probes.json`의 각 관측에서 `refs` 순서는 base, 첫 부모, 둘째 부모다. 해당 트리의 경로와 `files`의 blob SHA를 대조한다. 파일 3개의 원본 바이트를 각각 `base`, `p1`, `p2`에 저장하고 길이와 Git blob SHA, 엄격한 UTF-8 디코딩 및 NUL 부재를 확인한다. 실제 검사에서 빈 디렉터리 내 `git merge-file --stdout p1 base p2`를 실행해 종료 코드 0을 비충돌, 1~127을 충돌로 기록했다. 병합 출력을 버리고 오류는 표본에서 분리한다.

### 신규 후보 10곳의 비교 범위 재검증

Jackson에서 양쪽 수정 경로가 발견된 병합 6개의 GitHub 커밋 메시지와 8개 경로에 필요한 고유 blob 22개를 다시 읽었다. 크기·Git 객체 SHA를 대조하고 위 명령을 재실행한 결과, 기존 8개 종료 코드가 모두 일치했다. 양성이 나온 커밋은 `abe0a501`(3.0 → 3.x), `5a2fac6b`·`02919799`(둘 다 2.10 브랜치 병합)였다. 나머지 세 병합의 메시지도 버전 브랜치를 명시한다. 이 분류는 커밋 제목에서 확인한 브랜치에 근거한다. 개발 의도나 일반 기능 브랜치 병합의 양성 수율은 미측정이다. 메시지는 아래 증거의 `url`에서 `commit.message`의 첫 줄을 조회해 대조할 수 있다. [6개 커밋의 SHA·제목과 경로별 재실행 종료 코드](../../research/repository-audit/evidence/supplementary-followup/jackson-review.json)

신규 후보마다 커밋 창은 25개씩 세 번 조회했지만, 실제 **부모 양쪽의 변경 경로를 비교한 병합 수**가 다르다. 첫 선별에서 경로가 겹친 Jackson에는 11건(5·3·3)을 배정했다. 나머지 첫 조사 후보의 세 창에서 찾은 두 부모 병합은 Mockito 4건, GraphHopper·JGraphT 각 1건, Kafka 0건이었다. 다음 다섯 후보는 창당 최대 2건을 검사해 Cassandra·H2·JGit·Mindustry 각 6건, OsmAnd 5건이었다. 충돌 파일이 나온 **서로 다른 병합**은 Jackson 3/11, Mindustry 1/6, OsmAnd 1/5였다. 검사 기회와 병합 유형이 달라 이 분수로 학습 후보의 순위를 정하기 어렵다. Kafka의 분모가 0인 경우도 양성률은 미측정이다. [추가 5개 선별 기준과 개별 결과](additional-screen.md)

다음 소규모 전처리기 실험에서는 Jackson과 H2를 같은 기간·병합 수 상한·시간 예산으로 비교한다. 사전에 버전 브랜치 동기화, 일반 개발, 분류 불명으로 구분하고 각 유형의 관측 병합 수, 고유 양성 병합 수, 유효 행 수와 비용을 공개한다. 일반 개발 병합이 부족한 창도 포함해야 버전 브랜치 밖의 수율을 판단할 수 있다. Jackson은 관측된 충돌을 재검증하는 후보이고 H2는 두 시점에서 양쪽 수정 경로가 확인된 비교 후보다. 두 저장소의 실행 비용과 양성 확보량은 이 실험에서 처음 측정한다.

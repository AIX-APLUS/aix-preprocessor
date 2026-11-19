# Java 저장소 추가 선별

기존 5개 신규 후보에 데이터베이스 2개, Git 구현체 1개, 게임 1개, 내비게이션 1개를 더했다. 기존 후보와 분야가 다른 Java 코드, 접근 가능한 커밋 트리, 두 부모 병합이 관측된 프로젝트를 골랐다. 신규 5개 전체에서 375개 커밋의 부모를 읽고 병합 29건의 양쪽 변경 목록을 대조했다. 발견한 같은 Java 경로 10건은 세 버전의 Git blob을 받아 기본 텍스트 병합을 실행했다. 전처리기의 Parquet 추출은 이 다섯 곳에서 수행하지 않았다. [기존 신규 후보](supplementary-screen.md) · [고정 SHA·조회 URL·관측 내역](../../research/repository-audit/evidence/additional/screen.json) · [파일 병합 실행 결과](../../research/repository-audit/evidence/additional/text-probe.json)

## 고정 이력과 Java 규모

커밋 수는 기본 브랜치의 고정 SHA에서 부모를 따라 도달하는 GitHub 커밋 목록의 크기다. Java 규모는 해당 SHA의 전체 트리에서 소문자 `.java`로 끝나는 blob의 경로 수와 바이트 합계다. 테스트·생성·타사 코드가 포함될 수 있다. 다섯 트리 모두 GitHub가 잘림 없이 반환했다. 마지막 열은 2026-11-19 UTC 조회 당시 GitHub가 표시한 저장소 크기다. 내려받을 바이트, Parquet 크기, 최대 메모리, 실행 시간은 별도로 측정해야 한다.

| 고정 저장소 | 분야 | 도달 커밋 | Java 파일 | Java 바이트 | 저장소 크기 관측치(KiB) |
|---|---|---:|---:|---:|---:|
| [apache/cassandra](https://github.com/apache/cassandra/tree/53c3561e9db3fa0b1ed8e29ce462fde6ce566ff0) | 분산 데이터베이스 | 32,631 | 6,540 | 61,227,061 | 474,806 |
| [h2database/h2database](https://github.com/h2database/h2database/tree/1a1ca49da6ee10ed0502da0eeba0a18649f0e13e) | 임베디드 SQL 데이터베이스 | 14,919 | 1,261 | 12,013,805 | 93,629 |
| [eclipse-jgit/jgit](https://github.com/eclipse-jgit/jgit/tree/c746b7ff5a14955884a46134ea14b1967e29ba06) | Java Git 구현체 | 11,678 | 1,905 | 14,335,901 | 163,160 |
| [Anuken/Mindustry](https://github.com/Anuken/Mindustry/tree/19a0f40d44514f4802a8b79770456e7e32e34da0) | 전략 게임 | 21,598 | 871 | 6,612,901 | 2,013,704 |
| [osmandapp/OsmAnd](https://github.com/osmandapp/OsmAnd/tree/dddbd54ae754161741d8c5657959ce7fae10af5b) | 내비게이션 | 112,424 | 3,467 | 30,647,649 | 1,513,822 |

## 병합을 살펴봤을 때 남는 데이터

각 고정 SHA의 조상에서 API 순서대로 25개씩 읽었다. 세 시점은 고정 SHA, 2025-11-19 00:00 UTC까지, 2018-11-19 00:00 UTC까지다. 시점마다 부모가 정확히 둘인 커밋 중 앞에서 최대 2건을 골랐다. 각 병합에서 GitHub가 양방향 비교에 공통으로 반환한 merge base를 기준으로, 양쪽에서 상태가 모두 `modified`인 동일 Java 경로를 셌다. 한 경로가 한 병합에 등장하면 1건이다. 파일 추가·삭제·이름 변경과 다중 merge base를 이용한 별도 복원은 이 선별에서 다루지 않았다.

| 저장소 | 두 부모 수 / 각 25개 (고정·2025·2018) | 비교한 병합 | 양쪽 수정 경로 건수 | 해당 병합 수 | 기본 텍스트 병합 양성 / 음성 |
|---|---|---:|---:|---:|---:|
| Cassandra | 17 · 11 · 14 | 6 | ≥3 | ≥1 | 0 / 3 |
| H2 | 15 · 9 · 7 | 6 | 2 | 2 | 0 / 2 |
| JGit | 14 · 8 · 3 | 6 | 0 | 0 | 검사 대상 경로 없음 |
| Mindustry | 3 · 2 · 3 | 6 | 4 | 1 | 2 / 2 |
| OsmAnd | 7 · 3 · 1 | 5 | 1 | 1 | 1 / 0 |

Cassandra는 병합 6개 중 5개에서 한쪽 변경 목록이 GitHub의 300개 파일 상한에 닿았다. 표는 반환받은 경로의 하한이다. H2에서는 서로 다른 시기의 두 병합에서 경로가 겹쳤지만 두 경로 모두 기본 병합으로 합쳐졌다. JGit은 세 시점 모두 두 부모 병합이 있었으나 확인한 6건 모두 양쪽 수정 Java 경로가 없었다. Mindustry의 양성 2건은 2018년 같은 병합에 속한다. OsmAnd는 다른 병합에서 양성 1건을 추가로 보여 줬다. 각 프로젝트의 파일럿 전체 충돌률, 전체 두 부모 수, squash·rebase 비중은 미측정이다. 단일 부모만으로 실제 병합 방식을 식별할 수 없다. [병합별 변경 목록과 상한](../../research/repository-audit/evidence/additional/screen.json) · [기준·부모 blob SHA와 경로](../../research/repository-audit/evidence/additional/text-probe-input.json)

기본 텍스트 병합은 저장소 밖에서 세 UTF-8 blob의 Git SHA를 검산하고 `git merge-file --stdout p1 base p2`로 실행했다. 코드의 경로 추적, 추출 제외 조건, 커스텀 병합 드라이버와 파일 속성은 적용하지 않았다. 이 표의 양성·음성은 이 명령의 종료코드이며 학습용 레이블 확정에는 같은 범위의 전처리기 실행이 필요하다. [명령·Git 버전·종료코드](../../research/repository-audit/evidence/additional/text-probe.json)

## 다음 추출에 쓸 판단

- **제한된 비용으로 다음 파일럿을 실행할 때는 H2**를 우선할 수 있다. 이 다섯 중 GitHub 크기가 가장 작고, 서로 다른 두 시점에서 양쪽 수정 경로를 확보했다. 배포 라이선스는 MPL-2.0 또는 EPL-1.0이다. H2를 학습 데이터로 승격하려면 독립된 병합 여러 건에서 전처리기 양성을 확인해야 한다. [H2 고정 라이선스](https://github.com/h2database/h2database/blob/1a1ca49da6ee10ed0502da0eeba0a18649f0e13e/LICENSE.txt)
- **대형 변경과 병합 처리 비용은 Cassandra**에서 추가 시험할 만하다. 세 시점에 두 부모 병합이 반복됐고 API가 잘라낸 대형 변경이 있다. 로컬 Git에서 병합 범위와 시간·메모리를 고정 예산으로 먼저 재라. 대규모 이력에서 모델에 필요한 충돌 양성이 납품될지는 아직 모른다. 루트에는 Apache-2.0과 추가 고지문이 있다. [라이선스](https://github.com/apache/cassandra/blob/53c3561e9db3fa0b1ed8e29ce462fde6ce566ff0/LICENSE.txt) · [NOTICE](https://github.com/apache/cassandra/blob/53c3561e9db3fa0b1ed8e29ce462fde6ce566ff0/NOTICE.txt)
- **양성이 부족하고 다른 도메인이 필요하면 Mindustry와 OsmAnd**에 서로 다른 기간의 소규모 추출을 먼저 배정한다. 이미 확인한 양성 병합은 프로젝트당 1개에 그친다. 두 저장소 모두 크기 관측치가 크다. Mindustry 루트는 GPLv3이며 OsmAnd는 코드·그림·일부 외부 라이브러리에 서로 다른 조건을 명시한다. 대상 Java 파일의 출처와 조건을 확인한 뒤 소스 포함 데이터의 공유 범위를 정한다. [Mindustry 라이선스](https://github.com/Anuken/Mindustry/blob/19a0f40d44514f4802a8b79770456e7e32e34da0/LICENSE) · [OsmAnd 라이선스](https://github.com/osmandapp/OsmAnd/blob/dddbd54ae754161741d8c5657959ce7fae10af5b/LICENSE)
- **JGit은 보류**한다. 루트에는 Eclipse Distribution License v1.0이 명시되어 있다. Git 구현이라는 분야 다양성은 있지만 현재 증거에서 표본당 추출 가능성은 낮다. [JGit 고정 라이선스](https://github.com/eclipse-jgit/jgit/blob/c746b7ff5a14955884a46134ea14b1967e29ba06/LICENSE)

## 재현과 검증

1. 저장소 루트에서 `python research/repository-audit/verify_additional_screen.py`를 실행한다. 이번 작업에서 실행하여 15개 커밋 창의 집계, 29건의 부모 선택, 10건의 경로·blob·종료코드가 일치함을 확인했다.
2. 원격 재수집에는 같은 명령의 `--online` 옵션을 사용한다. 고정 커밋·전체 트리, 마지막 비어 있지 않은 커밋 페이지와 다음 빈 페이지, 각 창과 양방향 비교를 다시 읽는다. 이번 원격 수집은 GitHub 연결로 수행했다. 이 Python 옵션의 인터넷 실행은 별도로 검증하지 않았다. 저장소 크기 같은 실시간 메타데이터는 달라질 수 있다.
3. `research/repository-audit`에서 이번에 실행한 파일 병합 명령은 `python merge_file_probe.py evidence/additional/text-probe-input.json --blob-cache <임시 캐시 경로> --output evidence/additional/text-probe.json`이다. 캐시는 Git blob SHA를 키로, 내용을 Base64 값으로 둔 임시 JSON이다. 온라인 재현 시에는 `--blob-cache`를 생략하면 기존 도구가 고정 SHA로 GitHub에서 직접 읽는다. 소스 blob과 캐시는 저장소에 포함하지 않는다.

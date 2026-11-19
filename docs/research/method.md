## 어떤 병합이 학습 행이 되는가

분석 단위는 병합 하나에서 양쪽이 내용을 바꾼 Java 파일 하나다. 긍정은 해당 파일에서 Git이 재현한 텍스트 충돌이다. 실제 개발자가 마주친 모든 충돌, 컴파일 실패 또는 사람이 한 해결 작업은 이 레이블의 대상 범위를 벗어난다. 후보 선정 자체가 두 부모가 나중에 모두 수정한 파일이라는 조건에 의존한다. 따라서 분기 시점의 임의 파일 전체에 이 비율이나 성능을 적용할 수 없다. [병합 재현 코드](https://github.com/AIX-APLUS/aix-preprocessor/blob/06e755ebabed1707a3413ec99ffa2511b046c543/src/main/java/io/aix/preprocessor/MergeAnalyzer.java#L49-L110)

| 측정 단계 | 집계 단위와 조건 |
|---|---|
| 관측 가능한 병합 | 지정한 ref에서 도달 가능한 고유 커밋 가운데 부모 2개 이상. 부모가 정확히 2개인 수와 3개 이상인 octopus 수를 각각 기록한다. 기본 브랜치의 모든 조상을 포함하므로 첫 번째 부모만 따라가는 개수와도 다르다. |
| 단일 merge base | 두 부모에 대해 `git merge-base --all P1 P2`가 1개를 반환. 그 결과가 부모 자신인 경우도 단일 base 수에는 포함하되 추출은 여기서 끝난다. |
| 양쪽 Java 수정 후보 | 두 `base → parent` diff에서 base 경로를 교집합으로 정한다. 양쪽 모두 일반 파일, Git 상태 M 또는 R, base/최종 이름 모두 소문자 `.java`, blob 내용 변화가 필요하다. 추가·삭제·순수 이름변경·한쪽 변경은 행을 만들지 않는다. 교집합이 있는 병합 수와 교집합 파일 수를 분리한다. |
| 유효 행 | 대상 경로와 이름변경 후의 경로에서 비텍스트 충돌이 없어야 한다. base 소스를 UTF-8로 읽을 수 있고 NUL이 없으며 이력 통계를 구할 수 있어야 한다. `git merge-tree --write-tree -z`의 `CONFLICT (contents)`이면 참이다. 같은 병합의 비충돌 파일은 별도 음성 행이다. |

전처리기는 `rev-list --all --parents --min-parents=2 --max-parents=2`를 임시 공유 미러에서 실행한다. 로컬 브랜치·원격 추적 브랜치·태그 등 **실제 미러에 있는 refs**를 고정해야 결과가 재현된다. 원격이 광고하는 모든 ref나 GitHub PR 수를 이 수치로 대체할 수 없다. `Skips`의 `no unique merge base`는 병합 수, `non-text conflict`, `non-UTF-8 source`, `binary base`, `unavailable history`는 파일 수다. 부모가 base인 경우나 빈 교집합은 카운터 없이 반환한다. 합쳐서 전체 제외 건수로 보고하면 안 된다. [입력 미러와 얕은 저장소 검사](https://github.com/AIX-APLUS/aix-preprocessor/blob/06e755ebabed1707a3413ec99ffa2511b046c543/src/main/java/io/aix/preprocessor/Main.java#L84-L101) · [병합 열거](https://github.com/AIX-APLUS/aix-preprocessor/blob/06e755ebabed1707a3413ec99ffa2511b046c543/src/main/java/io/aix/preprocessor/Extraction.java#L10-L20) · [후보·건너뜀 조건](https://github.com/AIX-APLUS/aix-preprocessor/blob/06e755ebabed1707a3413ec99ffa2511b046c543/src/main/java/io/aix/preprocessor/MergeAnalyzer.java#L30-L81)

## 두 분할 전략과 누출 점검

분할기는 `(repo_id, base_path)`마다 전체 행·양성 행 수를 세고 **저장소별로 독립적으로** 배정한다. 큰 경로 그룹부터 처리하고 동률이면 `Objects.hash(repo,path)`와 경로를 사용한다. 각 그룹은 70/15/15 목표에 대한 행 비중 및 양성 비중 제곱 오차 증가량의 합이 가장 작은 분할 하나에 들어간다. 배정된 그룹에서 원래 행 순서를 보존한다. 행이 적거나 한 파일에 양성이 집중되면 빈 분할 또는 양성 0개인 평가셋이 생길 수 있다. [그룹 구성](https://github.com/AIX-APLUS/aix-preprocessor/blob/06e755ebabed1707a3413ec99ffa2511b046c543/src/main/java/io/aix/preprocessor/DatasetSplitter.java#L42-L77) · [배정 수식과 동률 처리](https://github.com/AIX-APLUS/aix-preprocessor/blob/06e755ebabed1707a3413ec99ffa2511b046c543/src/main/java/io/aix/preprocessor/DatasetSplitter.java#L100-L126)

| 방법 | 실제 효과와 선택 기준 |
|---|---|
| A. 병합 후 분할 | 기본 권장. 입력 전체에서 먼저 15컬럼 스키마와 중복 키를 검증한다. 이후 저장소별 그룹이 배정된다. 저장소 크기에 따른 학습 영향력은 그대로 남는다. |
| B. 저장소별 분할 후 train·val·test별 병합 | 저장소당 하나의 완결된 파일, 일관되고 서로 다른 repo_id, 동일 행·설정이라는 조건에서 A와 **동일한 키가 동일 분할에 배정**된다. 불균형 또는 경로 외 누출이 줄어드는 효과는 없다. 저장소 단위로 결과를 보관하거나 새 프로젝트를 추가할 때 편리하다. 동일 저장소의 기간별 조각을 각각 분할하면 같은 경로가 서로 다른 분할로 갈 수 있다. 이 경우 저장소별로 먼저 중복을 정리하고 조각을 합쳐야 한다. |

`merge`는 `(repo_id, merge_sha, base_path)`를 저장하고 입력 내·입력 간 중복을 거부한다. 행 내용이 같아도 키가 다르면 통과한다. 따라서 겹치는 기간을 재추출한 조각을 그대로 합치거나 저장소 이름 표기만 바꿔 중복 검사를 통과시키지 않는다. A/B 비교 시 비교 대상은 각 분할의 키·15컬럼 값·양성 수다. Parquet 파일 바이트는 행 배정 동등성 판단에 쓰지 않는다. [스키마 검사](https://github.com/AIX-APLUS/aix-preprocessor/blob/06e755ebabed1707a3413ec99ffa2511b046c543/src/main/java/io/aix/preprocessor/DatasetInput.java#L13-L20) · [중복과 순서 보존](https://github.com/AIX-APLUS/aix-preprocessor/blob/06e755ebabed1707a3413ec99ffa2511b046c543/src/main/java/io/aix/preprocessor/DatasetMerger.java#L35-L68)

| 남는 위험 | 평가에서 확인할 항목 |
|---|---|
| Rename, 복제, 저장소 간 공통 코드 | 분할 간 동일 base 코드의 SHA-256 교집합, 동일/다른 경로·저장소 구분, 빈 주석·공백 차이 등으로 바뀐 유사 코드 후보를 별도 표본 점검한다. 유사성만으로 서로 다른 라벨을 지우지 않는다. |
| 동일 병합의 여러 파일, 시간 인접 이력 | 분할 간 `(repo_id,merge_sha)` 교집합과 동일·인접 base가 등장하는 정도를 측정한다. 별도 시간 평가를 한다면 훈련 기록 이후에 발생한 병합을 평가하고, 학습·평가 간 복제도 재점검한다. |
| 미래 정보 | 입력은 base 코드와 base까지의 통계로 한정한다. 이력 인덱스는 모든 refs를 보지만 base에서 도달할 수 없는 커밋, base보다 committer 시간이 늦은 커밋은 제외한다. 과거 rename 전 경로 이력은 이어지지 않는다. merge·parent SHA, 경로, 레이블은 샘플 대조용으로 보관하며 세 모델 입력 텍스트에서 제외한다. |
| 같은 코드의 상반된 결과 | 코드가 같아도 서로 다른 분기 변경이 일어나면 참·거짓이 달라질 수 있다. 동일 코드 그룹별 레이블 혼재율을 확인하고 코드만 보는 실험의 한계로 해석한다. |
| 프로젝트 규모와 클래스 불균형 | 저장소별 행·양성·고유 양성 병합·경로 집중도, 평가셋별 두 클래스 실제 건수를 공개한다. 기본 음성 예측기의 정확도와 함께 양성 정밀도·재현율, PR-AUC, 저장소별·매크로 결과를 본다. 양성이 없는 분할의 관련 지표는 계산 불가로 표시한다. 필요 시 훈련에만 저장소/클래스 가중치를 적용하고 자연 분포 평가셋을 보존한다. |
| 낯선 프로젝트로의 일반화 | 일반 분할은 이미 본 프로젝트의 새 경로 평가다. 충분한 양성·음성이 있는 저장소 하나를 통째로 학습·검증에서 빼고 같은 세 입력 구성으로 별도 평가한다. 프로젝트 수가 허용되면 저장소를 바꾸어 반복한다. 평가셋을 보고 학습 저장소나 문턱을 바꾸지 않는다. |

코드 길이는 실제 Qwen 토크나이저와 그 리비전, 특수 토큰 포함 여부를 기록해야 토큰 수로 해석할 수 있다. 문자 수·UTF-8 바이트는 별도 지표다. 정해진 문맥 길이에 대해 잘리는 행 비율을 저장소와 레이블별로 세어 코드 입력 실험의 불리함을 구분한다. 저장소 코드 스타일의 대리지표로 경로별 모듈 집중도, 파일 크기, 테스트 코드 비중을 함께 보고, 이 값만으로 스타일 다양성을 단정하지 않는다. [base 시점과 통계 범위](https://github.com/AIX-APLUS/aix-preprocessor/blob/06e755ebabed1707a3413ec99ffa2511b046c543/src/main/java/io/aix/preprocessor/HistoryIndex.java#L65-L108) · [15개 컬럼 정의](https://github.com/AIX-APLUS/aix-preprocessor/blob/06e755ebabed1707a3413ec99ffa2511b046c543/src/main/java/io/aix/preprocessor/DatasetWriter.java#L17-L35)

### 과거 JabRef 결과의 출처

PR #1 작성자는 경로 1,047개에서 전체 2,625행을 분할했고, 학습 1,838행 중 양성 476, 검증 394행 중 양성 102, 테스트 393행 중 양성 102라고 보고했다. 합계로 계산하면 양성 680, 음성 1,945, 양성률 25.90%다. PR 본문과 공개 댓글에서 JabRef 입력 SHA·refs 목록·추출 시 사용한 Git 및 바이너리 버전과 원본 Parquet는 확인되지 않았다. PR 코드 HEAD `44eceea452b313cfa053f9135c3cd9340d8ce23a`는 분할 기능의 코드 버전이다. 이 수치는 후보 선정에 참고할 독립적인 과거 보고로 두고, 이번 실측의 분모나 통합 긍정률에 합산하지 않는다. [PR #1 원문](https://github.com/AIX-APLUS/aix-preprocessor/pull/1)

# 저장소 적합성 실험 재현

고정 전처리기는 `06e755ebabed1707a3413ec99ffa2511b046c543`이다. 본조사 대상 다섯 곳과 고정 기본 브랜치는 [pins.tsv](pins.tsv)에 있다. 파일 한 줄은 공백으로 구분한 별칭, owner/repository, 기본 브랜치, SHA다. 모든 실행은 새 작업 디렉터리를 사용한다. 저장소 클론, 소스가 든 Parquet, 토크나이저, 빌드 산출물은 연구 브랜치에 넣지 않는다.

## 보관된 원자료에서 재검산하기

기준 실행은 [44549292132](https://github.com/AIX-APLUS/aix-preprocessor/actions/runs/44549292132), 연구 커밋은 `a6a7c7ea2c699eb84d87c4b391e33497fd35cc5e`다. [실행 명세](evidence/run-44549292132-provenance.json)에 그래프 ZIP 5개와 집계 ZIP 1개의 ID, 크기, GitHub SHA-256, ZIP 엔트리 해시와 Job ID가 있다. 이번 회수에서는 GitHub Actions 다운로드 주소에서 ZIP을 직접 받았고, 별도로 pilot 로그의 SUMMARY 6개를 받아 검산했다. 각 ZIP과 로그는 저장소 밖에 두었다. ZIP 보존기간이 지나도 다음 검사는 저장소에 보관한 소형 증거만으로 실행할 수 있다.

저장소 루트에서 아래 명령을 실행했다. Python 3.10 이상을 사용한다. 정량 JSON을 다시 생성할 때는 지정한 출력 파일만 갱신된다.

```console
python research/repository-audit/verify_run_artifacts.py
python research/repository-audit/verify_results.py --check research/repository-audit/evidence/validation/pilot-integrity.json
python research/repository-audit/verify_additional_screen.py
python research/repository-audit/comparison.py --output docs/research/repository-suitability.json
python research/repository-audit/render_pilot.py --check
```

ZIP과 로그가 있다면, 여섯 ZIP의 파일명을 `aggregate-pilot-results.zip`, `graph-spring.zip`, `graph-jenkins.zip`, `graph-forge.zip`, `graph-jabref.zip`, `graph-quarkus.zip`으로 둔다. 이번 검산에서 아래 방식으로 원본 16개·ZIP 6개·로그 SUMMARY 6개의 일치를 확인했다. `DOWNLOADS`와 `PILOT_LOG`는 사용자가 저장한 경로로 치환한다.

```console
python research/repository-audit/verify_run_artifacts.py --zip-dir DOWNLOADS --pilot-log PILOT_LOG
```

로그는 [pilot job 135648324860](https://github.com/AIX-APLUS/aix-preprocessor/actions/runs/44549292132/job/135648324860)의 `Report aggregate evidence` 단계에서 받는다. ZIP을 구할 수 없으면 로그만 `--pilot-log PILOT_LOG`로 지정해도 된다. 검증기는 엄격한 Base64 디코딩 → gzip 해제 → UTF-8 JSON 파싱을 수행하고, 6개 자료의 이름·중복·누락·해시·보관 원문까지 검사한다. 그래프 refs는 [runs/](evidence/runs)의 TSV를 압축 해제해 graph JSON 해시와 대조한다. 기존 파일과 ZIP 내 파일의 gzip OS 헤더 1바이트 차이도 명세에 기록했다.

보고서 표를 갱신하려면 `render_pilot.py`에서 `--check`를 뺀다. 그림 재생성에는 matplotlib와 한국어 글꼴이 필요하다. [시각화 코드](render_pilot.py)와 [원래 구간 그래프 코드](plot_parent_windows.py)는 서로 다른 분모를 그린다.

```console
python research/repository-audit/render_pilot.py --check --figure docs/research/pilot-yield.png
```

## 성공한 Ubuntu 실행과 별도 로컬 재현 예시

실제로 성공한 런너는 Ubuntu 24.04.5, Git 2.56.1, Temurin 17.0.21+9, Python 3.12.3이었다. 추출용 JAR는 `06e755eb`의 `./gradlew --no-daemon --console=plain shadowJar`로 빌드했다. 그래프 작업은 `graph_inventory.py`를 다섯 저장소에 병렬로 실행했다. 파일럿 작업은 고정 `pins.tsv` 순서대로 다음 명령을 실행한 후, 같은 런너에서 `quality.py`로 Parquet 다섯 개를 검사했다. 전체 명령과 환경변수는 [실제 실행 워크플로](https://github.com/AIX-APLUS/aix-preprocessor/blob/a6a7c7ea2c699eb84d87c4b391e33497fd35cc5e/.github/workflows/repository-suitability-study.yml)에 고정되어 있다.

```bash
timeout 12m python research/repository-audit/pilot.py run "$repo" "$tip" \
  --source extractor --work "$RUNNER_TEMP/pilot" --out "$RUNNER_TEMP/results"
```

다음은 로컬 Linux에서 그래프를 재사용하는 대안 절차다. 이 블록 자체의 전 과정을 이번 회수에서 다시 실행하지 않았다.

아래 명령은 연구 브랜치 루트에서 Bash로 실행한다. JDK 17, `merge-tree --write-tree`를 지원하는 Git, Python 3.10 이상, 하드 링크를 지원하는 로컬 파일시스템이 필요하다. 정량 JSON의 프로그램 버전과 이력·파일 크기를 함께 비교한다.

```bash
set -euo pipefail
repo_root="$PWD"
scripts="$repo_root/research/repository-audit"
work="$(mktemp -d)"
mkdir "$work/results"
git clone --no-local "$repo_root" "$work/extractor"
git -C "$work/extractor" checkout --detach 06e755ebabed1707a3413ec99ffa2511b046c543
(cd "$work/extractor" && ./gradlew --no-daemon --console=plain shadowJar)
while read -r slug repo branch sha; do
  python "$scripts/graph_inventory.py" --repository "$repo" --branch "$branch" \
    --sha "$sha" --work-dir "$work/graph-$slug" --output "$work/results/$slug.json"
  python "$scripts/pilot.py" run "$repo" "$sha" --graph "$work/graph-$slug" \
    --source "$work/extractor" --work "$work/pilot" --out "$work/results"
done < "$scripts/pins.tsv"
python "$scripts/quality.py" --jar "$work/extractor/build/libs/aix-preprocessor.jar" \
  --benchmarks "$work/extractor/benchmarks" --output "$work/results/quality.json" \
  "$work"/pilot/datasets/*.parquet
```

호스티드 실행은 Qwen2.5-Coder-0.5B 리비전 `8123ea2e9354afb7ffcc6c8641d1b2f5ecf18301`, `tokenizers==0.21.4`, `tokenizer.json` SHA-256 `c0382117ea329cdf097041132f6d735924b697924d6f6fc3945713e96ce87539`로 실제 토큰을 셌다. 같은 결과를 얻으려면 위 `quality.py` 호출에 `--tokenizer-json FILE --tokenizer-sha256 HASH`를 추가한다. 생략하면 코드 포인트와 UTF-8 바이트만 기록하고 토큰은 미측정이다. 원 실행과 추가 측정 모두 base 코드에 특수 토큰, 패딩, 잘림을 적용하지 않았다. [토크나이저](https://huggingface.co/Qwen/Qwen2.5-Coder-0.5B/tree/8123ea2e9354afb7ffcc6c8641d1b2f5ecf18301)

## 논리 행을 재생성한 뒤 추가로 측정하기

이전 ZIP의 집계에는 양성 병합 수와 정확한 토큰 상한 초과 건수가 없었다. 다섯 고정 anchor에서 재생성한 Parquet에 동일한 독립 디코더를 적용했다. 저장소별 15개 자료형 전체의 논리 해시, 레이블 수, 고정 토크나이저 분위수가 Ubuntu 원본과 일치할 때만 아래 분석을 진행한다. 위 Linux 재현 절차의 `$work/pilot/datasets`에도 필요한 입력이 생긴다. 재추출 시간·메모리는 원래 Ubuntu 수치에 합산하지 않는다. [추가 측정 JSON](evidence/pilot-enrichment.json) · [Windows에서 실행한 경로와 코드](pilot-enrichment.md)

다음 명령은 재생성한 다섯 Parquet에서 실행했다. 경로는 로컬 입력으로 바꾼다. 결과는 저장소·병합 식별자 수, 여섯 이력 피처 분포, 소스코드의 토큰·바이트 기준 초과 행 수다.

```console
python research/repository-audit/pilot_enrichment.py --datasets DATASETS --jar JAR --tokenizer-json TOKENIZER_JSON --output OUTPUT_JSON
```

JabRef·Jenkins의 과거 소스 헤더 두 건이 어떤 파일럿 행에 실제로 포함됐는지도 대조했다. 같은 다섯 파일에 아래 명령을 실행해 [저장된 두 양성 행과 파일 해시](evidence/validation/license-row-match.json)를 재현한다. 여기서도 소스 본문은 결과 JSON에 쓰지 않는다.

```console
python research/repository-audit/verify_license_rows.py --parquet-dir DATASETS --jar JAR --output LICENSE_ROWS_JSON
```

## 이력 범위

- 전체 그래프는 체크아웃 없이 `--filter=tree:0`으로 모든 공개 heads/tags를 한 번에 가져온다. 커밋 부모 이력은 완전하다. 숨은 PR refs, 포크, 삭제된 브랜치는 범위 밖이다. 기본 브랜치 고정 SHA와 이 로컬 미러의 `--all`을 각각 집계한다. `git rev-list --parents`, `git merge-base --all P1 P2` 결과로 부모 수와 유일 base를 센다.
- 실제 추출은 고정 tip의 first-parent 선상에서 오래된 순서로 100번째 두 부모 병합을 고른다. 도달 커밋이 14,000개 또는 두 부모 병합이 450개를 초과하면 순번을 절반씩 낮춘다. 이력 경계는 병합의 결과나 레이블을 보기 전에 선택한다. `refs/heads/pilot` 하나로 새 bare 저장소에 해당 SHA의 **전체 조상과 객체**를 받는다. `git fsck --connectivity-only`와 `git rev-parse --is-shallow-repository`를 확인한다. 따라서 조상에 포함된 side branch의 병합까지 분석한다. `--depth`는 사용하지 않는다.
- SHA 하나로 파일럿을 재현할 수 있다. 반면 전체 heads/tags 범위는 이후 움직일 수 있다. 연구 실행의 `*.refs.tsv.gz`는 각 ref와 당시 객체 SHA 전체를 담는다. 재현 시 같은 ref 이름·SHA로 복원하고 JSON의 `refs_uncompressed_sha256`을 검사한다. upstream에서 과거 객체를 제공하지 않는 경우 장기 재현에는 별도 객체 보관본이 필요하다.
- `pilot.py`의 시간은 `java -Xmx2g -jar … extract … --threads 2` 한 번의 CLI 시작부터 종료까지다. 준비 fetch, 별도의 후보 파일 집계, 사후 `stats`는 구간 밖이다. Linux `/usr/bin/time %M`은 커널이 보고한 최대 RSS(KiB)로, 동시 자식 전체의 메모리 합계나 동시대 프로젝트 전체 처리량을 의미하지 않는다. 입력과 런타임이 달라 전체 처리시간을 선형 외삽하지 않는다.

## GitHub 메타데이터 재조회

```bash
cd research/repository-audit
python verify_default.py evidence/github-default-evidence.json evidence/latest-100-parent-counts.json
python verify_metadata.py evidence/github-metadata.json \
  --period evidence/recent-parent-counts.json --period evidence/historical-parent-counts.json
```

조사 당시 PR 식별자와 병합 결과 SHA를 고정한다. REST 결과의 부모 수, PR HEAD 포함 여부와 원본 URL은 `evidence/`에 있다. 이후 규칙 변경이나 미공개 merge 방식 추론을 별도 실측으로 합산하지 않는다.

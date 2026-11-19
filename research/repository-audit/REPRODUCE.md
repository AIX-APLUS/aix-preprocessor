# 저장소 적합성 실험 재현

고정 전처리기는 `06e755ebabed1707a3413ec99ffa2511b046c543`이다. 본조사 대상 다섯 곳과 고정 기본 브랜치는 [pins.tsv](pins.tsv)에 있다. 파일 한 줄은 공백으로 구분한 별칭, owner/repository, 기본 브랜치, SHA다. 모든 실행은 새 작업 디렉터리를 사용한다. 저장소 클론, 소스가 든 Parquet, 토크나이저, 빌드 산출물은 연구 브랜치에 넣지 않는다.

## 실험 환경과 명령

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

토크나이저 없이 실행하면 코드 포인트와 UTF-8 바이트 분포가 남고 토큰 필드는 비어 있다. 호스티드 연구 실행은 Qwen2.5-Coder-0.5B 리비전 `8123ea2e9354afb7ffcc6c8641d1b2f5ecf18301`의 `tokenizer.json`과 `tokenizers==0.21.4`를 요청한다. 같은 토큰 분포를 재현하려면 해당 파일을 내려받아 결과 JSON의 SHA-256과 일치하는지 확인하고 `quality.py`에 `--tokenizer-json FILE --tokenizer-sha256 SHA256`을 추가한다. 코드 문자열에 특수 토큰·패딩·잘림을 적용하지 않는다. [토크나이저](https://huggingface.co/Qwen/Qwen2.5-Coder-0.5B/tree/8123ea2e9354afb7ffcc6c8641d1b2f5ecf18301)

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

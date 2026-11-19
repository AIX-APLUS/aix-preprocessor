# 고정 파일럿의 행 단위 보완 측정

[Ubuntu 원자료](evidence/runs/)에는 15개 컬럼의 논리 해시가 있다. 연구용 Parquet을 다시 만든 뒤 모든 컬럼과 라벨이 그 해시와 일치하는지 확인했고, 다섯 저장소 모두 통과했다. [보완 측정값](evidence/pilot-enrichment.json)은 이 사본에서 계산한 수치다. 보고서의 시간·RSS·파일 크기는 원래 Ubuntu 측정을 따른다.

## 원본과 같은 Parquet에서 통계 재생성

Ubuntu 파일럿 절차에서 만들어진 `pilot/datasets/owner__repo.parquet` 파일을 다섯 개 모두 사용한다. 입력 디렉터리와 출력 파일은 분리한다. 아래 명령에서 경로는 실행 환경에 맞춘다. 검증에 사용한 라이브러리는 `tokenizers==0.21.4`, 토크나이저는 Qwen 리비전 `8123ea2e9354afb7ffcc6c8641d1b2f5ecf18301`이다.

```bash
python research/repository-audit/pilot_enrichment.py \
  --datasets "$work/pilot/datasets" \
  --jar "$work/extractor/build/libs/aix-preprocessor.jar" \
  --benchmarks "$work/extractor/benchmarks" \
  --tokenizer-json "$work/qwen.json" \
  --output "$work/pilot-enrichment.json"
```

프로파일러는 기존 `DumpParquet.java`와 `dataset.py`로 스키마, 중복 키, 양·음성 수와 전체 행의 논리 SHA-256을 검사한다. 이어 토크나이저 파일의 SHA-256과 각 저장소의 토큰 길이 min/p50/p90/p95/max를 Ubuntu JSON과 대조한 후 결과를 쓴다. `>`로 표시한 토큰 길이는 `base_code`에 대해서만 특수 토큰·패딩·절단 없이 계산한다. 병합 단위와 파일 단위 집계에는 저장소 식별자가 포함된다. 여섯 이력 컬럼의 분위수는 행별 가중치가 같은 최근접 순위(nearest rank)다.

## 이번 Windows 재실행의 경로

1. 각 원본 `pilot-*.json`에서 `pilot_anchor`를 읽었다. 개인 임시 폴더에 저장소별 bare 저장소를 새로 만들고, 해당 SHA에서 `refs/heads/pilot` 하나만 받아 shallow 여부와 전체 연결성을 검사했다. 실행에 사용한 Git 명령 형태는 다음과 같다.

   ```bash
   git init --bare "$private_repo"
   git -C "$private_repo" symbolic-ref HEAD refs/heads/pilot
   git -C "$private_repo" -c gc.auto=0 fetch --no-tags "$upstream" "$anchor:refs/heads/pilot"
   git -C "$private_repo" rev-parse --is-shallow-repository
   git -C "$private_repo" for-each-ref '--format=%(objectname) %(refname)'
   git -C "$private_repo" fsck --connectivity-only --no-dangling
   ```

2. Git for Windows의 로컬 `clone --mirror --shared` 단독 검사에서 `sh.exe: NtCreateDirectoryObject … 0xC0000022`가 재현됐다. 이미 격리한 임시 bare 입력에 원래 `Extraction.run`과 `DatasetWriter`를 직접 호출했다. 아래는 임시로 컴파일해서 사용한 진입점의 본문이다. 병합 라벨·이력 특성·행 쓰기는 모두 고정 전처리기 코드가 담당한다.

   ```java
   package io.aix.preprocessor;
   import java.nio.file.Path;
   public final class ReplayOnPrivateBareInput {
       public static void main(String[] args) throws Exception {
           try (var writer = new DatasetWriter(Path.of(args[2]))) {
               Extraction.run(new Git(Path.of(args[0])), args[1], 2, writer);
           }
       }
   }
   ```

3. `git diff --quiet 06e755ebabed1707a3413ec99ffa2511b046c543 -- src/main build.gradle benchmarks/dataset.py benchmarks/DumpParquet.java`의 종료 코드는 0이었다. 해당 생산 Java 소스 전부와 위 진입점·`DumpParquet.java`를 Oracle JDK 17.0.12의 `javac --release 17 -encoding UTF-8`로 컴파일했다. 기존 로컬 fat JAR(SHA-256 `c463a2dd6cca39ce9f9a5c1928571aee3fb7e0c30789c6a8502791f3beaa91db`)는 의존성으로 사용했다. 실행 클래스패스에서 새 클래스 폴더를 JAR보다 앞에 놓고 `java -Xmx2g -cp CLASSPATH io.aix.preprocessor.ReplayOnPrivateBareInput PRIVATE_BARE_REPO OWNER/REPO OUTPUT.parquet`를 실행했다. 재생성 환경은 Git 2.55.0.windows.5, Python 3.10.2, 추출 스레드 2개였다.
4. 위 프로파일러를 다섯 Parquet에 실행했다. 각 결과는 원래 Ubuntu 파일럿의 키 정렬 15개 필드 논리 SHA-256과 일치했다. 서로 다른 실행 환경의 속도 비교나 생산 CLI의 Windows 파일 게시 동작은 이번 통계가 검증하는 범위 밖이다.

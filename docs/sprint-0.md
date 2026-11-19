# Sprint 0 · 추출 결과와 처리 시간의 기준선

## 팀 최적화 병합 후의 호환성 검사

팀의 PR #3이 main `d7a6c921f841109a00682a212bfbd8b55ba0eb1a`에 병합되면서 이력 인덱스, 상주 `git cat-file --batch`, 이름 변경 한도, Gradle 9.1이 도입됐다. 아래 `d0bdc825` 성능표는 이 최적화 **이전**의 Sprint 0 기준선이다. 새 main은 동일 레코드를 생성하고 정상 종료하는지를 확인하는 호환성 검사 대상으로 삼았다. [팀의 PR #3](https://github.com/AIX-APLUS/aix-preprocessor/pull/3)

첫 결합 검사 `dcfc4ad55b4d3ef97181246f63fc3c1f341c6312`에서 읽기 전용 Git 객체와 junction에 대한 회귀 검사는 Windows에서 통과했다. 그러나 CLI는 골든과 일치하는 4행을 게시한 뒤 `mirror.git` **디렉터리**를 삭제할 때 공유 위반으로 실패했다. 종료 코드는 1이었고 임시 트리가 남았다. 수정 브랜치 단독 Windows JUnit도 같은 통합 테스트에서 실패했다. Ubuntu 첫 시도는 Maven Central HTTP 429로 의존성을 받지 못해 JUnit을 실행하지 못했다. [Windows CLI 실패 로그](https://github.com/AIX-APLUS/aix-preprocessor/actions/runs/44518179078/job/135539563549) · [Ubuntu 준비 실패 로그](https://github.com/AIX-APLUS/aix-preprocessor/actions/runs/44518179078/job/135539564025)

로컬 Windows에서 실제 blob을 쓰고 읽은 뒤 런처와 자식 프로세스를 관찰했다. 기존 `destroy()`는 런처를 종료했지만 자식이 남아 미러 즉시 삭제가 10/10회 실패했다. `destroy()` 뒤 런처만 기다려도 10/10회 실패했다. 표준 입력을 닫아 EOF를 보내고 Git이 정상 종료할 때까지 기다린 대조군은 자식 잔존 0건, 즉시 삭제 10/10회 성공이었다. 호환성 수정은 `BlobReader.close()`의 종료 순서와 그 회귀 검사에 한정했다. 이력 인덱스, blob 읽기, 행 선택, 스키마는 팀 커밋을 그대로 사용한다.

수정 커밋은 `9660be44adc9777333e4fb934df58639409fa388`이다. 동일한 Git 객체로 만든 새 JUnit은 이전 코드에서 디렉터리 공유 위반으로 실패했고 수정 후 통과했다. 호출 스레드의 인터럽트 상태가 보존되는 것도 로컬에서 확인했다. 독립 수정 CI는 양 OS에서 네 개의 필수 추출·정리 테스트가 실제로 실행돼 통과했는지 확인했다. 통합 `4a0828c0ce9f2f6a54c004447340ed7794880db6`에서는 양 OS에서 이 네 건과 팀의 이력 인덱스 테스트까지 JUnit 5/5, Python 14/14가 통과했다. 실제 CLI로 fixture와 고정 minimal-json을 모두 1·4스레드에서 실행했고, 각각 4행(양성 2·음성 2)과 1행(음성 1)의 기존 논리 해시를 재현했다. [독립 수정 CI](https://github.com/AIX-APLUS/aix-preprocessor/actions/runs/44519426115) · [통합 Windows 검사](https://github.com/AIX-APLUS/aix-preprocessor/actions/runs/44519464506/job/135544049459) · [통합 Ubuntu 검사](https://github.com/AIX-APLUS/aix-preprocessor/actions/runs/44519464506/job/135544049829)

### 최종 생산 코드 조합의 별도 측정

`aac7b74a2881227df8c2f1cc251599627a6cb473`은 위 기능 검증 커밋과 문서만 다르다. Windows·Ubuntu의 각 보고서에서 실제 checkout HEAD와 변경 파일 0건을 확인했다. 입력별·스레드별로 준비 1회와 본측정 3회를 수행했다. 총 32회가 모두 성공했고 준비 8회는 표에서 제외했다. fixture의 전체 논리 해시는 `b93b6d16e1ec0e95f924ac92d7e6a5b560b79677a5ca85583a30f77548dd4bcc`, minimal-json은 `8e4078e84ac01f4e86f2443972da696dbbc049d8ac24f4415560e131f261ba66`이다. [기능 검사와 벤치마크 4개 작업](https://github.com/AIX-APLUS/aix-preprocessor/actions/runs/44519600887)

| OS | 입력 | 스레드 | 병합 | 행 (양성 / 음성) | 중앙값 초 | 최소–최대 초 | 표본 표준편차 초 | 병합/초 | 행/초 | Parquet 바이트 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Ubuntu | fixture | 1 | 2 | 4 (2 / 2) | 0.5979 | 0.5960–0.9791 | 0.2206 | 3.345 | 6.690 | 5,130 |
| Ubuntu | fixture | 2 | 2 | 4 (2 / 2) | 0.5927 | 0.5799–0.5984 | 0.0095 | 3.374 | 6.748 | 5,130 |
| Ubuntu | minimal-json | 1 | 7 | 1 (0 / 1) | 0.6862 | 0.6787–0.9003 | 0.1258 | 10.201 | 1.457 | 13,162 |
| Ubuntu | minimal-json | 2 | 7 | 1 (0 / 1) | 0.6724 | 0.6723–0.7424 | 0.0405 | 10.410 | 1.487 | 13,162 |
| Windows | fixture | 1 | 2 | 4 (2 / 2) | 1.2533 | 1.2449–1.2957 | 0.0272 | 1.596 | 3.192 | 5,130 |
| Windows | fixture | 2 | 2 | 4 (2 / 2) | 1.1961 | 1.1831–1.2651 | 0.0441 | 1.672 | 3.344 | 5,130 |
| Windows | minimal-json | 1 | 7 | 1 (0 / 1) | 1.4387 | 1.4353–1.5290 | 0.0532 | 4.866 | 0.695 | 13,162 |
| Windows | minimal-json | 2 | 7 | 1 (0 / 1) | 1.4031 | 1.3155–1.4848 | 0.0847 | 4.989 | 0.713 | 13,162 |

| 러너 | OS / 커널 | CPU | 논리 CPU | 인식 RAM (바이트) | Python | Git | JAR SHA-256 |
| --- | --- | --- | ---: | ---: | --- | --- | --- |
| Ubuntu | Linux-7.0.0-1017-azure-x86_64-with-glibc2.39 | AMD EPYC 9V74 80-Core Processor | 4 | 16760348672 | 3.12.16 | 2.56.1 | `d9cff46620caec1d373bb5dd1d651471b58797cd5d7091a2367c819a05339aaa` |
| Windows | Windows-2025Server-10.0.26100-SP0 | AMD EPYC 9V74 80-Core Processor | 4 | 17174360064 | 3.12.10 | 2.56.0.windows.4 | `d9cff46620caec1d373bb5dd1d651471b58797cd5d7091a2367c819a05339aaa` |

양쪽 모두 Temurin 17.0.21+9, Gradle Wrapper 9.1.0이다. 고정된 소형 입력과 이 러너 조합의 관측값이며, Ubuntu 1스레드는 특히 실행별 편차가 컸다. 캐시와 장비가 다른 아래의 과거 측정으로 최적화나 정리 수정의 인과적 속도 변화를 계산할 수 없다. 최대 메모리·Git 호출 수·단계별 시간은 N/A다. [Windows 측정 로그](https://github.com/AIX-APLUS/aix-preprocessor/actions/runs/44519600887/job/135544521425) · [Ubuntu 측정 로그](https://github.com/AIX-APLUS/aix-preprocessor/actions/runs/44519600887/job/135544520858) · [Windows 원자료](https://github.com/AIX-APLUS/aix-preprocessor/actions/runs/44519600887/artifacts/14528001150) · [Ubuntu 원자료](https://github.com/AIX-APLUS/aix-preprocessor/actions/runs/44519600887/artifacts/14526269202)

병합 조건은 독립 수정 브랜치를 먼저 main에 병합하고, 그 main을 반영한 PR #2 자체에서 양 OS 검사가 통과하는 것이다. PR #2에는 생산 코드 수정을 포함하지 않았다. [독립 수정 브랜치와 main 비교](https://github.com/AIX-APLUS/aix-preprocessor/compare/main...fix/windows-git-object-cleanup) · [Sprint 0 PR #2](https://github.com/AIX-APLUS/aix-preprocessor/pull/2)

## PR #1 병합 후, 추출 최적화 이전의 성능 기준선

최초 검증 이후 팀에서 PR #1을 병합해 main이 `bc7e09c`에서 `8fbc0f01e71d6d8515781b5c4bd09e9b9a4c6fc7`로 이동했다. 이 변경은 CLI와 Parquet 작성기도 건드리므로 새 기준에서 다시 검증했다. 독립 수정 브랜치 `54d858998c83c70b3443632d9c9a59ba59dfc931`의 최신 main 대비 변경은 `Main.java`, `ExtractionTest.java`, `git-mirror-cleanup.yml` 세 파일이다. 팀원이 추가한 `DatasetSplitter.java`와 `DatasetWriter.java`는 main과 동일하다. 이 검증은 추출 경로를 대상으로 한다. [팀의 PR #1](https://github.com/AIX-APLUS/aix-preprocessor/pull/1) · [수정 브랜치의 양 OS JUnit 3/3](https://github.com/AIX-APLUS/aix-preprocessor/actions/runs/44516844265)

수정과 PR #2를 합친 `084484b6a785771cc1a6c0be7258ef094ce77fb5`에서는 두 OS의 JUnit 3건·Python 14건·실제 CLI가 모두 통과했다. Windows 벤치마크는 16/16회 성공했다. Ubuntu 벤치마크는 Maven Central이 의존성 다운로드에 HTTP 429를 반환해 측정을 시작하지 못했다. 해당 실패에서 성능 수치를 계산하지 않았다. 재실행 커밋 `d0bdc825ac6fbbc9a420b57c3a132e12b872a525`는 이전 커밋과 트리 ID `9ad3183bd819dbdc39cf8350fcfc59c76b942f55`가 같다. [최초 실행과 실패 로그](https://github.com/AIX-APLUS/aix-preprocessor/actions/runs/44516900544/job/135535140908) · [동일 트리 재실행](https://github.com/AIX-APLUS/aix-preprocessor/actions/runs/44517223600)

양쪽 러너 모두 체크아웃의 SHA 일치와 변경 파일 0건을 확인했다. 두 입력의 스키마 및 논리 해시는 최초 기준과 같았다. OS별 기능 검사는 JUnit 3/3, Python 14/14, CLI 1·4스레드 골든 비교, 원본 fixture 보존 및 임시 디렉터리 정리를 포함한다. [Windows 기능 검사](https://github.com/AIX-APLUS/aix-preprocessor/actions/runs/44517223600/job/135536265247) · [Ubuntu 기능 검사](https://github.com/AIX-APLUS/aix-preprocessor/actions/runs/44517223600/job/135536265073)

| OS | 입력 | 스레드 | 병합 | 행 (양성 / 음성) | 중앙값 초 | 최소–최대 초 | 표본 표준편차 초 | 병합/초 | 행/초 | Parquet 바이트 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Ubuntu | fixture | 1 | 2 | 4 (2 / 2) | 0.6338 | 0.5568–0.6351 | 0.0448 | 3.156 | 6.311 | 5,130 |
| Ubuntu | fixture | 2 | 2 | 4 (2 / 2) | 0.5843 | 0.5189–0.5876 | 0.0388 | 3.423 | 6.845 | 5,130 |
| Ubuntu | minimal-json | 1 | 7 | 1 (0 / 1) | 0.6009 | 0.5724–0.6090 | 0.0192 | 11.649 | 1.664 | 13,162 |
| Ubuntu | minimal-json | 2 | 7 | 1 (0 / 1) | 0.5939 | 0.5348–0.6014 | 0.0365 | 11.786 | 1.684 | 13,162 |
| Windows | fixture | 1 | 2 | 4 (2 / 2) | 1.4562 | 1.4287–1.4647 | 0.0188 | 1.373 | 2.747 | 5,130 |
| Windows | fixture | 2 | 2 | 4 (2 / 2) | 1.2315 | 1.2306–1.2605 | 0.0170 | 1.624 | 3.248 | 5,130 |
| Windows | minimal-json | 1 | 7 | 1 (0 / 1) | 1.4367 | 1.4162–1.4601 | 0.0220 | 4.872 | 0.696 | 13,162 |
| Windows | minimal-json | 2 | 7 | 1 (0 / 1) | 1.3163 | 1.3109–1.4703 | 0.0905 | 5.318 | 0.760 | 13,162 |

| 러너 | OS / 커널 | CPU | 논리 CPU | 인식 RAM (바이트) | Python | Git | JAR SHA-256 |
| --- | --- | --- | ---: | ---: | --- | --- | --- |
| Ubuntu | Linux-7.0.0-1017-azure-x86_64-with-glibc2.39 | AMD EPYC 9V45 96-Core Processor | 4 | 16760344576 | 3.12.16 | 2.56.1 | `9a5c3255b18c51ae5dbffabe2b27d589cb1ba639820e9ac6f1937cf18a17700b` |
| Windows | Windows-2025Server-10.0.26100-SP0 | AMD EPYC 9V74 80-Core Processor | 4 | 17174360064 | 3.12.10 | 2.56.0.windows.4 | `d80e534864d961d33aec5657b7381477eb6b8a590ed949f4da258cffdc180399` |

두 OS 각각 Temurin 17.0.21+9, Gradle 8.14.3에서 준비 4회와 본측정 12회가 모두 성공했다. 실행별 중앙값·범위·표본 표준편차와 처리량을 검산했다. 캐시는 비우지 않았다. 최대 메모리·Git 호출 수·단계별 시간은 N/A다. 이 수치는 각 환경의 다음 실험을 위한 기준이다. [Windows 원자료](https://github.com/AIX-APLUS/aix-preprocessor/actions/runs/44517223600/artifacts/14526301877) · [Ubuntu 원자료](https://github.com/AIX-APLUS/aix-preprocessor/actions/runs/44517223600/artifacts/14525638997)

병합 순서는 독립 Windows 수정 → PR #2에 최신 main 반영 → PR #2 자체의 Windows·Ubuntu 기능 검사 통과 확인 → PR #2 병합이다. 각 화살표의 병합은 담당자의 승인을 거친다.

## 최초 main 기준의 Windows 정리 수정 후 통합 검증

독립 버그 수정은 `main`에서 분기했고, PR #2에는 테스트·측정 도구·문서만 들어간다. 두 변경을 결합한 임시 브랜치의 실행과 PR #2 단독 실행은 SHA로 구분했다. 먼저 버그 수정을 병합한 뒤 PR #2에 최신 main을 반영하고 양 OS 기능 검사가 통과하는지 확인해야 한다. PR #1의 데이터 분할 작업은 이 검증에서 사용하지 않았다.

첫 통합 커밋 `53cb97139f8bf50645d4b6669969e6ed7dd7e0fe`에서 양 OS 모두 JUnit 3건·Python 13건·골든 CLI·두 입력 벤치마크를 통과했다. Windows 보고서는 측정 도구의 체크아웃을 `dirty=true`로 기록했다. 로컬 재현에서 Git의 개행 변환 설정을 끄고 상태를 읽으면 실제로 변경하지 않은 CRLF 파일도 수정된 것으로 표시됐다. 첫 러너는 해당 경로를 기록하지 않아 그 실행의 원인까지 특정할 수 없다. 아래 최종 측정은 러너의 일반 Git 설정으로 실제 SHA와 깨끗한 상태를 확인하는 절차를 추가한 실행이다. [첫 통합 실행과 원자료](https://github.com/AIX-APLUS/aix-preprocessor/actions/runs/44511702821)

### 최초 main에서 체크아웃까지 검증한 측정과 CI

측정한 코드의 커밋은 `81a823d89031432a9ff3ffadcc039cfbc511f12e`이다. 추출 코드·JUnit은 수정 브랜치 `7ca793f`와 같고 측정 코드·검증 워크플로는 PR #2의 `c84b9f4185f3a841e1f64965d8886972a51658b2`와 같다. 두 러너에서 일반 Git의 변경 경로는 0건이었으며, 네 벤치마크 JSON 모두 같은 HEAD와 `dirty=false`를 기록했다. Windows에서 설정을 격리한 Git으로 같은 시점에 읽으면 26개 경로가 달라 보였다. 이 러너에서 일반 설정의 `core.autocrlf`는 `true`, 격리 설정에서는 미지정이었다. [통합 실행](https://github.com/AIX-APLUS/aix-preprocessor/actions/runs/44512599507)

| OS | 입력 | 스레드 | 병합 | 행 (양성 / 음성) | 중앙값 초 | 최소–최대 초 | 표본 표준편차 초 | 병합/초 | 행/초 | Parquet 바이트 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Ubuntu | fixture | 1 | 2 | 4 (2 / 2) | 0.5373 | 0.5131–0.5391 | 0.0145 | 3.722 | 7.444 | 5,130 |
| Ubuntu | fixture | 2 | 2 | 4 (2 / 2) | 0.5139 | 0.5079–0.5180 | 0.0051 | 3.892 | 7.783 | 5,130 |
| Ubuntu | minimal-json | 1 | 7 | 1 (0 / 1) | 0.5313 | 0.5249–0.5440 | 0.0097 | 13.175 | 1.882 | 13,162 |
| Ubuntu | minimal-json | 2 | 7 | 1 (0 / 1) | 0.5096 | 0.5044–0.5235 | 0.0099 | 13.736 | 1.962 | 13,162 |
| Windows | fixture | 1 | 2 | 4 (2 / 2) | 1.8210 | 1.8197–1.8232 | 0.0018 | 1.098 | 2.197 | 5,130 |
| Windows | fixture | 2 | 2 | 4 (2 / 2) | 1.5697 | 1.5426–1.5749 | 0.0173 | 1.274 | 2.548 | 5,130 |
| Windows | minimal-json | 1 | 7 | 1 (0 / 1) | 1.8451 | 1.8342–1.8502 | 0.0081 | 3.794 | 0.542 | 13,162 |
| Windows | minimal-json | 2 | 7 | 1 (0 / 1) | 1.7029 | 1.6953–1.7174 | 0.0112 | 4.111 | 0.587 | 13,162 |

각 OS에서 입력별·스레드별로 준비 1회와 본측정 3회를 실행했다. 총 32회 중 준비 8회, 본측정 24회이며 모두 검증을 통과했다. 표는 본측정만 집계했다. 각 JSON의 개별 실행 시간과 건수로 중앙값·범위·표본 표준편차·처리량을 다시 계산해 대조했다. 두 운영체제는 장비와 Git 버전이 다르고, 최초 Ubuntu 측정과 이번 Ubuntu 측정도 CPU와 러너가 다르다. 이 표에서 수정으로 인한 속도 변화는 추론하지 않는다. 최대 메모리·Git 호출 수·단계별 시간은 N/A다. [Ubuntu 측정 로그](https://github.com/AIX-APLUS/aix-preprocessor/actions/runs/44512599507/job/135520369390) · [Windows 측정 로그](https://github.com/AIX-APLUS/aix-preprocessor/actions/runs/44512599507/job/135520369075)

| 러너 | OS / 커널 | CPU | 논리 CPU | 인식 RAM (바이트) | Python | Git | JAR SHA-256 |
| --- | --- | --- | ---: | ---: | --- | --- | --- |
| Ubuntu | Linux-7.0.0-1014-aws-x86_64-with-glibc2.39 | Intel(R) Xeon(R) 6975P-C | 4 | 16464297984 | 3.12.16 | 2.56.1 | `c7d8034a9f2ccc698df5657a49713ff60f8a92c51c2a80efb2c53121282795fc` |
| Windows | Windows-2025Server-10.0.26100-SP0 | AMD EPYC 7763 64-Core Processor | 4 | 17174360064 | 3.12.10 | 2.56.0.windows.4 | `08e658e91124d0db5436dea21d49fcc674b96a5c5ea7b86bcd413466214f0a5a` |

양쪽 모두 Temurin 17.0.21+9, Gradle 8.14.3에서 JUnit 3/3, Python 14/14, 실제 CLI 1·4스레드 검증을 통과했다. 두 입력의 논리 SHA-256은 아래 최초 기준값과 같다. fixture Parquet의 바이트 해시는 이번 Windows에서 `42d4ec4d…`, Ubuntu에서 `5ac4da08…`였다. 원본 fixture의 파일·Git 저장소 보존, 기존 출력 덮어쓰기 거부, 정상 완료 후 임시 디렉터리 0건도 검사했다. 아래 두 아티팩트(14일 보존)와 측정 로그에 네 JSON이 남는다. [Ubuntu 기능 검사](https://github.com/AIX-APLUS/aix-preprocessor/actions/runs/44512599507/job/135520369446) · [Windows 기능 검사](https://github.com/AIX-APLUS/aix-preprocessor/actions/runs/44512599507/job/135520369465) · [Ubuntu 원자료](https://github.com/AIX-APLUS/aix-preprocessor/actions/runs/44512599507/artifacts/14524417152) · [Windows 원자료](https://github.com/AIX-APLUS/aix-preprocessor/actions/runs/44512599507/artifacts/14523983273)

PR #2 단독 코드 `c84b9f4`에서는 Ubuntu 기능 검사가 통과하고 Windows 검사가 기존 생산 코드 정리 오류로 실패했다. 수정 브랜치와 통합 브랜치의 성공이 PR #2 자체의 Windows 실행을 대체하지 않는다. 최종 판정은 수정 PR 병합과 PR #2 갱신 후 양 OS 재확인을 조건으로 한다. [PR #2 단독 검사](https://github.com/AIX-APLUS/aix-preprocessor/actions/runs/44512538598)

## 2026-11-19 최초 기준 측정 · Windows 정리 수정 전

기준 생산 코드 `bc7e09c9e2244b3e93d9b2d6c89e3335275a80da`와 측정 도구 `fd222b50e326b8ace80a0fe6572217a9c4d7b31c`의 조합으로 실행했다. 두 커밋 사이에 생산 Java 코드, Gradle 빌드 설정, 기존 테스트의 변경은 없다. 기존 JUnit 통합 테스트 1개, 비교기 테스트 3개, 패키징된 CLI의 1·4스레드 Parquet 검증이 통과했다. 성능 측정은 같은 러너에서 입력 2종 × 스레드 설정 2종 × (준비 1회 + 본측정 3회), 총 16회 성공했다. [기능 검증 로그](https://github.com/AIX-APLUS/aix-preprocessor/actions/runs/44486889091/job/135432469642) · [측정 로그 및 원자료](https://github.com/AIX-APLUS/aix-preprocessor/actions/runs/44486889091/job/135432469383)

**측정 환경** · GitHub Actions `ubuntu-24.04` x86-64, Linux `7.0.0-1017-azure`, AMD EPYC 7763, 러너에 할당된 논리 CPU 4개, 인식 메모리 16,760,336,384바이트(15.61 GiB), Temurin 17.0.21+9, Git 2.56.1, Gradle Wrapper 8.14.3, Python 3.12.3. 측정 JAR SHA-256은 `14914770660506bfb11edda771ea6800ae754d3fc7494be62a6b0fb144aa18fa`다. 이후 날짜에 실행할 때는 호스팅 러너와 설치 도구의 세부 버전도 대조한다.

| 입력 | 스레드 | 병합 | 샘플 (양성 / 음성) | 중앙값 초 | 최소–최대 초 | 표본 표준편차 초 | 병합/초 | 샘플/초 | Parquet 바이트 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 고정 fixture | 1 | 2 | 4 (2 / 2) | 0.8370 | 0.8247–0.8377 | 0.0073 | 2.389 | 4.779 | 5,130 |
| 고정 fixture | 2 | 2 | 4 (2 / 2) | 0.7943 | 0.7942–0.8032 | 0.0051 | 2.518 | 5.036 | 5,130 |
| minimal-json | 1 | 7 | 1 (0 / 1) | 0.8522 | 0.8498–0.8953 | 0.0256 | 8.214 | 1.173 | 13,162 |
| minimal-json | 2 | 7 | 1 (0 / 1) | 0.8154 | 0.7949–0.8587 | 0.0326 | 8.585 | 1.226 | 13,162 |

초당 수치는 실행별 처리량의 중앙값이다. JVM 및 자식 프로세스의 최대 메모리, Git 호출 수, 단계별 시간은 **N/A**다. 기본 벤치마크는 프로세스 트리나 단계별 호출을 추적하지 않는다. Git의 요약에 명시적인 건너뜀 사유는 두 입력에서 모두 빈 집합이었다. minimal-json에서는 방문한 병합 7건 중 전체 출력이 음성 1행이었다. 어느 후보 필터가 나머지를 제외했는지는 이 계측으로 구분할 수 없다. 2스레드의 중앙값이 두 입력 모두 짧았지만, 특히 minimal-json은 반복 측정 범위가 겹친다. 대형 입력의 병렬 효율과 단계별 병목은 후속 측정 대상이다.

| 검증 항목 | 관측값 |
| --- | --- |
| 고정 fixture 논리 SHA-256 | `b93b6d16e1ec0e95f924ac92d7e6a5b560b79677a5ca85583a30f77548dd4bcc` |
| fixture 1·4스레드 Parquet 파일 SHA-256 | 두 파일 모두 `9c5949a3434b8f913ba26ec01e2869676d4c5b9d2ddc0975634aec2c6dfd8769` |
| minimal-json 논리 SHA-256 | `8e4078e84ac01f4e86f2443972da696dbbc049d8ac24f4415560e131f261ba66` |
| 원본 보존 | 고정 fixture의 작업 파일·인덱스·설정·객체·refs 대조 통과. 실제 입력 및 미러의 refs와 HEAD 대조 통과 |

최초 로컬 Windows 시도는 Gradle 배포 서버의 DNS 조회 단계에서 중단돼 JUnit까지 도달하지 못했다. 이후 의존성을 확보한 같은 프로젝트에서 별도의 Windows 런타임 결함이 드러났다. 위 표는 최초 Ubuntu 러너의 측정치다. 공개 Java 입력은 minimal-json의 단일 고정 ref로 한정했다. JabRef 전체 이력과 복잡한 병합은 후속 검증 대상이다. 두 측정 JSON은 원자료 아티팩트의 보존 기간 동안 받을 수 있다. [원본 JSON 두 개](https://github.com/AIX-APLUS/aix-preprocessor/actions/runs/44486889091/artifacts/14510599033)

## 독립 리뷰와 재검증

Claude가 검토한 PR #2 HEAD는 `9904344256f62eea3ba5c1e2ca3f68282915fdfe`, 기준 main은 `bc7e09c9e2244b3e93d9b2d6c89e3335275a80da`다. 이 두 버전의 생산 코드가 같다. 해당 HEAD에 대한 최초 PR 검사는 Ubuntu에서 통과했다. 별도 Windows 리뷰 worktree에서 작성된 전체 리뷰(F1–F8, 최초 판정 Comment), 후속 수정 보고, 미커밋 Java 패치를 확인했다. [최초 PR 검사](https://github.com/AIX-APLUS/aix-preprocessor/actions/runs/44491608573) · [PR #2](https://github.com/AIX-APLUS/aix-preprocessor/pull/2)

**Windows 실패 경로.** Git for Windows가 임시 미러에 쓴 loose object는 DOS 읽기 전용 속성을 갖는다. 기존 CLI는 Parquet를 하드 링크로 게시하고 `Saved`를 출력한 뒤 `finally`에서 이 객체를 `Files.delete`로 지웠다. 보존된 실패 로그에는 정상 집계(병합 2, 샘플 4, 양성 2), 게시 메시지, `Main.java:67`의 `AccessDeniedException`, 종료 코드 1이 차례로 있다. 출력 파일과 `.aix-*`가 남으며 같은 출력 경로를 다시 쓰면 기존 파일 보호 검사에 걸린다.

**Claude의 Windows 측정.** JDK 17.0.1, Git 2.55.0.windows.5에서 기존 PR HEAD의 통합 테스트가 실패했다. 회귀 사례를 추가한 수정 전 시험은 2/2 실패, Claude의 미커밋 수정안에서는 2/2 통과로 보고됐다. 비교기 3건, 1·4스레드 4행(양성 2, 음성 2), 한글 경로 CLI와 임시 폴더 정리를 확인했다고 보고했다. 해당 수정안의 보존된 벤치마크 JSON에서 fixture와 minimal-json 각각 8/8 성공과 위의 논리 해시를 확인했다. 1·2스레드 중앙값은 fixture 2.802·2.049초, minimal-json 3.071·2.546초였다. 이 시간은 Claude의 로컬 수정안으로 얻은 관측값이며, 아래 독립 버그 수정 커밋의 측정과 구분한다.

**독립 버그 수정.** main에서 분기한 `fix/windows-git-object-cleanup`의 `886de5c1319b8ebdc7ebea261e190315f6522abf`는 Claude의 삭제 재시도 범위를 좁혔다. Windows에서 삭제가 거부된 경우에만 링크를 따라가지 않고 DOS 속성을 읽는다. 읽기 전용 일반 파일이면 해당 속성만 해제하고 한 번 다시 지운다. ACL·디렉터리·심볼릭 링크 권한을 바꾸지 않으며 다른 삭제 실패는 호출자에게 전달한다. POSIX에서 파일 삭제는 부모 디렉터리 권한의 영향을 받으므로 Windows용 복구를 수행하지 않는다. 회귀 테스트는 실제 `git hash-object -w`로 객체를 생성하며, Windows에서는 Git이 붙인 속성과 첫 삭제 실패까지 검사한다. 추출 규칙·15열 스키마·하드 링크 게시 순서는 유지했다.

| 항목 | 독립 확인과 반영 | 검증 범위와 남은 조건 |
| --- | --- | --- |
| F1 · Windows 정리 실패 | 실패 로그와 기존 코드의 경로가 일치했다. 별도 수정 커밋의 JUnit은 Git 객체 삭제와 추출 후 임시 폴더 잔존을 검사한다. | 정리와 추출이 모두 실패하면 Java의 try-with-resources가 원래 예외를 보존하고 정리 예외를 suppressed로 남긴다. 게시 후 다른 정리 오류가 생기면 출력이 존재해도 종료 1이 가능하다. `Saved`는 정리 성공 후에만 출력하며 실패한 trial은 집계 대상에서 빠진다. |
| F2 · 외부 저장소의 고정 기준 | 최초 도구는 첫 trial도 정답으로 삼을 수 있었다. 현재 도구는 선택한 기대 행 수와 논리 해시를 준비 실행부터 매번 적용한다. 첫 실행이 일관되게 0행이어도 1행 기준에서 실패하는 회귀 사례가 있다. | minimal-json CI에 두 기준을 모두 고정했다. 임의 저장소에서 둘 다 생략한 경우 보고서에 `repeatability_only`가 표시된다. |
| F3 · JAR 출처 | 기존 JSON에는 측정 도구 HEAD·dirty 상태가 없었고 JAR 엔트리에는 빌드 시각이 들어갔다. 새 JSON은 `benchmark_checkout.head`와 `dirty`, 실제 사용한 JAR SHA-256을 구분해 기록한다. | Git 밖에서는 상태가 `null`이다. 외부에서 넘긴 JAR의 소스 커밋은 이 정보만으로 증명할 수 없다. 바이트 재현 빌드는 이후 과제다. |
| F4 · 테스트 0건, Windows CI 부재 | 양쪽 OS에서 Gradle 빌드 후 XML의 필수 JUnit 메서드가 실제 통과했는지 검사한다. Python 테스트 0건을 거부하고 CLI와 Golden 검증도 수행한다. | 수정 전 PR #2에는 정리 테스트 자체가 없다. 버그 수정이 포함된 통합 버전에서 해당 회귀 메서드의 실행까지 확인한다. 기능 검사는 PR마다, 반복 벤치마크는 별도로 실행한다. |
| F5 · Golden 타입과 float32 | 기존 비교기가 boolean과 같은 값의 정수를 받아들이고 FLOAT와 동등한 소수 `0.6666667`을 거부하는 현상을 재현했다. 15열의 문자열·boolean·int32·유한 FLOAT 자료형과 범위를 검사한다. 예상 소수는 Parquet FLOAT와 같은 IEEE 754 binary32로 반올림한다. | 잘못된 타입·범위, 같은 float32로 표현되는 소수와 바로 이웃한 다른 float32를 단위 테스트로 구분했다. 기존 4행의 논리 해시가 유지된다. |
| F6 · 원본 보존 검사 범위 | 기존 검사가 hook 변경을 놓치는 현상을 재현했다. 고정 fixture에서는 `.git`까지 이름·파일 종류·모드·읽기 전용 여부·파일 내용 해시·링크 대상을 대조한다. hook·exclude·alternates, repack과 인덱스 표현 변경을 검증하는 테스트가 있다. | 링크 대상 파일은 따라가지 않는다. 시각·ACL까지 보증하지 않는다. 외부 저장소는 원본 및 스냅샷의 refs·HEAD 확인으로 한정한다. |
| F7 · 실패 보고서에 남던 부분 통계 | 기존 보고서는 일부 trial이 실패해도 먼저 성공한 trial의 중앙값을 노출했다. 현재 보고서는 전체 성공 시에만 시간·처리량 분포를 계산한다. | 실패 시 원인과 개별 관측, 검증·실패 건수는 진단용으로 남긴다. 결과 소비자는 `success`를 먼저 확인한다. |
| F8 · Parquet 물리 해시 차이 | 최초 Ubuntu와 Claude의 Windows에서 파일 크기 5,130바이트와 fixture 논리 해시가 일치했다. 파일 바이트 해시 접두사는 각각 `9c5949a3`, `5ac4da08`였다. | 물리 바이트가 다른 원인은 미확정이다. 플랫폼 간 합격 기준은 스키마와 식별자별 15열 값이다. |

**확인과 조치.** F1·F2·F4·F5·F6·F7은 Confirmed로 수용했다. F1은 읽기 전용 처리 대상을 좁히고, 디렉터리 링크가 가리키는 외부 파일까지 보호하도록 수정 후 수용했다. F3는 출처 정보 누락을 확인해 보완했다. 빌드 환경 간 JAR 차이가 전적으로 타임스탬프 때문인지는 미검증이며, 바이트 단위 재현 빌드는 Deferred다. F8은 관측된 현상으로 Confirmed, 논리 동등성 검사 결함으로는 Not Applicable이다. PR #2에서 `1bd6c54`는 양 OS 기능검사, `073ef7f`는 타입·원본 보존, `a99d316`은 외부 기준·통계·실제 실행 건수 검증에 해당한다.

**Golden의 독립 근거.** Astra는 고정 fixture의 Git 트리에서 코드·경로·blob·부모와 기준 커밋을 읽고, 세 버전의 파일을 `git merge-file`로 합쳐 레이블을 구했다. 파일별 비병합 커밋과 줄 수 변화를 직접 집계한 결과는 4행 × 15열, 총 60개 값에서 Golden과 일치했다. 최초 Ubuntu 원자료와 Claude의 수정안 원자료에서 준비 실행을 빼고 시간·처리량 분포도 다시 계산했다. Claude는 별도로 Parquet 변형 21종, 장애 주입 5종, 한글·공백·이모지 문자열과 minimal-json의 유일한 음성 후보까지 조사했다. 이 추가 사례의 수치는 Claude가 실행한 범위다.

**독립 재현과 수정 후 JUnit.** Windows JDK 17.0.12와 Git 2.55.0.windows.5에서 실제 객체의 DOS 읽기 전용 속성과 첫 삭제 실패를 확인했다. 별도 실험에서 추출과 정리를 함께 실패시키자 기존 코드는 추출 오류를 잃었다. 수정 후에는 쓰기 가능한 파일의 삭제 잠금을 그대로 보고하며, 원래 Git 오류와 정리 예외 하나가 함께 전달됐다. 이 관리 환경에서는 MSYS 미러 복제와 junction 생성이 차단돼 최종 JUnit 3건 중 실제 객체 시험 1건만 로컬 통과했다. 쓰기 가능한 임시 경로에서 최종 Python 14건 중 13건이 통과했고, 링크 생성 권한이 필요한 1건은 생략됐다.

GitHub의 수정 전 Windows 러너에서는 1·4스레드 통합 JUnit이 첫 추출에서 실패했다. 별도로 실행한 CLI는 종료 1이었지만 게시된 출력은 골든 4행과 일치했고 `.aix-*`가 남았다. 같은 커밋의 Ubuntu 검사는 통과했다. 수정 브랜치의 `27db630`은 디렉터리 junction 및 심볼릭 링크를 따라가지 않고 제거한다. `7ca793fe85426304fa8c723129b4f728c282d874`의 양 OS 러너는 기존 통합 추출, 실제 읽기 전용 Git 객체, 외부 디렉터리 링크 대상 보존 세 테스트를 각각 모두 실행하고 통과했다. [수정 전 Windows](https://github.com/AIX-APLUS/aix-preprocessor/actions/runs/44511178870/job/135515512656) · [수정 전 Ubuntu](https://github.com/AIX-APLUS/aix-preprocessor/actions/runs/44511178870/job/135515513291) · [수정 브랜치 양 OS JUnit](https://github.com/AIX-APLUS/aix-preprocessor/actions/runs/44511530836)

JabRef 전체, 강제 종료 뒤 자동 복구, 네트워크 드라이브와 하드 링크를 지원하지 않는 파일시스템, Windows 보호 경로는 검증 범위에 포함되지 않았다. 출력을 게시한 뒤 실제 ACL이나 파일 잠금으로 정리가 실패하는 경우에는 종료 코드와 출력의 존재를 각각 확인해야 한다. 후속 Sprint 1에서 이 실패 계약과 경계 사례의 레이블을 점검한다.

## 기준 버전과 실행 경로

조사 시점에 `main`과 `test/extraction-baseline`의 HEAD는 모두 `bc7e09c9e2244b3e93d9b2d6c89e3335275a80da`였다. 작업 브랜치의 선행 변경은 0건이었다. 원격에는 `gradle-test`, `feature/data-split`도 있었다. 유일한 열린 PR #1은 `feature/data-split`에서 `main`으로 보내는 데이터 분할 작업이었다. 그 PR의 HEAD는 `44eceea452b313cfa053f9135c3cd9340d8ce23a`였다.

생산 코드 경로는 `src/main/java/io/aix/preprocessor/`다.

| 파일 | 입력에서 출력까지의 역할 |
| --- | --- |
| `Main.java` | `extract REPO`와 기존 `REPO` 호출을 받는다. 얕은 복제본과 기존 출력 경로를 거부한다. 입력 저장소의 Git 객체를 공유하는 임시 미러를 만들고, 완성한 Parquet 파일을 하드 링크로 게시한 뒤 임시 디렉터리를 정리한다. |
| `Extraction.java` | 미러의 `rev-list --all --parents --min-parents=2 --max-parents=2` 결과를 순회한다. 여러 refs에서 도달 가능한 같은 병합도 한 번만 처리한다. 병합 단위로 최대 스레드 수만큼 작업을 제출하고 제출 순서대로 결과를 기록한다. |
| `MergeAnalyzer.java` | 두 부모의 공통 병합 기준점(merge base)이 하나일 때 양쪽 차이를 구한다. 기준 경로의 일반 파일 중 양쪽에서 내용이 바뀌었고 이전·이후 경로 모두 소문자 `.java`인 항목을 고른다. Git이 감지한 이름 변경도 내용이 바뀌었으면 후보가 된다. |
| `History.java` | 기준 커밋에서 도달 가능한 비병합 커밋을 기준 경로로 조회한다. 기준의 커미터 시각까지 마지막 수정 이후 경과 일수와, 그 시각에서 90일 전까지 양 끝을 포함한 수정 횟수·저자 이메일 수·최다 저자 비중·추가 및 삭제 줄 수를 계산한다. 과거 이름은 따라가지 않는다. |
| `Git.java` | 명령마다 독립 Git 프로세스를 실행하고 표준 출력을 모두 읽는다. Git 환경 변수를 제거한 뒤 로케일과 시스템·전역 설정 사용 여부를 지정한다. |
| `Sample.java` | 저장소·병합·부모·기준 커밋 식별자, 기준점의 경로·blob·소스, 이력 통계와 레이블을 한 행으로 묶는다. |
| `DatasetWriter.java` | 단일 작성자가 15개 필수 열을 지정된 타입·순서로 기록한다. 출력은 Snappy 압축 Parquet다. |

README에 적힌 전체 refs 탐색, 단일 기준점, 기준 시점의 소스와 이력, Git 재현 레이블은 구현과 일치한다. 기본 스레드 수는 JVM에서 보이는 논리 프로세서 수와 8 중 작은 값이다. 입력 refs는 미리 로컬에 확보해야 한다. 추출기는 실행 중 원격을 가져오지 않는다.

양성은 `git merge-tree --write-tree -z`가 후보의 기준 경로 또는 두 부모의 대응 경로에 `CONFLICT (contents)`를 보고하고 다른 충돌 유형도 함께 표시하지 않은 경우다. 후보 파일에서 이런 텍스트 충돌이 없으면 음성이다. 같은 병합 안에서도 파일별 레이블이 다를 수 있다. 개발자가 작성한 해결 결과, 빌드 실패, 의미상의 충돌은 이 레이블로 알 수 없다.

추출 요약의 병합 수에는 출력 0행인 병합도 들어간다. `no unique merge base`는 **병합 건수**, `non-text conflict`, `non-UTF-8 source`, `binary base`, `unavailable history`는 **후보 파일 건수**다. 구조적·분류 불명 충돌은 제외하며 기준 소스를 UTF-8로 읽을 수 없거나 NUL이 포함된 경우도 제외한다. 이력에서 관측 가능한 마지막 변경이 없거나 90일 안에 이진 numstat가 있으면 이력 통계를 만들 수 없다. 한쪽만 변경, 신규 추가, 비-Java, 삭제, 내용이 같은 이름 변경 등은 후보 선별 단계에서 사라진다. 따라서 요약의 `Skips` 합계로 전체 탈락률을 계산할 수 없다.

## 출력 비교 기준

기존 `src/test/java/io/aix/preprocessor/ExtractionTest.java`는 독립된 두 가지 병합을 만든 후 1·4스레드 결과의 Parquet 바이트를 비교한다. 4행의 일부 값, 깨끗한 작업 트리, 기존 출력 파일 보호도 검사한다. 매번 새 커밋 시각을 사용하므로 서로 다른 날짜의 실행을 비교할 때는 아래 고정 입력을 사용한다.

`benchmarks/fixture.py`는 SHA-1, LF, 작성자·시각, 파일 내용, 부모 순서와 refs를 고정해 작은 Git 저장소를 만든다. `main`과 별도 `side` 브랜치의 병합 2개가 같은 기준 커밋에서 갈라진다. 태그 하나가 `main` 병합을 다시 가리킨다. 루트 시점은 90일 창 밖이고 Alice와 Bob의 일부 수정은 창 안에 있다.

| 두 병합에 각각 들어간 사례 | 기준 기대값 |
| --- | --- |
| `Clean.java`의 떨어진 두 줄을 양쪽에서 수정 | 음성 1행씩. 최근 수정 2회, 저자 2명, 최다 비중 0.5, 마지막 변경 후 2일, 추가·삭제 각 2줄 |
| `Conflict.java`의 같은 줄을 다르게 수정 | 양성 1행씩. 최근 수정 1회, 저자 1명, 최다 비중 1.0, 마지막 변경 후 4일, 추가·삭제 각 1줄 |
| `OneSide.java` 한쪽만 수정, `README.txt` 양쪽 수정, `Added.java` 양쪽 신규 추가 | 세 경로 모두 0행 |
| 별도 브랜치 병합과 같은 커밋을 가리키는 태그 | 서로 다른 병합 2개, 양성 2·음성 2, 합계 4행 |

`benchmarks/golden.json`은 예상 네 행의 15개 값을 모두 담는다. `DumpParquet.java`가 실제 파일의 열 이름·순서·필수 여부·물리 타입·논리 타입을 검사한다. `dataset.py`는 `(repo_id, merge_sha, base_path)`로 식별자를 확인하고 중복·누락·예상 밖의 행·개별 값 차이를 보고한다. 열 순서대로 직렬화한 각 행을 SHA-256으로 해싱하고, 식별자순으로 정렬한 행 해시들로 전체 논리 해시를 만든다. 물리 파일의 해시는 진단용이다. 행 순서나 Parquet 메타데이터가 달라도 논리 해시는 유지된다.

`verify.py`는 고정 입력에 스테이징한 수정, 스테이징 이후의 추가 수정, 추적하지 않는 파일을 남긴 상태로 실제 CLI를 1·4스레드로 실행한다. 각 실행 전후에 작업 트리와 `.git` 내부를 물리 파일 단위로 대조한다. 기존 출력에 식별 가능한 바이트를 써 둔 별도 호출로 종료 코드·거부 사유·파일 보존을 확인하고, 출력 옆에 남은 `.aix-*`도 검사한다. 실제 저장소 성능 실행에서는 원본을 읽기 전용으로 사용하고 스냅샷과 원본 refs 및 HEAD를 전후에 확인한다. 그 입력의 전체 파일·인덱스·설정을 대조하는 검사는 고정 fixture에 한정한다.

## 재현 방법

프로젝트 루트에서 실행한다. 준비물은 JDK 17, Git 2.43 이상, Python 3.10 이상이다. 첫 빌드에는 Gradle 8.14.3 배포본과 Maven 의존성이 필요하다. 임시 파일 및 Parquet 출력 위치는 하드 링크를 지원해야 한다. Windows PowerShell에서는 첫 명령을 `.\gradlew.bat --no-daemon build`로 실행한다.

```sh
./gradlew --no-daemon build
python -m unittest discover -s benchmarks -p "test_*.py" -v
python benchmarks/verify.py
python benchmarks/benchmark.py --threads 1 2 --warmups 1 --repeats 3 --report build/benchmarks/fixture.json
```

실제 저장소의 같은 표본을 확보하려면 다음과 같이 빈 경로에 공개 Java 프로젝트 `ralfstx/minimal-json`의 한 커밋과 조상 전체를 받아 한 개의 ref를 만든다. 다른 태그나 브랜치를 가져오면 분석 대상이 바뀐다.

```sh
git init -q --bare -b pinned ../minimal-json-sprint0.git
git -C ../minimal-json-sprint0.git fetch -q --no-tags https://github.com/ralfstx/minimal-json.git c091e6985620da04d5abcd902aafb6c9583c48ea:refs/heads/pinned
python benchmarks/benchmark.py --repo ../minimal-json-sprint0.git --repo-id ralfstx/minimal-json --threads 1 2 --warmups 1 --repeats 3 --expect-logical-sha256 8e4078e84ac01f4e86f2443972da696dbbc049d8ac24f4415560e131f261ba66 --expect-samples 1 --report build/benchmarks/minimal-json.json
```

보고서는 새 파일만 만든다. 이전 실행과 비교할 때는 새 출력 이름을 쓰고 refs·JDK·Git·하드웨어·스레드 수·반복 수를 맞춘다. 동일 논리 해시가 재현되는지 먼저 확인한 다음 시간을 비교한다. 실제 저장소에서 반복 간 출력이 같다는 사실만으로 개별 레이블의 정답 여부가 검증되지는 않는다.

## 시간과 처리량 해석

- 입력 생성·고정, 독립적인 병합 수 집계, 결과 파일 재독출과 해시 비교는 타이머 밖이다. 타이머는 새 JVM 프로세스 시작부터 종료까지를 잰다. 이 안에 CLI가 수행하는 미러 생성, 병합 재현, 이력 조회, Parquet 게시 및 임시 파일 정리가 포함된다.
- 각 설정에서 준비 실행 후 본측정을 반복한다. 한 실행마다 JVM이 바뀌어 JIT 컴파일 비용은 본측정에도 포함된다. 준비 실행은 OS·파일시스템 캐시를 데울 수 있다. 캐시는 강제로 비우지 않으며, 설정의 시작 순서를 라운드마다 회전한다.
- 초당 병합 수와 초당 샘플 수의 분모는 각각 해당 전체 실행의 초 단위 경과 시간이다. 검증에 성공한 본측정만 중앙값·최소·최대·표본 표준편차에 들어간다. 실패 시 JSON에 오류와 해당 실행을 기록하고 중단한다. 짧은 fixture에서는 JVM 시작 시간의 영향이 클 수 있다. 병합이 2건이어서 동시에 분석할 수 있는 병합도 최대 2건이다.
- JSON에는 입력 refs·실행 환경·JAR SHA-256, 스레드별 각 실행의 성공 여부·종료 코드·건너뛴 사유·Parquet 크기·논리 해시가 남는다. 최대 메모리, Git 하위 프로세스 호출 수, 단계별 시간은 기본 계측 대상에서 제외했다. JVM·Git 프로세스 트리 추적과 생산 코드 프로브를 추가하는 별도 실험이 필요하다.
- PR #1 작성자는 JabRef 분할 입력 2,625행, 이 중 양성 680행, 경로 1,047개를 보고했다. 입력 refs와 추출 시간·장비는 PR에 기록되지 않았다. 해당 수치는 이 실험의 성능이나 출력 동등성을 판단하는 기준으로 쓸 수 없다. [PR #1](https://github.com/AIX-APLUS/aix-preprocessor/pull/1)

## 후속 검증 우선순위

아래 성능 효과는 코드 구조에서 도출한 가설이다. 동일 refs의 논리 출력과 본측정 분포를 함께 비교해 채택 여부를 결정한다.

| 우선순위 | 관찰과 후속 작업 | 기대 효과 | 구현 위험 / 검증 난이도 |
| --- | --- | --- | --- |
| 1 · Sprint 1 | 단일 기준점, 경로 필터와 충돌 유형 분기에 별도 예제 추가. 이름 변경·비텍스트·특수 경로·다중 기준점·90일 경계의 포함·제외 이유를 수작업 예상값과 비교 | 잘못된 레이블과 조용히 누락되는 사례의 영향 범위 파악 | 중 / 높음. 과거 프로젝트의 사용자 정의 병합 드라이버까지 재현하는 범위는 별도 정의 |
| 2 · Sprint 2 | `History.collect`는 후보마다 기준점에 도달 가능한 해당 경로 전체 이력을 읽는다. 반복되는 기준점·경로의 빈도와 이력 조회 시간을 먼저 측정 | 같은 조회가 많은 입력에서 중복 탐색 감소 가능 | 중 / 높음. 90일 밖 마지막 변경, 저자와 numstat까지 기준행과 비교 |
| 3 · Sprint 3 | `Git.run`의 프로세스 수와 출력 바이트, JVM 및 Git 자식 프로세스 메모리를 계측. 큰 이력의 `readAllBytes`와 디코딩·분할 비용 분리 | 프로세스 시작 시간 및 최대 메모리 감소 가능 | 중~높음 / 중~높음. NUL 구분·UTF-8·실패 경로 회귀 필요 |
| 4 · Sprint 4 | 오래 걸리는 첫 작업을 기다리는 동안 후속 작업 제출이 지연되는지 병합별 시간·대기열로 확인. 분석과 단일 작성자·Snappy 출력 시간을 따로 측정 | 불균등한 병합에서 처리량 개선 가능. 직렬 출력 비중에 따라 한계 | 높음 / 높음. CPU 제약과 파일 캐시를 맞추고 행의 결정성·중복·메모리 검증 |

## 발표용 설명

두 사람이 같은 조별 과제 원본을 각자 고쳤다고 생각하자. 한 사람은 첫 문단을, 다른 사람은 마지막 문단을 고치면 두 수정을 모을 수 있다. 같은 문장을 서로 다르게 바꾸면 어느 쪽을 쓸지 사람이 정해야 한다. 전처리기는 과거 버전 두 개를 다시 합쳐 보며 이런 일이 생긴 파일에 표시한다. 예측 모델이 볼 수 있는 단서는 두 사람이 각자 작업을 시작한 시점까지의 파일과 수정 기록이다.

발표에서는 원본 한 장과 두 수정본을 나란히 두고, 멀리 떨어진 문장과 겹치는 문장을 다른 색으로 표시한다. 그다음 두 파일의 예상 결과표 옆에 실제 결과를 붙인다. 다음 버전도 같은 답을 냈을 때, 같은 묶음을 처리한 시간을 비교한다. 이 순서를 거치면 파일을 빠뜨려서 빨라진 경우를 성능 개선으로 잘못 발표하는 일을 막을 수 있다.

# 수정된 연구 Workflow의 Ubuntu 검증

2026년 11월 20일 02:39:01~02:41:43 KST(11월 19일 17:39:01~17:41:43 UTC), Ubuntu 24.04에서 연구 커밋 `4b623d5511db10a5014cc7f1c7c914be97b556b8`을 실행했다. 수정 커밋 `d82dee3` 이후 실행을 요청한 변경은 `launch.txt` 한 줄이다. 생산 전처리기는 두 실행 모두 `06e755ebabed1707a3413ec99ffa2511b046c543`을 사용했다. 이 문서와 증거 명세는 실행 종료 후 문서 전용 커밋으로 추가했다. [Ubuntu 실행 44579446949](https://github.com/AIX-APLUS/aix-preprocessor/actions/runs/44579446949) · [검증한 Workflow](https://github.com/AIX-APLUS/aix-preprocessor/blob/4b623d5511db10a5014cc7f1c7c914be97b556b8/.github/workflows/repository-suitability-study.yml)

| 검증 대상 | 관측 결과 |
|---|---|
| 실행과 테스트 | 첫 번째 시도에서 그래프 Job 5개는 각각 6단계, Pilot Job은 14단계가 모두 성공했다(6/6 Job, 44/44단계). Pilot 로그에서 연구 회귀 테스트 13/13 통과를 확인했다. 로컬 테스트는 비교표 출처 검사 2개를 더해 15개다. |
| Artifact와 로그 | GitHub가 게시한 ZIP 6개의 크기와 SHA-256, 내부 파일 16개(JSON 11개, 압축 refs 목록 5개)를 확인했다. Pilot 로그의 SUMMARY 6개를 Base64·gzip으로 복원한 바이트가 집계 ZIP의 JSON 6개와 각각 같았다. |
| 행과 레이블 | 380행, 양성 54행, 음성 326행. 고정 입력 다섯 곳에서 15컬럼 전체의 논리 SHA-256이 최초 Ubuntu 실행 및 독립 Git 레이블 검산 기록과 모두 일치했다. Ubuntu 원본 Parquet는 게시 목록에 없어 파일 자체의 물리 바이트 동일성은 미검증이다. |
| 분할과 품질 | Train/Validation/Test는 267/57/56행. 두 실행의 `quality.json`을 파싱해 비교하면 새 실행에 `"token_analysis": "measured"` 한 필드가 추가됐고 기존 필드 값은 모두 같다. |
| 변동 가능한 측정 | 파일럿은 고정된 과거 SHA와 그 조상을 사용했다. 두 실행 사이 공개 브랜치·태그 목록은 다섯 곳 모두 바뀌었다. 경과 시간과 최대 메모리는 각 실행의 측정값이다. |

[집계 Artifact 14556674496](https://github.com/AIX-APLUS/aix-preprocessor/actions/runs/44579446949/artifacts/14556674496) · [Pilot 로그](https://github.com/AIX-APLUS/aix-preprocessor/actions/runs/44579446949/job/135755788001) · [최초 Ubuntu 실행 44549292132](https://github.com/AIX-APLUS/aix-preprocessor/actions/runs/44549292132) · [독립 레이블 검산](../../research/repository-audit/evidence/validation/git-label-replay.json)

## Artifact 만료 후 추적과 재검산

[실행 명세](../../research/repository-audit/evidence/run-44579446949-provenance.json)에 여섯 ZIP의 GitHub ID·만료 시각·크기·SHA-256, 내부 파일 16개의 이름과 해시, 로그 SUMMARY 해시, 저장소별 행·레이블 수와 논리 해시를 보존했다. 집계 ZIP은 9,775바이트이고 SHA-256은 `948e5b8f40d4a296170f52efe2ca51a7cdcf0340d33d13b88f336d022e20ca68`이다. GitHub가 기록한 만료 예정 시각은 12월 3일 17:39~17:41 UTC(한국 12월 4일 02:39~02:41)다. 이후에는 보관해 둔 ZIP·로그가 있으면 아래 대조를 반복할 수 있다. 명세만으로 원본 ZIP을 복구할 수는 없다.

재검산할 때는 실행 페이지에서 ZIP을 받아 `ZIPS`에 Artifact 이름 그대로 저장한다. 여섯 ZIP의 파일을 같은 빈 폴더 `MEMBERS`에 풀고, Pilot Job 로그를 UTF-8 텍스트 `PILOT_LOG`로 저장한다. 저장소 루트에서 아래 세 경로를 실제 경로로 치환해 실행한다. 검증기는 ZIP과 내부 파일, 압축 해제된 refs, 로그 SUMMARY를 이 실행의 명세와 대조한다.

```console
python -B research/repository-audit/verify_run_artifacts.py --provenance research/repository-audit/evidence/run-44579446949-provenance.json --evidence-dir MEMBERS --zip-dir ZIPS --pilot-log PILOT_LOG
```

## PR에서 확인할 범위

일반 `main` 대상 PR의 `Extraction checks`는 Ubuntu·Windows에서 생산 전처리기와 벤치마크 검증 도구를 검사한다. 연구 Workflow는 연구 브랜치에 `research/repository-audit/launch.txt` 변경을 push할 때 실행된다. 이 문서 커밋과 `4b623d5`의 차이는 `git diff --name-status 4b623d5 HEAD`로 확인할 수 있다. [PR 검사 정의](../../.github/workflows/extraction-checks.yml) · [연구 재현 절차](../../research/repository-audit/REPRODUCE.md)

Claude가 남긴 후속 사항은 다음과 같다. N1은 중단 후 같은 경로로 재시도할 때 실패 JSON이 게시되는 경우로, 새 `--work`와 새 `--out`을 사용한다. N3은 Workflow 내부의 기대 논리 해시 자동 대조, N4는 일반 PR의 연구 테스트 범위와 추출 실패 시 로그에 의존하는 진단, N5는 Windows와 Linux의 JSON 줄바꿈 차이, N6는 패키지 배포 파일 해시·Action 커밋 고정과 `setup-java@v4` 경고다. 이번 두 실행의 논리 해시는 Artifact 게시 후 별도로 대조했다.

현재 학습 저장소 선정 판정은 **FURTHER VALIDATION REQUIRED**다. 2011~2018년의 서로 다른 표본, 테스트 56행 중 54행의 훈련 세트와 동일 병합 공유, 과거 소스 고지와 원문 이용 범위는 다음 확장 실험에서 검토한다. [최종 독립 리뷰에 대한 대응](claude-review-response.md) · [데이터 품질과 평가 한계](pilot-quality.md)

# 후보 식별과 소스코드 이용 조건

2026-11-19 조사에서 확인한 공식 저장소, 기본 브랜치의 고정 커밋과 해당 커밋의 원문이다. 이 스냅샷은 출처 식별용이다. 과거 학습 행에 적용할 조건은 행마다 merge base의 소스를 기준으로 확인한다.

| 후보 | 공식 저장소와 정체 | 기본 브랜치와 고정 커밋 | 확인한 루트 조건 |
|---|---|---|---|
| Spring Boot | [spring-projects/spring-boot](https://github.com/spring-projects/spring-boot), Spring 애플리케이션 프레임워크 | `main@dd87919e93e7` | [Apache-2.0](https://github.com/spring-projects/spring-boot/blob/dd87919e93e71b2ba270ec4f2f142645e06c7610/LICENSE.txt) |
| Jenkins | [jenkinsci/jenkins](https://github.com/jenkinsci/jenkins), Jenkins 자동화 서버 코어 | `master@e8ba485c828e` | [MIT](https://github.com/jenkinsci/jenkins/blob/e8ba485c828e25422d54c1d46e0bea1cb0305d03/LICENSE.txt) |
| JabRef | [JabRef/jabref](https://github.com/JabRef/jabref), BibTeX·BibLaTeX 참고문헌 관리 프로그램 | `main@75b35b962c1d` | [MIT](https://github.com/JabRef/jabref/blob/75b35b962c1d1f45cbd5be8af025b16cde9cc290/LICENSE), [개별 라이선스 디렉터리](https://github.com/JabRef/jabref/tree/75b35b962c1d1f45cbd5be8af025b16cde9cc290/licenses) |
| Quarkus | [quarkusio/quarkus](https://github.com/quarkusio/quarkus), Quarkus 자바 프레임워크 | `main@61d971888943` | [Apache-2.0](https://github.com/quarkusio/quarkus/blob/61d971888943ff815b86a179fbfcd1db22857730/LICENSE). [기여 지침](https://github.com/quarkusio/quarkus/blob/61d971888943ff815b86a179fbfcd1db22857730/CONTRIBUTING.md)은 파일·디렉터리가 별도 조건을 지정할 수 있다고 설명한다. |
| Forge | [Card-Forge/forge](https://github.com/Card-Forge/forge), Magic: The Gathering 비공식 카드 게임 규칙 엔진 | `master@9748ef2c96d1` | [GPLv3](https://github.com/Card-Forge/forge/blob/9748ef2c96d18bcb55271e20e63c32bdee3e991c/LICENSE). [프로젝트 README](https://github.com/Card-Forge/forge/blob/9748ef2c96d18bcb55271e20e63c32bdee3e991c/README.md)는 권리자인 Wizards of the Coast와의 독립성을 명시한다. |

### Forge 식별 근거

공개 팀 자료만으로는 Forge의 소유자를 식별하기 어려웠고, 사용자가 조사 중 `Card-Forge/forge`를 명시했다. 앞 표의 다섯 저장소를 본조사 대상으로 삼았다. 다음 두 프로젝트는 이름이 겹쳐 초기에 확인한 참고 항목이다.

| Java 프로젝트 | 식별 근거 | SHA 및 조건 |
|---|---|---|
| [MinecraftForge/MinecraftForge](https://github.com/MinecraftForge/MinecraftForge) | Minecraft 모드 호환 API | `26.3@6a06826b1491`. [루트 조건](https://github.com/MinecraftForge/MinecraftForge/blob/6a06826b149192c72faca0bb68df35bc28238c18/LICENSE.txt)은 기본 LGPL 2.1 및 별도 예외를 명시한다. GitHub SPDX 필드는 `NOASSERTION`이다. MCP 데이터 제3자 재배포는 별도 허가가 필요하며 일부 FML 경로 및 타 프로젝트에서 가져온 코드에는 다른 조건이 기재되어 있다. |
| [forge/core](https://github.com/forge/core) | JBoss Forge의 Java IDE 확장·CLI 프레임워크. 저장소는 archived 상태 | `master@ab9e14669161`, [EPL-1.0](https://github.com/forge/core/blob/ab9e146691617029861b4be59e01a83df682e7e4/LICENSE) |

### Parquet와 배포 시 주의점

- Card-Forge의 완전한 Java 소스를 제3자에게 제공할 때에는 해당 버전의 GPLv3 제4조(원본 소스 전달)와 수정했다면 제5조를 검토하고 저작권·라이선스·보증 고지와 라이선스 전문을 유지한다. 다른 프로젝트를 담은 데이터셋 전체의 조건은 결합 방식과 각 파일의 조건을 따로 검토한다. 게임 이미지·카드 텍스트 등 제3자 콘텐츠는 프로젝트 코드와 출처가 다를 수 있으므로 배포 권한을 별도로 확인한다. [Forge의 GPLv3 원문](https://github.com/Card-Forge/forge/blob/9748ef2c96d18bcb55271e20e63c32bdee3e991c/LICENSE) · [공식 README](https://github.com/Card-Forge/forge/blob/9748ef2c96d18bcb55271e20e63c32bdee3e991c/README.md)

- 추출 결과에 과거 Java 파일 전문이 들어가므로 현재 루트 라이선스만으로 과거 행 전체의 이용 조건을 단정할 수 없다. 예를 들어 **JabRef v2.11은 GPL-2.0-or-later**를 README와 실제 Java 헤더에 표시했고 조사 시점의 기본 브랜치는 MIT이다. 각 행의 `repo_id, merge_sha, base_path`에서 출발해 원본 `base_sha` 및 blob을 식별하고, 해당 커밋의 파일 헤더·루트와 하위 디렉터리 라이선스·NOTICE를 함께 대조할 수 있는 별도 기록을 보관한다. [과거 README](https://github.com/JabRef/jabref/blob/4bdf5e142511278d8dd2a466bf611994caf4d091/README.md) · [같은 버전의 JabRef.java](https://github.com/JabRef/jabref/blob/4bdf5e142511278d8dd2a466bf611994caf4d091/src/main/java/net/sf/jabref/JabRef.java) · [현재 LICENSE](https://github.com/JabRef/jabref/blob/75b35b962c1d1f45cbd5be8af025b16cde9cc290/LICENSE)
- MIT 소프트웨어의 복사본 또는 상당 부분을 제공할 때에는 저작권과 허락 고지를 함께 제공한다. Apache-2.0에서는 라이선스 사본 제공, 변경한 파일에 대한 변경 표시, 적용되는 고지의 보존 및 원저작물의 NOTICE가 있는 경우 관련 고지 전달 등 제4조 조건을 확인한다. 외부 배포 묶음에는 해당 소스 헤더와 라이선스·고지 문서, 행과 출처 간 대응표를 함께 제공하는 방안이 있다. [MIT 원문](https://opensource.org/license/mit) · [Apache-2.0 제4조](https://www.apache.org/licenses/LICENSE-2.0#redistribution)
- Jenkins 코어의 주 라이선스는 MIT이며 공식 정책은 제3자 구성요소별 여러 라이선스를 설명한다. 실제 행에 들어가는 복사된 코드·생성 코드·예제는 출처별 조건을 확인한다. 패키지 실행에 필요한 의존성이 있다는 이유만으로 그 라이선스를 데이터의 모든 Java 파일에 부여할 수는 없다. [Jenkins 거버넌스 문서](https://www.jenkins.io/project/governance/) · [Quarkus 기여 지침](https://github.com/quarkusio/quarkus/blob/61d971888943ff815b86a179fbfcd1db22857730/CONTRIBUTING.md)
- 팀 내부 추출과 외부 Parquet 배포의 범위를 구분하고 공개 자료에는 출처·집계·고정 SHA·재현 명령을 먼저 제공한다. 파일별 조건이나 재라이선스 범위를 확인하기 어려운 행은 공개 원본 묶음에서 보류한다. 발표용 집계, 소스코드 데이터, 향후 모델 가중치는 서로 다른 산출물이며, 이번 조사는 모델 가중치 배포에 대한 법적 판단을 다루지 않았다.
### Ubuntu 파일럿의 과거 소스 표본

JabRef와 Jenkins에서 파일럿 기준점의 조상 중 두 부모가 같은 Java 파일을 수정한 병합을 하나씩 골랐다. GitHub의 양방향 부모 비교에서 같은 공통 조상과 `modified` 경로를 확인하고, 해당 공통 조상에 있는 파일 전문의 Git blob SHA를 원문 바이트로 다시 계산했다. 이후 동일한 파일럿을 재현해 Ubuntu 집계 해시와 일치한 Parquet에서 두 표본의 행을 찾았다. [과거 파일 헤더와 조회 URL](../../research/repository-audit/evidence/historical-license-spot-check.json) · [Parquet 행 대조 결과](../../research/repository-audit/evidence/validation/license-row-match.json)

| 저장소와 실제 파일럿 시점 | 범위 안에서 확인한 파일 | 데이터 선정에 미치는 영향 |
| --- | --- | --- |
| JabRef · 2015-08-14 · `8d22827b` | 병합 `baf58627`의 공통 조상 `cf0cde78`에서 `MODSEntry.java` 헤더는 **GPL-2.0-or-later**다. 해당 기준점의 README도 같은 조건을 명시한다. [파일 헤더](https://github.com/JabRef/jabref/blob/cf0cde78a0ea22204891eae7a245ba9332dd4e91/src/main/java/net/sf/jabref/logic/mods/MODSEntry.java#L1-L5) · [파일럿 시점 README](https://github.com/JabRef/jabref/blob/8d22827be20de435b01844f8643fe014aa910daa/README.md#L129-L135) | 현재 MIT 표기를 과거 행에 일괄 부여하면 이 표본에서 오류가 난다. 공개할 코드 행마다 당시 공통 조상, 파일 헤더, 적용 고지를 연결한다. |
| Jenkins · 2011-06-07 · `285741a5` | 병합 `5abc651c`의 공통 조상 `fe452bfb`에서 `ExtensionComponent.java` 헤더는 **MIT**다. 공통 조상과 파일럿 기준점의 루트 `LICENSE.txt`는 같은 blob이다. [파일 헤더](https://github.com/jenkinsci/jenkins/blob/fe452bfbc5a4332c81a7cdf2cbd52c3af37ee36d/core/src/main/java/hudson/ExtensionComponent.java#L1-L21) · [파일럿 시점 LICENSE](https://github.com/jenkinsci/jenkins/blob/285741a5240f3658c6e5191edc9ba65fe7d5793c/LICENSE.txt) | 이 소스 표본은 현재 라이선스 표기와 일치한다. 나머지 행의 제3자 코드 및 개별 고지는 별도 확인 대상이다. |

**두 표본 모두 실제 충돌 양성 행이었다.** 기준 파일의 Git blob은 JabRef `b1b6d41f`, Jenkins `8b0af778`이다. 두 행에서 저장소·병합 SHA·경로로 구성된 키, 두 부모의 SHA와 순서, 공통 조상 SHA, 기준 blob SHA가 모두 일치했다. Parquet에 담긴 소스를 UTF-8로 다시 인코딩한 길이와 SHA-256도 원문과 일치했다. 이 두 건은 초기 표본 대조 결과다. 아래 후속 검사는 같은 파일럿의 380행 전체를 대상으로 한다. [행별 검증 기록](../../research/repository-audit/evidence/validation/license-row-match.json)

같은 판독에서 충돌 양성이 한 번이라도 나온 고유 `base_path` 문자열은 JabRef 20개, Jenkins 16개, Spring Boot 7개, Card Forge·Quarkus 각 0개였다. 저장소를 구분한 경로는 총 43개다. 파일명을 바꾸면 별도 경로가 되며 여러 병합에서 같은 경로에 양성이 나와도 한 번만 센다. 연구 폴더에서 `python verify_license_rows.py --parquet-dir <재현-Parquet-폴더> --jar <전처리기-JAR> --java <JDK17-java>`로 다시 검사할 수 있다. [재현 스크립트](../../research/repository-audit/verify_license_rows.py)

### 380행의 과거 파일 고지 재검산

Ubuntu 실행 `44549292132`에 보존된 15개 컬럼의 논리 해시와 일치하는 재현 Parquet 5개를 읽었다. 380행 각각의 공통 조상 커밋에서 기록된 경로를 열어 Git blob 식별자와 원문 바이트를 확인했다. 모두 같은 행의 `base_blob_sha` 및 UTF-8로 인코딩한 `base_code`와 일치했다. 소스 첫 6,000자의 주석에서 아래 고지 문구를 셌다. 같은 경로가 여러 병합에 나타나면 각 행에 한 번씩 포함된다. [저장소별 집계와 원본 파일 식별자](../../research/repository-audit/evidence/validation/pilot-notices.json)

| 저장소 | 식별한 고지 | 해당 행 / 전체 행 | 해당 양성 행 / 전체 양성 행 |
| --- | --- | ---: | ---: |
| JabRef | GPL-2.0-or-later | 161 / 195 | 20 / 26 |
| Jenkins | MIT | 140 / 148 | 20 / 21 |
| Spring Boot | Apache-2.0 | 27 / 27 | 7 / 7 |
| Card Forge | GPL-3.0-or-later | 1 / 1 | 양성 없음 |
| Quarkus | LGPL-2.1-or-later | 1 / 9 | 양성 없음 |
| Quarkus | Apache-2.0 | 1 / 9 | 양성 없음 |

JabRef에서 GPL 고지를 포함한 양성 20행의 경로는 17개다. 전체 양성 경로는 20개다. Quarkus의 LGPL 고지는 병합 `43dc7dc7`의 `DataSourceProducer.java`에서 확인했고, 헤더가 2.1 및 이후 버전을 명시한다. 검사한 문구와 일치하지 않은 JabRef 34행, Jenkins 8행, Quarkus 7행은 당시 상위 디렉터리 고지와 별도 저작권 표시 등을 추가로 확인해야 한다. [Quarkus 과거 파일](https://github.com/quarkusio/quarkus/blob/ff404300a4ca9ef034af81f70d6003b1029ca617/agroal/runtime/src/main/java/org/jboss/shamrock/agroal/runtime/DataSourceProducer.java)

팀은 내부 추출·모델 학습에 포함할 행의 기준을 정하고, 외부에 Java 원문을 포함한 Parquet를 제공할 경우 파일별 출처·해당 시점 고지·포함 범위를 따로 검토한다. 공개할 산출물이 통계표인지 모델 가중치인지도 기록한다. 이 집계에서 판정한 것은 헤더의 문구이며, 학습 또는 외부 배포의 법률 적합성은 미판정이다.

아래 명령은 저장소 루트에서 재현 Parquet와 각 파일럿의 로컬 Git 객체를 사용한다. `DATASETS`, `JAR`와 다섯 Git 경로를 실제 입력으로 바꾼다. Python 표준 라이브러리, Git, JDK 17로 실행했다. [검산 스크립트](../../research/repository-audit/verify_pilot_notices.py)

```bash
python research/repository-audit/verify_pilot_notices.py --parquet-dir DATASETS --jar JAR \
  --git-dir Card-Forge/forge FORGE_GIT --git-dir JabRef/jabref JABREF_GIT \
  --git-dir jenkinsci/jenkins JENKINS_GIT --git-dir quarkusio/quarkus QUARKUS_GIT \
  --git-dir spring-projects/spring-boot SPRING_GIT
```

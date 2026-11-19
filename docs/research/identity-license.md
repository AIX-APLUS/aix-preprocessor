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

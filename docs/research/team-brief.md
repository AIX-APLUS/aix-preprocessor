팀에서 제안한 Java 저장소 5곳의 조사 결과를 공유드립니다. 각 저장소의 고정된 과거 시점까지 두 브랜치가 함께 고친 파일을 다시 합쳐 보니, 총 380건 중 충돌 54건(14.21%), 비충돌 326건(85.79%)이었습니다. 기존 팀 PR의 JabRef 수치는 같은 입력인지 확인되지 않아 별도로 뒀습니다.

저장소별 결과입니다. 괄호 안은 충돌 / 비충돌 건수입니다.
• JabRef 195건 (26 / 169)
• Jenkins 148건 (21 / 127)
• Spring Boot 27건 (7 / 20)
• Quarkus 9건 (0 / 9)
• Card Forge 1건 (0 / 1)

다음 수집 실험은 JabRef와 Jenkins를 우선 제안합니다. JabRef의 양성 26건은 서로 다른 병합 16개에서 나왔고, Jenkins에서는 13개 병합에서 양성 21건이 나왔습니다. 두 프로젝트의 코드를 함께 쓰면 참고문헌 관리와 CI 서버라는 서로 다른 개발 환경을 비교할 수 있습니다. 조사 끝점이 2011~2018년으로 달라, 같은 시대·같은 수의 병합을 먼저 비교한 뒤 학습 대상을 확정하면 좋겠습니다. Spring Boot는 외부 평가 후보이고, Quarkus와 Card Forge는 우선 성능 시험 후보입니다.

신규 후보 중 Jackson Databind는 검사한 병합 11개에서 파일 충돌 3건이 나왔는데, 모두 버전 브랜치를 합친 경우였습니다. 다른 후보는 0~6개 병합만 검사해 우열을 정하기 이릅니다. Mindustry·OsmAnd에서도 충돌이 있었고, H2·Cassandra·JGit은 여러 시기에 병합이 관찰됐습니다. Mockito·GraphHopper·JGraphT·Kafka는 조사 구간에 병합이 드물었습니다. 신규 10곳의 실제 학습 행 수는 아직 미측정입니다.

팀에서 먼저 확인할 사항은 원문 사용 범위와 평가 방법입니다. JabRef 195행 중 161행(양성 26행 중 20행)에 과거 GPL 고지가 있었습니다. 또 이번 파일럿의 테스트 56행 중 54행, 테스트 양성 8행 중 7행이 훈련과 같은 병합에서 나왔습니다. 팀의 실제 학습 데이터와 성능에 미치는 영향은 별도 검증이 필요합니다. 같은 병합을 묶어서 평가하고, 학습 전에 테스트 전용 저장소도 정하면 좋겠습니다.

상세 보고서
https://github.com/AIX-APLUS/aix-preprocessor/blob/research/dataset-repository-audit/docs/research/repository-suitability.md

실측 원자료
https://github.com/AIX-APLUS/aix-preprocessor/actions/runs/44549292132

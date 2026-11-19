팀에서 제안한 Java 저장소 5곳의 조사 결과를 공유드립니다. 각 저장소의 고정된 과거 시점까지 두 브랜치가 함께 고친 파일을 다시 합쳐 보니, 총 380건 중 충돌 54건(14.21%), 비충돌 326건(85.79%)이었습니다. 기존 팀 PR의 JabRef 수치는 같은 입력인지 확인되지 않아 별도로 뒀습니다.

저장소별 결과입니다. 괄호 안은 충돌 / 비충돌 건수입니다.
• JabRef 195건 (26 / 169)
• Jenkins 148건 (21 / 127)
• Spring Boot 27건 (7 / 20)
• Quarkus 9건 (0 / 9)
• Card Forge 1건 (0 / 1)

전체 추출은 JabRef부터, 그다음은 Jenkins를 추천합니다. JabRef의 충돌 26건은 서로 다른 병합 16개와 파일 경로 20개에서 나왔습니다. 참고문헌 관리 도구인 JabRef에 CI 서버인 Jenkins를 더하면 서로 다른 분야의 코드로 학습할 수 있습니다. Spring Boot는 표본을 늘려 외부 평가용으로 남기고, 이번 구간에서 충돌이 없었던 Quarkus와 Card Forge는 우선 성능 시험에 쓰는 편이 좋겠습니다.

추가 후보 10곳 중 다음 파일럿은 Jackson Databind를 추천합니다. 파일 검사에서 서로 다른 병합 3개의 충돌을 확인했습니다. Mindustry·OsmAnd는 각각 병합 1개에서 충돌이 나왔고, Cassandra·H2·JGit은 병합 이력이 꾸준했습니다. Mockito·GraphHopper·JGraphT·Kafka는 조사 구간에서 두 부모 병합이 드물었습니다. 신규 후보의 실제 학습 행 수는 미측정이라 기존 추천보다 낫다고 판단하기는 이릅니다.

팀에서 먼저 정할 건 두 가지입니다. JabRef 양성 사례에 과거 GPL 코드가 포함돼 있어 원문 데이터의 사용·공유 범위를 확인해야 합니다. 또 현재 테스트 56건 중 54건은 훈련과 같은 병합에서 나왔습니다. 모델이 처음 보는 프로젝트에서도 맞히는지 평가하려면 학습 전에 테스트 전용 저장소를 정하면 좋겠습니다. 위 충돌률은 조사한 구간에만 해당합니다.

상세 보고서
https://github.com/AIX-APLUS/aix-preprocessor/blob/research/dataset-repository-audit/docs/research/repository-suitability.md

실측 원자료
https://github.com/AIX-APLUS/aix-preprocessor/actions/runs/44549292132

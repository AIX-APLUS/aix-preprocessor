### Windows 로컬 실행기 진단

2026-11-19 최신 `main` `06e755ebabed1707a3413ec99ffa2511b046c543`의 생산 Java 소스와 `build.gradle`에 작업 사본 차이가 없음을 확인했다. Oracle JDK 17.0.12의 `javac --release 17 -encoding UTF-8`으로 전체 생산 클래스를 컴파일했다. 클래스패스에는 기존 Sprint 0 fat JAR의 오프라인 의존성을 사용했고, 실행 시 새로 컴파일한 클래스를 먼저 놓았다. 이는 오프라인 소스 컴파일 검증이며 Gradle 패키징 검증과 구별한다.

* `java -cp CLASSES;DEPENDENCIES io.aix.preprocessor.Main --help`에서 네 명령이 표시됐다. 이전 Sprint 0 fixture에 `stats`를 실행해 4행, 양성 2행, 종료 코드 0을 확인했다. 이는 후보 저장소의 수치에 포함하지 않았다.
* 같은 바이너리로 이미 보유한 완전한 Git 저장소에 `extract PATH --threads 1 --repo-id research/local-control --output NEW_PATH`를 실행했다. Git for Windows의 로컬 임시 미러 생성 단계에서 `sh.exe: fatal error - NtCreateDirectoryObject(...) 0xC0000022`, `java.io.IOException: git clone failed (128)`가 발생했다. Java는 종료 코드 1을 반환했고 새 Parquet와 임시 디렉터리가 남지 않았다. 오류 위치는 `Main.java:94`다. [추출 진입점](https://github.com/AIX-APLUS/aix-preprocessor/blob/06e755ebabed1707a3413ec99ffa2511b046c543/src/main/java/io/aix/preprocessor/Main.java#L84-L101)
* 같은 로컬 소스에 `git clone --mirror --shared -- SOURCE NEW_MIRROR`를 독립 실행했을 때 시스템 Git 2.55.0.windows.5와 GitHub Desktop의 Git 2.56.1.windows.1이 각각 같은 오류와 코드 128을 냈다. Windows 로컬 셸에서 GitHub REST 엔드포인트 직접 접속은 DNS 오류로 끝났다. 이 환경에서의 실패는 후보 저장소의 처리 비용·코드 품질·충돌 발생률에 대한 증거가 아니다.
* 같은 셸에 노출된 WSL은 `wsl --list --quiet`에서 `Wsl/E_ACCESSDENIED`를 반환했다. Docker Desktop Linux Engine의 로컬 파이프도 열리지 않아 이 두 경로로 Linux 런너를 사용할 수 없었다.

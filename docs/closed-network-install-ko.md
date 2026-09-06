# 폐쇄망 설치 및 이관 가이드

## 1. 원칙과 범위

이 가이드는 Cline이 이미 설치된 폐쇄망 Linux PC에 RAN Wiki를 배치하는 절차다. 외부 OpenAI/Anthropic API, 결제 계정, 로컬 LLM은 사용하지 않는다. 네트워크 접근은 폐쇄망에서 허용된 3GPP 저장소와 Tailscale 또는 내부 단말 접속으로 제한한다.

RAN3/RAN4는 외부 환경에서 미리 다운로드하지 않는다. 폐쇄망에 들어간 뒤 실제 내부 저장소 구조를 조사하고 선택한 회의 범위만 활성화한다.

## 2. 권장 이관 방식

폐쇄망에서 PyPI/Docker Hub를 사용할 수 없다면 연결 가능한 준비 PC에서 이미지를 빌드한 후 파일로 이관한다.

준비 PC:

```bash
cd /home/molkey/3gpp_meeting_agent
docker compose build ran2wiki-web ran2wiki-mcp ran2wiki-update
docker image ls | grep 3gpp_meeting_agent
```

실제 image 이름을 확인한 후 각각 `docker save`로 저장한다. 예:

```bash
docker save -o ranwiki-images.tar \
  3gpp_meeting_agent-ran2wiki-web:latest \
  3gpp_meeting_agent-ran2wiki-mcp:latest \
  3gpp_meeting_agent-ran2wiki-update:latest
```

프로젝트 소스, `.cline`, 설정 예시와 필요한 기존 `data`를 승인된 매체로 복사한다. `.env`와 자격증명은 복사 패키지에 포함하지 말고 폐쇄망에서 별도로 생성한다.

폐쇄망 PC:

```bash
docker load -i ranwiki-images.tar
cd <이관된-project-root>
cp config.example.yaml config.yaml
cp .env.example .env
```

## 3. 설정

`.env`에는 API 키가 필요 없다. Tailscale 주소를 사용할 경우:

```bash
tailscale ip -4
```

출력된 주소를 `.env`에 넣는다.

```dotenv
TAILSCALE_BIND_ADDRESS=<tailscale-ipv4>
RAN2WIKI_WEB_PORT=3000
```

`config.yaml`에서 데이터 위치와 RAN2 repository를 확인한다. 인증이 필요한 내부 저장소라면 자격증명을 코드나 Git에 기록하지 말고 폐쇄망의 승인된 환경변수/secret 방식을 사용하도록 client adapter를 확장한다.

## 4. 데이터 디렉터리와 권한

```bash
mkdir -p data/raw data/extracted data/db data/db/backups
```

Docker를 실행하는 사용자와 컨테이너가 `data`에 쓸 수 있어야 한다. 웹 컨테이너는 compose 설정상 데이터를 read-only로 사용한다.

기존 DB를 이관했다면 시작 전에 백업한다.

```bash
cp data/db/ran2wiki.db data/db/backups/ran2wiki-before-closed-network.db
```

DB가 WAL 모드에서 실행 중일 때 단순 복사를 하지 않는다. 모든 서비스를 정지한 상태에서 복사하거나 SQLite online backup을 사용한다.

## 5. 최초 실행

이미지를 불러온 환경에서는 다시 빌드하지 않고 시작한다.

```bash
docker compose up -d --no-build ran2wiki-web ran2wiki-mcp
docker compose ps
```

웹 확인:

```bash
curl -f http://<tailscale-ip>:3000/healthz
```

태블릿에서는 다음 주소를 연다.

```text
http://molkey-ai-server:3000
```

MagicDNS를 사용하지 않으면 Tailscale IPv4 주소를 사용한다.

## 6. Cline 스킬 사용

Cline에서 `.cline`, `src`, `data`, `config.yaml`, `ranwiki`가 들어 있는 프로젝트 루트를 workspace로 연다. Cline은 `.cline/skills/ranwiki/SKILL.md`를 읽고 로컬 명령을 사용한다.

```bash
chmod +x ranwiki
./ranwiki status --json
./ranwiki audit --group RAN2 --json
```

호스트 Python dependency가 준비되지 않은 환경에서는 임의로 system Python을 변경하지 않는다. Docker 이미지 안에서 실행하거나 승인된 offline wheelhouse/venv를 준비한다. Debian/Ubuntu의 PEP 668 보호를 `--break-system-packages`로 우회하지 않는다.

컨테이너를 통한 CLI 예:

```bash
docker compose run --rm --no-deps ran2wiki-update ranwiki status --json
```

## 7. RAN2 초기화 및 업데이트

폐쇄망 repository 접속을 확인한 후:

```bash
docker compose --profile jobs up -d --no-build ran2wiki-update
docker compose logs -f ran2wiki-update
```

완료 후:

```bash
./ranwiki status --json
./ranwiki audit --group RAN2 --json
./ranwiki search "UE capability" --group RAN2 --scope ALL --json
```

동일 update를 다시 실행했을 때 대부분 `unchanged`가 되어야 한다.

## 8. 폐쇄망에서 RAN3/RAN4 확장

현재 설정의 RAN3/RAN4는 `enabled: false`, `base_url: null`이다. 단순히 추정한 URL을 넣지 않는다.

폐쇄망에서 그룹별로 다음 순서를 지킨다.

1. 실제 repository root와 meeting directory 이름을 읽기 전용으로 조사한다.
2. 최근 대표 회의에서 Docs/Inbox/Chair Notes/TDoc list/agenda/report 구조를 기록한다.
3. 실제 R3/R4 TDoc package와 spreadsheet fixture를 소량 확보한다.
4. `groups` adapter와 discovery/parser 규칙을 수정한다.
5. 인터넷이 필요 없는 fixture 테스트를 추가한다.
6. DB online backup을 만든다.
7. `config.yaml`의 해당 repository와 선택한 시작/종료 회의를 설정한다.
8. 해당 그룹만 활성화하고 제한된 회의 범위로 시험 update한다.
9. `audit --group RAN3` 또는 `RAN4`와 대표 검색을 수행한다.
10. RAN2 웹 검색과 테스트가 그대로 동작하는지 회귀 검증한다.

RAN3/RAN4는 동일 DB를 사용한다. 별도 애플리케이션이나 독립 RAN2 복제 DB를 만들지 않는다.

## 9. 보안 확인표

- `.env`, token, credential을 Git 또는 이관 문서에 포함하지 않는다.
- MCP 8000 포트를 public host port로 publish하지 않는다.
- 웹 포트는 Tailscale 주소 또는 내부 인터페이스에만 bind한다.
- public router port forwarding을 만들지 않는다.
- 원본 `data/raw`를 삭제하지 않는다.
- update는 사용자가 명시적으로 요청했을 때 실행한다.
- 외부 LLM API와 로컬 대형 모델을 구성하지 않는다.

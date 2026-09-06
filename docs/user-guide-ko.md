# RAN Wiki 사용자 설명서

## 1. 용도

RAN Wiki는 로컬에 저장된 3GPP RAN 회의 자료를 검색하고 검증하는 지식 베이스다. 현재 활성 그룹은 RAN2이며 Rel-20 및 6G 자료를 대상으로 한다. 검색, 파싱, SQLite FTS5, 웹 UI와 MCP는 서버 안에서 동작한다. 유료 LLM API나 로컬 LLM은 필요하지 않다.

다음 세 가지 방법으로 같은 데이터베이스를 사용한다.

- 태블릿: `http://molkey-ai-server:3000`
- Cline: 프로젝트 루트에서 `./ranwiki ... --json`
- MCP 클라이언트: 내부 `ran2wiki-mcp` 서비스

## 2. 빠른 상태 확인

프로젝트 루트에서 실행한다.

```bash
cd /home/molkey/3gpp_meeting_agent
./ranwiki status --json
./ranwiki audit --group RAN2 --json
```

`status`는 회의/TDoc 수, 최신 회의와 업데이트 상태를 보여준다. `audit`은 DB 무결성, 추출 상태, TDoc 본문 연결률, Chair Notes 누락과 outcome 통계를 보여준다.

## 3. 검색

기본 검색:

```bash
./ranwiki search "dynamic UE capability" --group RAN2 --scope ALL --limit 20 --json
```

필터 예시:

```bash
./ranwiki search "UE capability" --group RAN2 --release 20 --scope ALL --json
./ranwiki search "mobility" --group RAN2 --scope 6G --from-meeting 131 --to-meeting 135 --json
./ranwiki search "dynamic UE capability" --group RAN2 --company Samsung --json
./ranwiki search "measurement" --group RAN2 --meeting 135 --agenda 9.4 --json
```

주요 결과 필드는 다음과 같다.

- `evidence_type`: `CHAIR_NOTES` 또는 `TDOC`
- `event_type`: `PROPOSAL`, `DISCUSSION`, outcome 종류 또는 일반 문서
- `group`, `meeting`, `meeting_date`, `agenda`
- `tdoc_id`, `title`, `source`, `document_status`
- `snippet`, `section`, `relevance`
- `source_file`, `source_url`, `local_source_path`

FTS의 `relevance`는 BM25 점수다. 절대값 자체보다 같은 결과 목록 안의 순서를 이용한다.

## 4. 회의와 Chair Notes 조회

```bash
./ranwiki meeting 135 --group RAN2 --json
./ranwiki chair-notes 135 --group RAN2 --json
./ranwiki chair-notes 135 --group RAN2 --agenda 9.2.1 --limit 500 --json
```

회의 조회는 agenda, TDoc 수, Chair Notes 존재 여부와 outcome 요약을 반환한다. Working Group의 결론을 판단할 때는 TDoc보다 Chair Notes를 우선한다.

## 5. TDoc 조회

기본 조회는 Cline context가 과도해지지 않도록 본문을 제한한다.

```bash
./ranwiki tdoc R2-2509073 --group RAN2 --json
./ranwiki tdoc R2-2509073 --group RAN2 --max-chars 12000 --json
./ranwiki tdoc R2-2509073 --group RAN2 --full --json
```

`--full`은 필요한 경우에만 사용한다. `chair_notes_references`가 있으면 해당 TDoc이 회의 기록에서 언급된 위치를 함께 확인한다.

## 6. 합의와 FFS 조회

```bash
./ranwiki outcomes "UE capability" --group RAN2 \
  --types AGREEMENT,CONCLUSION,FFS --limit 30 --json
```

종류별 조회:

```bash
./ranwiki outcomes "mobility" --group RAN2 --types AGREEMENT,CONCLUSION --json
./ranwiki outcomes "mobility" --group RAN2 --types FFS --json
```

TDoc에 쓰인 `Proposal` 문구는 RAN2 합의가 아니다. `AGREEMENT`와 `CONCLUSION`은 Chair Notes에서 해당 outcome으로 명시적으로 파싱된 경우에만 그룹 결정 근거로 사용한다.

## 7. 주제 이력 추적

```bash
./ranwiki trace "dynamic UE capability" --group RAN2 --scope ALL --json
./ranwiki trace "6G mobility" --group RAN2 --scope 6G --json
```

결과는 회의 순서로 정렬되며 회의별 Chair Notes evidence, TDocs와 명시적 outcomes를 분리한다.

## 8. 업데이트

사용자가 새 회의 또는 갱신을 명시적으로 요청했을 때 실행한다.

```bash
./ranwiki status --json
./ranwiki update --group RAN2 --json
./ranwiki audit --group RAN2 --json
```

특정 회의만 갱신할 수도 있다.

```bash
./ranwiki update --group RAN2 --meeting 135 --json
```

업데이트는 원격 metadata와 로컬 manifest를 비교해 새 파일과 변경 파일만 받는다. 이미 실행 중인 updater가 있으면 두 번째 실행을 거부한다. 부분적인 FTP 실패가 발생해도 완전히 다운로드된 로컬 파일은 추출·인덱싱한다.

## 9. 서비스 운영

```bash
docker compose ps
docker compose logs --tail 100 ran2wiki-web
docker compose logs --tail 100 ran2wiki-mcp
docker compose logs --tail 100 ran2wiki-update
```

웹 및 MCP 시작:

```bash
docker compose up -d ran2wiki-web ran2wiki-mcp
```

장시간 업데이트 작업:

```bash
docker compose --profile jobs up -d --build ran2wiki-update
```

업데이트 컨테이너가 종료된 뒤 결과를 확인한다.

```bash
docker compose ps -a
docker compose logs --tail 200 ran2wiki-update
./ranwiki audit --group RAN2 --json
```

## 10. 데이터 위치

- 원본: `data/raw/<meeting>/`
- 추출 JSON: `data/extracted/<meeting>/`
- SQLite: `data/db/ran2wiki.db`
- DB 백업: `data/db/backups/`

원본 파일은 삭제하거나 덮어쓰지 않는다. 변경된 원본의 이전 버전도 보존한다.

## 11. 문제 해결

웹 UI가 열리지 않으면:

```bash
tailscale status
tailscale ip -4
docker compose ps
curl -f http://127.0.0.1:3000/healthz
```

`molkey-ai-server` 이름이 해석되지 않으면 태블릿의 Tailscale 연결과 MagicDNS를 확인하고 `http://<tailscale-ip>:3000`을 사용한다.

업데이트가 오래 걸리면 로그에서 파일 수가 증가하는지 확인한다. 3GPP 저장소의 timeout/522는 재시도될 수 있다. 실행 중인 컨테이너를 임의로 중복 실행하지 않는다.

검색 결과가 없으면 범위를 `ALL`로 넓히고 영어 기술 용어로 다시 검색한다. 그래도 결과가 없으면 현재 인덱스에 충분한 근거가 없다고 판단한다.

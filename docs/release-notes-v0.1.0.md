# RAN Wiki v0.1.0

로컬 SQLite/FTS5 기반 3GPP RAN2 Rel-20/6G 지식 베이스와 Cline integration의 첫 배포판이다.

## 주요 기능

- RAN2 meeting, agenda, Chair Notes, TDoc list와 TDoc 증분 수집
- DOCX, PPTX, XLSX, PDF, TXT, ZIP의 결정론적 추출
- Chair Notes의 AGREEMENT, CONCLUSION, FFS, POSTPONED, NOTED 구분
- SQLite FTS5/BM25 검색과 meeting 기반 topic trace
- provenance를 포함한 JSON CLI와 로컬 MCP
- Tailscale 전용 웹 UI
- `.cline/skills/ranwiki/SKILL.md` 기반 Cline workflow
- 유료 LLM API, 로컬 LLM 및 vector database 불필요
- RAN3/RAN4 폐쇄망 확장을 위한 비활성 group adapter/configuration

## 설치

ZIP을 풀고 다음 문서를 먼저 읽는다.

- `docs/user-guide-ko.md`
- `docs/closed-network-install-ko.md`
- `docs/cline-prompt-guide-ko.md`

이 source ZIP에는 3GPP 원본 자료, SQLite DB, `.env`, API key, credential, Python dependency cache와 Docker image가 포함되지 않는다.

## 검증

- offline pytest: 39 passed
- SQLite FTS5 및 schema migration 테스트
- Cline JSON command workflow 테스트
- 기존 Tailscale 웹 UI 회귀 확인

## 주의

RAN3/RAN4는 이 배포판에서 기본 비활성 상태다. 폐쇄망에서 실제 repository 구조를 조사하고 fixture test를 추가한 뒤 활성화해야 한다.

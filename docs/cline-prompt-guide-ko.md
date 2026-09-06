# Cline 프롬프트 가이드와 예시

## 1. 기본 사용법

Cline에서 이 프로젝트 루트를 연 뒤 자연어로 질문한다. 스킬은 먼저 로컬 `ranwiki` JSON 도구를 사용하고 그 근거만으로 답하도록 구성돼 있다.

좋은 질문에는 다음 요소 중 필요한 것을 넣는다.

- 그룹: RAN2
- 범위: Rel-20, 6G 또는 전체
- 주제: 가능하면 영어 기술 용어 병기
- 기간: 특정 회의 또는 회의 범위
- 원하는 evidence: 제안, 토론, 합의, 결론, FFS
- 원하는 비교: 회사별, 회의별, revision별
- 출력 형태: 시간순, 표, 요약과 근거 목록

## 2. 기본 연구 프롬프트

```text
RAN2의 Rel-20 UE capability 논의를 조사해줘.
먼저 로컬 ranwiki를 검색하고, 중요한 주장마다 meeting, agenda, TDoc ID와
Chair Notes 근거를 표시해줘. 제안과 실제 합의를 분리하고 근거가 없으면 추측하지 마.
```

```text
6G mobility 논의를 처음 등장한 회의부터 현재 로컬 DB의 최신 회의까지 시간순으로 정리해줘.
trace를 사용하고 각 회의에서 proposal, discussion, agreement, conclusion, FFS를 구분해줘.
```

## 3. 회사별 제안 비교

```text
dynamic UE capability에 대해 Samsung과 Ericsson이 제출한 제안을 각각 찾아 비교해줘.
회사 필터로 검색한 뒤 중요한 TDoc을 조회하고, Chair Notes에서 수용·보류·FFS 여부를 별도로 확인해줘.
회사 제안을 RAN2 합의로 표현하지 마.
```

권장 결과 구조:

```text
1. Samsung 제안
2. Ericsson 제안
3. 공통점과 차이점
4. Chair Notes에 기록된 실제 WG outcome
5. 남은 FFS
6. 근거 목록
```

## 4. 최종 합의 확인

```text
UE capability 주제에서 RAN2가 실제로 합의한 내용과 아직 FFS인 내용을 분리해줘.
outcomes의 AGREEMENT, CONCLUSION, FFS와 Chair Notes만 합의 판단 근거로 사용해.
TDoc의 proposal 문구만으로 합의했다고 결론내리지 마.
```

```text
이 주제에서 '최종 합의'라고 부를 수 있는 근거가 충분한지 검증해줘.
후속 회의에서 변경되거나 다시 FFS가 된 내용도 추적하고, 불충분하면 불충분하다고 말해줘.
```

## 5. 특정 TDoc 검토

```text
R2-xxxxxxx를 로컬 DB에서 조회해줘.
제안 내용, source/company, meeting, agenda, revision 관계와 Chair Notes reference를 정리해줘.
기본 excerpt가 부족할 때만 full text를 요청해.
```

실제 `R2-xxxxxxx`는 먼저 검색해서 얻은 번호로 교체한다.

## 6. 회의 리뷰

```text
RAN2#135에서 6G 관련 agenda와 주요 discussion을 정리해줘.
meeting과 chair-notes 명령을 사용하고 AGREEMENT/FFS를 별도 표로 보여줘.
```

```text
RAN2#134와 #135 사이에서 mobility 논의가 어떻게 바뀌었는지 비교해줘.
각 변화에 Chair Notes locator 또는 TDoc provenance를 붙여줘.
```

## 7. 업데이트 요청

```text
새 RAN2 회의가 끝났으니 로컬 지식 베이스를 업데이트해줘.
업데이트 전 status, update, 업데이트 후 status와 audit을 실행하고
새 회의, 다운로드/변경 파일, 추출 실패, Chair Notes 존재 여부와 최신 회의를 보고해줘.
```

이미 updater가 실행 중이면 Cline은 두 번째 updater를 시작하지 않고 현재 run 정보를 보고해야 한다.

## 8. 데이터 품질 점검

```text
현재 RAN2 데이터베이스 품질을 점검해줘.
ranwiki audit 결과를 바탕으로 pending/failed extraction, TDoc 본문 연결률,
Chair Notes 누락 회의, FTS 행 수와 DB 무결성을 설명해줘.
```

```text
검색 결과가 제목 metadata에만 근거하는지 실제 TDoc 본문까지 연결됐는지 확인해줘.
본문이 없으면 그 한계를 답변에 명시해줘.
```

## 9. RAN3/RAN4 폐쇄망 확장 프롬프트

폐쇄망에서만 다음과 같이 요청한다.

```text
이제 RAN3 지원을 추가해줘.
먼저 현재 shared DB와 group adapter를 확인하고, 접근 가능한 실제 내부 3GPP repository의
meeting/Docs/Inbox/Chair Notes/TDoc list 구조를 조사해 문서화해줘.
추정 URL을 사용하지 말고 대표 fixture와 offline test를 만든 다음,
선택한 회의 범위만 활성화해. 기존 RAN2 웹 UI와 검색을 회귀 검증해줘.
```

```text
RAN4도 같은 shared database에 추가해줘. RAN3/RAN2와 구조가 같다고 가정하지 말고
실제 저장소와 R4 TDoc 형식을 먼저 검사해. 데이터베이스를 변경하기 전에 online backup을 만들어.
```

## 10. 피해야 할 프롬프트

다음 요청은 근거 없는 답을 만들기 쉽다.

```text
UE capability 최종 결론 알려줘.
```

다음처럼 바꾸는 것이 좋다.

```text
로컬 RAN2 Chair Notes에서 UE capability 관련 AGREEMENT, CONCLUSION, FFS를 검색하고
회의 순서대로 비교한 뒤, 최종 결론이라고 판단할 근거가 충분한지 설명해줘.
```

또한 다음을 피한다.

- 출처 없이 모델 기억만으로 답하도록 요청
- proposal과 agreement를 섞어 요약하도록 요청
- 전체 대형 문서를 처음부터 모두 context에 넣도록 요청
- RAN3/RAN4 repository 경로를 추정하도록 요청
- update 요청 없이 네트워크에 접속하도록 요청

## 11. 권장 답변 형식

```text
요약

회의별 전개
- Meeting / agenda
- 제안 또는 논의
- 명시적 outcome
- 남은 FFS

회사별 입장

판단과 근거 한계

근거
- [RAN2, meeting, agenda, TDoc ID, company, source file, locator]
```

중요한 주장은 반드시 로컬 retrieval 결과로 검증할 수 있어야 한다. 로컬 데이터가 충분하지 않으면 “현재 인덱스에서는 충분한 근거를 찾지 못했다”고 답한다.

# 합성 입력으로 검증하는 오프라인 설계 코어

이 예제는 **실제 Codex 작업, 계정, 프로젝트, 사용자 승인, 플러그인 상태를 읽지 않는다.** 네트워크, 메시지 전송, 예약 실행, 작업 중단, 외부 명령 실행, 상태 파일 저장 기능이 없다. 모든 식별자와 이벤트는 가상 데이터다.

```sh
python3 scripts/offline_core.py demo
python3 -m unittest discover -s tests -v
```

`demo`의 `SYNTHETIC_HOST_ATTESTATION` 및 hard-off capability 값은 **가상 테스트 입력**이다. 현재 Codex가 해당 수명주기 보장을 제공한다는 증거가 아니다. `plugin_enabled=True` 같은 로컬 플래그는 신뢰 근거가 아니며, `UNVERIFIED_LOCAL` provenance에서는 `DENY`가 나온다. 모든 성공 결과는 `WOULD_ALLOW_SIMULATION_ONLY`, `production_authorized=false`다. 실제 실행기로 연결할 코드가 없다.

## 보고 구간 계약

`prepare_report(events, captured_until=..., now=..., timezone_name=..., last_delivered_cutoff=..., coverage=...)`는 보고서를 구성할 순수 함수다.

- 최초 보고는 `captured_until`이 속한 지정 시간대의 날짜 00:00부터 시작한다. 그 이후에는 마지막으로 완전히 전달된 보고의 cutoff부터 시작한다.
- 구간은 `[start, captured_until)`이다. 시작은 포함하고 끝은 제외한다. cutoff 이후 이벤트는 다음 보고 대상이다.
- 모든 datetime은 시간대가 있어야 한다. 미래 cutoff와 cutoff보다 뒤인 watermark는 오류다. DST가 있는 지역도 현지 날짜의 자정을 사용한다.
- 작업 생성일이 아닌 이벤트 발생 시각으로 고른다. 오래된 작업에서 새로 생긴 변경도 포함한다. `(host_id, thread_id, event_id)`와 내용이 같으면 한 번만 포함하며, 같은 키의 다른 내용은 데이터 오류로 처리한다. 서로 다른 host/작업의 같은 event ID는 각각 보존한다.
- `host_id`는 명시적으로 전달해야 한다. 생략 시 값 `synthetic-host`는 기존 예제의 합성 입력 호환을 위한 기본값이다. 실제 adapter는 실제 host 식별자를 전달하고, 지연 색인·늦게 도착한 이벤트를 처리할 수집 계약도 별도로 증명해야 한다. 이 코어는 과거 watermark 이전의 지연 이벤트를 자동으로 회수하지 않는다.
- 프로젝트가 없는 작업은 `project_id=None`으로 명시한다. 빈 문자열이나 wildcard로 다른 프로젝트 범위를 대체하지 않는다.
- `Coverage`는 선언한 source inventory의 수집 완결성이다. 모든 Codex 작업에 접근했다는 증명은 아니다. 숨겨진 작업, 보관 작업, 다른 host, 페이지 잘림과 권한 실패를 실제 collector가 판별해야 한다.

`commit_report_delivery(report, current_watermark=..., receipt=..., now=...)`는 저장할 다음 watermark 제안만 반환한다. 보고가 완전하고, 잘림/오류 없이 모든 요청 소스를 읽었으며, 정확한 report ID의 전달이 확인됐을 때만 전진한다. 부분/실패/불명 전달과 stale receipt는 이전 watermark를 유지한다. 성공 전달이나 동시 실행에 대한 실제 증명·원자적 저장은 구현하지 않았다.

## 개입 판정 계약

`evaluate(mandate, evidence, action, now=...)`는 `EligibilityDecision(decision, reasons, simulation_only=True, production_authorized=False)`를 반환한다.

`Mandate`는 frozen dataclass이며 scope는 host/프로젝트/작업의 정확한 조합으로 이루어진 `frozenset[Target]`이다. 프로젝트가 없는 작업은 `project_id=None`인 해당 작업을 따로 승인해야 한다. wildcard와 빈 scope를 금지한다. 사용자 승인, revision, 방향 version, 만료 시각, 허용 행동, 일일 횟수와 추정 비용 단위, 한 번의 비용 한도, cooldown을 모두 검사한다. 비용 단위는 추상 정수이며 실제 토큰 또는 API 요금 추정기가 아니다.

가상 `HostEvidence`에는 최신 플러그인 활성화, hard-off의 네 가지 능력, 유효한 mandate/revision/방향, 대상 일치, 단독 controller, worker와 목표 상태, 새로 발생한 의미 있는 근거, 같은 현지 날짜의 예산 사용량, 이전 개입 이력, action별 idempotency 상태가 필요하다. 다음 예약 취소, 실행 중 controller 취소, 플러그인이 소유한 worker 취소, 비활성 상태의 dispatch 차단이 모두 있어야 hard-off 조건이 만족된다. 실행 중 worker, 사람 답변 대기, 완료 또는 불명 목표, 새로운 근거가 없는 상황, 확인되지 않은 소유권, 오래되거나 미래인 관측, 예산 초과, cooldown, 전송 중/전송 완료/불명 idempotency는 모두 거절한다. `IDLE`만으로 완료된 작업을 재시작할 수 없다.

이 함수는 행동의 경제적 가치나 자유 텍스트 지시의 의미가 안전한지를 평가하지 않는다. 사용자 승인의 진위, 실제 lifecycle 보장, 예산 예약, lock/lease, 전송 직전 재검증, idempotency의 원자적 기록은 호스트 adapter의 별도 요구 사항이다. 합성 fixture 통과를 실제 활성화 또는 공개 배포 승인으로 해석하면 안 된다.

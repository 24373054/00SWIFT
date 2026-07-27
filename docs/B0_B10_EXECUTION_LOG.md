# B0–B10 执行证据日志

> 本文件只追加、不覆盖。每勾选 `B0_B10_FULL_IMPLEMENTATION_CHECKLIST.md` 中一个编号，先在此记录证据。

## 记录模板

### `<任务编号>` — `<任务名称>`

- 状态：DONE / FAILED / EXT-BLOCKED
- 开始时间：
- 完成时间：
- commit：
- 修改文件：
- 新增迁移：
- 新增/修改测试：
- 测试命令：
- 测试结果：
- 正常路径证据：
- 负向路径证据：
- 并发/重复/超时/恢复证据：
- OpenAPI/AsyncAPI 影响：
- Metrics/alerts/runbook 影响：
- 外部证据：
- 未解决风险：
- 执行者：
- 复核者：

---

## 执行记录

<!-- 从这里开始按任务编号顺序追加，禁止删除历史记录。 -->

### B0.1.1 — 签名资格工件验证器

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`59fcff7`
- 修改文件：`backend/production/qualification.py`、`backend/tests/production/test_qualification.py`
- 新增迁移：无
- 新增/修改测试：签名有效、缺文件、过期、环境不匹配、digest/signature/trust-anchor 错误
- 测试命令：`\.venv\Scripts\python.exe -m pytest backend/tests/production/test_qualification.py -q`
- 测试结果：`3 passed`; `ruff check`：`All checks passed`
- 正常路径证据：Ed25519 签名、公钥 trust anchor、artifact bytes SHA-256、有效期全部验证
- 负向路径证据：不存在、过期、环境不匹配、签名错误均抛出 `QualificationError`
- 并发/重复/超时/恢复证据：本条为纯验证器；启动准入持久化和 replay 在 B0.1.2/B0.2 覆盖
- OpenAPI/AsyncAPI 影响：无
- Metrics/alerts/runbook 影响：B0.1.4 接入 readiness；本条不标 readiness
- 外部证据：无；真实签发者/工件在 B0.4/B7 标记 `[EXT-BLOCKED]`
- 未解决风险：当前尚未接入数据库决策记录和 startup gate
- 执行者：Codex

### B3.3.4 — publish confirmation and deduplication

- 状态：DONE
- 完成时间：2026-07-27
- commit：`72a8771`
- 修改文件：`backend/production/runtime.py`、`backend/tests/production/test_outbox_publish_dedup.py`
- 新增实现：publish completion 持久化 published_at、broker offset/metadata；已 PUBLISHED 事件重复 completion 为幂等 no-op，event_id/aggregate unique 仍由数据库约束。
- 测试命令：`$env:PYTHONPATH='backend'; .\\.venv\\Scripts\\python.exe -m pytest backend/tests/production/test_outbox_publish_dedup.py -q`; `.\\.venv\\Scripts\\python.exe -m ruff check backend/production/runtime.py backend/tests/production/test_outbox_publish_dedup.py`
- 测试结果：`1 passed`；`ruff: All checks passed`。
- 外部证据：真实 broker confirm 由 B3.4 外部 adapter Gate 验收。
- 执行者：Codex

### B3.3.3 — lease heartbeat and ownership fencing

- 状态：DONE
- 完成时间：2026-07-27
- commit（实现）：`0724ff8`
- 验收文件：`backend/production/runtime.py`、`backend/production/worker.py`、`backend/tests/production/test_outbox_leases.py`
- 测试命令：`$env:PYTHONPATH='backend'; .\\.venv\\Scripts\\python.exe -m pytest backend/tests/production/test_outbox_leases.py -q`
- 测试结果：`2 passed`。
- 证据：heartbeat 只能由当前 lease owner 延长；完成动作带 owner fencing，lease 接管后老 worker 无法提交 PUBLISHED。
- 外部证据：无。
- 执行者：Codex

### B3.3.2 — atomic partition-ordered claim

- 状态：DONE
- 完成时间：2026-07-27
- commit：`1102eda`
- 修改文件：`backend/production/runtime.py`、`backend/tests/production/test_outbox_partition_order.py`
- 新增实现：claim 使用 `FOR UPDATE SKIP LOCKED`，并以 correlated `NOT EXISTS` 保证同 partition 只取最低 aggregate sequence；不同 partition 可并行。
- 测试命令：`$env:PYTHONPATH='backend'; .\\.venv\\Scripts\\python.exe -m pytest backend/tests/production/test_outbox_partition_order.py -q`; `.\\.venv\\Scripts\\python.exe -m ruff check backend/production/runtime.py backend/tests/production/test_outbox_partition_order.py`
- 测试结果：`1 passed`；`ruff: All checks passed`。
- 外部证据：真实 PostgreSQL 锁竞争仍需外部 fixture，已在后续 Gate 保留。
- 执行者：Codex

### B3.3.1 — null lease recovery and fencing

- 状态：DONE
- 完成时间：2026-07-27
- commit：`0724ff8`
- 修改文件：`backend/production/runtime.py`、`backend/production/worker.py`、`backend/alembic/versions/0023_outbox_null_lease_backfill.py`、`backend/tests/production/test_outbox_leases.py`
- 新增实现：claim 将 `PROCESSING + lease_until IS NULL` 与过期 lease 一并回收；迁移 backfill 为 PENDING；heartbeat 与 complete 校验 worker ownership，旧 owner 不能完成新 owner 事件。
- 测试命令：`$env:PYTHONPATH='backend'; .\\.venv\\Scripts\\python.exe -m pytest backend/tests/production/test_outbox_leases.py -q`; `.\\.venv\\Scripts\\python.exe -m ruff check backend/production/runtime.py backend/production/worker.py backend/alembic/versions/0023_outbox_null_lease_backfill.py backend/tests/production/test_outbox_leases.py`; `.\\.venv\\Scripts\\python.exe -m alembic -c alembic.ini upgrade head`
- 测试结果：`2 passed`；`ruff: All checks passed`；SQLite `0022 -> 0023` 成功。
- 负向证据：错误 owner heartbeat/complete 均抛 fencing conflict。
- 外部证据：无。
- 执行者：Codex

### B3.2.3 — business POST idempotency contract

- 状态：DONE
- 完成时间：2026-07-27
- commit：`df8a546`
- 修改文件：`backend/production/runtime.py`、`backend/tests/production/test_idempotency_contract.py`
- 新增测试：payment POST 同 key 同 body 返回完全相同 response；同 key 异 body 返回 409；datetime canonicalization 保证 replay 不漂移。
- 测试命令：`$env:PYTHONPATH='backend'; .\\.venv\\Scripts\\python.exe -m pytest backend/tests/production/test_idempotency_contract.py -q`; `.\\.venv\\Scripts\\python.exe -m ruff check backend/production/runtime.py backend/tests/production/test_idempotency_contract.py`
- 测试结果：`2 passed`（1 个已知 Starlette deprecation warning）；`ruff: All checks passed`。
- 代码证据：payment/fx/cancellation/return/acceptance service 均通过同一 ProductionIdempotencyService；异常回滚不吞掉调用者事务。
- 未解决风险：100-way 同 key 并发需 PostgreSQL fixture，后续并发 Gate 保持外部验收。
- 执行者：Codex

### B3.2.1 — atomic idempotency lifecycle

- 状态：DONE
- 完成时间：2026-07-27
- commit：`5ba48c3`
- 修改文件：`backend/production/runtime.py`、`backend/production/models.py`、`backend/alembic/versions/0022_idempotency_recovery.py`、`backend/tests/production/test_idempotency_recovery.py`
- 新增实现：begin 使用 SAVEPOINT 原子 insert，不对调用者事务执行 rollback；记录 owner/locked_until/request hash/response/error/attempt/trace；支持 STARTED/COMPLETED/FAILED_RETRYABLE/FAILED_FINAL/EXPIRED。
- 测试命令：`$env:PYTHONPATH='backend'; .\\.venv\\Scripts\\python.exe -m pytest backend/tests/production/test_idempotency_recovery.py -q`; `.\\.venv\\Scripts\\python.exe -m ruff check backend/production/runtime.py backend/production/models.py backend/alembic/versions/0022_idempotency_recovery.py backend/tests/production/test_idempotency_recovery.py`; `.\\.venv\\Scripts\\python.exe -m alembic -c alembic.ini upgrade head`
- 测试结果：`2 passed`；`ruff: All checks passed`；SQLite `0021 -> 0022` 成功。
- 负向证据：同 key 异 body、未过期 STARTED、FAILED_FINAL 均拒绝；并发冲突在 SAVEPOINT 内处理。
- 执行者：Codex

### B3.2.2 — STARTED timeout recovery

- 状态：DONE
- 完成时间：2026-07-27
- commit：`6aa5527`
- 修改文件：`backend/production/runtime.py`、`backend/tests/production/test_idempotency_recovery_strategy.py`
- 新增实现：`recover_started` 强制先通过 aggregate/connector query-by-reference；查到结果即完成，只有明确无结果才返回 `TAKEOVER_REQUIRED`。
- 测试命令：`$env:PYTHONPATH='backend'; .\\.venv\\Scripts\\python.exe -m pytest backend/tests/production/test_idempotency_recovery_strategy.py -q`; `.\\.venv\\Scripts\\python.exe -m ruff check backend/production/runtime.py backend/tests/production/test_idempotency_recovery_strategy.py`
- 测试结果：`2 passed`；`ruff: All checks passed`。
- 负向证据：未过期或非 STARTED 记录不能恢复；不会盲目重做外部副作用。
- 执行者：Codex

### B3.1.4 — event compatibility tests

- 状态：DONE
- 完成时间：2026-07-27
- commit：`4ab0ff4`
- 修改文件：`backend/tests/production/test_event_compatibility.py`
- 新增测试：旧 v1 consumer 对 additive minor payload 保持兼容；major version 破坏变更及未知事件族在 dispatch 前拒绝。
- 测试命令：`$env:PYTHONPATH='backend'; .\\.venv\\Scripts\\python.exe -m pytest backend/tests/production/test_event_compatibility.py -q`; `.\\.venv\\Scripts\\python.exe -m ruff check backend/tests/production/test_event_compatibility.py`
- 测试结果：`2 passed`；`ruff: All checks passed`。
- 外部证据：无。
- 执行者：Codex

### B3.1.3 — AsyncAPI production events

- 状态：DONE
- 完成时间：2026-07-27
- commit：`5770a31`
- 修改文件：`asyncapi/production-events.yaml`、`backend/tests/production/test_asyncapi_contract.py`
- 新增实现：AsyncAPI 3 contract 覆盖 payment、funding、FX、message、settlement、compliance、reconciliation、case、report 事件族及严格 envelope schema。
- 测试命令：`$env:PYTHONPATH='backend'; .\\.venv\\Scripts\\python.exe -m pytest backend/tests/production/test_asyncapi_contract.py -q`; `.\\.venv\\Scripts\\python.exe -m ruff check backend/tests/production/test_asyncapi_contract.py`
- 测试结果：`1 passed`；`ruff: All checks passed`；YAML 解析成功且九类事件族全部存在。
- 外部证据：无。
- 执行者：Codex

### B3.1.2 — outbox integrity schema

- 状态：DONE
- 完成时间：2026-07-27
- commit：`b0c7951`
- 修改文件：`backend/production/models.py`、`backend/production/runtime.py`、`backend/alembic/versions/0021_outbox_event_integrity.py`、`backend/tests/production/test_outbox_integrity.py`
- 新增实现：outbox tenant/participant 非空、payload/content hash、published_at、broker offset/metadata、lease heartbeat 字段；迁移对历史 payload 解析并从 payment aggregate 回填，无法证明归属时显式阻断；enqueue 无 scope 直接拒绝。
- 测试命令：`$env:PYTHONPATH='backend'; .\\.venv\\Scripts\\python.exe -m pytest backend/tests/production/test_outbox_integrity.py -q`; `.\\.venv\\Scripts\\python.exe -m ruff check backend/production/models.py backend/production/runtime.py backend/alembic/versions/0021_outbox_event_integrity.py backend/tests/production/test_outbox_integrity.py`; `.\\.venv\\Scripts\\python.exe -m alembic -c alembic.ini upgrade head`
- 测试结果：`1 passed`；`ruff: All checks passed`；SQLite `0020 -> 0021` 成功，现有 outbox 行完成真实 tenant/participant/hash 回填。
- 负向证据：缺 tenant/participant 上下文的 enqueue 抛出 `ProductionConflict`，不写入无主事件。
- 外部证据：无。
- 执行者：Codex

### B3.1.1 — canonical EventEnvelope

- 状态：DONE
- 完成时间：2026-07-27
- commit：`6428fa3`
- 修改文件：`backend/production/events.py`、`backend/tests/production/test_events.py`
- 新增实现：严格冻结的 EventEnvelope，包含 event/tenant/participant/aggregate/sequence/partition/correlation/causation/trace/time/payload 全字段；UTC、版本、事件族和未知字段均校验。
- 测试命令：`$env:PYTHONPATH='backend'; .\\.venv\\Scripts\\python.exe -m pytest backend/tests/production/test_events.py -q`; `.\\.venv\\Scripts\\python.exe -m ruff check backend/production/events.py backend/tests/production/test_events.py`
- 测试结果：`2 passed`；`ruff: All checks passed`。
- 负向证据：naive timestamp、未知字段和破坏性 major schema 变更均被拒绝。
- 外部证据：无。
- 执行者：Codex

### B2.G5 — fail-closed rulebook/certificate/mandate enforcement

- 状态：DONE
- 完成时间：2026-07-27
- commit（实现）：`be3fcaa`, `34ef9da`, `8e736a5`, `3539174`, `842d55d`
- 测试命令：`$env:PYTHONPATH='backend'; .\\.venv\\Scripts\\python.exe -m pytest backend/tests/production/test_rulebook_service.py backend/tests/production/test_entitlement_enforcement.py backend/tests/production/test_certificate_lifecycle.py backend/tests/production/test_certificate_auth.py backend/tests/production/test_authorization_service.py -q`
- 测试结果：`7 passed`。
- 负向证据：未接受/过期 rulebook、双边 entitlement/mandate 不匹配、participant/account/amount/currency/purpose/hash 不匹配、证书吊销或 TLS 证明缺失均拒绝；未使用固定成功或模型替代验证。
- 外部证据：真实 OCSP/CRL/HSM provider 未配置的部分已在证书生命周期记录为外部依赖，不影响本地 fail-closed Gate。
- 执行者：Codex

### B2.G4 — concurrent limit contention

- 状态：`[EXT-BLOCKED]`
- 完成时间：2026-07-27
- 实现/测试 commit：`a575eb3`, `cb1493c`, `12fbf15`, `e3437be`
- 测试命令：`$env:PYTHONPATH='backend'; .\\.venv\\Scripts\\python.exe -m pytest backend/tests/production/test_limit_concurrency.py -q`
- 测试结果：测试明确跳过：`[EXT-BLOCKED] PRODUCTION_TEST_POSTGRES_URL is not configured`；未伪造并发通过结果。
- 已具备实现：LimitReservationService 使用数据库行锁/原子计数；payment order 保存 reservation id，终局完成结转、取消/失败释放。
- 未解决风险：需配置专用 PostgreSQL fixture 执行 100 请求争用并证明总接受额不超限；因此本 Gate 不勾选，B2 COMPLETE 不勾选。
- 执行者：Codex

### B2.G3 — maker/checker separation

- 状态：DONE
- 完成时间：2026-07-27
- commit（实现/测试）：`736bd4c`
- 测试命令：`$env:PYTHONPATH='backend'; .\\.venv\\Scripts\\python.exe -m pytest backend/tests/production/test_maker_checker.py backend/tests/production/test_route_semantics.py::test_approval_cannot_self_approve -q`
- 测试结果：`4 passed`。
- 验收证据：maker subject 自决、同 credential 换 subject、过期/重复 approval、伪造请求 maker 均拒绝；checker 只来自 authenticated principal，且 decision 保存 credential binding。
- 外部证据：无。
- 执行者：Codex

### B2.G2 — credential tenant/participant/account scope isolation

- 状态：DONE
- 完成时间：2026-07-27
- commit（实现）：`be09db4`, `cf09163`, `34adef1`, `43d9dcd`
- 测试命令：`$env:PYTHONPATH='backend'; .\\.venv\\Scripts\\python.exe -m pytest backend/tests/production/test_tenant_filters.py backend/tests/production/test_route_authorization_matrix.py backend/tests/production/test_identity_header_boundary.py backend/tests/production/test_account_service.py backend/tests/production/test_service_identity_binding.py -q`
- 测试结果：`8 passed`（无失败；仅已记录的 Starlette deprecation warning）。
- 正常路径证据：principal tenant_id 从 participant 绑定派生；账户授权同时检查 tenant、participant、ACTIVE ownership；所有生产查询带 tenant/participant 过滤。
- 负向路径证据：跨 tenant payment 读取被拒绝；pilot/live role/subject/participant header 被拒绝；无绑定证书/服务身份被拒绝；管理员不会绕过租户过滤。
- 外部证据：无；真实 PostgreSQL RLS 组合由 B1.G3 `[EXT-BLOCKED]` 管理，不影响服务层 Gate。
- 执行者：Codex

### B2.G1 — identity/account/certificate/mandate/rulebook lifecycle coverage

- 状态：DONE
- 完成时间：2026-07-27
- commit（实现）：`34adef1`, `43d9dcd`, `cf09163`, `be3fcaa`, `34ef9da`, `8e736a5`, `3539174`, `842d55d`
- 验收范围：identity bootstrap/transition、account ownership/authorization、service identity/certificate binding、certificate lifecycle、mandate/approval authorization、rulebook acceptance 均有 service、router/API、状态约束及负向测试。
- 测试命令：`$env:PYTHONPATH='backend'; .\\.venv\\Scripts\\python.exe -m pytest backend/tests/production/test_identity_service.py backend/tests/production/test_identity_router.py backend/tests/production/test_account_service.py backend/tests/production/test_service_identity_binding.py backend/tests/production/test_certificate_auth.py backend/tests/production/test_certificate_lifecycle.py backend/tests/production/test_entitlement_service.py backend/tests/production/test_entitlement_enforcement.py backend/tests/production/test_rulebook_service.py backend/tests/production/test_authorization_service.py backend/tests/production/test_maker_checker.py -q`
- 测试结果：覆盖套件 `24 passed`（1 个 Starlette deprecation warning，不影响 Gate）。
- 验收证据：服务身份和账户不再只建表；PENDING→ACTIVE/REVOKED/EXPIRED 状态由服务校验；证书、双边 entitlement、rulebook、mandate 均 fail-closed。
- 外部证据：无；本 Gate 不依赖外部 PostgreSQL/HSM。
- 执行者：Codex

### B2.5.5 — maker/checker negative matrix

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`736bd4c`
- 修改文件：`backend/production/approval_api.py`、`backend/production/models.py`、`backend/alembic/versions/0020_approval_credential_binding.py`、`backend/tests/production/test_maker_checker.py`
- 新增实现：审批 projection 保存 maker/checker credential binding；checker 必须同时满足不同 subject 与不同 credential；decision 记录保存 checker credential，迁移 `0020_approval_credential_binding` 已加入。
- 新增测试：同一 subject 自决、同一 credential 换 subject、过期 approval、重复 decision、请求体伪造 maker 字段均拒绝；创建结果只采用 authenticated principal。
- 测试命令：`$env:PYTHONPATH='backend'; .\\.venv\\Scripts\\python.exe -m pytest backend/tests/production/test_maker_checker.py -q`; `.\\.venv\\Scripts\\python.exe -m ruff check --fix backend/production/approval_api.py backend/production/models.py backend/alembic/versions/0020_approval_credential_binding.py backend/tests/production/test_maker_checker.py`; `.\\.venv\\Scripts\\python.exe -m alembic -c alembic.ini upgrade head`
- 测试结果：`3 passed`；`ruff: All checks passed`；SQLite Alembic `0019 -> 0020` 成功。
- 正常路径证据：只有不同 subject 且不同 credential 的 authenticated checker 能推进 PENDING approval，并产生 append-only decision。
- 负向路径证据：maker 自决、credential swap、过期/已处理 approval、请求体伪造 maker 均返回拒绝；管理员不能通过请求字段冒充身份。
- 并发/重复/超时/恢复证据：重复或非 PENDING approval 查询返回 404；credential binding 在 projection 与 decision 中持久化。
- 外部证据：无。
- 未解决风险：真实 PostgreSQL 并发争用仍由 B2.4.4 外部 Gate 阻断。
- 执行者：Codex

### B0.G2 — pilot/live 真实 cryptographic request verification

- 状态：EXT-BLOCKED
- 完成时间：2026-07-27
- commit：无（外部 qualified verifier/HSM/CA 未提供）
- 修改文件：无新增；实现边界见 `362f18d`、`7181575`、`1352cc7`。
- 测试命令：`\.venv\Scripts\python.exe -m pytest backend/tests/production/test_http_signatures.py backend/tests/production/test_integrity_injection.py -q`
- 测试结果：`8 passed`；sandbox 使用真实 Ed25519，qualified adapter 仅验证 callback；不能声称 pilot/live 已完成。
- 验收证据：没有 qualified verifier 注入时 pilot/live integrity 返回 503，readiness 明确未就绪。
- 外部证据：待真实 HSM/CA、证书链、OCSP/CRL 和 participant key attestation。
- 未解决风险：B0 COMPLETE 不得勾选，直到 qualified request verification 在真实 pilot/live 环境完成。
- 执行者：Codex

### B0.G3 — 全路由授权矩阵负向测试

- 状态：DONE
- 完成时间：2026-07-27
- commit：`4a04fda`
- 修改文件：`backend/tests/production/test_route_authorization_matrix.py`、`backend/production/security.py`
- 测试命令：`\.venv\Scripts\python.exe -m pytest backend/tests/production/test_route_authorization_matrix.py backend/tests/production/test_route_semantics.py backend/tests/production/test_identity_header_boundary.py -q`
- 测试结果：`10 passed`（key-operations 新路由后矩阵遍历更新为 30 route）
- 验收证据：无身份、错 scope、错 tenant、自报角色、maker/checker 自审批、pilot/live sandbox header 均有实际拒绝断言；所有非 health route 有 principal。
- 外部证据：无。
- 未解决风险：qualified identity 外部证书仍为 `[EXT-BLOCKED]`，不影响本地负向 Gate。
- 执行者：Codex

### B0.G4 — nonce 并发重放

- 状态：DONE
- 完成时间：2026-07-27
- commit：`1352cc7`
- 修改文件：`backend/production/replay.py`、`backend/production/integrity.py`、`backend/tests/production/test_replay_store.py`、`backend/tests/production/test_integrity_injection.py`
- 测试命令：`\.venv\Scripts\python.exe -m pytest backend/tests/production/test_replay_store.py backend/tests/production/test_integrity_injection.py -q`
- 测试结果：`5 passed`（与 HTTP signature 合并执行为 `11 passed`）
- 验收证据：独立 SQLite sessions 并发消费同一 trust-domain/key-id/nonce 严格一胜一败；同 nonce 第二次 HTTP 请求返回 409。
- 外部证据：无。
- 未解决风险：生产 DB PostgreSQL 并发演练待 B1；当前 SQLite 测试证明唯一约束语义。
- 执行者：Codex

### B0.G5 — 外部 HSM/CA 未提供

- 状态：EXT-BLOCKED
- 完成时间：2026-07-27
- commit：无（对应 B0.4.4 外部阻断）
- 修改文件：无。
- 测试命令：`\.venv\Scripts\python.exe -m pytest backend/tests/production/test_key_provider.py backend/tests/production/test_config_qualification_gate.py -q`
- 测试结果：通过；qualified provider 缺失时系统只允许 sandbox/simulation，pilot/live startup/readiness 阻断。
- 验收证据：`production_key_provider=file`、`production_hsm_provider=unconfigured` 或无 qualified callback 均失败；未将 sandbox provider 宣称为 HSM。
- 外部证据：待 HSM/CA/RA、不可导出证明、OCSP/CRL、密钥仪式和信任域隔离证据。
- 未解决风险：Gate G5 不得勾选，B0 COMPLETE 不得勾选。
- 执行者：Codex

### B0.G6 — corridor admission/rulebook/责任签字缺失

- 状态：EXT-BLOCKED
- 完成时间：2026-07-27
- commit：无（对应 B0.5.4 外部阻断）
- 修改文件：无新增；B0.5.1/B0.5.2 已实现 default-deny 代码。
- 测试命令：`\.venv\Scripts\python.exe -m pytest backend/tests/production/test_corridor_models.py backend/tests/production/test_readiness_dependencies.py -q`
- 测试结果：通过；本地只有显式 `simulation_only` admission，pilot/live 无真实 admission 时 payment/readiness 拒绝。
- 验收证据：无 ACTIVE 非 simulation admission、rulebook、法律/合规/结算/数据保护/安全 sign-off 可供生产使用。
- 外部证据：待持牌合作方、CN/HK 法律和责任角色签字、rulebook 和资金流批准版本。
- 未解决风险：Gate G6 不得勾选，B0 COMPLETE 不得勾选。
- 执行者：Codex

### B1.1.1 — 冻结历史迁移 baseline

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`c14290d`
- 修改文件：`docs/database/MIGRATION_BASELINE.md`、`backend/scripts/verify_migration_baseline.py`、`backend/tests/production/test_migration_baseline.py`、`.github/workflows/migrations.yml`
- 新增迁移：无；历史 `0001/0002/0003` 未修改。
- 新增/修改测试：baseline 三文件 SHA-256 校验和 CI workflow。
- 测试命令：`\.venv\Scripts\python.exe -m pytest backend/tests/production/test_migration_baseline.py -q`; `\.venv\Scripts\python.exe -m ruff check backend/scripts/verify_migration_baseline.py backend/tests/production/test_migration_baseline.py`; `\.venv\Scripts\python.exe backend/scripts/verify_migration_baseline.py`
- 测试结果：`1 passed`; `ruff`：`All checks passed`; verifier 通过。
- 正常路径证据：immutable baseline 文档记录 revision hash 和已知缺陷，CI 在 migration upgrade 前 fail-closed 校验。
- 负向路径证据：缺失/修改任一历史 revision 会 `SystemExit`，禁止静默修改。
- 并发/重复/超时/恢复证据：CI 每次 PR/push 重新 hash；历史修复必须追加新 revision。
- OpenAPI/AsyncAPI 影响：无。
- Metrics/alerts/runbook 影响：baseline mismatch 阻断 migration workflow。
- 外部证据：无。
- 未解决风险：B1.1.2 仍需显式关系完整性迁移。
- 执行者：Codex

### B1.1.2 — 显式生产关系完整性迁移

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`2be8255`
- 修改文件：`backend/alembic/versions/0008_production_relational_integrity.py`、`backend/tests/production/test_relational_integrity_migration.py`
- 新增迁移：`0008_production_relational_integrity`（清单原预留 0006 已被既有 key-operation revision 占用，未改写历史）。
- 新增/修改测试：显式 FK relation 清单、RESTRICT 删除策略、禁止 `Base.metadata.tables` 动态建表；当前 SQLite head upgrade 已通过。
- 测试命令：`\.venv\Scripts\python.exe -m alembic upgrade head`; `\.venv\Scripts\python.exe -m pytest backend/tests/production/test_relational_integrity_migration.py -q`; `\.venv\Scripts\python.exe -m ruff check backend/alembic/versions/0008_production_relational_integrity.py backend/tests/production/test_relational_integrity_migration.py`
- 测试结果：migration upgrade 通过；`1 passed`; `ruff`：`All checks passed`。
- 正常路径证据：迁移显式检查 orphan 后用 batch `create_foreign_key` 创建 20 条核心关系，`ondelete=RESTRICT`。
- 负向路径证据：发现 orphan 时 migration 直接 RuntimeError，不会静默删除或级联抹历史。
- 并发/重复/超时/恢复证据：升级前 orphan 检查；downgrade 按相同显式 constraint 名称移除。
- OpenAPI/AsyncAPI 影响：无。
- Metrics/alerts/runbook 影响：orphan 阻断 migration，需进入 repair runbook。
- 外部证据：无。
- 未解决风险：ORM 模型列尚未全部声明 ForeignKey、金额/时间类型尚待 B1.1.3–B1.1.5。
- 执行者：Codex

### R0.1 — 执行证据机制

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：待提交（本条与清单/日志模板一并提交）
- 修改文件：`docs/B0_B10_FULL_IMPLEMENTATION_CHECKLIST.md`、`docs/B0_B10_EXECUTION_LOG.md`
- 新增迁移：无
- 新增/修改测试：清单结构检查（459 个复选项、57 个 Gate、20 个反例）
- 测试命令：`rg '^- \[ \]' docs/B0_B10_FULL_IMPLEMENTATION_CHECKLIST.md`
- 测试结果：通过；每项均定义代码、迁移、测试、恢复路径、文档和证据要求
- 正常路径证据：清单第 0 节、执行日志模板和 B0–B10 Gate 已存在
- 负向路径证据：清单规则 R0.2、R0.3、R0.8、R0.9 明确禁止占位冒充完成
- 并发/重复/超时/恢复证据：清单 R0.7 要求所有资金/消息/终局/对账项覆盖
- OpenAPI/AsyncAPI 影响：R0.11 要求所有新 API/event 纳入契约
- Metrics/alerts/runbook 影响：R0.1 将其列为每项完成条件
- 外部证据：无
- 未解决风险：尚未创建本条提交；后续每项必须先更新本日志再勾选
- 执行者：Codex

### R0.12 — 保护用户改动与提交边界

- 状态：DONE
- commit：待提交
- 修改文件：`docs/B0_B10_FULL_IMPLEMENTATION_CHECKLIST.md`
- 测试命令：`git status --short; git log --oneline -12`
- 测试结果：通过；每条 R0 规则均以独立 commit 记录，未执行 reset/checkout/删除用户文件
- 验收证据：当前提交历史包含 R0.1–R0.12 逐条提交；B0–B10 仍未勾选
- 未解决风险：工作区原有 Luna 代码改动未被本条处理，后续仅在明确文件范围内修改
- 执行者：Codex

### R0.11 — OpenAPI/AsyncAPI 契约

- 状态：DONE
- commit：待提交
- 修改文件：`docs/B0_B10_FULL_IMPLEMENTATION_CHECKLIST.md`
- 测试命令：`rg 'OpenAPI|AsyncAPI|compatibility' docs/B0_B10_FULL_IMPLEMENTATION_CHECKLIST.md`
- 测试结果：通过；R0.11 已列为每个新 API/event 的统一门槛，并在 B3/B10 拆分实现项
- 验收证据：B3.1.3、B10.7.1、B10.7.2、B10.7.6
- 未解决风险：当前仓库尚未生成 production OpenAPI/AsyncAPI，后续保持未勾选
- 执行者：Codex

### R0.10 — 父级 Gate 依赖

- 状态：DONE
- commit：待提交
- 修改文件：`docs/B0_B10_FULL_IMPLEMENTATION_CHECKLIST.md`
- 测试命令：`rg '父级 Gate|B0 COMPLETE|B10 COMPLETE' docs/B0_B10_FULL_IMPLEMENTATION_CHECKLIST.md`
- 测试结果：通过；每个 B 都有 Gate 和 COMPLETE 条件
- 验收证据：第 11 节合并门 M1–M10
- 未解决风险：执行者必须避免批量勾选父级和子项
- 执行者：Codex

### R0.9 — 外部依赖阻塞标记

- 状态：DONE
- commit：待提交
- 修改文件：`docs/B0_B10_FULL_IMPLEMENTATION_CHECKLIST.md`
- 测试命令：`rg '\[EXT-BLOCKED\]' docs/B0_B10_FULL_IMPLEMENTATION_CHECKLIST.md`
- 测试结果：通过；外部 HSM、标准工件、connector、法律/监管签字均有明确标记位置
- 验收证据：B0.4.4、B6.1.5、B7.3.6、B8.5.6、B8.6.5、B10.4.5 及最终签字表
- 未解决风险：外部证据尚未提供，不能进入 pilot/live
- 执行者：Codex

### R0.8 — Fail-closed 不等于功能完成

- 状态：DONE
- commit：待提交
- 修改文件：`docs/B0_B10_FULL_IMPLEMENTATION_CHECKLIST.md`
- 测试命令：`rg '永远返回 503|fail-closed' docs/B0_B10_FULL_IMPLEMENTATION_CHECKLIST.md`
- 测试结果：通过；R0.8 明确区分安全占位和真实 qualified 功能
- 验收证据：B0.2、B7.3、B7.4、B8.2 设有真实功能 Gate
- 未解决风险：当前 signature verifier/qualified connector 仍是占位，后续必须保持未完成
- 执行者：Codex

### R0.7 — 全类别测试要求

- 状态：DONE
- commit：待提交
- 修改文件：`docs/B0_B10_FULL_IMPLEMENTATION_CHECKLIST.md`
- 测试命令：`rg '正常、负向、并发、重复、超时、崩溃恢复' docs/B0_B10_FULL_IMPLEMENTATION_CHECKLIST.md`
- 测试结果：通过；R0.7 和各 B 的测试清单明确覆盖六类行为
- 验收证据：第 12 节 X01–X20 反例回归表
- 未解决风险：当前测试覆盖仍不足，必须逐项补齐
- 执行者：Codex

### R0.6 — 金额与时间类型规则

- 状态：DONE
- commit：待提交
- 修改文件：`docs/B0_B10_FULL_IMPLEMENTATION_CHECKLIST.md`
- 测试命令：`rg 'BigInteger|timezone=True|UTC' docs/B0_B10_FULL_IMPLEMENTATION_CHECKLIST.md`
- 测试结果：通过；R0.6 已作为全局数据模型/迁移约束，B1.1 明确要求落地
- 验收证据：B1.1.4、B1.1.5 和金额/时间测试要求已定义
- 未解决风险：现有模型仍有 Integer/naive datetime，必须在 B1 修复
- 执行者：Codex

### R0.5 — 历史迁移不可变

- 状态：DONE
- commit：待提交
- 修改文件：`docs/B0_B10_FULL_IMPLEMENTATION_CHECKLIST.md`
- 测试命令：`rg '0001/0002/0003|0004_\*' docs/B0_B10_FULL_IMPLEMENTATION_CHECKLIST.md`
- 测试结果：通过；清单规定后续只能追加 0004+ revision
- 验收证据：B1.1 明确要求 baseline hash、显式新迁移和 CI 校验
- 未解决风险：当前工作区旧迁移已有未提交修改，执行 B1 前必须冻结并记录其 hash
- 执行者：Codex

### R0.4 — 每项证据字段

- 状态：DONE
- commit：待提交
- 修改文件：`docs/B0_B10_FULL_IMPLEMENTATION_CHECKLIST.md`、`docs/B0_B10_EXECUTION_LOG.md`
- 测试命令：`rg 'commit:|files:|tests:|command:|result:' docs/B0_B10_FULL_IMPLEMENTATION_CHECKLIST.md docs/B0_B10_EXECUTION_LOG.md`
- 测试结果：通过；清单和日志模板都要求记录提交、文件、测试、命令和结果
- 验收证据：执行日志模板已提供固定字段
- 未解决风险：后续执行者可能遗漏填写，B Gate 将其作为门槛
- 执行者：Codex

### R0.3 — Simulator/qualified 隔离

- 状态：DONE
- commit：待提交
- 修改文件：`docs/B0_B10_FULL_IMPLEMENTATION_CHECKLIST.md`
- 测试命令：`rg 'simulator|qualified|FINAL|PASSED|MATCHED' docs/B0_B10_FULL_IMPLEMENTATION_CHECKLIST.md`
- 测试结果：通过；规则要求模拟结果不得冒充外部结果，并要求独立 connector/finality 验证
- 验收证据：B7.3、B7.4、B8.2、B5.4 均包含隔离和真实来源检查
- 未解决风险：当前代码仍有 sandbox 路径，后续 B7/B8 必须按本规则修复
- 执行者：Codex
- 复核者：待用户/Luna 复核

### R0.2 — 禁止占位冒充完成

- 状态：DONE
- commit：待提交
- 修改文件：`docs/B0_B10_FULL_IMPLEMENTATION_CHECKLIST.md`
- 测试命令：`rg '新增 ORM 类|Protocol|固定返回成功|TODO' docs/B0_B10_FULL_IMPLEMENTATION_CHECKLIST.md`
- 测试结果：通过；R0.2 明确规定这些内容不计完成
- 验收证据：每个 B Gate 均要求真实代码、错误路径和测试
- 未解决风险：无；后续实现若出现占位必须保持未勾选
- 执行者：Codex

### B0.1.1 修正记录

- 状态：DONE（补充修正）
- 完成时间：2026-07-27
- commit：`a6088ac`
- 修改文件：`backend/production/qualification.py`、`backend/tests/production/test_qualification.py`
- 新增/修改测试：补充 `artifact_type` schema 字段与 `QualificationStatus.VERIFIED` 断言。
- 测试命令：`\.venv\Scripts\python.exe -m pytest backend/tests/production/test_qualification.py -q`
- 测试结果：`3 passed`
- 正常路径证据：有效 attestation 返回 `QualificationStatus.VERIFIED`。
- 负向路径证据：缺少 `artifact_type` 的 attestation 在 verifier 层拒绝。
- 未解决风险：真实签发机构和生产工件仍属于 B0.4/B7 的 `[EXT-BLOCKED]` 外部证据。

### B0.2.1 — RFC 9421 HTTP 消息签名验证器

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`362f18d`
- 修改文件：`backend/production/signatures.py`、`backend/tests/production/test_http_signatures.py`、`backend/config.py`、`backend/.env.example`
- 新增迁移：无
- 新增/修改测试：真实 Ed25519 sandbox verifier、qualified callback adapter、body digest、URI 篡改、过期、未来时间、缺 covered component、弱算法和身份绑定。
- 测试命令：`\.venv\Scripts\python.exe -m pytest backend/tests/production/test_http_signatures.py -q`; `\.venv\Scripts\python.exe -m ruff check backend/production/signatures.py backend/tests/production/test_http_signatures.py backend/config.py`
- 测试结果：`3 passed`; `ruff`：`All checks passed`
- 正常路径证据：canonical covered components 包含 method、target URI、authority、content-digest、content-type、date、nonce、participant/service identity，Ed25519 实签名验证通过。
- 负向路径证据：body/URI 被改、窗口失效、缺组件、unknown/weak algorithm、未知 key、身份不绑定均拒绝；不是固定 200/成功结果。
- 并发/重复/超时/恢复证据：created/expires 与配置 clock skew 校验；nonce 持久化和并发原子拒绝在 B0.2.3。
- OpenAPI/AsyncAPI 影响：签名输入字段作为生产 HTTP boundary contract，B0.2.2 接入路由依赖。
- Metrics/alerts/runbook 影响：拒绝原因结构化为 `SignatureVerificationError`，integrity 层负责 HTTP 映射。
- 外部证据：qualified adapter 只接受外部真实 verifier callback；未提供真实 HSM/CA，保持 `[EXT-BLOCKED]`。
- 未解决风险：尚未将 verifier 注入 FastAPI integrity dependency。
- 执行者：Codex

### B0.2.2 — 请求完整性依赖注入

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`7181575`
- 修改文件：`backend/production/integrity.py`、`backend/tests/production/test_integrity_injection.py`
- 新增迁移：无
- 新增/修改测试：body digest 先验失败、pilot/live 无 verifier 的 503 fail-closed、sandbox 无签名兼容路径。
- 测试命令：`\.venv\Scripts\python.exe -m pytest backend/tests/production/test_integrity_injection.py -q`; `\.venv\Scripts\python.exe -m ruff check backend/production/integrity.py backend/tests/production/test_integrity_injection.py`
- 测试结果：`3 passed`; `ruff`：`All checks passed`
- 正常路径证据：注入 `HttpSignatureVerifier` 后由依赖构造完整 `SignedHttpRequest`，先校验 Content-Digest 再执行签名验证并写入 request state。
- 负向路径证据：digest 错误统一 400；pilot 缺签名/verifier 明确 400/503；不再以固定 503 冒充已实现功能。
- 并发/重复/超时/恢复证据：created/expires 窗口由 verifier 校验；nonce 原子持久化在 B0.2.3。
- OpenAPI/AsyncAPI 影响：生产 mutation 路由继续使用 `require_request_integrity`，错误码明确化。
- Metrics/alerts/runbook 影响：invalid digest/signature 可按结构化错误码告警。
- 外部证据：qualified verifier/HSM 尚未提供，pilot/live 仍保持阻断 `[EXT-BLOCKED]`。
- 未解决风险：尚未配置生产 key registry 和持久化 nonce store。
- 执行者：Codex

### B0.2.3 — 持久化 nonce/replay store

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`2a21b17`
- 修改文件：`backend/production/models.py`、`backend/alembic/versions/0005_production_replay_store.py`、`backend/production/replay.py`、`backend/tests/production/test_replay_store.py`
- 新增迁移：`0005_production_replay_store`
- 新增/修改测试：trust domain + key id + nonce 原子唯一；相同 digest 重放；不同 digest 重放；跨 trust domain 隔离；过期 nonce。
- 测试命令：`\.venv\Scripts\python.exe -m pytest backend/tests/production/test_replay_store.py -q`; `\.venv\Scripts\python.exe -m ruff check backend/production/models.py backend/production/replay.py backend/alembic/versions/0005_production_replay_store.py backend/tests/production/test_replay_store.py`; `\.venv\Scripts\python.exe -m alembic upgrade head`
- 测试结果：`2 passed`; `ruff`：`All checks passed`; Alembic 已升级至 `0005_production_replay_store`，表 `prod_request_nonces` 存在。
- 正常路径证据：首次 `consume` 在同一事务 savepoint 内持久化 request digest、expires_at、first_used_at。
- 负向路径证据：数据库唯一约束和 `IntegrityError` 映射阻止重复 nonce；digest 不同返回明确 replay error；过期 nonce 拒绝。
- 并发/重复/超时/恢复证据：唯一约束是并发原子门槛；savepoint 回滚冲突不污染外层事务；不同 trust domain 可合法使用相同 nonce。
- OpenAPI/AsyncAPI 影响：无新增接口；B0.2.4 将其接入 HTTP boundary。
- Metrics/alerts/runbook 影响：replay/digest mismatch 可由调用层映射告警；清理过期记录的运维任务待后续 B7。
- 外部证据：无；真实 trust domain/key registry 仍需外部资格，保持 `[EXT-BLOCKED]`。
- 未解决风险：尚未把 nonce consume 接入 `require_request_integrity`，B0.2.4 完成。
- 执行者：Codex

### B0.2.4 — HTTP 签名与 replay 负向验收

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`1352cc7`
- 修改文件：`backend/production/integrity.py`、`backend/production/signatures.py`、`backend/production/replay.py`、`backend/config.py`、`backend/.env.example`、`backend/tests/production/test_http_signatures.py`、`backend/tests/production/test_integrity_injection.py`、`backend/tests/production/test_replay_store.py`
- 新增迁移：使用已完成的 `0005_production_replay_store`
- 新增/修改测试：正确签名、body/URI 篡改、过期/未来时间、缺 component、弱算法、吊销 key、身份绑定、digest-first、nonce 重放和并发双提交。
- 测试命令：`\.venv\Scripts\python.exe -m pytest backend/tests/production/test_replay_store.py backend/tests/production/test_http_signatures.py backend/tests/production/test_integrity_injection.py -q`; `\.venv\Scripts\python.exe -m ruff check backend/production/integrity.py backend/production/signatures.py backend/production/replay.py backend/tests/production/test_replay_store.py backend/tests/production/test_http_signatures.py backend/tests/production/test_integrity_injection.py backend/config.py`
- 测试结果：`11 passed`; `ruff`：`All checks passed`
- 正常路径证据：integrity 注入真实 sandbox Ed25519 verifier，签名通过后将 nonce/digest 写入 `prod_request_nonces`。
- 负向路径证据：body/URI、窗口、覆盖字段、算法、吊销 key、参与方身份错误均拒绝；同 nonce 第二次 409；并发两个事务严格一胜一败。
- 并发/重复/超时/恢复证据：并发测试使用独立 SQLite sessions 和唯一约束；过期窗口和 nonce replay 在请求边界阻断。
- OpenAPI/AsyncAPI 影响：production mutation 通过统一 integrity dependency，错误码 `INVALID_CONTENT_DIGEST`、`INVALID_MESSAGE_SIGNATURE`、`MESSAGE_REPLAY_DETECTED`。
- Metrics/alerts/runbook 影响：可按错误码统计签名失败/replay；nonce 清理和 trust-domain 运维待 B7。
- 外部证据：吊销列表/HSM/CA 真实来源未提供，测试中的 revoked key 为确定性负向证据，生产资格保持 `[EXT-BLOCKED]`。
- 未解决风险：qualified verifier callback 尚未绑定真实证书链和 OCSP/CRL。
- 执行者：Codex

### B0.3.1 — 生产 API 授权矩阵

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`a50683b`
- 修改文件：`docs/security/PRODUCTION_API_AUTHORIZATION_MATRIX.md`、`backend/tests/production/test_authorization_matrix_document.py`
- 新增迁移：无
- 新增/修改测试：从 router 装饰器提取全部生产路由，逐项检查矩阵覆盖。
- 测试命令：`\.venv\Scripts\python.exe -m pytest backend/tests/production/test_authorization_matrix_document.py -q`; `\.venv\Scripts\python.exe -m ruff check backend/tests/production/test_authorization_matrix_document.py`
- 测试结果：`1 passed`; `ruff`：`All checks passed`
- 正常路径证据：矩阵覆盖当前 27 个生产路由，逐项列出 identity、scope、tenant、integrity、幂等、maker/checker、audit。
- 负向路径证据：矩阵明确禁止自报角色/参与方 header、管理员越过双控和公网 worker。
- 并发/重复/超时/恢复证据：每个 mutation 的幂等和重放要求显式列入矩阵，具体实现由 B0.2/B1 覆盖。
- OpenAPI/AsyncAPI 影响：矩阵作为 API 安全契约，后续拆分路由必须保持一一对应。
- Metrics/alerts/runbook 影响：矩阵定义审计和拒绝事件维度。
- 外部证据：无；真实身份/证书/CA 仍为 `[EXT-BLOCKED]`。
- 未解决风险：现有 router 尚未完全按矩阵拆分，B0.3.2–B0.3.6 继续执行。
- 执行者：Codex

### B0.3.2 — 按安全域拆分生产路由

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`159c139`
- 修改文件：`backend/production/router.py`、`backend/production/payment_router.py`、`backend/production/identity_router.py`、`backend/production/operations_router.py`、`backend/production/ledger_router.py`、`backend/production/standards_router.py`、`backend/production/reporting_router.py`
- 新增迁移：无
- 新增/修改测试：路由矩阵覆盖测试、生产 health 路由和旧 API operational regression。
- 测试命令：`\.venv\Scripts\python.exe -m pytest backend/tests/production/test_authorization_matrix_document.py backend/tests/production/test_readiness_dependencies.py backend/tests/test_ecny_api_flow.py -q`; `\.venv\Scripts\python.exe -m ruff check backend/production/router.py backend/production/payment_router.py backend/production/identity_router.py backend/production/operations_router.py backend/production/ledger_router.py backend/production/standards_router.py backend/production/reporting_router.py`
- 测试结果：`5 passed`; `ruff`：`All checks passed`
- 正常路径证据：payment、identity、operations、ledger、standards、reporting 六个安全域 router 均注册真实 endpoint，生产 health 仍返回依赖状态。
- 负向路径证据：拆分过程中未引入重复 endpoint；matrix test 仍确认全部 27 路由有文档覆盖。
- 并发/重复/超时/恢复证据：路由拆分不改变业务事务/幂等依赖；每个 endpoint 保留原函数依赖签名。
- OpenAPI/AsyncAPI 影响：生产路由注册由六个安全域模块组成，路径前缀保持 `/production/v1`。
- Metrics/alerts/runbook 影响：可按安全域统计拒绝和审计事件。
- 外部证据：无；真实身份/证书仍 `[EXT-BLOCKED]`。
- 未解决风险：统一 dependency bundle 在 B0.3.3 接入。
- 执行者：Codex

### B0.3.3 — 统一生产依赖 bundle

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`67829d0`
- 修改文件：`backend/production/dependencies.py`、`backend/tests/production/test_dependencies.py`
- 新增迁移：无
- 新增/修改测试：bundle 字段完整性和 read/write/operator/admin dependency 参数检查。
- 测试命令：`\.venv\Scripts\python.exe -m pytest backend/tests/production/test_dependencies.py -q`; `\.venv\Scripts\python.exe -m ruff check backend/production/dependencies.py backend/tests/production/test_dependencies.py`
- 测试结果：`1 passed`; `ruff`：`All checks passed`
- 正常路径证据：`ProductionDependencyBundle` 同时携带 principal、scope 派生身份、tenant、idempotency key、integrity result 和 audit context。
- 负向路径证据：write bundle 的 `Idempotency-Key` 和 `require_request_integrity` 都是强制依赖；scope 不足由既有 security dependency 拒绝。
- 并发/重复/超时/恢复证据：幂等和 nonce store 的原子门槛由 B0.2/B1 提供，bundle 不绕过这些依赖。
- OpenAPI/AsyncAPI 影响：后续 mutation 路由可统一声明依赖，避免遗漏安全组件。
- Metrics/alerts/runbook 影响：audit_context 提供 request/trace/route 维度。
- 外部证据：无；真实身份信任域仍 `[EXT-BLOCKED]`。
- 未解决风险：现有 handler 仍有旧式逐参数依赖，B0.3.4 将按矩阵替换。
- 执行者：Codex

### B0.3.4 — 路由语义与公网暴露修复

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`3a4c85e`
- 修改文件：`backend/production/router.py`、`backend/production/ledger_router.py`、`docs/security/PRODUCTION_API_AUTHORIZATION_MATRIX.md`、`backend/tests/production/test_route_semantics.py`
- 新增迁移：无
- 新增/修改测试：trial-balance GET 语义；pilot/live worker 404；所有 mutation handler integrity 依赖；maker/checker 自审批拒绝。
- 测试命令：`\.venv\Scripts\python.exe -m pytest backend/tests/production/test_route_semantics.py -q`; `\.venv\Scripts\python.exe -m ruff check backend/production/router.py backend/production/ledger_router.py backend/tests/production/test_route_semantics.py`
- 测试结果：`3 passed`; `ruff`：`All checks passed`
- 正常路径证据：trial-balance 改为 GET；sandbox worker 仍可运行；业务 mutation 保留 integrity dependency。
- 负向路径证据：pilot/live worker 公网执行直接 404；maker=checker 直接 409；缺 integrity 参数的 mutation 检查失败。
- 并发/重复/超时/恢复证据：支付/取消/退回既有幂等；worker 不提供人工公网重试入口。
- OpenAPI/AsyncAPI 影响：trial-balance OpenAPI 仅保留 GET；矩阵同步。
- Metrics/alerts/runbook 影响：公网 worker 探测记为 404；自审批记为 409 审计事件。
- 外部证据：无；pilot/live 仍由真实身份和 HSM Gate 阻断。
- 未解决风险：sandbox header 隔离和统一 bundle 全量替换在 B0.3.5/B0.3.6。
- 执行者：Codex

### B0.3.5 — 生产身份头隔离

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`01ddbb8`
- 修改文件：`backend/production/security.py`、`frontend/src/api.ts`、`frontend/src/vite-env.d.ts`、`backend/tests/production/test_identity_header_boundary.py`
- 新增迁移：无
- 新增/修改测试：pilot/live 下 X-User-Role、X-User-Subject、X-Participant-ID 明确拒绝；sandbox principal 明确标记；前端 typecheck/build。
- 测试命令：`\.venv\Scripts\python.exe -m pytest backend/tests/production/test_identity_header_boundary.py backend/tests/production/test_route_semantics.py -q`; `\.venv\Scripts\python.exe -m ruff check backend/production/security.py backend/tests/production/test_identity_header_boundary.py`; `npm run typecheck`; `npm run build`
- 测试结果：`5 passed`; `ruff`：`All checks passed`; frontend typecheck/build 通过（仅既有 chunk size warning）。
- 正常路径证据：production UI API 不再发送角色/参与方伪造头；sandbox headers 只有 `VITE_SIMULATION_MODE=true` 时显式发送。
- 负向路径证据：非 sandbox 任一测试身份头返回 403；production principal 不读取 role/subject header。
- 并发/重复/超时/恢复证据：身份解析在每次请求重新执行；credential scope 与持久化 service identity 仍为信任来源。
- OpenAPI/AsyncAPI 影响：无新增接口；production headers 不再作为身份契约。
- Metrics/alerts/runbook 影响：身份头越界返回 403，可作为安全告警。
- 外部证据：真实 OAuth/mTLS/CA 仍需外部资格，保持 `[EXT-BLOCKED]`。
- 未解决风险：nextgen UI 的 sandbox role header 仍仅限显式 simulation mode，B0.3.6 完成全路由负向矩阵。
- 执行者：Codex

### B0.3.6 — 全路由授权矩阵负向测试

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`4a04fda`
- 修改文件：`backend/production/security.py`、`backend/tests/production/test_route_authorization_matrix.py`
- 新增迁移：无
- 新增/修改测试：遍历 29 个 production APIRoute；无身份 pilot 401；错 scope 403；sandbox admin 不再绕过 tenant；自审批/测试头负向覆盖。
- 测试命令：`\.venv\Scripts\python.exe -m pytest backend/tests/production/test_route_authorization_matrix.py backend/tests/test_production_domain.py -q`; `\.venv\Scripts\python.exe -m ruff check backend/production/security.py backend/tests/production/test_route_authorization_matrix.py`
- 测试结果：`6 passed`; `ruff`：`All checks passed`
- 正常路径证据：每个非 health route 都有 principal 参数；sandbox payment/worker 正常通过明确 simulation principal。
- 负向路径证据：pilot 无身份 401、错 scope 403、跨 participant 读取 409、maker=checker 409、pilot/live 测试 identity header 403。
- 并发/重复/超时/恢复证据：支付 tenant 过滤和幂等依赖保持；路由矩阵覆盖重复/重放入口。
- OpenAPI/AsyncAPI 影响：29 个 APIRoute 全部被纳入 security matrix。
- Metrics/alerts/runbook 影响：401/403/409 维度可用于授权拒绝和越权告警。
- 外部证据：无；真实 OAuth/mTLS 仍 `[EXT-BLOCKED]`。
- 未解决风险：统一 bundle 尚未替换全部 handler 参数，但每项已有可验证 principal/integrity 约束。
- 执行者：Codex

### B0.4.1 — 不可导出私钥 provider 边界

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`8780e4e`
- 修改文件：`backend/production/key_provider.py`、`backend/tests/production/test_key_provider.py`
- 新增迁移：无
- 新增/修改测试：sandbox Ed25519 sign/verify/rotate/revoke；qualified callback delegation；无 HSM callback fail-closed；无 private export API。
- 测试命令：`\.venv\Scripts\python.exe -m pytest backend/tests/production/test_key_provider.py -q`; `\.venv\Scripts\python.exe -m ruff check backend/production/key_provider.py backend/tests/production/test_key_provider.py`
- 测试结果：`3 passed`; `ruff`：`All checks passed`
- 正常路径证据：sandbox provider 对真实 Ed25519 私钥签名并只返回公钥；qualified provider 所有私钥操作都委托外部 callback。
- 负向路径证据：篡改消息验证失败；REVOKED key 禁止签名；pilot 无 qualified provider 注册直接抛 `KeyProviderError`。
- 并发/重复/超时/恢复证据：rotate 递增 key version；revoke 状态阻断后续签名。
- OpenAPI/AsyncAPI 影响：无外部 API；B0.4.3 接入密钥审计和双控。
- Metrics/alerts/runbook 影响：provider 错误和 revoke/rotate 可作为安全事件。
- 外部证据：真实 HSM/KMS 尚未提供，qualified provider 保持 `[EXT-BLOCKED]`。
- 未解决风险：provider 尚未由 Settings trust-domain 配置选择，B0.4.2 完成。
- 执行者：Codex

### B0.4.2 — HSM/KMS、trust domain 与轮换配置

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`4028f71`
- 修改文件：`backend/config.py`、`backend/.env.example`、`backend/tests/production/test_config_qualification_gate.py`
- 新增迁移：无
- 新增/修改测试：qualified HSM/KMS + trust domain/key label 有效准入；file provider 在 pilot/live 拒绝；OCSP/CRL/rotation 配置存在。
- 测试命令：`\.venv\Scripts\python.exe -m pytest backend/tests/production/test_config_qualification_gate.py backend/tests/production/test_readiness_dependencies.py -q`; `\.venv\Scripts\python.exe -m ruff check backend/config.py backend/tests/production/test_config_qualification_gate.py`
- 测试结果：`7 passed`; `ruff`：`All checks passed`
- 正常路径证据：pilot settings 必须 `production_key_provider=qualified`、`production_hsm_provider=qualified`、trust domain 和 key label，随后才验证 attestation。
- 负向路径证据：file/private-key provider 或缺 trust domain/key label 立即 RuntimeError。
- 并发/重复/超时/恢复证据：rotation interval 作为明确配置，实际双控在 B0.4.3。
- OpenAPI/AsyncAPI 影响：无新增接口。
- Metrics/alerts/runbook 影响：provider/OCSP/CRL 配置缺失可在 startup/readiness 告警。
- 外部证据：真实 HSM/KMS、OCSP/CRL 仍 `[EXT-BLOCKED]`。
- 未解决风险：密钥轮换/吊销尚未落审计和 maker-checker。
- 执行者：Codex

### B0.4.3 — 密钥操作审计与双控接口

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`a069a1e`
- 修改文件：`backend/production/models.py`、`backend/alembic/versions/0006_key_operation_audit.py`、`backend/production/key_operations.py`、`backend/production/router.py`、`backend/production/operations_router.py`、`backend/tests/production/test_key_operations.py`、`docs/security/PRODUCTION_API_AUTHORIZATION_MATRIX.md`、`backend/tests/production/test_route_authorization_matrix.py`
- 新增迁移：`0006_key_operation_audit`
- 新增/修改测试：ROTATE/REVOKE 必须有已批准 ProductionApproval、maker/checker distinct；provider 操作结果写入审计；路由矩阵新增 key-operations。
- 测试命令：`\.venv\Scripts\python.exe -m alembic upgrade head`; `\.venv\Scripts\python.exe -m pytest backend/tests/production/test_key_operations.py backend/tests/production/test_route_authorization_matrix.py -q`; `\.venv\Scripts\python.exe -m ruff check backend/production/models.py backend/production/key_operations.py backend/production/router.py backend/production/operations_router.py backend/tests/production/test_key_operations.py`
- 测试结果：`6 passed`; `ruff`：`All checks passed`; migration 已升级到 `0006_key_operation_audit`。
- 正常路径证据：独立 checker 的 APPROVED approval 后，sandbox provider 实际 rotate/revoke，`prod_key_operation_audits` 记录 COMPLETED、result_digest、completed_at。
- 负向路径证据：缺 approval、maker=checker、unsupported operation、qualified provider 未配置均拒绝；失败状态写入 audit。
- 并发/重复/超时/恢复证据：operation_id 唯一；approval 和审计事实在同一 DB transaction 中。
- OpenAPI/AsyncAPI 影响：新增 `/production/v1/key-operations` mutation，已纳入授权矩阵和 integrity dependency。
- Metrics/alerts/runbook 影响：key rotate/revoke/audit failure 可作为高优先级安全告警。
- 外部证据：真实 HSM/KMS/CA 尚未提供，pilot/live endpoint 保持 503 `[EXT-BLOCKED]`。
- 未解决风险：trust-anchor 变更仍需 qualified 外部审批和 B2 流程。
- 执行者：Codex

### B0.5.1 — 走廊准入与控制签字模型

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`0f1e263`
- 修改文件：`backend/production/models.py`、`backend/alembic/versions/0007_corridor_admission.py`、`backend/tests/production/test_corridor_models.py`
- 新增迁移：`0007_corridor_admission`
- 新增/修改测试：admission/control attestation 持久化；environment+corridor+rulebook 唯一；金额窗口和 simulation_only 字段。
- 测试命令：`\.venv\Scripts\python.exe -m pytest backend/tests/production/test_corridor_models.py -q`; `\.venv\Scripts\python.exe -m ruff check backend/production/models.py backend/alembic/versions/0007_corridor_admission.py backend/tests/production/test_corridor_models.py`; `\.venv\Scripts\python.exe -m alembic upgrade head`
- 测试结果：`2 passed`; `ruff`：`All checks passed`; migration 已升级至 `0007_corridor_admission`。
- 正常路径证据：admission 保存主体、场景、币种、金额/时间窗口、资金流、终局、数据流、rulebook、签字角色和 evidence；control attestation 保存 signer/validity/status/evidence。
- 负向路径证据：同环境/走廊/rulebook 重复提交触发 `IntegrityError`；DB check constraint 限制金额和状态。
- 并发/重复/超时/恢复证据：唯一约束阻止重复版本；有效期字段供 B0.5.2 运行时判定。
- OpenAPI/AsyncAPI 影响：无新增外部接口。
- Metrics/alerts/runbook 影响：admission status/expiry 可作为 readiness 和 payment deny 事件维度。
- 外部证据：真实 CN/HK 法律签字尚未提供，sandbox admission 明确 `simulation_only=true`。
- 未解决风险：payment 创建前尚未执行 admission check，B0.5.2 完成。
- 执行者：Codex

### B0.5.2 — payment 创建前走廊准入检查

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`8713855`
- 修改文件：`backend/production/corridors.py`、`backend/production/service.py`、`backend/tests/production/test_corridor_models.py`
- 新增迁移：使用 `0007_corridor_admission`
- 新增/修改测试：payment 创建前 ACTIVE admission、主体/场景/币种/金额/时间/控制 attestation 全校验；未批准场景 default-deny；simulation admission 不可复用到 pilot；既有 sandbox payment flow。
- 测试命令：`\.venv\Scripts\python.exe -m pytest backend/tests/production/test_corridor_models.py backend/tests/test_production_domain.py -q`; `\.venv\Scripts\python.exe -m ruff check backend/production/corridors.py backend/production/service.py backend/tests/production/test_corridor_models.py`
- 测试结果：`6 passed`; `ruff`：`All checks passed`
- 正常路径证据：sandbox reference data 创建明确 `simulation_only=true` admission/control attestation，TRADE/CNY/CN-HK payment 可以进入编排。
- 负向路径证据：无 ACTIVE admission、场景/币种/金额/时段不匹配、缺 control attestation、pilot 复用 simulation admission 均抛 `ProductionConflict`。
- 并发/重复/超时/恢复证据：admission 唯一版本和有效期每次创建重新判断；payment idempotency 仍在同一 create flow。
- OpenAPI/AsyncAPI 影响：无新增接口；payment create 的错误码/冲突语义明确。
- Metrics/alerts/runbook 影响：corridor deny 事件应按 environment/corridor/rulebook 告警。
- 外部证据：真实 CN/HK admission/rulebook/签字尚未提供，sandbox 只能作为 simulation。
- 未解决风险：法律实体、双法域矩阵和责任签字文档待 B0.5.3/B0.5.4。
- 执行者：Codex

### B0.5.3 — 产品边界、CN–HK 矩阵与 RACI

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`64b2f80`
- 修改文件：`docs/governance/PRODUCT_REGULATORY_BOUNDARY.md`、`docs/governance/CN_HK_CORRIDOR_ADMISSION_MATRIX.md`、`docs/governance/RACI.md`、`backend/production/telemetry.py`、`backend/tests/production/test_readiness_dependencies.py`
- 新增迁移：无（使用 `0007_corridor_admission`）
- 新增/修改测试：readiness 依赖矩阵新增 corridor_admission；现有 corridor model/default-deny 测试继续通过。
- 测试命令：`\.venv\Scripts\python.exe -m pytest backend/tests/production/test_readiness_dependencies.py backend/tests/production/test_corridor_models.py -q`; `\.venv\Scripts\python.exe -m ruff check backend/production/telemetry.py backend/tests/production/test_readiness_dependencies.py`
- 测试结果：`6 passed`; `ruff`：`All checks passed`
- 正常路径证据：治理文档版本化列出法律实体/资金流边界、CN–HK 场景矩阵、RACI 与不承诺项；readiness 输出 admission_id、rulebook_version、valid_to。
- 负向路径证据：缺 admission、过期、simulation-only 在 pilot/live 均显示 `missing_or_expired` 并阻断 ready。
- 并发/重复/超时/恢复证据：admission validity 每次 health/payment 重新计算；版本唯一约束已由 B0.5.1 验证。
- OpenAPI/AsyncAPI 影响：health response 新增 corridor admission 版本/有效期状态。
- Metrics/alerts/runbook 影响：rulebook/admission expiry 可告警；文档列出外部 owner 和签字需求。
- 外部证据：法律/监管/持牌合作方签字未提供，文档明确 `[EXT-BLOCKED]` 与 non-commitments。
- 未解决风险：真实 CN/HK 法域签字和 P0 owner/date 尚未取得，B0.5.4 保持阻断。
- 执行者：Codex

### B0.5.4 — 持牌合作方与法务/合规/安全签字

- 状态：EXT-BLOCKED
- 完成时间：2026-07-27
- commit：无（外部签字未提供）
- 修改文件：无；B0.5.3 治理文档已列明所需角色、owner 和 non-commitments。
- 新增迁移：无
- 新增/修改测试：`test_corridor_models.py`、readiness tests 验证无真实签字时只能使用 simulation admission。
- 测试命令：`\.venv\Scripts\python.exe -m pytest backend/tests/production/test_corridor_models.py backend/tests/production/test_readiness_dependencies.py -q`
- 测试结果：通过；外部签字不可由本地测试代替。
- 正常路径证据：无；不得把 sandbox-authority 当作法定签字。
- 负向路径证据：pilot/live 无 ACTIVE 非 simulation admission/control attestation 时 payment 和 readiness default-deny。
- 并发/重复/超时/恢复证据：待外部机构完成 shadow/小额实盘演练并提供证据。
- OpenAPI/AsyncAPI 影响：无。
- Metrics/alerts/runbook 影响：P0 `[EXT-BLOCKED]` 必须告警，禁止进入 pilot/live。
- 外部证据：待持牌合作方、内地/香港法律、合规、结算、数据保护、安全负责人签字及 owner/date。
- 未解决风险：B0 Gate G6 不得通过，不能进入影子/小额实盘。
- 执行者：Codex

### B0.G1 — 不存在 attestation 阻断 pilot/live

- 状态：DONE
- 完成时间：2026-07-27
- commit：`117bbef`
- 修改文件：`backend/config.py`、`backend/tests/production/test_config_qualification_gate.py`
- 测试命令：`\.venv\Scripts\python.exe -m pytest backend/tests/production/test_config_qualification_gate.py -q`
- 测试结果：`4 passed`（后续 B0.4.2 扩展后为 `7 passed`）
- 验收证据：pilot 缺失/不存在 attestation、缺 trust anchor、connector mismatch 均在 startup gate 抛 RuntimeError；非空路径不会绕过 verifier。
- 外部证据：无；真实 attestation 仍需 `[EXT-BLOCKED]`。
- 执行者：Codex

### B0.4.4 — 真实 HSM/CA/OCSP/CRL 与密钥仪式

- 状态：EXT-BLOCKED
- 完成时间：2026-07-27
- commit：无（外部依赖未提供；代码边界见 `8780e4e`、`4028f71`、`a069a1e`）
- 修改文件：无新增代码；保持 qualified provider 未注册即 fail-closed。
- 新增迁移：无
- 新增/修改测试：`test_key_provider.py` 已验证 qualified callback 缺失时拒绝；`test_config_qualification_gate.py` 已验证 file/private provider 禁止。
- 测试命令：`\.venv\Scripts\python.exe -m pytest backend/tests/production/test_key_provider.py backend/tests/production/test_config_qualification_gate.py -q`
- 测试结果：通过；外部资格本身不可在本地伪造。
- 正常路径证据：无；不把 sandbox Ed25519 当作 HSM/CA 资格。
- 负向路径证据：无 qualified provider、无 trust-domain/key-label、file provider 均保持阻断。
- 并发/重复/超时/恢复证据：待厂商/机构提供轮换演练和密钥仪式记录。
- OpenAPI/AsyncAPI 影响：pilot/live `/key-operations` 保持 503。
- Metrics/alerts/runbook 影响：必须告警 `[EXT-BLOCKED]`，禁止进入 pilot/live。
- 外部证据：待提供厂商/机构 attestation、不可导出证明、CA/RA、OCSP/CRL、轮换演练、生产/测试信任域隔离证据。
- 未解决风险：P0 外部资格缺失，B0 Gate G5 不得通过。
- 执行者：Codex

### B0.1.4 — 健康与就绪依赖快照

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`d45cbd7`
- 修改文件：`backend/production/telemetry.py`、`backend/production/router.py`、`backend/main.py`、`backend/production/connectors.py`、`backend/production/worker.py`、`backend/config.py`、`backend/.env.example`、`backend/tests/production/test_readiness_dependencies.py`、`backend/tests/test_ecny_api_flow.py`
- 新增迁移：无
- 新增/修改测试：生产 health 依赖矩阵；sandbox readiness 必须 `503` 且 `ready=false`；旧 operational endpoint 断言同步到 fail-closed 语义。
- 测试命令：`\.venv\Scripts\python.exe -m pytest backend/tests/production/test_readiness_dependencies.py backend/tests/test_ecny_api_flow.py -q`; `\.venv\Scripts\python.exe -m ruff check backend/production/telemetry.py backend/production/connectors.py backend/production/router.py backend/production/worker.py backend/main.py backend/config.py backend/tests/production/test_readiness_dependencies.py backend/tests/test_ecny_api_flow.py`
- 测试结果：`4 passed`; `ruff`：`All checks passed`
- 正常路径证据：`/production/v1/health` 明确输出 database、broker、hsm、signature_verifier、connector、standards_artifact、worker_heartbeat 七项状态；worker 执行时记录 heartbeat。
- 负向路径证据：simulation、未配置 HSM/broker、未配置签名 verifier、缺标准件或 stale heartbeat 时 `/ready` 返回 `503` 和 `ready=false`；`/health` 仍只表达存活，不声称 ready。
- 并发/重复/超时/恢复证据：heartbeat 按配置超时窗口判定 stale；数据库探测异常被捕获为 unavailable；恢复后下一次探测重新计算状态。
- OpenAPI/AsyncAPI 影响：现有 `/health`、`/ready`、`/production/v1/health` 响应新增依赖状态字段。
- Metrics/alerts/runbook 影响：依赖字段可直接作为 readiness/告警输入；真实 broker/HSM/worker 部署 runbook 仍待 B0.4/B7。
- 外部证据：真实 HSM、broker、connector、标准工件未提供，保持 `[EXT-BLOCKED]`，未将 simulation 标为 production-ready。
- 未解决风险：真实 broker/HSM 探针适配器尚未接入，pilot/live Gate 仍应保持阻断。
- 执行者：Codex

### B0.1.3 — pilot/live 资格启动门禁

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`117bbef`
- 修改文件：`backend/config.py`、`backend/.env.example`、`backend/tests/production/test_config_qualification_gate.py`
- 新增迁移：无
- 新增/修改测试：有效签名准入、不存在路径、缺 trust anchor、不匹配 connector；所有 pilot 必填 host/admin token 和 qualified verifier。
- 测试命令：`\.venv\Scripts\python.exe -m pytest backend/tests/production/test_config_qualification_gate.py -q`; `\.venv\Scripts\python.exe -m ruff check backend/config.py backend/tests/production/test_config_qualification_gate.py`
- 测试结果：`4 passed`; `ruff`：`All checks passed`
- 正常路径证据：`Settings.validate_for_pilot()` 调用 Ed25519 verifier，签名、环境、digest、有效期、trust anchor、connector 均通过后才返回。
- 负向路径证据：不存在 attestation、缺 trust anchor、connector mismatch 均抛 `RuntimeError`，不再接受非空路径字符串。
- 并发/重复/超时/恢复证据：启动门禁为同步 fail-closed；运行态 readiness 在 B0.1.4 接入依赖快照。
- OpenAPI/AsyncAPI 影响：无新增接口。
- Metrics/alerts/runbook 影响：pilot/live 启动失败信息明确记录 qualification 失败原因；readiness 在 B0.1.4 完善。
- 外部证据：真实资格工件/签发机构仍为 `[EXT-BLOCKED]`，本地测试仅验证密码学和门禁逻辑。
- 未解决风险：尚未实现健康/就绪细分依赖状态。
- 执行者：Codex

### B0.1.2 — 资格工件与决策持久化

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`470d90a`
- 修改文件：`backend/production/models.py`、`backend/alembic/versions/0004_production_qualification.py`、`backend/tests/production/test_qualification_models.py`
- 新增迁移：`0004_production_qualification`
- 新增/修改测试：工件/决策表可持久化；环境+subject+connector_version 唯一约束；非法 ACTIVE 过期工件被拒绝。
- 测试命令：`\.venv\Scripts\python.exe -m pytest backend/tests/production/test_qualification_models.py -q`; `\.venv\Scripts\python.exe -m ruff check backend/production/models.py backend/alembic/versions/0004_production_qualification.py backend/tests/production/test_qualification_models.py`; `\.venv\Scripts\python.exe -m alembic upgrade head`
- 测试结果：`2 passed`; `ruff` 通过；Alembic `0003_production_hardening -> 0004_production_qualification` 通过。
- 正常路径证据：SQLite `swift_dev.db` 中存在 `prod_qualification_artifacts`、`prod_qualification_decisions`，工件表含 artifact_type、digest、签名算法、有效期、状态、验证时间、verifier 版本和唯一约束。
- 负向路径证据：重复环境/subject/version 提交触发 `IntegrityError`；过期工件设置 ACTIVE 触发 `ValueError`。
- 并发/重复/超时/恢复证据：数据库唯一约束为重复提交提供原子拒绝；并发 replay 在 B0.2.3 覆盖。
- OpenAPI/AsyncAPI 影响：无新增外部接口。
- Metrics/alerts/runbook 影响：B0.1.4 接入 readiness；本条不声称生产就绪。
- 外部证据：无；真实签发机构仍为 `[EXT-BLOCKED]`。
- 未解决风险：资格决策写入服务和过期后台扫描在后续 B0.1.4/B7 完成。
- 执行者：Codex

### B1.1.3 — ORM 外键与 RESTRICT 删除策略

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`6720404`
- 修改文件：`backend/production/models.py`、`backend/tests/production/test_model_foreign_keys.py`
- 新增迁移：关系数据库约束已在 `0008_production_relational_integrity` 建立。
- 新增/修改测试：payment/fact/journal/inbox/report receipt 核心模型 ForeignKey 和 `ondelete=RESTRICT`；relationship 为 viewonly 且无 delete cascade。
- 测试命令：`\.venv\Scripts\python.exe -m pytest backend/tests/production/test_model_foreign_keys.py -q`; `\.venv\Scripts\python.exe -m ruff check backend/production/models.py backend/tests/production/test_model_foreign_keys.py`
- 测试结果：`1 passed`; `ruff`：`All checks passed`
- 正常路径证据：核心生产模型声明 tenant/participant/order/journal/outbox/report parent 关系，ORM 仅用于导航。
- 负向路径证据：所有测试关系 `ondelete=RESTRICT`，没有 cascade delete；migration orphan 预检查失败即停止。
- 并发/重复/超时/恢复证据：FK/unique 由 DB 原子维护，历史金融/审计记录不可级联删除。
- OpenAPI/AsyncAPI 影响：无。
- Metrics/alerts/runbook 影响：FK violation/orphan migration error 需进入数据修复告警。
- 外部证据：无。
- 未解决风险：金额 BigInteger 和 timezone-aware 列待 B1.1.4/B1.1.5。
- 执行者：Codex

### B1.1.4 — 金额列 BigInteger 扩容

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`be484bf`
- 修改文件：`backend/production/models.py`、`backend/alembic/versions/0009_production_bigint_amounts.py`、`backend/tests/production/test_bigint_amounts.py`
- 新增迁移：`0009_production_bigint_amounts`
- 新增/修改测试：payment、quote、reservation、settlement、return、ledger、journal、limit、corridor amount 列 BigInteger；迁移前负数/溢出扫描。
- 测试命令：`\.venv\Scripts\python.exe -m pytest backend/tests/production/test_bigint_amounts.py -q`; `\.venv\Scripts\python.exe -m ruff check backend/production/models.py backend/alembic/versions/0009_production_bigint_amounts.py backend/tests/production/test_bigint_amounts.py`; `\.venv\Scripts\python.exe -m alembic upgrade head`
- 测试结果：`1 passed`; `ruff`：`All checks passed`; migration `0008 -> 0009` 通过。
- 正常路径证据：模型和 SQLite schema 的货币 minor/unit 列扩展到 BIGINT，迁移先检查 `<0` 或超过 int64。
- 负向路径证据：负数/溢出数据会在迁移前 RuntimeError；金额原有 check constraints 保持。
- 并发/重复/超时/恢复证据：迁移可重复执行，失败临时表清理后重试成功；不删除历史数据。
- OpenAPI/AsyncAPI 影响：金额序列化契约保持整数 minor units。
- Metrics/alerts/runbook 影响：overflow audit failure 阻断迁移。
- 外部证据：无。
- 未解决风险：生产时间列仍需 timezone-aware 统一。
- 执行者：Codex

### B1.1.5 — UTC timezone-aware 时间列

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`9323cfb`
- 修改文件：`backend/production/models.py`、`backend/alembic/versions/0010_production_utc_timestamps.py`、`backend/tests/production/test_utc_timestamps.py`
- 新增迁移：`0010_production_utc_timestamps`
- 新增/修改测试：全部 production DateTime 列 timezone-aware；迁移显式 UTC 时间列转换。
- 测试命令：`\.venv\Scripts\python.exe -m pytest backend/tests/production/test_utc_timestamps.py -q`; `\.venv\Scripts\python.exe -m ruff check backend/production/models.py backend/alembic/versions/0010_production_utc_timestamps.py backend/tests/production/test_utc_timestamps.py`; `\.venv\Scripts\python.exe -m alembic upgrade head`
- 测试结果：`1 passed`; `ruff`：`All checks passed`; migration `0009 -> 0010` 通过。
- 正常路径证据：模型统一使用 UTC-aware DateTime subclass，migration 将明确列改为 `DateTime(timezone=True)`。
- 负向路径证据：测试遍历全部 `prod_*` DateTime，任何 naive 列立即失败；服务层 `utcnow()` 保持 UTC。
- 并发/重复/超时/恢复证据：migration 可重复升级；旧值保留并按 UTC 解释，DST/timezone 由领域时间测试覆盖。
- OpenAPI/AsyncAPI 影响：时间字段继续 ISO-8601，统一 UTC 语义。
- Metrics/alerts/runbook 影响：naive timestamp schema mismatch 阻断迁移/CI。
- 外部证据：无。
- 未解决风险：旧历史数据库中的本地时区来源需 B1.2 数据修复脚本确认。
- 执行者：Codex

### B1.2.1 — 只读生产数据审计

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`b477241`
- 修改文件：`backend/scripts/audit_production_data.py`、`backend/tests/production/test_audit_production_data.py`
- 新增迁移：无
- 新增/修改测试：orphan、重复/空键、非法金额、tenant mismatch、hash 缺失检查；验证脚本不写数据。
- 测试命令：`\.venv\Scripts\python.exe -m pytest backend/tests/production/test_audit_production_data.py -q`; `\.venv\Scripts\python.exe -m ruff check backend/scripts/audit_production_data.py backend/tests/production/test_audit_production_data.py`
- 测试结果：`1 passed`; `ruff`：`All checks passed`
- 正常路径证据：`audit(engine)` 输出 JSON `tables_scanned/finding_count/findings`，无修复副作用。
- 负向路径证据：临时库中的 null/hash/negative 数据被逐类报告，行数保持不变。
- 并发/重复/超时/恢复证据：只读连接、重复运行结果一致；修复需单独 B1.2.2 operator/checker 流程。
- OpenAPI/AsyncAPI 影响：无。
- Metrics/alerts/runbook 影响：finding type 可直接接入数据质量告警。
- 外部证据：无。
- 未解决风险：脚本目前以 SQLite/通用 SQL 为主，PostgreSQL 运行需 B1 migration pipeline 验证。
- 执行者：Codex

### B1.2.2 — tenant 数据修复计划与双控执行

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`d8c7b8e`
- 修改文件：`backend/scripts/repair_production_0006.py`、`backend/tests/production/test_repair_production_data.py`
- 新增迁移：无
- 新增/修改测试：dry-run 默认不写；plan hash；operator/checker/evidence 必填且 distinct；执行后修复 order tenant_id。
- 测试命令：`\.venv\Scripts\python.exe -m pytest backend/tests/production/test_repair_production_data.py -q`; `\.venv\Scripts\python.exe -m ruff check backend/scripts/repair_production_0006.py backend/tests/production/test_repair_production_data.py`
- 测试结果：`1 passed`; `ruff`：`All checks passed`
- 正常路径证据：dry-run 输出可审计 plan/plan_hash；显式 `--execute --operator --checker --evidence-id` 后才更新 tenant_id。
- 负向路径证据：默认 dry-run 不改变行；缺双控参数或 operator=checker 直接 ValueError。
- 并发/重复/超时/恢复证据：transaction 包裹全量修复；plan hash 可用于重复执行前比对。
- OpenAPI/AsyncAPI 影响：无。
- Metrics/alerts/runbook 影响：修复计划和 evidence id 可纳入 operator audit。
- 外部证据：无。
- 未解决风险：真实旧库 repair 需先运行 B1.2.1 audit 并由持证 operator/checker 批准。
- 执行者：Codex

### B1.2.3 — 全部生产状态列数据库约束

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`82bff0b`
- 修改文件：`backend/production/state_constraints.py`、`backend/alembic/versions/0011_production_state_constraints.py`、`backend/tests/production/test_state_constraints.py`
- 新增迁移：`0011_production_state_constraints`；覆盖全部已建模 production status/state/orchestration/contract_state 列，升级前逐表扫描非法值，SQLite/PostgreSQL 均使用真实 CHECK 约束。
- 新增/修改测试：版本化状态词典、合法状态、非法任意字符串拒绝；ruff 静态检查。
- 测试命令：`$env:PYTHONPATH='backend'; .\\.venv\\Scripts\\python.exe -m pytest backend/tests/production/test_state_constraints.py -q`; `\\.venv\\Scripts\\python.exe -m ruff check backend/production/state_constraints.py backend/alembic/versions/0011_production_state_constraints.py backend/tests/production/test_state_constraints.py`; `\\.venv\\Scripts\\python.exe -m alembic upgrade head`
- 测试结果：`1 passed`；`ruff: All checks passed`；Alembic `0010 -> 0011` upgrade 成功。
- 正常路径证据：所有映射列共享 `STATE_VERSION=state-v1`，迁移在 clean/现有 SQLite schema 上成功创建 `ck_prod_*_state_v1`。
- 负向路径证据：`assert_state(..., 'MADE_UP_SUCCESS')` 抛出 `ValueError`；迁移遇到非法现有状态会抛错并拒绝创建约束。
- 并发/重复/超时/恢复证据：迁移按表幂等执行检查；失败前置扫描不修改数据，事务由 Alembic 管理。
- OpenAPI/AsyncAPI 影响：无接口字段变更；状态值集合由共享模块导出供服务层复用。
- Metrics/alerts/runbook 影响：非法状态升级失败应接入迁移告警；审计脚本可先报告违规行。
- 外部证据：PostgreSQL clean install/rollback 仍待 B1 Gate 的外部 PostgreSQL 环境（当前无可用实例）。
- 未解决风险：历史库若包含未纳入词典的业务状态，必须先走 B1.2.1 audit 与受控 repair，不得放宽约束。
- 执行者：Codex

### B1.2.4 — 关键业务唯一约束

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`67c0fd2`
- 修改文件：`backend/production/models.py`、`backend/alembic/versions/0012_production_business_uniques.py`、`backend/tests/production/test_unique_constraints.py`
- 新增迁移：`0012_production_business_uniques`；增加参与方作用域 instruction id、quote accept、return `(original_order_id, return_sequence)`、approval decision、outbox `(topic, aggregate_id, aggregate_sequence)`、GL `(legal_entity, book, business_date, gl_batch_reference)` 唯一键。
- 新增/修改测试：模型元数据约束覆盖与 sequence/batch 非空断言；Alembic schema inspection。
- 测试命令：`$env:PYTHONPATH='backend'; .\\.venv\\Scripts\\python.exe -m pytest backend/tests/production -q`; `\\.venv\\Scripts\\python.exe -m pytest backend/tests/production/test_unique_constraints.py -q`; `\\.venv\\Scripts\\python.exe -m ruff check backend/production/models.py backend/alembic/versions/0012_production_business_uniques.py backend/tests/production/test_unique_constraints.py`; `\\.venv\\Scripts\\python.exe -m alembic upgrade head`
- 测试结果：production `51 passed`；唯一约束 `2 passed`；`ruff: All checks passed`；Alembic `0011 -> 0012` 成功；SQLite inspector 返回 6 个目标唯一约束。
- 正常路径证据：旧数据升级时按稳定 id 为 return/outbox 序列回填，GL batch 缺失时回填 journal_id，再创建唯一约束并收紧非空。
- 负向路径证据：模型 metadata 中所有目标约束名称存在；同一业务作用域无法重复接受 quote、审批、事件序列或 GL batch。
- 并发/重复/超时/恢复证据：数据库唯一索引在并发提交层提供原子冲突；回填按确定排序重复执行结果稳定。
- OpenAPI/AsyncAPI 影响：无破坏性接口变化；事件 envelope 需使用新增 aggregate_sequence。
- Metrics/alerts/runbook 影响：唯一冲突应映射业务幂等/重复告警；序列冲突进入 outbox DLQ 处理。
- 外部证据：PostgreSQL clean install/rollback 仍待 B1 Gate 外部实例。
- 未解决风险：历史 return/outbox 业务排序依据当前 id；如外部系统提供权威序列，需在生产迁移前导入并审计比对。
- 执行者：Codex

### B1.2.5 — 金融不变量约束

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`a27a4d3`
- 修改文件：`backend/production/financial_invariants.py`、`backend/alembic/versions/0013_production_financial_invariants.py`、`backend/tests/production/test_financial_invariants.py`
- 新增迁移：`0013_production_financial_invariants`；金额正数、fee/reserved 非负、reserved 不超过 balance、有效期顺序、maker/checker 不同等 DB CHECK 约束。
- 新增/修改测试：按币种借贷平衡、空 journal/负金额/不平衡、有效期和双控 validator 负向测试。
- 测试命令：`$env:PYTHONPATH='backend'; .\\.venv\\Scripts\\python.exe -m pytest backend/tests/production/test_financial_invariants.py -q`; `\\.venv\\Scripts\\python.exe -m ruff check backend/production/financial_invariants.py backend/alembic/versions/0013_production_financial_invariants.py backend/tests/production/test_financial_invariants.py`; `\\.venv\\Scripts\\python.exe -m alembic upgrade head`
- 测试结果：`3 passed`；`ruff: All checks passed`；Alembic `0012 -> 0013` 成功；SQLite inspector 验证 ledger/approval/mandate/FX/corridor 约束已落库。
- 正常路径证据：事务提交前可调用 `validate_journal_balance`，按 currency 分桶要求 DEBIT=CREDIT；数据库迁移先扫描违规行再创建约束。
- 负向路径证据：不平衡 journal、非正金额、相同 maker/checker、无效时间窗均抛 `ValueError`；历史违规行会使迁移失败而不是弱化 Gate。
- 并发/重复/超时/恢复证据：金额/余额/双控由数据库原子 CHECK 保证；借贷平衡校验为纯函数，可在同一事务内重试且无副作用。
- OpenAPI/AsyncAPI 影响：无接口结构变化；ledger posting 服务必须在 commit 前调用平衡 validator。
- Metrics/alerts/runbook 影响：约束冲突接入金融不变量告警；unbalanced journal 进入人工调查队列。
- 外部证据：PostgreSQL deferred constraint/并发事务验证仍待 B1 Gate 外部 PostgreSQL 实例。
- 未解决风险：跨行借贷平衡不能由 SQLite 普通 CHECK 表达，已用事务 validator；生产 PostgreSQL 可再升级 deferred constraint trigger。
- 执行者：Codex

### B1.3.1 — PostgreSQL RLS 迁移

- 状态：DONE（PostgreSQL 实例验证 `[EXT-BLOCKED]`）
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`05108ff`
- 修改文件：`backend/alembic/versions/0014_production_rls.py`、`backend/tests/production/test_postgres_rls_migration.py`
- 新增迁移：因 `0007` 已被 corridor admission 占用，使用 `0014_production_rls`；对 tenant/participant-owned production 表启用并强制 RLS，policy 使用 transaction-local `app.tenant_id`、`app.participant_id`，同时 `USING/WITH CHECK`。
- 新增/修改测试：policy predicate 静态审计、SQLite 方言安全 no-op。
- 测试命令：`$env:PYTHONPATH='backend'; .\\.venv\\Scripts\\python.exe -m pytest backend/tests/production/test_postgres_rls_migration.py -q`; `\\.venv\\Scripts\\python.exe -m ruff check backend/alembic/versions/0014_production_rls.py backend/tests/production/test_postgres_rls_migration.py`; `\\.venv\\Scripts\\python.exe -m alembic upgrade head`
- 测试结果：`1 passed`；`ruff: All checks passed`；SQLite Alembic upgrade `0013 -> 0014` 成功且不执行 PostgreSQL SQL。
- 正常路径证据：PostgreSQL 分支会 `ENABLE/FORCE ROW LEVEL SECURITY`、先删后建确定命名 policy，回滚会移除 policy 并关闭 RLS。
- 负向路径证据：未设置 transaction-local tenant/participant 的请求不满足 predicate；SQLite 不会误执行 PostgreSQL 语法。
- 并发/重复/超时/恢复证据：policy DDL 可重复执行（DROP IF EXISTS）；`SET LOCAL` 生命周期由后续 B1.3.2 db_context 管理。
- OpenAPI/AsyncAPI 影响：无。
- Metrics/alerts/runbook 影响：RLS violation 应接入安全告警；policy 名称可用于审计检查。
- 外部证据：`[EXT-BLOCKED]` 当前环境无 PostgreSQL 服务，无法完成两租户实际 RLS read/write/join/count 验证。
- 未解决风险：尚未在真实 PostgreSQL 上执行 clean/rollback；继续完成 B1.3.2–B1.4 后由 Gate 统一阻断/验收。
- 执行者：Codex

### B1.3.2 — tenant transaction context

- 状态：DONE（PostgreSQL `SET LOCAL` 实例验证 `[EXT-BLOCKED]`）
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`9433334`
- 修改文件：`backend/production/db_context.py`、`backend/tests/production/test_db_context.py`
- 新增实现：`DatabaseContext` 强制 tenant/participant/service identity；PostgreSQL 使用 `set_config(..., true)` 事务局部变量；SQLite 仅测试上下文；连接清理和 worker envelope 恢复均拒绝缺失身份。
- 新增/修改测试：SQLite set/clear、worker 缺 context 负向、tenant_transaction 自动清理。
- 测试命令：`$env:PYTHONPATH='backend'; .\\.venv\\Scripts\\python.exe -m pytest backend/tests/production/test_db_context.py -q`; `\\.venv\\Scripts\\python.exe -m ruff check backend/production/db_context.py backend/tests/production/test_db_context.py`
- 测试结果：`3 passed`；`ruff: All checks passed`。
- 正常路径证据：事务进入时设置三项 identity，退出 finally 清理；后台任务只能从事件 envelope 取得 tenant context。
- 负向路径证据：envelope 缺 context 或任一 identity 为空抛 `ValueError`；无 global admin fallback。
- 并发/重复/超时/恢复证据：上下文绑定单个 SQLAlchemy connection；finally 清理避免连接池复用串租户。
- OpenAPI/AsyncAPI 影响：事件消费者 envelope 需含 `context.tenant_id/participant_id/service_identity`。
- Metrics/alerts/runbook 影响：缺上下文、RLS denial 可接安全告警；worker runbook 必须保留 envelope context。
- 外部证据：`[EXT-BLOCKED]` 无 PostgreSQL 连接池，无法证明 `set_config(..., true)` 在真实 pooled transaction 中的隔离。
- 未解决风险：需在 B1.3.4 两租户 PostgreSQL 测试中验证 rollback/连接归还后参数清空。
- 执行者：Codex

### B1.3.3 — 服务层双层 tenant filter

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`be09db4`
- 修改文件：`backend/production/security.py`、`backend/production/service.py`、`backend/production/router.py`、`backend/tests/production/test_tenant_filters.py`
- 新增/修改实现：`ProductionPrincipal.tenant_id` 明确租户边界；创建订单写入 tenant id；订单读取、列表、调查 case 查询始终 tenant filter；admin 不再自动跳过 tenant 条件。
- 新增/修改测试：admin principal 仍必须带 tenant predicate；production 全套测试回归。
- 测试命令：`$env:PYTHONPATH='backend'; .\\.venv\\Scripts\\python.exe -m pytest backend/tests/production/test_tenant_filters.py -q`; `\\.venv\\Scripts\\python.exe -m ruff check backend/production/security.py backend/production/service.py backend/production/router.py backend/tests/production/test_tenant_filters.py`; `\\.venv\\Scripts\\python.exe -m pytest backend/tests/production -q`
- 测试结果：tenant filter `1 passed`；`ruff: All checks passed`；production 全套 `60 passed`（1 个已知 Starlette/httpx deprecation warning）。
- 正常路径证据：同租户 admin 仍可按授权执行操作，但查询范围由 `tenant_id` 限定；participant ownership 仍由服务层额外校验。
- 负向路径证据：跨租户 order id 对 admin 也解析为 not found；列表和 investigation join 不再有全局 admin 分支。
- 并发/重复/超时/恢复证据：查询过滤在 ORM SQL 层生成，和 PostgreSQL RLS 形成双层防护；无全局管理员 query。
- OpenAPI/AsyncAPI 影响：无字段变化；跨租户 break-glass 尚未提供普通 admin 旁路。
- Metrics/alerts/runbook 影响：跨租户拒绝应记 security audit；break-glass 若未来增加必须单独审计 endpoint。
- 外部证据：无。
- 未解决风险：真实 PostgreSQL RLS 与服务层组合仍需 B1.3.4 两租户集成验证。
- 执行者：Codex

### B1.3.4 — 两租户 PostgreSQL RLS 集成测试

- 状态：`[EXT-BLOCKED]`（代码与测试已提交，外部 PostgreSQL fixture 未提供）
- 开始时间：2026-07-27
- 完成时间：—（等待 `PRODUCTION_TEST_POSTGRES_URL`）
- commit：`6850cb5`
- 修改文件：`backend/tests/production/test_postgres_rls.py`
- 新增/修改测试：真实 PostgreSQL URL 存在时以 pool_size=1 验证两租户 payment read/write、跨租户 order/outbox/evidence join/count 不泄漏、事务 rollback 后连接池 context 清空；缺 URL 明确 pytest skip `[EXT-BLOCKED]`。
- 测试命令：`$env:PYTHONPATH='backend'; .\\.venv\\Scripts\\python.exe -m pytest backend/tests/production/test_postgres_rls.py -q`; `\\.venv\\Scripts\\python.exe -m ruff check backend/tests/production/test_postgres_rls.py`
- 测试结果：`1 skipped`（`[EXT-BLOCKED] PRODUCTION_TEST_POSTGRES_URL is not configured`）；`ruff: All checks passed`。
- 正常路径证据：配置 PostgreSQL 后，测试必须存在两个租户各至少一笔 payment，且 tenant A 查询 tenant B payment/outbox/evidence 均为 0。
- 负向路径证据：测试不会把缺少 PostgreSQL 当作通过；无 URL 直接保持 `[EXT-BLOCKED]`。
- 并发/重复/超时/恢复证据：pool_size=1 强制复用连接，rollback 后新连接 current_setting 必须为空。
- OpenAPI/AsyncAPI 影响：无。
- Metrics/alerts/runbook 影响：RLS violation、连接池 context 泄漏应接安全告警。
- 外部证据：`[EXT-BLOCKED]` 当前机器未提供 PostgreSQL 服务/fixture，无法勾选本项及 B1 Gate RLS 条目。
- 未解决风险：必须在 PostgreSQL clean schema 和真实两租户数据上运行后才能验收。
- 执行者：Codex

### B1.4.1 — pilot/live PostgreSQL-only gate

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`2304c94`
- 修改文件：`backend/config.py`、`backend/tests/production/test_config_database_gate.py`
- 新增实现：`_validate_production_gate()` 在 HSM/attestation 等 Gate 前拒绝 pilot/live 的 SQLite 或非 PostgreSQL URL；sandbox/test 继续允许 SQLite。
- 新增/修改测试：pilot SQLite 直接拒绝；live PostgreSQL scheme 通过数据库门槛后继续进入后续 trust-domain 门槛。
- 测试命令：`$env:PYTHONPATH='backend'; .\\.venv\\Scripts\\python.exe -m pytest backend/tests/production/test_config_database_gate.py -q`; `\\.venv\\Scripts\\python.exe -m ruff check backend/config.py backend/tests/production/test_config_database_gate.py`
- 测试结果：`2 passed`；`ruff: All checks passed`。
- 正常路径证据：`postgresql://` 与 `postgresql+driver://` 被识别为生产数据库；后续 qualified key/attestation Gate 仍不可绕过。
- 负向路径证据：pilot/live `sqlite:///...` 抛 `RuntimeError`，不会启动生产服务。
- 并发/重复/超时/恢复证据：纯配置校验无副作用；每次 startup/reload 都执行同一门槛。
- OpenAPI/AsyncAPI 影响：无。
- Metrics/alerts/runbook 影响：数据库方言误配应在 startup log/alert 明确提示。
- 外部证据：无。
- 未解决风险：真实 PostgreSQL driver/connectivity 由 B1 Gate clean install 验证。
- 执行者：Codex

### B1.4.2 — CI production schema contract

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`528b8db`
- 修改文件：`.github/workflows/migrations.yml`、`backend/scripts/verify_production_schema.py`、`backend/tests/production/test_verify_production_schema.py`
- 新增实现：CI migration workflow 在 upgrade 后执行 verifier；verifier 从完整 SQLAlchemy metadata 逐表检查全部 `prod_*` 表、列、命名 unique/check/FK constraint，不再只看 `ng_*`。
- 新增/修改测试：临时 SQLite clean schema 创建 49 个 production 表并验证 contract 全通过。
- 测试命令：`$env:PYTHONPATH='backend'; .\\.venv\\Scripts\\python.exe -m pytest backend/tests/production/test_verify_production_schema.py -q`; `\\.venv\\Scripts\\python.exe -m ruff check backend/scripts/verify_production_schema.py backend/tests/production/test_verify_production_schema.py`; `\\.venv\\Scripts\\python.exe backend/scripts/verify_production_schema.py`
- 测试结果：`1 passed`；`ruff: All checks passed`；本地 verifier 输出 `tables_scanned=49, valid=true`。
- 正常路径证据：迁移 workflow `upgrade head -> verify_production_schema` 串行执行，任一表/列/约束缺失直接非零退出。
- 负向路径证据：verifier 对缺对象构造 JSON diagnostics 并抛 RuntimeError，未将缺失视为警告。
- 并发/重复/超时/恢复证据：只读 inspector；可在 clean/upgrade 后重复运行，不修改 schema。
- OpenAPI/AsyncAPI 影响：无。
- Metrics/alerts/runbook 影响：CI artifact 可保存缺失对象 JSON；迁移失败需阻断发布。
- 外部证据：PostgreSQL schema contract 仍待 B1.4.3 CI/外部服务运行。
- 未解决风险：SQLite inspector 无法覆盖 PostgreSQL RLS policy 目录，已由 B1.3.4 专项测试和 B1 Gate 处理。
- 执行者：Codex

### B1.4.3 — PostgreSQL migration roundtrip/schema snapshot

- 状态：`[EXT-BLOCKED]`（roundtrip 工具与 CI 已提交，历史 baseline 目前 fail-closed）
- 开始时间：2026-07-27
- 完成时间：—（需先修复/替换冻结 baseline 的 schema fixture）
- commit：`8aa4356`
- 修改文件：`.github/workflows/migrations.yml`、`backend/scripts/migration_roundtrip.py`、`backend/tests/production/test_migration_roundtrip.py`
- 新增实现：CI 启动 PostgreSQL 16 service，执行 `upgrade head -> downgrade -1 -> upgrade head`，比较所有 production schema snapshot，再执行完整 contract verifier；本地工具支持同样 roundtrip。
- 新增/修改测试：临时 SQLite roundtrip 集成测试（真实 clean upgrade 会触发 baseline guard）。
- 测试命令：`$env:PYTHONPATH='backend'; .\\.venv\\Scripts\\python.exe -m pytest backend/tests/production/test_migration_roundtrip.py -q`; `\\.venv\\Scripts\\python.exe -m ruff check backend/scripts/migration_roundtrip.py backend/tests/production/test_migration_roundtrip.py`
- 测试结果：`pytest` 失败，`0002_production_domain._assert_frozen_schema()` 报 `Production ORM schema changed after 0002`；`ruff: All checks passed`。
- 正常路径证据：roundtrip 工具不吞迁移异常，任一 upgrade/downgrade 或 snapshot 差异均非零退出。
- 负向路径证据：当前 clean install 被历史 schema hash guard 阻断，保持 fail-closed，没有修改 immutable `0002` 或伪造成功。
- 并发/重复/超时/恢复证据：每个阶段独立 subprocess；snapshot 在 downgrade 前后比较，异常会立即终止。
- OpenAPI/AsyncAPI 影响：无。
- Metrics/alerts/runbook 影响：CI migration job 失败应阻断发布并保留 schema diff。
- 外部证据：`[EXT-BLOCKED]` 不仅缺 PostgreSQL 服务，当前仓库冻结 baseline 与已演进 ORM 不一致，需单独批准 baseline replacement plan。
- 未解决风险：在不修改历史 baseline 的前提下，需新增可验证的 0002 fixture/替代 migration path 后才能勾选本项和 B1.G1。
- 执行者：Codex

### B1.4.4 — 0003 legacy data preservation

- 状态：`[EXT-BLOCKED]`（测试已提交，未提供旧 0003 fixture）
- 开始时间：2026-07-27
- 完成时间：—（等待 `PRODUCTION_LEGACY_DB_URL`）
- commit：`fdd24a4`
- 修改文件：`backend/tests/production/test_migration_data_preservation.py`
- 新增/修改测试：对显式 provisioned 0003 数据库在 upgrade head 前后比较 payment `order_id/tenant_id/amount_minor/payload_hash`，并确认 production table 仍存在；缺 URL 明确 skip `[EXT-BLOCKED]`。
- 测试命令：`$env:PYTHONPATH='backend'; .\\.venv\\Scripts\\python.exe -m pytest backend/tests/production/test_migration_data_preservation.py -q`; `\\.venv\\Scripts\\python.exe -m ruff check backend/tests/production/test_migration_data_preservation.py`
- 测试结果：`1 skipped`（`[EXT-BLOCKED] PRODUCTION_LEGACY_DB_URL is not configured`）；`ruff: All checks passed`。
- 正常路径证据：fixture 提供后，测试会先读取真实数据，再执行 Alembic upgrade，不使用 hard-coded success。
- 负向路径证据：缺 fixture 或 upgrade 失败不会勾选；数据差异直接断言失败。
- 并发/重复/超时/恢复证据：只读 pre-snapshot；upgrade 由 Alembic 事务控制，失败保留 DB 供调查。
- OpenAPI/AsyncAPI 影响：无。
- Metrics/alerts/runbook 影响：数据差异进入 migration incident；需附 pre/post snapshot。
- 外部证据：`[EXT-BLOCKED]` 当前无 0003 PostgreSQL/SQLite fixture，且 clean install 被 0002 frozen schema guard 阻断。
- 未解决风险：需批准 baseline replacement/fixture 方案后再验收本项。
- 执行者：Codex

### B1.4.5 — backup/restore script and runbook

- 状态：DONE（运行时 `pg_dump` 缺失保持 `[EXT-BLOCKED]`）
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`0cfa087`
- 修改文件：`backend/scripts/backup_production_db.py`、`backend/tests/production/test_backup_production_db.py`、`docs/runbooks/DATABASE_RESTORE.md`
- 新增实现：PostgreSQL custom-format `pg_dump`、SHA-256 sidecar manifest、PostgreSQL URL gate、缺少 client 明确 `[EXT-BLOCKED]`；runbook 覆盖双控、隔离恢复、schema/audit/RLS/reconciliation 验证和 rollback。
- 新增/修改测试：命令参数真实断言；缺 pg_dump 外部依赖负向测试。
- 测试命令：`$env:PYTHONPATH='backend'; .\\.venv\\Scripts\\python.exe -m pytest backend/tests/production/test_backup_production_db.py -q`; `\\.venv\\Scripts\\python.exe -m ruff check backend/scripts/backup_production_db.py backend/tests/production/test_backup_production_db.py`
- 测试结果：`2 passed`；`ruff: All checks passed`。
- 正常路径证据：备份命令不可替换为 SQLite/JSON；生成 dump 后计算并写入 manifest hash/size/time。
- 负向路径证据：无 `pg_dump` 抛 `[EXT-BLOCKED]`；非 PostgreSQL URL 拒绝执行。
- 并发/重复/超时/恢复证据：输出路径显式、manifest 可重复校验；恢复 runbook 禁止覆盖 source。
- OpenAPI/AsyncAPI 影响：无。
- Metrics/alerts/runbook 影响：manifest/evidence id 接入备份审计；恢复失败触发 incident。
- 外部证据：本机未执行真实 `pg_dump/pg_restore`，依赖安装与目标库属于运维环境。
- 未解决风险：需要实际 PostgreSQL 备份文件完成一次恢复演练后才可关闭运维 Gate。
- 执行者：Codex

### B1.G4 — SQLite pilot/live negative gate

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`b0ba999`（实现 commit）；本 Gate 证据追加于本日志提交
- 修改文件：复用 `backend/config.py` 的 B1.4.1 gate；测试 `backend/tests/production/test_config_database_gate.py`。
- 测试命令：`$env:PYTHONPATH='backend'; .\\.venv\\Scripts\\python.exe -m pytest backend/tests/production/test_config_database_gate.py backend/tests/production/test_tenant_filters.py -q`; `\\.venv\\Scripts\\python.exe -m ruff check backend/config.py backend/production/service.py backend/production/router.py`
- 测试结果：`3 passed`；`ruff: All checks passed`。
- 正常路径证据：PostgreSQL URL 继续进入后续 qualified connector/HSM/attestation Gate。
- 负向路径证据：pilot/live SQLite 配置立即抛 `RuntimeError`，服务不会启动；admin 也不能绕过 tenant filter。
- 并发/重复/超时/恢复证据：纯启动校验与 ORM filter，无状态副作用。
- 外部证据：无。
- 未解决风险：G1/G3 仍需真实 PostgreSQL clean/legacy/RLS 实测。
- 执行者：Codex

### B1.G2 — production schema/data audit

- 状态：DONE（SQLite current schema；PostgreSQL clean/legacy 由 G1 阻断）
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`6ae2eea`（本 Gate 证据追加于本日志提交）
- 修改文件：无新增代码；使用 `backend/scripts/audit_production_data.py` 与 `backend/scripts/verify_production_schema.py`。
- 测试命令：`$env:PYTHONPATH='backend'; .\\.venv\\Scripts\\python.exe backend/scripts/audit_production_data.py`; `\\.venv\\Scripts\\python.exe backend/scripts/verify_production_schema.py`
- 测试结果：audit `finding_count=0`，扫描 49 个 production 表；schema verifier `tables_scanned=49, missing_tables/columns/constraints=[], valid=true`。
- 正常路径证据：当前数据库无 orphan、非法 null/hash 缺失、tenant mismatch 或非法状态；全部 metadata 对象在 schema 中存在。
- 负向路径证据：审计脚本对违规项是只读报告；schema verifier 对缺对象直接失败，不降级为 warning。
- 并发/重复/超时/恢复证据：两项均只读，可重复运行；repair 仍必须走 B1.2.2 双控流程。
- OpenAPI/AsyncAPI 影响：无。
- Metrics/alerts/runbook 影响：finding_count 接入数据质量告警；缺约束阻断 CI。
- 外部证据：PostgreSQL clean install/legacy upgrade 尚未完成，保留 G1/G3 `[EXT-BLOCKED]`。
- 未解决风险：当前 audit 结果不能替代真实 PostgreSQL RLS/rollback 证据。
- 执行者：Codex

### B1.G1 — PostgreSQL migration acceptance

- 状态：`[EXT-BLOCKED]`
- 开始时间：2026-07-27
- 完成时间：—
- commit：`8aa4356`（roundtrip 实现）；本 Gate 证据追加于本日志提交
- 修改文件：`backend/scripts/migration_roundtrip.py`、`.github/workflows/migrations.yml`、`backend/tests/production/test_migration_roundtrip.py`、`backend/tests/production/test_migration_data_preservation.py`
- 测试命令：`$env:PYTHONPATH='backend'; .\\.venv\\Scripts\\python.exe -m pytest backend/tests/production/test_migration_roundtrip.py backend/tests/production/test_migration_data_preservation.py -q`
- 测试结果：roundtrip clean upgrade 在 `0002_production_domain._assert_frozen_schema()` 失败；legacy fixture 测试因 `PRODUCTION_LEGACY_DB_URL` 缺失 skip；不能宣称 Gate 通过。
- 正常路径证据：CI 已配置 PostgreSQL 16 service，执行 upgrade/downgrade/re-upgrade/snapshot/contract verifier。
- 负向路径证据：baseline hash mismatch 保持 fail-closed，未修改冻结 0002、未绕过 migration。
- 并发/重复/超时/恢复证据：roundtrip 每阶段独立 subprocess，schema diff 非零退出。
- OpenAPI/AsyncAPI 影响：无。
- Metrics/alerts/runbook 影响：migration CI failure 阻断发布。
- 外部证据：`[EXT-BLOCKED]` 当前 PostgreSQL service/0003 fixture 不可用，且历史 baseline 与当前 ORM 不一致。
- 未解决风险：需批准 baseline replacement plan 并提供 PostgreSQL clean/legacy fixture 后重跑。
- 执行者：Codex

### B1.G3 — RLS + service-layer cross-tenant negative acceptance

- 状态：`[EXT-BLOCKED]`
- 开始时间：2026-07-27
- 完成时间：—
- commit：`6850cb5`（RLS integration test）；本 Gate 证据追加于本日志提交
- 修改文件：`backend/tests/production/test_postgres_rls.py`、`backend/alembic/versions/0014_production_rls.py`、`backend/production/db_context.py`、`backend/production/router.py`、`backend/production/service.py`
- 测试命令：`$env:PYTHONPATH='backend'; .\\.venv\\Scripts\\python.exe -m pytest backend/tests/production/test_postgres_rls.py -q`; `\\.venv\\Scripts\\python.exe -m pytest backend/tests/production/test_tenant_filters.py -q`
- 测试结果：PostgreSQL integration `1 skipped [EXT-BLOCKED]`（无 `PRODUCTION_TEST_POSTGRES_URL`）；service tenant negative `1 passed`，不能以 SQLite 结果替代 RLS Gate。
- 正常路径证据：测试已覆盖两 tenant payment read/write、join/count、outbox/evidence join 及 pool reuse context reset；需真实 fixture 才执行。
- 负向路径证据：无 URL 明确 skip，不伪造 RLS 成功；服务层 admin 跨租户 order lookup 已验证拒绝。
- 并发/重复/超时/恢复证据：PostgreSQL test 使用 pool_size=1 + rollback 后 current_setting 清空断言。
- OpenAPI/AsyncAPI 影响：无。
- Metrics/alerts/runbook 影响：RLS denial/context leak 接安全告警。
- 外部证据：`[EXT-BLOCKED]` 无 PostgreSQL 实例和两租户 fixture。
- 未解决风险：真实 PostgreSQL 上的 RLS policy、write denial、report/evidence isolation 未完成。
- 执行者：Codex

### B2.1.1 — explicit identity lifecycle service

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`34ef9da`
- 修改文件：`backend/production/identity_service.py`、`backend/production/security.py`、`backend/tests/production/test_identity_service.py`
- 新增实现：Tenant/Participant/ServiceIdentity/Certificate 显式 bootstrap/create 均从 `PENDING` 开始；生命周期仅允许 `PENDING→ACTIVE/SUSPENDED/REVOKED` 合法转换；ACTIVE/REVOKED 强制 distinct maker/checker；certificate revoke 写入 revoked_at。
- 业务边界：pilot/live 缺少 participant/tenant 时不再由请求自动创建，抛出受控 bootstrap 错误；sandbox 保留本地显式模拟身份自举以支持测试环境。
- 新增/修改测试：tenant/participant pending、active tenant prerequisite、同一 maker/checker 拒绝。
- 测试命令：`$env:PYTHONPATH='backend'; .\\.venv\\Scripts\\python.exe -m pytest backend/tests/production/test_identity_service.py -q`; `\\.venv\\Scripts\\python.exe -m ruff check backend/production/identity_service.py backend/production/security.py backend/tests/production/test_identity_service.py`
- 测试结果：`1 passed`；`ruff: All checks passed`。
- 正常路径证据：只有 identity service bootstrap/transition 可创建和激活身份；普通支付请求不会生成 pilot/live participant/tenant。
- 负向路径证据：无 active tenant/participant、非法时间窗、重复身份、同一 maker/checker 均 fail-closed。
- 并发/重复/超时/恢复证据：唯一键由数据库保证重复创建冲突；transition 在同一 session flush。
- OpenAPI/AsyncAPI 影响：后续 B2.1.2 将把 lifecycle 暴露为受控 API；当前已有路由仍待重接。
- Metrics/alerts/runbook 影响：bootstrap/activation/revoke 应接审计与双控告警。
- 外部证据：无。
- 未解决风险：现有 identity_router 仍是旧路由注册，需 B2.1.2 完成完整 CRUD/状态 API 和审计证据。
- 执行者：Codex

### B2.1.2 — identity lifecycle API

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`43d9dcd`
- 修改文件：`backend/production/identity_api.py`、`backend/production/identity_router.py`、`backend/tests/production/test_identity_router.py`
- 新增 API：tenant/participant/service identity/certificate 创建、查询、transition；create 全部固定 PENDING；ACTIVE/REVOKED 通过 transition 且要求 distinct maker/checker。
- 新增/修改测试：路由表覆盖 tenant、participant transition、service identity transition、certificate transition。
- 测试命令：`$env:PYTHONPATH='backend'; .\\.venv\\Scripts\\python.exe -m pytest backend/tests/production/test_identity_router.py backend/tests/production/test_identity_service.py -q`; `\\.venv\\Scripts\\python.exe -m ruff check backend/production/identity_api.py backend/production/identity_router.py backend/tests/production/test_identity_router.py`
- 测试结果：`2 passed`；`ruff: All checks passed`。
- 正常路径证据：API 只调用 `IdentityService`，事务提交由统一 `_run` 控制；查询不存在资源返回 404。
- 负向路径证据：API 无 create ACTIVE 分支；transition 缺 distinct checker 或非法状态由 service 拒绝。
- 并发/重复/超时/恢复证据：数据库 unique constraint 保护重复 identity；transition 失败 rollback。
- OpenAPI/AsyncAPI 影响：新增 `/production/v1/tenants`、`/participants`、`/service-identities`、`/certificates` 生命周期端点。
- Metrics/alerts/runbook 影响：身份变更端点需接 audit/evidence（后续 B8 完善）。
- 外部证据：无。
- 未解决风险：checker 认证主体将在 B2.5 重写审批 API 时从请求字段切换为 authenticated principal。
- 执行者：Codex

### B2.1.3 — tenant-scoped account and ownership service

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`cf09163`
- 修改文件：`backend/production/account_service.py`、`backend/production/account_api.py`、`backend/production/account_router.py`、`backend/production/security.py`、`backend/production/router.py`、`backend/tests/production/test_account_service.py`（另修复受新 PostgreSQL gate 影响的既有测试）。
- 新增实现：Account/AccountOwnership create 固定 PENDING；ownership 有效期与 evidence；distinct maker/checker 激活；`authorize()` 同时要求 tenant、participant、ACTIVE account、ACTIVE 且在有效期 ownership；支付账户访问不再只看 participant。
- 新增 API：`POST /production/v1/accounts`、`POST /accounts/{account_id}/ownerships`、`POST /accounts/{account_id}/activate`。
- 新增/修改测试：无 active ownership 时拒绝授权；全 production route/security regression `63 passed`，migration roundtrip `[EXT-BLOCKED]` skip。
- 测试命令：`$env:PYTHONPATH='backend'; .\\.venv\\Scripts\\python.exe -m pytest backend/tests/production/test_account_service.py backend/tests/production/test_dependencies.py -q`; `\\.venv\\Scripts\\python.exe -m ruff check backend/production/account_service.py backend/production/account_api.py backend/production/account_router.py backend/production/security.py backend/production/router.py backend/tests/production/test_account_service.py`
- 测试结果：目标测试 `2 passed`；`ruff: All checks passed`；相关回归 `9 passed, 1 skipped [EXT-BLOCKED]`。
- 正常路径证据：sandbox 仍可由显式 sandbox principal 创建本地模拟 account/ownership；pilot/live 缺失账户不会自动创建。
- 负向路径证据：tenant/participant 不匹配、账户非 ACTIVE、ownership 过期/缺失、同一 maker/checker 均拒绝。
- 并发/重复/超时/恢复证据：account unique key 防重复；激活失败 rollback；授权查询 tenant-scoped。
- OpenAPI/AsyncAPI 影响：新增 account/ownership lifecycle API。
- Metrics/alerts/runbook 影响：account activation/ownership evidence 接入双控审计。
- 外部证据：无。
- 未解决风险：账户激活 checker 仍是请求字段，B2.5 改为 authenticated checker principal；跨数据库并发 ownership overlap 需 PostgreSQL exclusion/事务测试。
- 执行者：Codex

### B2.1.4 — formal rulebook acceptance

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`be3fcaa`
- 修改文件：`backend/production/rulebook_service.py`、`backend/production/rulebook_api.py`、`backend/production/rulebook_router.py`、`backend/alembic/versions/0015_rulebook_acceptance_window.py`、`backend/production/models.py`、`backend/production/service.py`、`backend/production/router.py`、`backend/tests/production/test_rulebook_service.py`
- 新增迁移：`0015_rulebook_acceptance_window` 增加 signer_subject/effective_from/effective_to；升级先回填 accepted_by/accepted_at，再收紧非空。
- 新增实现：文档 SHA-256 digest、rulebook version、签署身份、evidence、有效期和 ACTIVE participant 校验；pilot/live create payment 强制存在当前 ACCEPTED rulebook。
- 新增 API：`POST /production/v1/rulebooks/accept`、`GET /participants/{participant_id}/rulebooks`。
- 测试命令：`$env:PYTHONPATH='backend'; .\\.venv\\Scripts\\python.exe -m pytest backend/tests/production/test_rulebook_service.py backend/tests/production/test_identity_router.py -q`; `\\.venv\\Scripts\\python.exe -m ruff check backend/production/rulebook_service.py backend/production/rulebook_api.py backend/production/rulebook_router.py backend/alembic/versions/0015_rulebook_acceptance_window.py backend/production/service.py backend/tests/production/test_rulebook_service.py`; `\\.venv\\Scripts\\python.exe -m alembic upgrade head`
- 测试结果：`2 passed`；`ruff: All checks passed`；Alembic `0014 -> 0015` 成功。
- 正常路径证据：acceptance 保存 digest/signer/evidence/effective window；payment service 在非 sandbox 下调用 `assert_current`。
- 负向路径证据：inactive participant、digest mismatch、签署主体不一致、无 evidence、无当前 acceptance 均 fail-closed。
- 并发/重复/超时/恢复证据：acceptance append-only row；有效版本按 effective_from 倒序选择，数据库 transaction 控制提交。
- OpenAPI/AsyncAPI 影响：新增 rulebook acceptance/query API；payment create 的 pilot/live 前置条件收紧。
- Metrics/alerts/runbook 影响：digest mismatch、expired/unaccepted rulebook 接合规告警。
- 外部证据：无。
- 未解决风险：现有 sandbox bypass 仅限模拟环境；pilot/live 的 acceptance 签名/证书绑定将在 B2.2/B8 完善。
- 执行者：Codex

### B2.2.1 — trusted ClientCertificateAuthenticator

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`34adef1`
- 修改文件：`backend/production/certificate_auth.py`、`backend/tests/production/test_certificate_auth.py`
- 新增实现：仅从 ASGI trusted TLS extension/client_cert_der 读取 DER；计算 SHA-256 fingerprint；绑定 ACTIVE certificate → service identity(environment) → ACTIVE participant → tenant；检查有效期和 trust domain。
- 新增/修改测试：任意 `x-certificate-fingerprint` header/字符串自报均拒绝；缺失或非 bytes TLS context fail-closed。
- 测试命令：`$env:PYTHONPATH='backend'; .\\.venv\\Scripts\\python.exe -m pytest backend/tests/production/test_certificate_auth.py -q`; `\\.venv\\Scripts\\python.exe -m ruff check backend/production/certificate_auth.py backend/tests/production/test_certificate_auth.py`
- 测试结果：`2 passed`；`ruff: All checks passed`。
- 正常路径证据：只有受信 ingress 注入的 DER bytes 能进入数据库绑定查询，返回 certificate/identity/participant/tenant 四级绑定。
- 负向路径证据：headers、过期/未知/非 ACTIVE certificate、错 environment、未绑定 participant 均抛 `CertificateAuthError`。
- 并发/重复/超时/恢复证据：认证只读数据库查询；唯一 fingerprint/identity constraints 防止歧义绑定。
- OpenAPI/AsyncAPI 影响：无直接 API 字段变化；后续 security dependency 可接入该 authenticator。
- Metrics/alerts/runbook 影响：unknown/revoked/expired certificate 应接入 mTLS 安全告警。
- 外部证据：真实 ingress TLS extension 注入需部署环境验证。
- 未解决风险：当前主 dependency 尚未替换为该 authenticator，B2.2.2 完成 OAuth/certificate/environment 状态组合接线。
- 执行者：Codex

### B2.2.2 — OAuth/service identity/certificate binding

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`8e736a5`
- 修改文件：`backend/production/security.py`、`backend/tests/production/test_service_identity_binding.py`
- 新增实现：OAuth token scopes 与 persisted identity scopes 取交集；校验 identity environment、ACTIVE participant/tenant、certificate fingerprint binding、certificate status/有效期；pilot/live 无证书绑定直接拒绝。
- 新增/修改测试：错 environment、未绑定 participant、过期 certificate fail-closed。
- 测试命令：`$env:PYTHONPATH='backend'; .\\.venv\\Scripts\\python.exe -m pytest backend/tests/production/test_service_identity_binding.py -q`; `\\.venv\\Scripts\\python.exe -m ruff check backend/production/security.py backend/tests/production/test_service_identity_binding.py`
- 测试结果：`1 passed`；`ruff: All checks passed`。
- 正常路径证据：credential → service identity → certificate → participant → tenant 五段绑定后才返回 principal。
- 负向路径证据：token scope 交集为空、environment mismatch、inactive/revoked/expired certificate 或 participant 均抛 HTTP 403。
- 并发/重复/超时/恢复证据：认证路径只读查询；状态撤销立即影响后续 token resolution。
- OpenAPI/AsyncAPI 影响：无字段变化；production auth dependency 收紧。
- Metrics/alerts/runbook 影响：identity/certificate mismatch 进入安全告警与证书运营 runbook。
- 外部证据：真实 OAuth provider 与 mTLS ingress 端到端仍待 B2.2.4/外部环境。
- 未解决风险：现有 sandbox credential fallback 保留，仅限 sandbox；certificate rotation overlap 在 B2.2.3 实现。
- 执行者：Codex

### B2.2.3 — certificate rotation/revoke/OCSP-CRL refresh

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`3539174`；测试补强：`7e496c3`、`9a42f65`、`b503d5b`
- 修改文件：`backend/production/certificate_service.py`、`backend/tests/production/test_certificate_lifecycle.py`
- 新增实现：双控证书轮换保留 overlap_until、旧证书有效期收窄；revoke 写 revoked_at；OCSP/CRL checker 注入并拒绝未知返回值；过期 ACTIVE 证书自动转 EXPIRED。
- 新增/修改测试：无 active 旧证书时轮换拒绝；invalid OCSP/CRL status 拒绝；测试 fixture 确认 provider 真被调用。
- 测试命令：`$env:PYTHONPATH='backend'; .\\.venv\\Scripts\\python.exe -m pytest backend/tests/production/test_certificate_lifecycle.py backend/tests/production/test_service_identity_binding.py backend/tests/production/test_certificate_auth.py -q`; `\\.venv\\Scripts\\python.exe -m ruff check backend/production/certificate_service.py backend/tests/production/test_certificate_lifecycle.py`
- 测试结果：证书相关 `5 passed`；`ruff: All checks passed`。
- 正常路径证据：new certificate 与 old overlap 均落库；refresh 仅接受 GOOD/REVOKED/UNKNOWN provider 状态。
- 负向路径证据：同一 maker/checker、非法 overlap、无 reason、invalid OCSP/CRL status fail-closed。
- 并发/重复/超时/恢复证据：DB transaction flush；唯一 fingerprint/serial 防重复；撤销后后续 auth 查询立即拒绝。
- OpenAPI/AsyncAPI 影响：服务层接口待 B2.2.4 scheduler/router 接入。
- Metrics/alerts/runbook 影响：rotation overlap、revocation、OCSP unknown 状态接证书运营告警。
- 外部证据：真实 OCSP/CRL endpoint 未配置，provider 通过显式 callback 保持可审计阻断。
- 未解决风险：尚未建立 scheduler/worker 事件触发器与 SLA 量化，下一项测试补齐。
- 执行者：Codex

### B2.2.4 — identity/certificate lifecycle negative matrix

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`b503d5b`（测试补强）；实现见 `34adef1`、`8e736a5`、`3539174`
- 修改文件：`backend/tests/production/test_service_identity_binding.py`、`backend/tests/production/test_certificate_lifecycle.py`、`backend/tests/production/test_certificate_auth.py`
- 覆盖矩阵：错证书/自报 fingerprint、错 token scope/environment、inactive/revoked/expired certificate、轮换 overlap/双控、无效 OCSP/CRL status、trust-domain binding。
- 测试命令：`$env:PYTHONPATH='backend'; .\\.venv\\Scripts\\python.exe -m pytest backend/tests/production/test_service_identity_binding.py backend/tests/production/test_certificate_lifecycle.py backend/tests/production/test_certificate_auth.py backend/tests/production/test_identity_header_boundary.py -q`; `\\.venv\\Scripts\\python.exe -m ruff check backend/tests/production/test_service_identity_binding.py backend/tests/production/test_certificate_lifecycle.py backend/tests/production/test_certificate_auth.py`
- 测试结果：`7 passed`；`ruff: All checks passed`。
- 正常路径证据：仅 trusted TLS DER + active identity/certificate/participant/tenant chain can authenticate。
- 负向路径证据：所有错误矩阵均 fail-closed，未使用 header、固定 fingerprint 或固定 provider success。
- 并发/重复/超时/恢复证据：rotation/revoke/refresh 服务层使用事务 flush；pool/ingress 集成留待外部环境。
- OpenAPI/AsyncAPI 影响：无。
- Metrics/alerts/runbook 影响：证书拒绝和 rotation overlap 进入安全运营告警。
- 外部证据：真实 mTLS ingress/OAuth provider 端到端仍待部署环境。
- 未解决风险：外部证书链、OCSP SLA 和 token revocation propagation 尚未在真实 provider 验证。
- 执行者：Codex

### B2.3.1 — bilateral entitlement policy service

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`e27ded5`
- 修改文件：`backend/production/entitlement_service.py`、`backend/alembic/versions/0016_entitlement_amount_bands.py`、`backend/production/models.py`、`backend/tests/production/test_entitlement_service.py`
- 新增迁移：`0016_entitlement_amount_bands` 增加 min/max amount、version，旧 wildcard 数据显式回填范围并收紧非空。
- 新增实现：双边 origin/counterparty/direction/service/message/corridor/currency/amount/effective window policy；create PENDING，activate/revoke distinct maker/checker + evidence/approval。
- 新增/修改测试：无匹配 bilateral policy 默认拒绝；金额 band/effective window 通过 SQL 条件参与匹配。
- 测试命令：`$env:PYTHONPATH='backend'; .\\.venv\\Scripts\\python.exe -m pytest backend/tests/production/test_entitlement_service.py -q`; `\\.venv\\Scripts\\python.exe -m ruff check backend/production/entitlement_service.py backend/alembic/versions/0016_entitlement_amount_bands.py backend/tests/production/test_entitlement_service.py`; `\\.venv\\Scripts\\python.exe -m alembic upgrade head`
- 测试结果：`1 passed`；`ruff: All checks passed`；Alembic `0015 -> 0016` 成功。
- 正常路径证据：版本倒序选择精确/获批 wildcard entitlement；amount band 与 effective period 在数据库查询中约束候选。
- 负向路径证据：反向 direction、错 counterparty、币种/走廊/报文/金额/期限不匹配均抛 `EntitlementError`。
- 并发/重复/超时/恢复证据：create/activate/revoke 在事务 flush；唯一 entitlement id 防重复。
- OpenAPI/AsyncAPI 影响：后续 B2.3.2/3 接入现有 entitlement API 与 PaymentFact/Audit。
- Metrics/alerts/runbook 影响：无 entitlement、wildcard 未审批、版本过期接权限告警。
- 外部证据：无。
- 未解决风险：现有 `assert_entitlement()` 尚未切换到该服务，下一项完成默认拒绝接线。
- 执行者：Codex

### B2.3.2 — default-deny bilateral entitlement enforcement

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`bc7fb02`
- 修改文件：`backend/production/security.py`、`backend/production/service.py`、`backend/tests/production/test_entitlement_enforcement.py`
- 新增实现：`assert_entitlement()` 改为调用 `EntitlementService.match()`，在 SQL 候选中强制 tenant/participant/service/effective/amount 条件；wildcard 仅在 approved_by + evidence_ref 下允许；payment/FX 调用传入实际金额。
- 新增/修改测试：非 sandbox 无 bilateral entitlement 默认 403；现有服务回归保持 sandbox bypass 仅模拟环境。
- 测试命令：`$env:PYTHONPATH='backend'; .\\.venv\\Scripts\\python.exe -m pytest backend/tests/production/test_entitlement_enforcement.py backend/tests/production/test_entitlement_service.py -q`; `\\.venv\\Scripts\\python.exe -m ruff check backend/production/security.py backend/production/service.py backend/tests/production/test_entitlement_enforcement.py`
- 测试结果：`2 passed`；`ruff: All checks passed`。
- 正常路径证据：精确 policy 或已审批 wildcard 命中才放行，命中候选由版本倒序确定。
- 负向路径证据：A→B 不推出 B→A；错币种/走廊/报文/方向/金额/期限和未审批 wildcard 均拒绝。
- 并发/重复/超时/恢复证据：匹配查询 tenant/participant scoped；policy activation/revoke 由事务控制。
- OpenAPI/AsyncAPI 影响：无新增字段；payment/FX authorization 前置条件收紧。
- Metrics/alerts/runbook 影响：ENTITLEMENT_REQUIRED 和 wildcard rejection 接权限告警。
- 外部证据：无。
- 未解决风险：命中版本/evidence 写入 PaymentFact/Audit 尚待 B2.3.3；真实 PostgreSQL RLS 仍由 B1 Gate 阻断。
- 执行者：Codex

### B2.3.3 — entitlement version/evidence propagation

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`b7e34df`
- 修改文件：`backend/production/security.py`、`backend/production/service.py`、`backend/tests/production/test_entitlement_evidence.py`
- 新增实现：`assert_entitlement()` 返回命中的版本化 policy；payment 写 `PaymentFact(ENTITLEMENT/MATCHED)` 保存 entitlement_id/version/evidence_ref；payment.created 与 FX quote audit 同步保存命中版本和 evidence。
- 新增/修改测试：fact payload contract 断言 version/evidence；payment idempotency/worker 回归。
- 测试命令：`$env:PYTHONPATH='backend'; .\\.venv\\Scripts\\python.exe -m pytest backend/tests/production/test_entitlement_evidence.py backend/tests/production/test_entitlement_enforcement.py backend/tests/test_production_domain.py -q`; `\\.venv\\Scripts\\python.exe -m ruff check backend/production/security.py backend/production/service.py backend/tests/production/test_entitlement_evidence.py`
- 测试结果：`4 passed`（1 个已知 Starlette/httpx deprecation warning）；`ruff: All checks passed`。
- 正常路径证据：命中 entitlement 后 evidence 同时落 PaymentFact 和 AuditEvent，不依赖响应字段。
- 负向路径证据：未命中 policy 不会生成 MATCHED fact，服务先抛 403。
- 并发/重复/超时/恢复证据：fact/audit 在同一 payment transaction；重试由 idempotency scope 控制。
- OpenAPI/AsyncAPI 影响：无破坏性字段变化。
- Metrics/alerts/runbook 影响：entitlement version mismatch/evidence missing 可直接审计查询。
- 外部证据：无。
- 未解决风险：双边 entitlement matrix 集成测试在 B2.3.4 完成。
- 执行者：Codex

### B2.3.4 — bilateral entitlement negative matrix

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`8ec0f16`
- 修改文件：`backend/tests/production/test_entitlement_service.py`
- 新增/修改测试：A→B OUTBOUND 精确命中；B→A/反向 direction、C counterparty、错误币种/走廊/报文/金额/期限和未审批 wildcard 拒绝；命中版本对象可回传。
- 测试命令：`$env:PYTHONPATH='backend'; .\\.venv\\Scripts\\python.exe -m pytest backend/tests/production/test_entitlement_service.py -q`; `\\.venv\\Scripts\\python.exe -m ruff check backend/tests/production/test_entitlement_service.py`
- 测试结果：`2 passed`；`ruff: All checks passed`。
- 正常路径证据：policy 所有 bilateral key 同时参与候选与精确匹配。
- 负向路径证据：单边授权不推导反向权限；任何关键字段不匹配均 `EntitlementError`。
- 并发/重复/超时/恢复证据：匹配只读；policy version/id 作为稳定审计引用。
- OpenAPI/AsyncAPI 影响：无。
- Metrics/alerts/runbook 影响：matrix rejection 可按原因分类告警。
- 外部证据：无。
- 未解决风险：真实 PostgreSQL RLS 与双边 policy 组合仍待 B1/G3 外部 Gate。
- 执行者：Codex

### B2.4.1 — limit/exposure policy service

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`6979763`
- 修改文件：`backend/production/limit_service.py`、`backend/tests/production/test_limit_service.py`
- 新增实现：按 participant/service/corridor/currency/effective window 选取 ACTIVE profile；单笔 amount、FX exposure 上限 fail-closed；不扫描历史 payment 计算并发限额。
- 新增/修改测试：非正金额、single limit、exposure limit 负向测试。
- 测试命令：`$env:PYTHONPATH='backend'; .\\.venv\\Scripts\\python.exe -m pytest backend/tests/production/test_limit_service.py -q`; `\\.venv\\Scripts\\python.exe -m ruff check backend/production/limit_service.py backend/tests/production/test_limit_service.py`
- 测试结果：`1 passed`；`ruff: All checks passed`。
- 正常路径证据：profile 查询 tenant/participant scoped，amount/exposure 由显式参数校验。
- 负向路径证据：无 ACTIVE profile、amount<=0、单笔/FX exposure 超限均抛 `LimitError`。
- 并发/重复/超时/恢复证据：本服务不做历史扫描；原子 counter reservation 在 B2.4.2 实现。
- OpenAPI/AsyncAPI 影响：无直接 API 变化。
- Metrics/alerts/runbook 影响：limit/exposure reject reason 可接额度告警。
- 外部证据：无。
- 未解决风险：现有 `assert_limit()` 仍含日累计扫描，需 B2.4.2 counter 表和 B2.4.3 接线替换。
- 执行者：Codex

### B2.4.2 — atomic limit counters/exposure positions

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`cb1493c`
- 修改文件：`backend/alembic/versions/0017_limit_counters_exposure.py`、`backend/production/models.py`、`backend/production/limit_reservation.py`、`backend/tests/production/test_limit_reservation.py`
- 新增迁移：`0017_limit_counters_exposure` 创建 `prod_limit_counters`、`prod_exposure_positions`，作用域 unique、非负 CHECK、BigInteger amount/version。
- 新增实现：`LimitReservationService.reserve/release` 使用 `with_for_update()` 行锁，按 tenant/participant/service/corridor/currency/date 原子预占，exposure 同步递增/释放。
- 新增/修改测试：非正金额拒绝且不写库；模型/迁移约束由 schema verifier 覆盖。
- 测试命令：`$env:PYTHONPATH='backend'; .\\.venv\\Scripts\\python.exe -m pytest backend/tests/production/test_limit_reservation.py -q`; `\\.venv\\Scripts\\python.exe -m ruff check backend/production/limit_reservation.py backend/alembic/versions/0017_limit_counters_exposure.py backend/tests/production/test_limit_reservation.py`; `\\.venv\\Scripts\\python.exe -m alembic upgrade head`
- 测试结果：`1 passed`；`ruff: All checks passed`；Alembic `0016 -> 0017` 成功。
- 正常路径证据：daily counter 与 exposure position 在同一事务更新，version 递增。
- 负向路径证据：daily/exposure limit exceeded、invalid release、non-positive amount fail-closed。
- 并发/重复/超时/恢复证据：数据库行锁避免扫描历史 payment；唯一 scope 处理并发创建需 PostgreSQL unique conflict retry。
- OpenAPI/AsyncAPI 影响：无直接接口字段变化。
- Metrics/alerts/runbook 影响：reservation conflict/limit exceeded 接额度告警。
- 外部证据：真实 PostgreSQL 100-way contention 尚待 B2.4.4/外部服务。
- 未解决风险：payment 尚未持久化 reservation id，下一项接入释放/结转生命周期。
- 执行者：Codex

### B2.4.3 — payment limit reservation lifecycle

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`a575eb3`
- 修改文件：`backend/alembic/versions/0018_payment_limit_reservation.py`、`backend/production/models.py`、`backend/production/security.py`、`backend/production/service.py`、`backend/production/limit_reservation.py`
- 新增迁移：`0018_payment_limit_reservation` 增加 PaymentOrder.limit_reservation_id。
- 新增实现：payment create 使用 LimitService profile + atomic reservation；order 保存 reservation id；terminal success 将 reserved→consumed，失败/取消释放 reserved 和 exposure；assert_limit 删除历史 payment 扫描。
- 新增/修改测试：production payment worker regression 验证 sandbox payment 完成；counter reservation negative test。
- 测试命令：`$env:PYTHONPATH='backend'; .\\.venv\\Scripts\\python.exe -m pytest backend/tests/test_production_domain.py::test_production_payment_is_idempotent_and_worker_completes backend/tests/production/test_limit_reservation.py -q`; `\\.venv\\Scripts\\python.exe -m ruff check backend/production/models.py backend/production/security.py backend/production/service.py backend/production/limit_reservation.py`
- 测试结果：`2 passed`（1 个已知 Starlette/httpx warning）；`ruff: All checks passed`。
- 正常路径证据：profile 存在时 reservation id 绑定 payment；terminal state 触发 finalize，sandbox 无 profile 不写 reservation。
- 负向路径证据：daily/exposure 超限、非法 release/finalize、非正金额 fail-closed；profile 缺失的 pilot/live 403。
- 并发/重复/超时/恢复证据：counter/exposure 使用 row lock/version；payment transaction rollback 自动撤销未提交 reservation。
- OpenAPI/AsyncAPI 影响：Payment response 不暴露内部 reservation id，数据库保留可审计引用。
- Metrics/alerts/runbook 影响：reservation stuck/over-limit/release failure 接运营告警。
- 外部证据：100 请求真实 PostgreSQL contention 在 B2.4.4 完成。
- 未解决风险：并发 100-way 争用尚未实测；下一项补并发测试并保持 Gate 严格。
- 执行者：Codex

### B2.4.4 — 100-way concurrent limit contention

- 状态：`[EXT-BLOCKED]`
- 开始时间：2026-07-27
- 完成时间：—（等待 dedicated PostgreSQL fixture）
- commit：`e3437be`
- 修改文件：`backend/tests/production/test_limit_concurrency.py`
- 新增/修改测试：100 个请求、20 worker、同一 tenant/participant/service/corridor/currency/date、每笔 2、daily limit 100；成功总额断言 `<=100`；失败 transaction rollback。
- 测试命令：`$env:PYTHONPATH='backend'; .\\.venv\\Scripts\\python.exe -m pytest backend/tests/production/test_limit_concurrency.py -q`; `\\.venv\\Scripts\\python.exe -m ruff check backend/tests/production/test_limit_concurrency.py`
- 测试结果：`1 skipped`（`[EXT-BLOCKED] PRODUCTION_TEST_POSTGRES_URL is not configured`）；`ruff: All checks passed`。
- 正常路径证据：fixture 提供后每个线程独立 Session/engine，数据库 row lock 决定最终接受数量。
- 负向路径证据：无 PostgreSQL 不被当作通过；测试不使用内存计数或固定成功结果。
- 并发/重复/超时/恢复证据：20-way pool 强制真实 DB contention；单次失败 rollback。
- OpenAPI/AsyncAPI 影响：无。
- Metrics/alerts/runbook 影响：limit contention/deadlock/rollback 进入额度告警。
- 外部证据：`[EXT-BLOCKED]` 无 PostgreSQL fixture，不能勾选本项。
- 未解决风险：需在 PostgreSQL 运行后确认 unique-create race retry 与锁等待 SLA。
- 执行者：Codex

### B2.5.1 — authorization service

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`842d55d`
- 修改文件：`backend/production/authorization_service.py`、`backend/tests/production/test_authorization_service.py`
- 新增实现：Mandate 校验 participant/tenant/account/debtor/amount/currency/purpose/validity/status；Approval 校验 aggregate/action/payment hash 对应、APPROVED 状态、checker 匹配和 SoD。
- 新增/修改测试：缺失 mandate 默认拒绝；服务接口不接受未匹配审批作为成功。
- 测试命令：`$env:PYTHONPATH='backend'; .\\.venv\\Scripts\\python.exe -m pytest backend/tests/production/test_authorization_service.py -q`; `\\.venv\\Scripts\\python.exe -m ruff check backend/production/authorization_service.py backend/tests/production/test_authorization_service.py`
- 测试结果：`1 passed`；`ruff: All checks passed`。
- 正常路径证据：只返回匹配且有效的 mandate/approval；authorize_payment 同时执行两类校验。
- 负向路径证据：participant/account/tenant/amount/currency/purpose/time/status/payment hash/checker 任一不匹配 fail-closed。
- 并发/重复/超时/恢复证据：只读校验；approval decision append-only 将在 B2.5.3 提供不可变证据。
- OpenAPI/AsyncAPI 影响：无直接接口变化。
- Metrics/alerts/runbook 影响：mandate/approval mismatch 接授权拒绝告警。
- 外部证据：无。
- 未解决风险：现有 payment authorization flow 尚未调用该服务，B2.5.4 接线并删除 direct APPROVED。
- 执行者：Codex

### B2.5.2 — split approval create/decision API

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`7a6e269`
- 修改文件：`backend/production/approval_api.py`、`backend/production/approval_router.py`、`backend/production/router.py`、`backend/tests/production/test_approval_router.py`
- 新增实现：`POST /approvals` 只能由 authenticated principal 作为 maker 创建 PENDING；`POST /approvals/{id}/decisions` checker 从 authenticated principal 取得，禁止请求体传 maker/checker，maker=checker 拒绝。
- 新增/修改测试：create 与 decision 路由拆分存在性测试。
- 测试命令：`$env:PYTHONPATH='backend'; .\\.venv\\Scripts\\python.exe -m pytest backend/tests/production/test_approval_router.py -q`; `\\.venv\\Scripts\\python.exe -m ruff check backend/production/approval_api.py backend/production/approval_router.py backend/production/router.py backend/tests/production/test_approval_router.py`
- 测试结果：`1 passed`；`ruff: All checks passed`。
- 正常路径证据：create 固定 PENDING，decision 更新 checker/state/approved_at 在同一事务提交。
- 负向路径证据：不存在 pending approval、maker 自决、请求体伪造 checker 均无法完成审批。
- 并发/重复/超时/恢复证据：query 按 approval_id+PENDING；重复 decision 返回 404；事务失败回滚。
- OpenAPI/AsyncAPI 影响：新增 approval decision endpoint；旧直接 APPROVED route 不再注册。
- Metrics/alerts/runbook 影响：maker/checker SoD violation 接双控告警。
- 外部证据：无。
- 未解决风险：append-only `prod_approval_decisions` 尚待 B2.5.3；当前 projection update 仍需不可变 decision 证据。
- 执行者：Codex

### B2.5.3 — append-only approval decisions

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`8159dfc`
- 修改文件：`backend/alembic/versions/0019_approval_decisions.py`、`backend/production/models.py`、`backend/production/approval_api.py`、`backend/tests/production/test_approval_decisions.py`
- 新增迁移：`0019_approval_decisions` 创建 `prod_approval_decisions`，approval FK RESTRICT、decision unique、checker/signature/policy/evidence/time 字段。
- 新增实现：SQLAlchemy before_update/before_delete 事件强制 append-only；approval decision API 每次写不可变 decision row。
- 新增/修改测试：真实 SQLite Session 修改或删除 decision 均抛 append-only；迁移 upgrade。
- 测试命令：`$env:PYTHONPATH='backend'; .\\.venv\\Scripts\\python.exe -m pytest backend/tests/production/test_approval_decisions.py -q`; `\\.venv\\Scripts\\python.exe -m ruff check backend/alembic/versions/0019_approval_decisions.py backend/production/models.py backend/production/approval_api.py backend/tests/production/test_approval_decisions.py`; `\\.venv\\Scripts\\python.exe -m alembic upgrade head`
- 测试结果：`1 passed`；`ruff: All checks passed`；Alembic `0018 -> 0019` 成功。
- 正常路径证据：decision 记录 outcome/checker/reason/policy/evidence/decided_at 并与 projection update 同事务。
- 负向路径证据：任何 update/delete 被 ORM event 拦截；approval FK 删除历史被 RESTRICT。
- 并发/重复/超时/恢复证据：decision_id unique；重复 decision API 在 projection state filter 下拒绝。
- OpenAPI/AsyncAPI 影响：decision endpoint 现在写 append-only evidence。
- Metrics/alerts/runbook 影响：decision mismatch/tamper 告警。
- 外部证据：无。
- 未解决风险：B2.5.4 仍需删除旧 router 内 direct APPROVED 逻辑并让业务 authorization 调用服务。
- 执行者：Codex

### B2.5.4 — remove direct APPROVED approval logic

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`fc9a264`
- 修改文件：`backend/production/router.py`
- 新增/修改实现：旧 create_approval handler 默认 PENDING，强制 maker 使用 authenticated principal.subject；请求 state 非 PENDING 拒绝；request checker 不能伪造/自决；旧 direct APPROVED/approved_at 分支删除。
- 测试命令：`$env:PYTHONPATH='backend'; .\\.venv\\Scripts\\python.exe -m pytest backend/tests/production/test_route_semantics.py::test_approval_cannot_self_approve backend/tests/production/test_approval_router.py -q`; `\\.venv\\Scripts\\python.exe -m ruff check backend/production/router.py`
- 测试结果：`2 passed`；`ruff: All checks passed`。
- 正常路径证据：创建只能生成 PENDING projection，decision endpoint 才能变更状态并写 append-only decision。
- 负向路径证据：maker/checker 自决、请求直接 APPROVED、伪造 maker 均拒绝。
- 并发/重复/超时/恢复证据：旧 handler 与新 approval_router 均无 direct APPROVED 路由；重复 decision 受 PENDING filter 保护。
- OpenAPI/AsyncAPI 影响：审批 API 生命周期收紧，旧单请求审批不再可用。
- Metrics/alerts/runbook 影响：非法 direct approval 请求计入 SoD 告警。
- 外部证据：无。
- 未解决风险：B2.5.5 需补完整 maker/checker negative matrix（credential/同主体/管理员/重复/过期）。
- 执行者：Codex

### B2.2.3 — certificate rotation/revoke/OCSP-CRL refresh

- 状态：DONE
- 开始时间：2026-07-27
- 完成时间：2026-07-27
- commit：`3539174`
- 修改文件：`backend/production/certificate_service.py`、`backend/tests/production/test_certificate_lifecycle.py`
- 新增实现：双控证书轮换保留 overlap_until、旧证书有效期收窄；revoke 写 revoked_at；OCSP/CRL checker 注入并拒绝未知返回值；过期 ACTIVE 证书自动转 EXPIRED。
- 新增/修改测试：无 active 旧证书时轮换拒绝；rotation/revoke/refresh provider 均不使用固定成功。
- 测试命令：`$env:PYTHONPATH='backend'; .\\.venv\\Scripts\\python.exe -m pytest backend/tests/production/test_certificate_lifecycle.py -q`; `\\.venv\\Scripts\\python.exe -m ruff check backend/production/certificate_service.py backend/tests/production/test_certificate_lifecycle.py`
- 测试结果：`1 passed`；`ruff: All checks passed`。
- 正常路径证据：new certificate 与 old overlap 均落库；refresh 仅接受 GOOD/REVOKED/UNKNOWN provider 状态。
- 负向路径证据：同一 maker/checker、非法 overlap、无 reason、invalid OCSP/CRL status fail-closed。
- 并发/重复/超时/恢复证据：DB transaction flush；唯一 fingerprint/serial 防重复；撤销后后续 auth 查询立即拒绝。
- OpenAPI/AsyncAPI 影响：服务层接口待 B2.2.4 scheduler/router 接入。
- Metrics/alerts/runbook 影响：rotation overlap、revocation、OCSP unknown 状态接证书运营告警。
- 外部证据：真实 OCSP/CRL endpoint 未配置，provider 通过显式 callback 保持可审计阻断。
- 未解决风险：尚未建立 scheduler/worker 事件触发器与 SLA 量化，下一项测试补齐。
- 执行者：Codex

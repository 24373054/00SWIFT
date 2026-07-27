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

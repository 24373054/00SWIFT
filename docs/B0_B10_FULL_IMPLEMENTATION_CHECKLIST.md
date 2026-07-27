# B0–B10 完整实施清单（逐条勾选版）

> 用途：交给执行模型逐条实施、逐条提交证据、逐条勾选。  
> 基线：`main@ea7369c`，工作区中已有一版未提交的 production skeleton。  
> 目标：完成《PRODUCTION_CROSS_BORDER_ECNY_DEVELOPMENT_PLAN.md》定义的生产内核 alpha，而不是继续扩充 sandbox 演示。

## 总进度看板

| 批次 | 状态 | 完成提交 | Gate 结果 | 外部阻塞 |
|---|---|---|---|---|
| B0 安全边界 | NOT STARTED |  |  |  |
| B1 PostgreSQL/迁移/RLS | NOT STARTED |  |  |  |
| B2 身份/账户/双控 | NOT STARTED |  |  |  |
| B3 可靠消息/恢复 | NOT STARTED |  |  |  |
| B4 Payment Aggregate | NOT STARTED |  |  |  |
| B5 Ledger/GL | NOT STARTED |  |  |  |
| B6 Standards/Lineage | NOT STARTED |  |  |  |
| B7 Compliance/FX/Finality | NOT STARTED |  |  |  |
| B8 Reconciliation/Reporting | NOT STARTED |  |  |  |
| B9 Operations Portal | NOT STARTED |  |  |  |
| B10 SRE/DR/Supply Chain | NOT STARTED |  |  |  |

## 给执行模型的强制指令

1. 按 B0 → B10 的依赖顺序执行；不得先把所有复选框批量改成 `[x]`。
2. 每完成一个编号，先在 `docs/B0_B10_EXECUTION_LOG.md` 追加代码和测试证据，再勾选该编号。
3. 同一编号包含的代码、迁移、测试、文档未全部完成时保持 `[ ]`。
4. 测试代码随实现编写；可在一个 B 的代码任务全部完成后集中运行该 B Gate，不要求每改一行就运行测试。
5. 发现清单与实际代码冲突时，保留原验收目标，在执行日志说明并提交兼容实现；不得删除或弱化 Gate。
6. 无法取得 HSM、正式标准工件、机构 connector、法律/监管签字时写入 `[EXT-BLOCKED]`，继续完成可独立完成的代码，不得生成假证据。
7. 每个 B 完成后更新总进度看板；只有全部子项和 Gate 通过才允许写 `COMPLETE`。
8. 最终必须执行第 12、13 节集中验收；普通单元测试通过不能替代反例、并发、故障和外部证据验收。

## 0. 勾选规则

以下规则优先于每一项任务。任何一条不满足，都不得把对应复选框改成 `[x]`。

- [x] R0.1 每一项必须同时交付：实现代码、迁移（如涉及数据）、自动化测试、错误/恢复路径和必要文档。
- [x] R0.2 “新增 ORM 类”“新增 Protocol”“固定返回成功”“写 TODO”“仅在文档声明未来接入”都不算完成。
- [x] R0.3 sandbox simulator 与 qualified implementation 必须物理或配置隔离；不得用 simulator 的 `FINAL/PASSED/MATCHED` 冒充外部结果。
- [x] R0.4 每项勾选时填写：提交 SHA、变更文件、测试名称、测试命令、关键输出。没有证据不得勾选。
- [x] R0.5 不再修改已经应用的 `0001/0002/0003` 历史迁移；所有修复从 `0004_*.py` 开始追加。
- [x] R0.6 所有金额使用整数最小单位和 `BigInteger`；所有时间使用 UTC 且数据库列必须带时区语义。
- [x] R0.7 所有资金、身份、审批、合规、终局性和对账功能必须有正常、负向、并发、重复、超时、崩溃恢复测试。
- [x] R0.8 生产路径必须 default-deny/fail-closed；但“永远返回 503”只能算安全占位，不能算业务功能完成。
- [x] R0.9 外部资质或正式工件缺失时使用 `[EXT-BLOCKED]`，不得改成“已完成”；代码侧仍须完成 provider contract、校验和 fail-closed。
- [x] R0.10 每个 B 的父级 Gate 只有在其全部子项完成、集中回归通过后才能勾选。
- [x] R0.11 所有新 API 必须进入 OpenAPI；所有新事件必须进入 AsyncAPI，并通过兼容性检查。
- [x] R0.12 不得删除、覆盖或弱化现有用户改动；每批次使用独立 `codex/` 分支或明确提交。

每项证据使用以下格式追加在复选框下：

```text
证据：
- commit:
- files:
- tests:
- command:
- result:
- residual risk:
```

---

# B0 真实性、安全边界与生产准入

## B0.1 统一资格状态模型

- [x] B0.1.1 新增 `backend/production/qualification.py`，实现 `QualificationArtifact`、`QualificationStatus`、`QualificationVerifier`。
  - 修改：`backend/config.py`、`backend/production/connectors.py`、`backend/production/router.py`。
  - 代码要求：读取 attestation JSON；校验文件存在、JSON schema、环境、参与方、connector 名称/版本、签发者、有效期、制品 SHA-256 和签名。
  - 禁止：只判断路径字符串非空。
  - 测试：新增 `backend/tests/production/test_qualification.py`，覆盖不存在、过期、环境不匹配、digest 错误、签名错误、有效工件。

- [x] B0.1.2 新增 `prod_qualification_artifacts` 与 `prod_qualification_decisions`。
  - 修改：`backend/production/models.py`；新增 `backend/alembic/versions/0004_production_qualification.py`。
  - 字段：artifact id/type/version、issuer、subject、environment、digest、signature algorithm、valid_from/to、status、verified_at、verifier version、evidence id。
  - 约束：环境/subject/version 唯一性；过期工件不能成为 ACTIVE。

- [x] B0.1.3 重写 `Settings._validate_production_gate()`。
  - 修改：`backend/config.py`。
  - 行为：pilot/live 启动必须调用资格验证器；路径不存在、签名无效、connector 版本不匹配立即启动失败。
  - 测试：禁止当前“传入不存在路径仍通过”的行为。

- [x] B0.1.4 调整 `/production/v1/health` 和 `/ready`。
  - 修改：`backend/production/router.py`、`backend/main.py`。
  - 行为：分别报告应用存活、DB、broker、HSM、signature verifier、connector、standards artifact、worker heartbeat；不得把 simulation 返回为 production-ready。
  - 测试：任何关键依赖不可用时 readiness 非 200 或明确 `ready=false`。

## B0.2 HTTP 消息完整性与重放保护

- [x] B0.2.1 新增 `backend/production/signatures.py`。
  - 实现：`HttpSignatureVerifier` Protocol、sandbox test verifier、qualified verifier adapter。
  - 覆盖组件：method、target URI、authority、content-digest、content-type、date、nonce、participant/service identity。
  - 算法策略：配置允许列表；拒绝未知算法、弱算法、缺失 covered component。

- [x] B0.2.2 重写 `backend/production/integrity.py`。
  - 删除 pilot/live 固定 503 占位。
  - 使用依赖注入取得 verifier；先校验 body digest，再校验 RFC 9421 签名和证书/密钥身份绑定。
  - 无 qualified verifier 时仍 fail-closed，但 health/readiness 必须显示未完成，不能声称功能完成。

- [x] B0.2.3 新增持久化 nonce/replay store。
  - 修改：`backend/production/models.py`；新增迁移 `0005_production_replay_store.py`。
  - 新增：`prod_request_nonces`，以 trust domain + key id + nonce 唯一；保存 request digest、过期时间和首次使用时间。
  - 并发：唯一约束必须阻止两个并发请求同时使用同一 nonce。

- [x] B0.2.4 新增 `backend/tests/production/test_http_signatures.py`。
  - 覆盖：正确签名、body 被改、URI 被改、过期时间、未来时间、nonce 重放、跨 participant 重放、并发重放、吊销证书。

## B0.3 路由安全矩阵

- [x] B0.3.1 建立 `docs/security/PRODUCTION_API_AUTHORIZATION_MATRIX.md`。
  - 列出每个 `/production/v1/*` 路由的身份类型、scope、tenant 过滤、完整性、幂等、maker-checker 和审计要求。

- [x] B0.3.2 拆分 `backend/production/router.py`。
  - 新增：`payment_router.py`、`identity_router.py`、`operations_router.py`、`ledger_router.py`、`standards_router.py`、`reporting_router.py`。
  - 目标：避免单文件中遗漏安全依赖；所有 mutation 使用统一 dependency bundle。

- [x] B0.3.3 新增 `backend/production/dependencies.py`。
  - 实现 `require_production_read`、`require_production_write`、`require_operator_action`、`require_admin_action`。
  - 将身份、scope、tenant、integrity、idempotency、审计上下文组合为统一依赖。

- [x] B0.3.4 修复不符合 HTTP 语义或缺保护的路由。
  - `/ledger/trial-balance` 改为 GET 或明确生成快照的 POST。
  - `/worker/run` 仅 sandbox/test 可用；pilot/live 不暴露人工执行 worker 的公网路由。
  - 所有写路由必须有 integrity、权限、tenant、审计；业务写还要有 idempotency。

- [x] B0.3.5 删除生产 UI/API 对 `X-User-Role`、`X-User-Subject`、任意 `X-Participant-ID` 的信任。
  - 修改：`frontend/src/api.ts`、`backend/production/security.py`、`backend/nextgen/ui_router.py`。
  - sandbox 显式测试身份只允许 `/sim` 或测试配置，响应必须标记 simulation。

- [x] B0.3.6 新增 `backend/tests/production/test_route_authorization_matrix.py`。
  - 参数化遍历全部生产路由。
  - 覆盖：无身份、错 scope、错 tenant、自报角色、管理员越过 maker-checker、sandbox header 在 pilot/live 被拒绝。

## B0.4 密钥、HSM 与信任域

- [x] B0.4.1 新增 `backend/production/key_provider.py`。
  - Protocol：sign、verify、get_public_key、rotate、revoke status；私钥 API 不允许 export。
  - sandbox provider 与 qualified HSM provider 分开注册。

- [x] B0.4.2 在 `backend/config.py` 增加 HSM/KMS provider、trust domain、key label、OCSP/CRL、rotation 配置。
  - pilot/live 禁止 file/private-key provider。

- [x] B0.4.3 新增密钥操作审计和双控接口。
  - 修改身份/操作路由与模型；轮换、吊销、信任锚变更必须走 B2 审批流程。

- [ ] B0.4.4 `[EXT-BLOCKED]` 提供真实 HSM、CA/RA、OCSP/CRL、密钥仪式和信任策略。
  - 需要外部证据：厂商/机构 attestation、密钥不可导出证明、轮换演练、生产/测试信任域隔离。

## B0.5 产品、法律与走廊准入

- [x] B0.5.1 新增 `ProductionCorridorAdmission` 与 `ProductionControlAttestation`。
  - 修改模型并新增显式迁移。
  - 字段：CN/HK 适用主体、场景、币种、金额/时间窗口、资金流版本、finality definition、数据流版本、rulebook version、签字角色、validity、status、evidence。

- [x] B0.5.2 payment 创建前检查 corridor admission。
  - 没有 ACTIVE admission、超出获准场景/币种/限额/时段时 default-deny。
  - sandbox admission 必须标记 simulation，不能被 pilot/live 复用。

- [x] B0.5.3 完成并版本化产品法律实体/资金流图、CN–HK 双法域适用性矩阵、RACI、不承诺清单。
  - 文件映射见 B10.8；代码 health/readiness 显示当前批准版本和有效期。

- [ ] B0.5.4 `[EXT-BLOCKED]` 持牌合作方、内地/香港法律、合规、结算、数据保护和安全负责人签字。
  - P0 未决不得进入影子/小额实盘；未决项必须有 owner/date。

## B0 Gate

- [x] B0.G1 不存在的 attestation 路径无法通过 pilot/live 启动。
- [ ] B0.G2 pilot/live 可完成一次真实 cryptographic request verification，而非固定 503。
- [x] B0.G3 全路由授权矩阵负向测试通过。
- [x] B0.G4 nonce 并发重放测试通过。
- [ ] B0.G5 外部 HSM/CA 未提供时标记 `[EXT-BLOCKED]`，系统只允许 simulation。
- [ ] B0.G6 无有效 corridor admission/rulebook/责任签字时禁止 pilot/live payment。
- [ ] B0 COMPLETE。

---

# B1 PostgreSQL 数据库基线、迁移与租户隔离

## B1.1 冻结历史迁移并建立显式生产迁移

- [x] B1.1.1 将 `0001/0002/0003` 记录为 immutable baseline。
  - 新增：`docs/database/MIGRATION_BASELINE.md`，记录 revision hash 和已知历史缺陷。
  - CI 校验迁移文件 hash，禁止后续静默修改历史 revision。

- [x] B1.1.2 新增显式生产关系完整性迁移（实际 revision 为 `0008_production_relational_integrity.py`，因 `0006` 已被占用）。
  - 不允许通过 `Base.metadata.tables` 动态建表。
  - 使用显式 `op.create_table/op.create_foreign_key/op.create_index/op.create_check_constraint`。
  - 为 tenant、participant、account、order、fact、decision、reservation、leg、journal、entry、case、report、outbox/inbox 建立 Foreign Key。

- [x] B1.1.3 修复当前 production 模型完全没有 Foreign Key 的问题。
  - 修改：`backend/production/models.py`。
  - 指定删除策略：金融/审计记录 `RESTRICT`；不可使用级联删除抹掉历史。
  - 增加 relationship 仅用于导航，不得依赖 ORM cascade 删除。

- [x] B1.1.4 将金额、计数器和序列列升级为 `BigInteger`。
  - 覆盖：payment、quote、reservation、settlement、return、ledger balance、journal entry、limit、report totals。
  - 迁移必须先检查溢出和负数数据。

- [x] B1.1.5 将生产时间列改为 `DateTime(timezone=True)`。
  - 清理 naive/aware 比较补丁；数据库统一保存 UTC。
  - 测试 DST、不同 client timezone 和旧数据 backfill。

## B1.2 数据修复与约束

- [x] B1.2.1 新增 `backend/scripts/audit_production_data.py`。
  - 只读输出 orphan、重复、null、非法状态、金额溢出、tenant 不一致、hash 缺失。

- [x] B1.2.2 新增 `backend/scripts/repair_production_0006.py`。
  - dry-run 默认；生成修复计划和 hash；执行需 operator + checker evidence。
  - 修复 `PaymentOrder.tenant_id` 当前写 participant id 而非 tenant id 的数据。

- [x] B1.2.3 为所有状态列增加数据库约束或 PostgreSQL enum/domain。
  - 状态集合与 Python state machine 共享版本，禁止任意字符串。

- [x] B1.2.4 增加关键唯一约束。
  - UETR、instruction id 的参与方作用域、quote accept、return 累计序列、approval decision、event aggregate sequence、GL batch reference。

- [x] B1.2.5 增加金融不变量约束。
  - amount > 0、reserved >= 0、reserved <= balance（若余额投影保留）、有效期顺序、maker != checker、同币 journal 借贷平衡由 deferred constraint/transaction validator保证。

## B1.3 PostgreSQL RLS

- [x] B1.3.1 新增 `0007_production_rls.py`。（实际迁移编号：`0014_production_rls.py`，因 `0007` 已占用）
  - 对所有 tenant-owned 表启用并强制 RLS。
  - policy 使用 transaction-local `app.tenant_id`、`app.participant_id`、`app.service_identity`。

- [x] B1.3.2 新增 `backend/production/db_context.py`。
  - 每个事务开始时设置 `SET LOCAL` 上下文；连接池归还前不可泄漏。
  - 后台任务必须从事件 envelope 恢复 tenant，不允许使用全局管理员上下文。

- [x] B1.3.3 服务层继续保留 tenant filter，形成双层防护。
  - 修改所有 query；禁止 admin 仅因 scope 自动跳过 tenant，跨 tenant 操作使用单独 audited break-glass flow。

- [ ] B1.3.4 新增 `backend/tests/production/test_postgres_rls.py`。
  - 两租户相同业务键；读、写、join、count、outbox、evidence、报告均不能泄漏。
  - 测试连接池复用后 tenant context 不串线。

## B1.4 环境与迁移验收

- [x] B1.4.1 `backend/config.py`：pilot/live 只允许 PostgreSQL；SQLite 仅 sandbox/test。
- [x] B1.4.2 `.github/workflows/migrations.yml`：required table/column/constraint 集合加入全部 `prod_*`，不再只验 `ng_*`。
- [ ] B1.4.3 CI 执行 PostgreSQL upgrade → downgrade one revision → re-upgrade；比较 schema snapshot。
- [ ] B1.4.4 新增 `backend/tests/production/test_migration_data_preservation.py`，用旧 0003 fixture 数据升级并验证数据、FK、tenant、金额不丢失。
- [x] B1.4.5 新增备份/恢复脚本和 runbook：`backend/scripts/backup_production_db.py`、`docs/runbooks/DATABASE_RESTORE.md`。

## B1 Gate

- [ ] B1.G1 PostgreSQL clean install、旧数据 upgrade、单 revision rollback/re-upgrade 全部通过。
- [x] B1.G2 production schema 无 orphan、无非法 null、无未解释弱约束。
- [ ] B1.G3 RLS 与服务层跨租户负向测试通过。
- [x] B1.G4 SQLite 无法被误用于 pilot/live。
- [ ] B1 COMPLETE。

---

# B2 身份、Tenant、账户、额度、授权与双控

## B2.1 领域服务与 API

- [x] B2.1.1 新增 `backend/production/identity_service.py`。
  - 实现 Tenant/Participant/ServiceIdentity/Certificate 生命周期：PENDING → ACTIVE → SUSPENDED/REVOKED。
  - 删除业务请求中自动创建 participant/tenant 的行为；bootstrap 只能走受控管理流程。

- [x] B2.1.2 新增 `backend/production/identity_router.py`。
  - API：tenant、participant、service identity、certificate 创建/查询/更新/暂停/吊销。
  - 所有 ACTIVE/REVOKE 操作走 maker-checker，不允许创建接口直接 ACTIVE。

- [x] B2.1.3 新增 `backend/production/account_service.py` 和 `account_router.py`。
  - Account、AccountOwnership、owner evidence、币种、法人、状态和有效期。
  - 支付账户必须由 principal participant + tenant + active ownership 三者共同授权。

- [x] B2.1.4 实现正式 Rulebook acceptance。
  - 新增 `rulebook_service.py`、`rulebook_router.py`。
  - 校验 document digest、版本、生效日、participant 签署身份和 evidence。
  - 未接受当前版本的参与者不能发起交易。

## B2.2 mTLS、OAuth 与证书生命周期

- [x] B2.2.1 新增 `ClientCertificateAuthenticator`。
  - 从受信 ingress/ASGI TLS context 获取证书；不得相信任意客户端自报 fingerprint header。
  - 绑定 certificate → service identity → participant → tenant。

- [x] B2.2.2 修改 `backend/production/security.py`。
  - OAuth token scopes 与 service identity scopes、participant entitlement 取交集。
  - 验证 identity/certificate/environment/status/effective period。

- [x] B2.2.3 实现 certificate rotation overlap、revoke、OCSP/CRL refresh。
  - 新增 `certificate_service.py` 和 scheduler/worker 事件。
  - 吊销后现有 token 在规定 SLA 内失效。

- [x] B2.2.4 新增 `test_service_identity_binding.py`、`test_certificate_lifecycle.py`。
  - 覆盖错证书、错 token、错环境、吊销、轮换重叠、证书过期和 trust-domain 混用。

## B2.3 双边 Entitlement

- [x] B2.3.1 新增 `backend/production/entitlement_service.py`。
  - 双边键：origin participant、counterparty、direction、service、message type、corridor、currency、amount band、effective period。
  - 修改/激活/撤销必须 maker-checker。

- [x] B2.3.2 修复 `assert_entitlement()`。
  - 不能只在 Python 拉出候选后宽松匹配；查询必须 tenant-scoped、默认拒绝。
  - 对 wildcard 使用明确 policy，pilot/live 禁止无审批的 `*`。

- [x] B2.3.3 增加 entitlement version/evidence，并把命中版本写入 PaymentFact/Audit。

- [x] B2.3.4 新增 bilateral negative matrix 测试。
  - A→B 允许不代表 B→A；C 无权；币种/走廊/报文/期限任一不匹配均拒绝。

## B2.4 额度与暴露

- [x] B2.4.1 新增 `backend/production/limit_service.py`。
  - 单笔、日累计、在途、FX exposure、participant、corridor、currency、时间窗。
  - 不得通过扫描历史 payment 后在应用层相加实现并发额度。

- [x] B2.4.2 新增 `prod_limit_counters`、`prod_exposure_positions` 和显式迁移。
  - 使用行锁/CAS 原子预占额度；失败事务自动释放或补偿。

- [x] B2.4.3 把 limit reservation id 写入 payment，并在取消/失败/完成时正确释放或结转。

- [ ] B2.4.4 新增并发测试：100 个请求争用同一额度，最终接受总额不得超过上限。

## B2.5 Mandate 与真正的 maker-checker

- [x] B2.5.1 新增 `backend/production/authorization_service.py`。
  - Mandate 校验 participant、tenant、account、debtor、amount、currency、purpose、validity、revocation 和 payment hash。
  - Approval 校验 aggregate type/id、action、payment hash、金额、审批策略和签字人。

- [x] B2.5.2 重写审批 API。
  - `POST /approvals` 只能由 maker 创建 PENDING。
  - 新增 `POST /approvals/{id}/decisions`，checker 身份来自 authenticated principal，不能来自请求 body。
  - 同一 subject、credential、人员组或不满足 SoD policy 时拒绝。

- [x] B2.5.3 增加 `prod_approval_decisions` append-only 表。
  - Approval projection 可更新，decision 记录不可更新/删除。
  - checker 的签名、时间、reason、policy version、evidence 必须保留。

- [x] B2.5.4 删除当前单请求直接 `APPROVED` 的逻辑。
  - 修改：现有 `backend/production/router.py` 相应路由。

- [x] B2.5.5 新增 `test_maker_checker.py`。
  - 同一调用者伪造 Alice/Bob 必须失败。
  - maker 换 credential、同一自然人、管理员越权、重复 decision、过期 approval 均有测试。

## B2 Gate

- [x] B2.G1 所有现有身份/账户/证书/mandate/rulebook 模型都有服务、API、状态机和测试，不再是“只建表”。
- [x] B2.G2 任一 credential 只能访问其 tenant/participant/account。
- [x] B2.G3 单一调用者无法完成 maker+checker。
- [ ] B2.G4 并发额度不超限。
- [x] B2.G5 rulebook 未接受、证书吊销、mandate 不匹配均 fail-closed。
- [ ] B2 COMPLETE。

---

# B3 幂等、Outbox/Inbox、Broker、Worker 与恢复

## B3.1 标准事件 Envelope 与 schema

- [x] B3.1.1 新增 `backend/production/events.py`。
  - EventEnvelope 字段：event_id、event_type、schema_version、tenant_id、participant_id、aggregate_id/type/version、sequence、partition_key、correlation_id、causation_id、trace_id、occurred_at、payload。

- [x] B3.1.2 扩展 outbox schema 和迁移。
  - aggregate sequence 唯一；tenant 不可空；payload/content hash；published_at；broker offset；lease heartbeat。

- [x] B3.1.3 新增 `asyncapi/production-events.yaml`。
  - 覆盖 payment、funding、FX、message、settlement、compliance、reconciliation、case、report 事件。

- [x] B3.1.4 新增事件兼容性测试。
  - 旧 consumer 能读取兼容版本；破坏性 schema 变更 CI 拒绝。

## B3.2 幂等记录

- [x] B3.2.1 重写 `ProductionIdempotencyService.begin()`。
  - 使用数据库原子 insert/upsert，不得在 `IntegrityError` 后 rollback 调用者完整事务。
  - 状态：STARTED/COMPLETED/FAILED_RETRYABLE/FAILED_FINAL/EXPIRED。
  - owner、locked_until、request hash、response、错误、attempt、trace。

- [x] B3.2.2 定义 STARTED 超时恢复策略。
  - 超时后先查询聚合/外部结果，再 takeover；不得盲目重做。

- [x] B3.2.3 给所有业务 POST 增加 idempotency contract test。
  - 同 key 同 body 返回同 response；同 key 异 body 409；并发同 key 仅一个业务效果。

## B3.3 Outbox claim、租约与顺序

- [x] B3.3.1 修复 `PROCESSING + lease_until IS NULL` 永久卡死。
  - 修改：`backend/production/runtime.py`。
  - migration backfill 旧 PROCESSING 事件；claim 条件包含 null/过期 lease。

- [x] B3.3.2 使用 PostgreSQL 原子 claim。
  - `SELECT ... FOR UPDATE SKIP LOCKED` 与状态更新同一事务。
  - 对相同 partition/aggregate 只允许处理最低 sequence。

- [x] B3.3.3 增加 lease heartbeat 与 worker ownership fencing。
  - 老 worker lease 失效后不得完成新 owner 已接管的事件。

- [x] B3.3.4 增加 published/outcome 去重。
  - broker publish confirm 后记录 broker metadata；崩溃重启通过 event_id 保证 consumer 幂等。

## B3.4 Broker 与 dispatcher

- [x] B3.4.1 新增 `backend/production/broker.py`。
  - Protocol：publish、subscribe、ack/nack、health。
  - sandbox memory adapter；pilot/live approved broker adapter。

- [x] B3.4.2 将 outbox dispatcher 与 payment business worker 分开。
  - 新增入口：`backend/scripts/run_outbox_dispatcher.py`、`backend/scripts/run_production_worker.py`。
  - pilot/live 禁止 FastAPI 进程内 worker。

- [x] B3.4.3 增加 schema registry adapter。
  - 发布前验证 event schema；未知 schema 进入 DLQ，不投递业务 handler。

## B3.5 Inbox、外部副作用与 crash window

- [ ] B3.5.1 Inbox receipt、领域变更和新 outbox 必须在同一数据库事务。
- [ ] B3.5.2 外部 connector 调用必须使用稳定 idempotency reference。
  - worker 崩溃后先调用 connector query-by-client-reference，再决定是否重发。

- [ ] B3.5.3 为每个 handler 定义恢复函数。
  - reserve、FX accept、message send、settlement submit、cancel、return 都必须有 query/recover。

- [ ] B3.5.4 新增 fault injection hooks，仅测试环境启用。
  - crash points：claim 后、inbox 后、外部调用前、外部成功后/DB commit 前、DB commit 后/ack 前。

## B3.6 DLQ、重放和运营

- [ ] B3.6.1 新增 DLQ 查询/详情 API。
- [ ] B3.6.2 新增 replay request 聚合。
  - replay 必须 operator 创建、checker 批准、记录原因和原 event hash；不能直接把状态改回 PENDING。

- [ ] B3.6.3 新增 worker heartbeat、lag、oldest event age、retry、DLQ metrics。
- [ ] B3.6.4 新增 runbook：`docs/runbooks/OUTBOX_RECOVERY.md`。

## B3.7 测试

- [ ] B3.7.1 `test_outbox_leases.py`：null lease、过期 lease、fencing、heartbeat。
- [ ] B3.7.2 `test_outbox_partition_order.py`：同 aggregate 顺序、不同 partition 并行。
- [ ] B3.7.3 `test_worker_crash_recovery.py`：全部 crash points 无丢失、无重复业务效果。
- [ ] B3.7.4 `test_broker_recovery.py`：broker unavailable/restart/publish timeout。
- [ ] B3.7.5 `test_dlq_replay.py`：权限、双控、重复 replay、审计。

## B3 Gate

- [ ] B3.G1 当前 null lease 卡死反例通过。
- [ ] B3.G2 多 worker、重复发布/消费、broker 重启无重复业务效果或丢失。
- [ ] B3.G3 外部成功后进程崩溃可 query 恢复，不会重复扣款/结算。
- [ ] B3.G4 DLQ replay 具有双控和完整证据。
- [ ] B3 COMPLETE。

---

# B4 Canonical Payment、状态机、撤销、退回与恢复

## B4.1 Payment Aggregate 与多维状态

- [ ] B4.1.1 新增 `backend/production/payment_aggregate.py`。
  - Payment aggregate 只通过 command 方法改变 projection；禁止 worker/router 任意赋值状态。
  - command：create、authorize、screen、reserve、accept_fx、deliver_message、settle、credit、cancel、return、suspend、resume、close。

- [ ] B4.1.2 拆分状态维度。
  - orchestration、authorization、compliance、funding、FX、message delivery、value settlement、beneficiary、reconciliation 各自独立。
  - `DELIVERED/NETWORK_ACKED` 不得等价于 `FINAL`；`CUSTOMER_COMPLETED` 不得自动等价于 operational close。

- [ ] B4.1.3 新增显式 state transition specification。
  - 文件：`backend/production/payment_state_machine.py`、`docs/domain/PAYMENT_STATE_MACHINE.md`。
  - 每个 transition 写明 guard、command、event、timeout、compensation、terminal semantics。

- [ ] B4.1.4 删除不合法捷径。
  - 当前 `CONTROL_CHECKS → CUSTOMER_COMPLETED`、`RESERVATION_PENDING → CUSTOMER_COMPLETED` 等未经证明的 transition 必须删除。

## B4.2 CAS 与并发控制

- [ ] B4.2.1 重写 `set_order_state()` 为真实 CAS。
  - SQL：`UPDATE ... WHERE order_id=:id AND version=:expected`；rowcount != 1 返回 version conflict。
  - 禁止仅 `SELECT FOR UPDATE` 后可选检查从未传入的 `expected_version`。

- [ ] B4.2.2 所有 command 必须传 aggregate expected version。
  - API 支持 `If-Match`/ETag 或 command version。
  - event envelope 带 aggregate version；旧事件不得覆盖新状态。

- [ ] B4.2.3 新增 `test_payment_cas.py`。
  - 并发撤销/结算、重复 event、乱序 event、stale API update 均不得丢失更新。

## B4.3 Append-only facts 与 decision

- [ ] B4.3.1 将 `_replace_fact()` 更名并重构为 `append_fact()`。
  - reference 保持业务引用，另加 fact sequence/version；不通过伪造 reference suffix 绕过唯一约束。
  - supersedes 关系有 FK；每个 fact 带 input/output hash、规则版本、evidence、actor、occurred_at。

- [ ] B4.3.2 AuthorizationDecision、ComplianceDecision、FinalityDecision 改为 append-only。
  - 禁止 `ProductionComplianceService.evaluate()` 和 worker 原地修改旧 decision。
  - 新决定创建新记录，projection 单独维护 latest decision id。

- [ ] B4.3.3 数据库限制 posted fact/decision 的 UPDATE/DELETE。
  - PostgreSQL trigger/privilege + 测试；修正操作使用 amendment/superseding record。

## B4.4 创建与授权

- [ ] B4.4.1 `ProductionPaymentService.create_payment()` 使用真实 tenant id。
- [ ] B4.4.2 UETR、instruction id、end-to-end id、transaction id 分开存储并建立作用域唯一性。
- [ ] B4.4.3 payment payload 先经过 B6 registry/gateway，再生成 canonical payment；不得直接调用 `nextgen.standards`。
- [ ] B4.4.4 authorization 必须调用 B2 `AuthorizationService`，校验 mandate/approval/payment hash 全字段，sandbox 自动 PASS 仅限 `/sim`。
- [ ] B4.4.5 建立 payment graph。
  - original、cancellation、return、investigation、FX trade、settlement leg、journal、report 使用明确关系/FK。

## B4.5 撤销聚合

- [ ] B4.5.1 新增 `backend/production/cancellation_service.py`。
  - CancellationRequest 有自己的状态机：REQUESTED/VALIDATING/SENT/ACCEPTED/REJECTED/UNKNOWN/CLOSED。

- [ ] B4.5.2 修复“撤销后仍预留资金”的 P0 缺陷。
  - 撤销接受后停止后续 message/value 事件。
  - 释放全部 RESERVED funding/limit/FX exposure。
  - 已发生外部调用时先 query，按 finality 决定取消、退回或人工案件。

- [ ] B4.5.3 撤销成功后进入合法 terminal projection。
  - `EXECUTION_CANCELLED → OPERATIONALLY_CLOSED_UNSUCCESSFUL`，关闭前必须通过资金/消息/外部状态对账。

- [ ] B4.5.4 处理竞态。
  - cancel-before-reserve、cancel-during-reserve、cancel-vs-message、cancel-vs-finality、重复 cancel。

- [ ] B4.5.5 新增 `test_payment_cancellation.py`。
  - 必须包含当前反例：取消后 reservation 不得为 RESERVED，后续 message 不得停在无限重试。

## B4.6 退回聚合

- [ ] B4.6.1 新增 `backend/production/return_service.py`。
  - ReturnPayment 独立状态机和 UETR；关联原支付但不修改原始事实。

- [ ] B4.6.2 使用行锁/原子累计控制 over-return。
  - 并发两个 100% return 只能一个成功；金额按原结算/入账定义，处理费用和 FX 差异。

- [ ] B4.6.3 return 必须生成资金/结算 leg、ledger reversal/return journal、message 和 evidence。
- [ ] B4.6.4 处理 partial/multiple return、return rejection、UNKNOWN、重复 external response。
- [ ] B4.6.5 新增 `test_payment_returns.py`，覆盖并发超额、部分退回、重复请求和账本闭环。

## B4.7 Timeout、UNKNOWN 与补偿

- [ ] B4.7.1 新增 `prod_payment_timers` 和 timer worker。
  - timer 类型：authorization、compliance、funding、FX、delivery、settlement、beneficiary、reconciliation。

- [ ] B4.7.2 外部 timeout 一律进入 UNKNOWN/QUERY_REQUIRED。
  - 禁止直接标失败并自动重发可能已成功的资金操作。

- [ ] B4.7.3 新增 `backend/production/recovery_service.py`。
  - 根据 connector client reference 查询并恢复；无法判断时开 case，不自动猜测。

- [ ] B4.7.4 定义 compensation table。
  - 每一步明确 release/return/reversal/manual action；补偿本身也幂等、有事件、有证据。

## B4.8 Completion projection

- [ ] B4.8.1 新增 `CompletionPolicyEvaluator`。
  - 从 versioned CompletionProfile 读取必需事实；不得在 worker 里硬编码“执行完就完成”。

- [ ] B4.8.2 `CUSTOMER_COMPLETED` 前必须有 beneficiary credit 的已验证证据。
- [ ] B4.8.3 `OPERATIONALLY_CLOSED` 前必须满足 B5 journal、B7 finality、B8 reconciliation 和无未决 reservation/case。
- [ ] B4.8.4 completion evaluation 结果本身写 evidence，包含 profile/version/input facts/hash。

## B4 Gate

- [ ] B4.G1 同币和跨币 happy path 通过且每个状态均可追溯。
- [ ] B4.G2 拒绝、撤销、退回、UNKNOWN、恢复、补偿全路径通过。
- [ ] B4.G3 当前撤销冻结资金反例通过。
- [ ] B4.G4 并发 CAS、乱序和重复事件测试通过。
- [ ] B4.G5 无账本/终局/对账证据时不能 operational close。
- [ ] B4 COMPLETE。

---

# B5 资金预留、不可变账本、负债边界与 GL Bridge

## B5.1 会计领域模型

- [ ] B5.1.1 拆分 `backend/production/ledger.py`。
  - 新增：`ledger_models.py`、`ledger_service.py`、`funding_service.py`、`gl_bridge.py`、`ledger_router.py`。
  - 旧 `ledger.py` 仅保留兼容导入或删除重复路径。

- [ ] B5.1.2 扩展模型和显式迁移。
  - LegalEntity、LedgerBook、LedgerAccount、Journal、JournalEntry、Hold、BalanceSnapshot、LedgerPeriod、Fee/Tax、FxRevaluation、GlMapping、GlBatch、GlReceipt。
  - 每个对象 tenant、legal entity、book、business date、currency、version、evidence 完整。

- [ ] B5.1.3 明确账户类型和正常余额方向。
  - asset/liability/equity/income/expense/contra/suspense；不能统一用 credit 加、debit 减。

- [ ] B5.1.4 LiabilityProfile 真正接入。
  - 明确平台是权威账本还是运营机构 mirror；记录负债主体、2.0 利息、存保、准备金/保证金规则版本。

## B5.2 不可变分录

- [ ] B5.2.1 Journal 先 DRAFT/VALIDATED，再原子 POSTED。
  - POSTED journal/entry 禁止 UPDATE/DELETE。
  - journal idempotency key 和 business reference 唯一。

- [ ] B5.2.2 数据库层验证每个 journal、每个 currency 借贷平衡。
  - 多币 journal 拆成独立 currency groups 和明确 FX clearing legs。

- [ ] B5.2.3 余额必须可从 entries 重建。
  - `balance_minor` 如保留只能是带 version 的 projection/cache，不能成为唯一权威。

- [ ] B5.2.4 新增 reversal。
  - 不修改原 journal；创建相反分录并链接 `reverses_journal_id`、reason、approval、evidence。

- [ ] B5.2.5 新增 fee、tax、interest 和 adjustment journal templates。
  - 模板 versioned；科目映射和负债主体明确。

## B5.3 Hold/Reservation

- [ ] B5.3.1 用 `ProductionHold` 替代支付 worker 直接操作 connector reservation 字符串。
  - 状态：REQUESTED/HELD/CONSUMED/RELEASED/EXPIRED/UNKNOWN。
  - account、amount、currency、expiry、purpose、payment、external reference。

- [ ] B5.3.2 reserve/release/consume 使用行锁和 CAS。
  - `available = posted balance - active holds`，同一事务内检查和新增 hold。

- [ ] B5.3.3 所有失败/撤销路径必须释放 hold；所有完成路径必须 consume，不得遗留 RESERVED。
- [ ] B5.3.4 增加 hold expiry worker；到期前若外部状态 UNKNOWN，不可盲目释放。

## B5.4 支付集成

- [ ] B5.4.1 修改 `backend/production/worker.py`，注入 `FundingService` 和 `LedgerService`，禁止直接只用 `SandboxFundingConnector` 完成内部资金状态。
- [ ] B5.4.2 支付完成前生成并 POST payment journal。
  - debit payer/subledger source、credit settlement/beneficiary clearing；科目由 versioned template 决定。

- [ ] B5.4.3 FX payment 为 sell/buy/value 三类 leg 分别记账并按币种平衡。
- [ ] B5.4.4 return/cancellation/fee/adjustment 生成对应 journal/reversal。
- [ ] B5.4.5 CompletionPolicy 必须查询 posted journal ids；`journals=0` 时不得 `MATCHED/OPERATIONALLY_CLOSED`。

## B5.5 试算、期间与快照

- [ ] B5.5.1 重写 trial balance，从 POSTED entries 汇总 debit/credit/ending balance，不是简单求 account balance 总和。
- [ ] B5.5.2 LedgerPeriod 支持 OPEN/SOFT_CLOSED/CLOSED/REOPEN_PENDING。
  - closed period 禁止普通 posting；reopen 必须 maker-checker。

- [ ] B5.5.3 BalanceSnapshot 带 source max entry sequence/hash，可与 entries 重算验证。
- [ ] B5.5.4 试算不平立即阻断相关 completion/GL batch 并创建 SEV-0 case。

## B5.6 GL Bridge

- [ ] B5.6.1 实现 `GlMapping` version、科目转换和 batch builder。
- [ ] B5.6.2 GlBatch 保存 journal 范围、mapping version、debit/credit totals、payload hash。
- [ ] B5.6.3 支持发送、ACK、REJECTED、重送、receipt hash；不能生成文件后直接视为接收。
- [ ] B5.6.4 B8 四方对账读取真实 GlBatch/Receipt，不允许用 payment 字段伪造 `institution_gl_hash`。

## B5.7 测试

- [ ] B5.7.1 `test_ledger_properties.py`：引入 Hypothesis，随机 posting/reversal 后保持平衡和可重建。
- [ ] B5.7.2 `test_ledger_concurrency.py`：并发 hold、consume、release 无双花/负余额。
- [ ] B5.7.3 `test_ledger_immutability.py`：数据库拒绝修改/删除 posted entry。
- [ ] B5.7.4 `test_payment_ledger_integration.py`：每种 payment outcome 对应准确 journal/hold。
- [ ] B5.7.5 `test_gl_bridge.py`：mapping、batch、ACK、reject/replay、hash。

## B5 Gate

- [ ] B5.G1 当前“零 journal 仍完成并 MATCHED”反例必须失败。
- [ ] B5.G2 所有余额可由 entries 重建。
- [ ] B5.G3 posted entry 数据库不可变。
- [ ] B5.G4 并发/属性/故障测试无超额扣款或不平。
- [ ] B5.G5 GL batch 有真实 ACK/receipt 才能作为四方对账来源。
- [ ] B5 COMPLETE。

---

# B6 Standards Registry、ISO 20022 Gateway、Transaction Copy 与 Lineage

## B6.1 正式工件模型与导入

- [ ] B6.1.1 扩展 `ProductionStandardArtifact`。
  - 字段：artifact type、message set、release、community、source、license、raw content digest、signature、issuer、effective_from/to、approval、status。
  - digest 必须来自实际工件 bytes，不是 profile 名称元数据。

- [ ] B6.1.2 新增 `backend/production/artifact_store.py`。
  - 保存不可变工件到 approved object/WORM store；DB 保存 manifest。
  - sandbox 可本地只读目录，但仍校验 bytes digest。

- [ ] B6.1.3 新增 `backend/scripts/import_standard_artifact.py`。
  - 显式导入、验证、审批、激活；API 请求不得自动创建 artifact。

- [ ] B6.1.4 删除 `/standards/validate` 中 `ensure_artifact(...simulation_only=True)` 自动补工件。
  - 缺工件返回明确 fail-closed 错误，并记录 evidence/metric。

- [ ] B6.1.5 `[EXT-BLOCKED]` 获取获准使用的 XSD、code set、usage guideline、CBPR+/目标社区规则和正负样例。
  - 记录许可、来源、release digest 和合作方确认范围。

## B6.2 Registry 与版本日历

- [ ] B6.2.1 新增 `backend/production/standards_registry.py`。
  - 按 community/message/release/effective date/corridor/participant 查找 profile。
  - 支持 CURRENT/FUTURE/RETIRED，禁止调用者任意指定未批准 profile。

- [ ] B6.2.2 新增标准变更日历和 compatibility policy。
  - 文件：`docs/standards/STANDARDS_CALENDAR.md`、`docs/standards/PROFILE_COMPATIBILITY.md`。

- [ ] B6.2.3 payment 创建时由 registry 决定 profile，并把 artifact ids/digests 写入 validation evidence。

## B6.3 Gateway 验证

- [ ] B6.3.1 新增 `backend/production/standards_gateway.py`。
  - 安全 XML parsing、BAH、namespace、XSD、code sets、usage rules、business rules 分层返回错误。

- [ ] B6.3.2 生产路径删除对 `nextgen.standards.validate_message` 的直接依赖。
  - `nextgen` 只保留 sandbox/research。

- [ ] B6.3.3 支持首期批准消息集。
  - `pain.001/pain.002/pacs.008/pacs.002/pacs.004/camt.055/camt.056/camt.029`。
  - 每种报文是否启用由合作方批准结果控制，未批准不可假装支持。

- [ ] B6.3.4 防 XML 攻击。
  - 禁止 DTD/entity/network schema fetch；限制大小、深度、节点数；测试 XXE、billion laughs、namespace confusion。

## B6.4 Canonical mapping、copy 与字段血缘

- [ ] B6.4.1 新增 `backend/production/canonical_payment.py`。
  - 明确定义 canonical fields、类型、必填、分类、来源、可见性。

- [ ] B6.4.2 TransactionCopy 保存：
  - 原始 bytes、parsed canonical、outbound transformed copy、response copy。
  - 每个 copy 有 parent、artifact/profile、content hash、evidence、retention。

- [ ] B6.4.3 FieldLineage 必须逐字段记录。
  - source message/path/value hash → canonical field → target message/path/value hash → transform rule/version。
  - 不得只写一条 `document → ledger.instruction` 通用占位。

- [ ] B6.4.4 新增 protected-field policy。
  - UETR、金额、币种、付款人、收款人、账户、remittance 等变更规则明确。
  - 非法重生成 UETR、删除汇款信息、修改付款人必须拒绝/隔离并生成案件/evidence。

- [ ] B6.4.5 新增 loss report。
  - 每次 mapping 输出 mapped/defaulted/dropped/rejected 字段；生产路径要求零静默字段损失。

## B6.5 测试

- [ ] B6.5.1 `test_artifact_registry.py`：缺失、digest 错、过期、future、未批准、许可元数据。
- [ ] B6.5.2 `test_iso20022_xsd.py`：每种消息官方/获准正负样例。
- [ ] B6.5.3 `test_bah.py`：sender/receiver/message definition/business service 一致性。
- [ ] B6.5.4 `test_transaction_copy.py`：copy hash、不可变、版本关系。
- [ ] B6.5.5 `test_field_lineage.py`：逐字段可追溯、protected field 拒绝、零静默损失。
- [ ] B6.5.6 `test_xml_security.py`：XXE、实体、深度、大小、恶意 namespace。

## B6 Gate

- [ ] B6.G1 当前“请求时自动生成 embedded artifact”反例被拒绝。
- [ ] B6.G2 生产路径不再导入 nextgen sandbox validator。
- [ ] B6.G3 每个启用消息有真实 artifact digest、版本、许可、正负样例证据。
- [ ] B6.G4 任意 payment 字段可追溯到原始 copy 和 transform rule。
- [ ] B6.G5 零静默字段损失。
- [ ] B6 COMPLETE。

---

# B7 Compliance、FX、Connector 与 Finality

## B7.1 Compliance provider 与规则证据

- [ ] B7.1.1 将 `backend/production/compliance.py` 拆为 provider + orchestrator。
  - 新增：`compliance_provider.py`、`compliance_service.py`、`compliance_models.py`。
  - 删除仅检查 `SANCTIONS/TERROR/PROHIBITED` 字符串的生产语义。

- [ ] B7.1.2 定义 provider contract。
  - KYB/UBO/CDD reference、sanctions/PEP、AML/fraud、purpose/FX controls。
  - 返回 provider request id、input hash、rule/list/model version、match details、outcome、validity、evidence。

- [ ] B7.1.3 provider 故障 fail-closed。
  - timeout/unavailable → REVIEW_REQUIRED/UNKNOWN + case；不得 PASS。
  - query-by-request-id 恢复，禁止不确定状态盲目重复筛查后覆盖历史。

- [ ] B7.1.4 compliance decision append-only。
  - rescreen 创建新 decision；名单更新不回写旧 decision。

- [ ] B7.1.5 人工 override 使用 B2 maker-checker。
  - 保存 reason、obligation、有效期、审批人、规则版本和 evidence。

- [ ] B7.1.6 敏感 match/PII 单独 scope 和字段脱敏；普通 payment reader 不可见。

## B7.2 FX quote、position 与 liquidity

- [ ] B7.2.1 新增 `backend/production/fx_service.py`。
  - quote 绑定 participant、tenant、corridor、base/quote currency、amount、fees、provider、cut-off、expiry。

- [ ] B7.2.2 quote acceptance 使用行锁/CAS。
  - 过期、已接受、金额/币种/participant/payment 不匹配拒绝。
  - 同 quote 并发接受只能成功一次。

- [ ] B7.2.3 新增 position/exposure/reservation。
  - 每币种独立平衡；participant/corridor/provider exposure limit 原子占用。

- [ ] B7.2.4 FX provider timeout 使用 client reference 查询。
  - UNKNOWN 不得自动接受第二次；恢复后创建唯一 trade。

- [ ] B7.2.5 费用透明和 expected credit amount 写入 payment authorization/confirmation。

## B7.3 Connector registry 与资格

- [ ] B7.3.1 重写 `backend/production/connectors.py`。
  - 分离 MessageTransport、Funding、FxQuote、ValueSettlement、Statement、BeneficiaryCredit connector。
  - 每个实现有 capabilities、version、environment、qualification artifact、health。

- [ ] B7.3.2 删除通用 `QualifiedConnector.__getattr__` 占位作为“完成”依据。
  - 未安装实现时 registry 构建失败并 readiness=false。
  - 真实 adapter 使用显式类和显式方法。

- [ ] B7.3.3 新增 connector 配置 allowlist。
  - pilot/live 只能加载 attestation 中批准的 module/class/version；禁止动态任意 import。

- [ ] B7.3.4 connector 统一 resiliency。
  - connect/read timeout、retry classification、circuit breaker、rate limit、mTLS、HSM signing、idempotency、query。

- [ ] B7.3.5 新增 mock connector server。
  - 文件：`backend/tests/fixtures/connectors/`。
  - 能模拟 accepted、delivered、final、reject、timeout、late success、duplicate response、invalid proof。

- [ ] B7.3.6 `[EXT-BLOCKED]` 实现和认证真实目标轨道 connector。
  - 合作机构提供 endpoint、mTLS trust、消息/终局规则、statement、测试窗口和签字。

## B7.4 Finality proof

- [ ] B7.4.1 新增 `backend/production/finality.py`。
  - FinalityProfile 定义 accepted/irrevocable/final 事件、法域、责任主体、proof schema、签名/信任锚、query policy。

- [ ] B7.4.2 新增 `FinalityProofValidator`。
  - 校验 proof schema、签名、connector、transaction reference、amount、currency、participant、timestamp、状态和 profile version。

- [ ] B7.4.3 worker 不得信任 `ConnectorResult.state == FINAL`。
  - 必须先保存 raw proof，再由 validator 产生 append-only FinalityDecision，之后才能更新 settlement projection。

- [ ] B7.4.4 network ACK/delivery 与 value finality 明确隔离。
  - Message delivered 只能推进 message dimension，不能直接证明资金结算。

- [ ] B7.4.5 timeout → UNKNOWN → query。
  - late final、conflicting proof、proof invalid 自动案件化，不得自动重提本金操作。

## B7.5 Statement 与 beneficiary evidence

- [ ] B7.5.1 新增 statement connector/ingestion contract，供 B8 使用。
- [ ] B7.5.2 beneficiary credit 不能由 worker 本地构造 `sim-credit-*` 直接视为 CREDITED。
- [ ] B7.5.3 Credit evidence 校验 account/reference/amount/currency/time/provider signature。

## B7.6 测试

- [ ] B7.6.1 `test_compliance_provider.py`：规则版本、名单版本、timeout、rescreen、override、脱敏。
- [ ] B7.6.2 `test_fx_concurrency.py`：expiry、双 accept、position limit、provider late success。
- [ ] B7.6.3 `test_connector_contracts.py`：每种 connector 的 contract suite。
- [ ] B7.6.4 `test_finality.py`：ACK≠FINAL、invalid proof、timeout UNKNOWN、query recover、conflicting proof。
- [ ] B7.6.5 `test_beneficiary_credit.py`：缺证据/错误金额/错误币种不得完成。

## B7 Gate

- [ ] B7.G1 字符串黑名单不再是 production compliance 实现。
- [ ] B7.G2 FX 过期/并发/position/exposure 测试通过。
- [ ] B7.G3 qualified mode 不再只是 unavailable 占位。
- [ ] B7.G4 任一 FINAL 可追溯到验证过的外部 proof。
- [ ] B7.G5 ACK/DELIVERED、UNKNOWN、FINAL 三者不会混淆。
- [ ] B7.G6 外部 provider/connector 未获准部分保持 `[EXT-BLOCKED]`。
- [ ] B7 COMPLETE。

---

# B8 四方对账、Break、Investigation、报告与数据治理

## B8.1 四个真实来源

- [ ] B8.1.1 新增 `backend/production/reconciliation_sources.py`。
  - `PaymentSource`：canonical payment、amount/currency/value date/UETR。
  - `SubledgerSource`：B5 posted journal/entries/hold。
  - `ExternalStatementSource`：B7 connector statement/finality records。
  - `InstitutionGlSource`：B5 GlBatch + GlReceipt。

- [ ] B8.1.2 为每个 source 建 normalized record 和 manifest。
  - 字段：source type、source system、as-of、business date、record id、raw evidence、content hash、ingested_at。
  - hash 表示来源完整性，不能拿四个不同业务 payload 的 hash 是否相等当作业务匹配。

- [ ] B8.1.3 删除 worker 本地伪造 reconciliation source。
  - 禁止用 `order.payload_hash` 或 `{order_id, amount, currency}` 生成 `institution_gl_hash`。

- [ ] B8.1.4 ingestion 必须幂等。
  - 外部 statement/GL receipt 重复、修订、撤回有版本和 supersedes 关系。

## B8.2 Matching engine

- [ ] B8.2.1 新增 `backend/production/reconciliation_service.py`。
  - 匹配键：UETR、instruction/transaction reference、journal reference、external settlement reference、GL batch line reference。
  - 比较：amount、currency、value date、participant、direction、finality、fees。

- [ ] B8.2.2 定义 reconciliation state。
  - WAITING_SOURCES/PARTIALLY_MATCHED/MATCHED/BROKEN/UNDER_INVESTIGATION/RESOLVED。
  - 缺任一必需来源不能 MATCHED。

- [ ] B8.2.3 删除 `ProductionWorker._complete_payment()` 中无条件 `state="MATCHED"`。
  - 完成 payment 后只 enqueue reconciliation request。
  - B8 matching engine 收齐来源并匹配后才产生 MATCHED decision。

- [ ] B8.2.4 ReconciliationDecision append-only。
  - 保存 policy/version/input record ids/hashes/findings/evidence。

- [ ] B8.2.5 支持 tolerances，但 tolerance 必须 versioned、币种/场景特定、双控批准。

## B8.3 Break 与案件

- [ ] B8.3.1 扩展 `ProductionReconciliationBreak`。
  - break type：missing/duplicate/amount/currency/date/reference/finality/ledger/GL。
  - 保存 expected/actual、source records、severity、SLA、owner、state、evidence。

- [ ] B8.3.2 每个 material break 自动创建并关联 `ProductionInvestigationCase`。
  - 当前只创建 break 不创建 case 的逻辑必须删除。

- [ ] B8.3.3 新增 `backend/production/case_service.py`。
  - 状态：OPEN/ASSIGNED/WAITING_EXTERNAL/REMEDIATION_PENDING/RESOLVED/CLOSED。
  - comment/action/attachment/assignment/decision 全部 append-only。

- [ ] B8.3.4 case resolution 不能删除 break。
  - 解决动作创建 adjustment/reversal/replay/report correction；保留 before/after evidence。

- [ ] B8.3.5 高风险 resolution 使用 B2 maker-checker。

## B8.4 Scheduled reconciliation

- [ ] B8.4.1 新增独立 reconciliation worker/scheduler。
  - per payment near-real-time + intraday + end-of-day runs。

- [ ] B8.4.2 run 保存 population definition、watermark、source manifests、counts、totals、policy version。
- [ ] B8.4.3 late-arriving statement/GL 自动触发 re-match，不覆盖旧 run。
- [ ] B8.4.4 SEV-0：试算不平、重复本金、无法解释的总额差异；阻断相关 completion/batch。

## B8.5 Regulatory reporting

- [ ] B8.5.1 让 `ProductionReportBatch`、`ProductionReportReceipt` 真正进入 service/API。
  - 新增 `reporting_service.py` 和 report state machine。

- [ ] B8.5.2 report batch 从固定 data snapshot 构建。
  - 保存 source record ids、schema/rule version、period、row hashes、batch hash。

- [ ] B8.5.3 去重同一底层交易。
  - reporting key + report type + jurisdiction + period + version 唯一。

- [ ] B8.5.4 支持 VALIDATED/SUBMITTED/ACKNOWLEDGED/REJECTED/CORRECTED。
  - receipt 必须来自 receiver，不得本地生成 ACK。

- [ ] B8.5.5 correction 创建新 batch 并引用原 batch；不得修改已提交 payload。

- [ ] B8.5.6 `[EXT-BLOCKED]` 由合作机构/监管责任人提供国际收支、跨境人民币、准备金/保证金等正式 schema、责任和回执契约。

## B8.6 数据治理

- [ ] B8.6.1 新增字段级 data classification。
  - public/internal/confidential/restricted；PII、财务、合规 match、密钥元数据。

- [ ] B8.6.2 报告/案件/evidence API 实施字段脱敏、purpose limitation、tenant/role scope。
- [ ] B8.6.3 retention/legal hold/erasure exception 进入 versioned policy。
- [ ] B8.6.4 新增 `docs/data/DATA_INVENTORY.md`、`DATA_FLOW.md`、`RETENTION_POLICY.md`。
- [ ] B8.6.5 `[EXT-BLOCKED]` PIA、数据出境评估、接收方责任和保留期由 DPO/法律签字。

## B8.7 测试

- [ ] B8.7.1 `test_four_way_reconciliation.py`：完整 match、缺每一来源、金额/币种/日期/reference 差异。
- [ ] B8.7.2 明确测试：`journals=0`、`gl_receipt=0` 时绝不能 MATCHED。
- [ ] B8.7.3 `test_reconciliation_duplicates.py`：重复 statement/GL/payment。
- [ ] B8.7.4 `test_cases.py`：自动建案、SLA、resolution、before/after evidence、双控。
- [ ] B8.7.5 `test_reporting.py`：去重、版本、提交、ACK/reject、correction。
- [ ] B8.7.6 `test_data_access.py`：普通用户看不到敏感合规/报告数据。

## B8 Gate

- [ ] B8.G1 当前“journals=0、entries=0 仍 MATCHED”反例被阻止。
- [ ] B8.G2 四个真实 source 全部可追溯到 raw evidence。
- [ ] B8.G3 缺失/重复/金额/币种/日期不一致自动案件化。
- [ ] B8.G4 ReportBatch/Receipt 不再是只建表未使用。
- [ ] B8.G5 correction/解决动作保留前后证据。
- [ ] B8 COMPLETE。

---

# B9 真实 Operations Portal 与 Production BFF

## B9.1 Production BFF

- [ ] B9.1.1 新增 `backend/production/bff_router.py`。
  - 只组合 production services；不得读取 `nextgen` fixture/representative payload。

- [ ] B9.1.2 新增 command-center API。
  - 数据：真实 payment counts/value、outbox lag/DLQ、funding/FX exposure、settlement UNKNOWN、reconciliation breaks、case SLA、dependency health。

- [ ] B9.1.3 新增 payment search/detail API。
  - 搜索：UETR、instruction、participant、account token、state、date、amount/currency。
  - detail：canonical payment、facts、decisions、messages、reservations、FX、legs、journals、proof、reconciliation、cases、reports、audit timeline。

- [ ] B9.1.4 新增 operations queue API。
  - approval、compliance review、UNKNOWN settlement、DLQ replay、reconciliation break、case、report rejection。

- [ ] B9.1.5 新增真实 ledger/standards/connector/status API。
  - 所有 query tenant/role scoped；敏感字段按 B8 分类脱敏。

- [ ] B9.1.6 API 分页使用稳定 cursor，不允许生产大表 `.all()` 后内存聚合。

## B9.2 前端身份与 API client

- [ ] B9.2.1 重写 `frontend/src/api.ts`。
  - 使用 authenticated session/token；删除自报 `X-User-Role`、`X-User-Subject`、任意 participant header。
  - 统一 timeout、problem details、request id、retry policy；mutation 不自动重试。

- [ ] B9.2.2 新增类型化 clients。
  - `frontend/src/api/payments.ts`
  - `frontend/src/api/cases.ts`
  - `frontend/src/api/approvals.ts`
  - `frontend/src/api/reconciliation.ts`
  - `frontend/src/api/ledger.ts`
  - `frontend/src/api/standards.ts`
  - `frontend/src/api/operations.ts`

- [ ] B9.2.3 OpenAPI 生成 TypeScript types/client；CI 检查生成物未漂移。

## B9.3 移除生产 fixture

- [ ] B9.3.1 `frontend/src/App.tsx` 不再以 `fallbackBootstrap/fallbackCommandCenter` 初始化 production workspace。
- [ ] B9.3.2 investigations 页面改读真实 cases，不再显示 fixture `UetrLifecycle/MessageDiff`。
- [ ] B9.3.3 settlement 页面改读真实 legs/finality/ledger/reconciliation，不再显示代表性 DNS/PvP fixture。
- [ ] B9.3.4 standards 页面改读真实 registry/artifacts/findings/lineage。
- [ ] B9.3.5 risk/compliance 页面改读真实 decision/case/limit/exposure。
- [ ] B9.3.6 fixture/replay 保留时移动到明确 `/sim` workspace，并在视觉、路由、响应中标记 SIMULATION。
- [ ] B9.3.7 backend 不可用只显示 error/retry，不渲染任何可能被误解为真实的 fallback 数字。

## B9.4 页面实现

- [ ] B9.4.1 Command Center：真实指标、告警、依赖、队列。
- [ ] B9.4.2 Payments：列表、详情、多维状态、evidence lineage。
- [ ] B9.4.3 Investigations：queue、case detail、assignment、comments、resolution。
- [ ] B9.4.4 Approvals：maker queue、checker queue、SoD decision。
- [ ] B9.4.5 Settlement：message delivery 与 value finality 分栏；UNKNOWN/query。
- [ ] B9.4.6 Reconciliation：run、break、四来源 comparison、resolution。
- [ ] B9.4.7 Ledger：account、journal、entry、hold、trial balance、period、GL batch。
- [ ] B9.4.8 Standards：artifact/version/calendar、validation findings、transaction copy、field lineage。
- [ ] B9.4.9 Compliance/Risk：脱敏 decision、review、limits、FX exposure。
- [ ] B9.4.10 Administration：tenant/participant/identity/certificate/entitlement/rulebook 配置及双控。

## B9.5 实时更新与交互安全

- [ ] B9.5.1 使用受权 SSE/WebSocket 或 polling，支持 cursor/resume；断线不丢队列状态。
- [ ] B9.5.2 高风险动作显示 effect、reason、idempotency、maker-checker 状态；后端仍是唯一授权源。
- [ ] B9.5.3 所有 mutation 显示 request id、decision id、最终/异步状态；不能按钮成功就当业务成功。
- [ ] B9.5.4 loading/error/empty/partial/stale/permission-denied 状态齐全。
- [ ] B9.5.5 URL/日志/浏览器存储不得泄漏账户、合规 match、证书或 PII。

## B9.6 前端测试与性能

- [ ] B9.6.1 将 fixture-only 测试扩展为 production component tests。
- [ ] B9.6.2 新增 API error、permission、empty、stale、UNKNOWN、DLQ、case tests。
- [ ] B9.6.3 新增 Playwright E2E：payment → review → settlement → reconciliation → case/report。
- [ ] B9.6.4 E2E 验证 backend down 不显示代表性数据。
- [ ] B9.6.5 使用 dynamic import/manual chunks；解决当前约 1.1 MB JS chunk 警告并设 bundle budget。
- [ ] B9.6.6 accessibility：keyboard、focus、screen reader、contrast、reduced motion。

## B9 Gate

- [ ] B9.G1 `frontend/src/App.tsx` production workspace 不再 import/use fallback fixtures。
- [ ] B9.G2 所有核心页面有真实 production API。
- [ ] B9.G3 backend down、403、partial dependency failure 的 UI 行为通过 E2E。
- [ ] B9.G4 高风险动作后端权限+双控，UI 不能绕过。
- [ ] B9.G5 production 前端测试不再只有 2 个 fixture tests。
- [ ] B9 COMPLETE。

---

# B10 SRE、可观测性、DR、供应链、API 与交付文档

## B10.1 OpenTelemetry 与可观测性

- [ ] B10.1.1 在 runtime requirements 增加并锁定 OpenTelemetry。
  - FastAPI、SQLAlchemy、httpx、worker/broker instrumentation；OTLP exporter。

- [ ] B10.1.2 重写 `backend/production/telemetry.py`。
  - 使用真实 tracer/meter；删除 `contract-fallback/not-configured` 作为完成依据。
  - span attributes 禁止 PII；使用 payment/correlation ids 的安全 token。

- [ ] B10.1.3 定义 metrics。
  - request latency/error、payment state age、outbox lag/DLQ、worker heartbeat、connector latency/error/circuit、UNKNOWN age、hold age、trial balance、reconciliation break、case SLA、report rejection。

- [ ] B10.1.4 structured logs 接入 SIEM。
  - trace/request/actor/tenant/action/result/decision/evidence；敏感字段 redaction。

- [ ] B10.1.5 audit/evidence 输出到 approved WORM adapter。
  - 当前 `db://production-evidence` 仅 sandbox；pilot/live readiness 要求 WORM 可用。

## B10.2 SLO、告警与容量

- [ ] B10.2.1 新增 `docs/sre/SLO.md`。
  - availability、API latency、payment processing、UNKNOWN resolution、outbox lag、reconciliation、case response；定义 error budget。

- [ ] B10.2.2 新增 alert rules 和 dashboard definitions。
  - 目录：`ops/alerts/`、`ops/dashboards/`。

- [ ] B10.2.3 新增容量模型 `docs/sre/CAPACITY_MODEL.md`。
  - TPS、峰值、事件放大、DB/broker/storage、evidence retention、headroom。

- [ ] B10.2.4 新增 load tests。
  - 目录：`tests/performance/`；payment、query、outbox、ledger、reconciliation。
  - 验证目标负载下不超额扣款、不乱序、不丢事件。

## B10.3 Backup、Restore 与 DR

- [ ] B10.3.1 新增 `docs/runbooks/BACKUP_RESTORE.md` 和自动化脚本。
- [ ] B10.3.2 新增 `docs/runbooks/REGION_FAILOVER.md`。
  - RPO/RTO、fencing、DNS/traffic、DB/broker/object store、worker restart、external connector coordination。

- [ ] B10.3.3 restore 后自动执行：
  - ledger rebuild/trial balance；
  - outbox/inbox gap；
  - payment/external/GL reconciliation；
  - evidence chain verification。

- [ ] B10.3.4 CI/预生产定期执行 restore drill；保存 duration/result/evidence。
- [ ] B10.3.5 故障演练：DB failover、broker restart、HSM down、compliance down、connector timeout、WORM down、region loss。

## B10.4 Incident 与安全运营

- [ ] B10.4.1 新增 SEV 分类、on-call、沟通、监管/合作方通知 runbook。
- [ ] B10.4.2 为重复扣款、账本不平、未知终局、数据泄漏、密钥事件分别写 playbook。
- [ ] B10.4.3 更新 `docs/THREAT_MODEL.md`。
  - 覆盖 tenant escape、approval spoofing、event replay、connector compromise、proof forgery、insider、supply chain。

- [ ] B10.4.4 新增 control register/CSCF mapping，记录 owner、evidence、测试频率。
- [ ] B10.4.5 `[EXT-BLOCKED]` 独立渗透、红队、DR/BCP、审计和控制签字。

## B10.5 依赖锁、SBOM、签名与 provenance

- [ ] B10.5.1 重建 Python runtime lock。
  - 使用 `pip-compile --generate-hashes` 或等价工具。
  - 分开 `requirements.lock` 和 `requirements-dev.lock`；runtime lock 不包含 pytest/ruff/bandit 等开发工具。

- [ ] B10.5.2 `start.ps1`、Dockerfile、CI 全部从 hash lock 安装。
  - 禁止生产安装使用范围型 `requirements.txt`。

- [ ] B10.5.3 前端 CI 使用 `npm ci`，不再 `npm install`。
  - 校验 `package-lock.json` 与 package.json 一致。

- [ ] B10.5.4 使用正式 CycloneDX 工具生成 Python、npm、container SBOM。
  - 替换“CycloneDX-like”自制 JSON；CI schema validate。

- [ ] B10.5.5 生成制品 SHA、SBOM、provenance，并用 Sigstore/cosign 或批准系统签名。
- [ ] B10.5.6 release 验证签名/provenance/SBOM；不只验证 SHA256SUMS。
- [ ] B10.5.7 dependency audit、license policy、secret scan、SAST、container scan 均为阻断 gate。

## B10.6 CI/CD 与部署硬化

- [ ] B10.6.1 `.github/workflows/ci.yml` 使用新 locks，并运行所有 `backend/tests/production/`。
- [ ] B10.6.2 `.github/workflows/migrations.yml` 验证完整 `prod_*` schema、FK、RLS、constraints。
- [ ] B10.6.3 新增 PostgreSQL concurrency/fault/contract jobs。
- [ ] B10.6.4 新增 frontend Playwright E2E 和 bundle budget。
- [ ] B10.6.5 Docker 以 non-root、read-only filesystem、drop capabilities、固定 digest base image 运行。
- [ ] B10.6.6 `docker-compose.yml` 明确标记 development only；pilot/live 使用独立受控 deployment manifests。
- [ ] B10.6.7 migration、API、worker、scheduler、dispatcher 作为独立 deployment/job，不在 Web 进程自动 create_all/seed。

## B10.7 OpenAPI、AsyncAPI、SDK 与参与者体验

- [ ] B10.7.1 生成并版本化 `openapi/production-v1.yaml`。
- [ ] B10.7.2 完成 `asyncapi/production-events.yaml`，与 B3 schema registry 一致。
- [ ] B10.7.3 标准化 RFC 9457/Problem Details 错误码、重试语义和 correlation id。
- [ ] B10.7.4 生成至少一个受支持 SDK，并运行 contract tests。
- [ ] B10.7.5 新增 participant onboarding runbook、测试证书、sandbox scenario、正负样例、版本弃用策略。
- [ ] B10.7.6 API compatibility/diff 为 CI gate。

## B10.8 必须配套的文档

- [ ] B10.8.1 `docs/governance/PRODUCT_REGULATORY_BOUNDARY.md`
- [ ] B10.8.2 `docs/governance/CN_HK_CORRIDOR_ADMISSION_MATRIX.md`
- [ ] B10.8.3 `docs/governance/NETWORK_PARTICIPANT_RULEBOOK.md`
- [ ] B10.8.4 `docs/governance/RACI.md`
- [ ] B10.8.5 `docs/domain/PAYMENT_STATE_MACHINE.md`
- [ ] B10.8.6 `docs/api/API_VERSIONING.md` 与 OpenAPI/AsyncAPI
- [ ] B10.8.7 `docs/standards/ISO20022_PROFILES.md`
- [ ] B10.8.8 `docs/connectors/FINALITY_AND_CONNECTOR_SPEC.md`
- [ ] B10.8.9 `docs/ledger/ACCOUNTING_AND_RECONCILIATION.md`
- [ ] B10.8.10 `docs/compliance/CONTROL_SPEC.md`
- [ ] B10.8.11 `docs/reporting/REGULATORY_REPORTING_SPEC.md`
- [ ] B10.8.12 `docs/data/DATA_INVENTORY.md`、PIA/跨境评估引用
- [ ] B10.8.13 `docs/security/PKI_HSM_TRUST_POLICY.md`
- [ ] B10.8.14 更新威胁模型和控制矩阵
- [ ] B10.8.15 SLO、容量、监控、事件、DR 手册
- [ ] B10.8.16 测试策略、participant certification、evidence index
- [ ] B10.8.17 数据库 migration/rollback/data repair 手册

## B10 Gate

- [ ] B10.G1 telemetry 不再报告 `tracing/metrics=not-configured`。
- [ ] B10.G2 SLO 告警、容量、backup/restore、region failover 有实际演练证据。
- [ ] B10.G3 runtime/dev locks 分离且带 hash；CI/Docker 使用 lock。
- [ ] B10.G4 Python/npm/container SBOM 通过正式 schema 校验并随制品签名。
- [ ] B10.G5 production tests、PostgreSQL、fault、E2E、migration、security 均为 CI gate。
- [ ] B10.G6 OpenAPI/AsyncAPI/SDK contract tests 通过。
- [ ] B10.G7 外部审计/红队/DR/资质未完成项保留 `[EXT-BLOCKED]`。
- [ ] B10 COMPLETE。

---

# 11. 执行顺序与合并门槛

不得简单按文件数量并行勾选。推荐依赖顺序：

1. B0 安全边界、B1 PostgreSQL/约束/RLS。
2. B2 身份/账户/双控、B3 可靠消息。
3. B4 Payment Aggregate、B5 Ledger。
4. B6 Standards/Lineage、B7 Compliance/FX/Connector/Finality。
5. B8 Reconciliation/Reporting。
6. B9 Portal。
7. B10 SRE/DR/Supply Chain/Docs。

每个 B 使用以下合并门：

- [ ] M1 子项代码全部完成，禁止 placeholder。
- [ ] M2 对应迁移 upgrade/rollback/re-upgrade 通过。
- [ ] M3 对应测试文件已编写。
- [ ] M4 集中运行正常、负向、并发、重复、超时、恢复测试。
- [ ] M5 Ruff/format/typecheck/build 通过。
- [ ] M6 OpenAPI/AsyncAPI/schema compatibility 通过。
- [ ] M7 文档、runbook、metrics、alerts 同步。
- [ ] M8 Security/Domain/QA review 意见关闭。
- [ ] M9 外部依赖明确标为 `[EXT-BLOCKED]`，未伪造完成。
- [ ] M10 提交 SHA 和验收输出回填到本清单。

---

# 12. 当前已知反例回归表

这些反例是最终集中验收的最低集合；任何一条失败，B0–B10 总体不得标记完成。

- [ ] X01 不存在的 qualification attestation 路径导致 pilot/live 启动失败。
- [ ] X02 同一调用者在一个请求中伪造 maker/checker 被拒绝。
- [ ] X03 `PROCESSING + lease_until=NULL` outbox 可被安全恢复。
- [ ] X04 worker 在外部成功后、DB commit 前崩溃不会重复资金效果。
- [ ] X05 取消 payment 后无 RESERVED hold/reservation、无后续 message/value 发送。
- [ ] X06 两个并发 100% return 只能一个成功。
- [ ] X07 stale aggregate version 无法更新 payment。
- [ ] X08 缺 Standards artifact 时拒绝；不得自动创建 embedded artifact。
- [ ] X09 修改 UETR/付款人/金额或删除 remittance 被拒绝并有 evidence。
- [ ] X10 `journals=0` 时 payment 不得 operational close。
- [ ] X11 posted journal entry 无法 UPDATE/DELETE。
- [ ] X12 并发 hold 不超余额/额度。
- [ ] X13 network ACK/DELIVERED 不得变成 settlement FINAL。
- [ ] X14 settlement timeout 进入 UNKNOWN 并 query 恢复，不盲目重提。
- [ ] X15 invalid/conflicting finality proof 不得完成 payment。
- [ ] X16 缺 external statement 或 GL receipt 时 reconciliation 不得 MATCHED。
- [ ] X17 reconciliation 金额/币种/日期不一致自动创建 case。
- [ ] X18 backend unavailable 时 Portal 不显示 fixture/representative 数据。
- [ ] X19 tenant A 无法通过列表、详情、搜索、统计、报告、evidence 枚举 tenant B。
- [ ] X20 DB/broker/HSM/compliance/connector/WORM 故障演练后账本、事件和对账一致。

---

# 13. 最终验收记录

## 13.1 自动化结果

```text
Ruff:
Format:
Compile:
Backend unit:
Production unit:
PostgreSQL integration:
Concurrency:
Fault injection:
Migration roundtrip:
OpenAPI compatibility:
AsyncAPI compatibility:
Frontend unit:
Frontend E2E:
Frontend build/bundle:
Security scans:
SBOM validation:
Container smoke:
Load/performance:
Restore/DR drill:
```

## 13.2 签字/外部证据

- [ ] Product owner
- [ ] Payment domain owner
- [ ] Ledger/finance control
- [ ] Security
- [ ] Compliance/MLRO
- [ ] Data protection
- [ ] QA/certification
- [ ] SRE/operations
- [ ] 合作银行/数字人民币运营机构 `[EXT-BLOCKED until supplied]`
- [ ] 目标 connector/network owner `[EXT-BLOCKED until supplied]`

## 13.3 最终判定

- [ ] 所有 B0–B10 子项及 Gate 完成。
- [ ] X01–X20 全部通过。
- [ ] 无未关闭 P0/P1。
- [ ] 所有 `[EXT-BLOCKED]` 在进入对应环境前获得签字证据。
- [ ] 只有满足以上全部条件，才允许把状态从 `sandbox skeleton` 改为 `production kernel alpha`。

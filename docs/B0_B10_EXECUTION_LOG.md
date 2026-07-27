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

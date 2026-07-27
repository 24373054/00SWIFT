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

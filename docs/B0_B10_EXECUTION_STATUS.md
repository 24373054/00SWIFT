# B0–B10 执行状态与验收边界

更新时间：2026-07-28。

本文件记录本轮 Luna 工作的复核结论，不替代
`B0_B10_FULL_IMPLEMENTATION_CHECKLIST.md`。结论是：B0–B10 **没有全部完成**；
所有仍未勾选的子项、Gate 和 `B COMPLETE` 必须继续保持未完成。

代码默认仍为 `SWIFT_ENV=sandbox`。所有模拟连接器、标准工件和证据 URI
均显式标记为 simulation，不能宣称已取得 SWIFT、人民银行、香港金管局或
任何清算网络的生产资格。

| 批次 | 本地已验证的落地范围 | 仍未完成或外部阻塞 |
|---|---|---|
| B0 安全边界 | pilot/live 配置门禁、请求完整性接口、沙箱身份隔离和 simulation 标识 | 合格 HSM/CA/OCSP/CRL、真实签名验证、走廊法律与责任签字 |
| B1 数据库 | 0001–0003 immutable baseline 校验、SQLite clean install/round-trip、全部 production state/status 列的 state-v2 CHECK、沙箱旧库可恢复升级 | PostgreSQL clean/rollback、RLS 负向测试、真实 0003 遗留库数据保持 |
| B2 身份与控制 | tenant/participant/certificate/account/limit/mandate/approval 服务与本地测试 | 100-way PostgreSQL 额度竞争、正式 CA/rulebook/双控系统 |
| B3 消息可靠性 | 本地 outbox/inbox、租约、去重、DLQ 数据结构与单进程测试 | 合格 broker、多 worker、broker 重启、外部成功后崩溃恢复 |
| B4 支付生命周期 | 多维 projection、append-only facts、CAS、取消/退回基础聚合和本地 worker 流程 | 清单 B4.4.4、B4.6.3 及所有跨 B5/B7/B8 的完成 Gate |
| B5 账本资金 | hold/ledger/journal/period/GL bridge 基础服务和局部不变量 | payment worker 与账本闭环、真实 GL ACK、属性/并发/故障测试和四方对账来源 |
| B6 标准与副本 | 仅有现有 standards facade、artifact/transaction-copy/lineage 基础表 | registry/gateway、获准 XSD/规则包、逐字段 lineage、XML 安全和完整测试矩阵；B6 全部保持未完成 |
| B7 连接器终局 | simulation connector 与 qualified-mode fail-closed 边界 | 显式合格适配器、真实终局性 proof、provider 超时查询、beneficiary credit evidence；B7 未完成 |
| B8 对账报告 | operational summary、break 持久化和只读 report projection | 四个真实 source、独立 reconciliation worker/decision、case 闭环、监管回执与数据治理；B8 未完成 |
| B9 运维门户 | 新增真实 production payment 列表/提交视图和 API 失败态 | command center/investigation/settlement 等仍含 fixture，BFF、分页、生成 client、RBAC 与 E2E 未完成 |
| B10 SRE/供应链 | 一键沙箱启动、依赖锁、SBOM 生成入口、健康探针 | OTel/SLO/DR/容量、签名制品、OpenAPI/AsyncAPI/SDK、完整治理与 runbook Gate；B10 未完成 |

## 集中验收命令

```powershell
.\start.ps1 -NoBrowser -HealthCheck
.\.venv\Scripts\python.exe -m ruff check backend
.\.venv\Scripts\python.exe -m compileall -q backend
$env:PYTHONPATH='backend'
.\.venv\Scripts\python.exe -m pytest backend/tests -q
npm run typecheck --prefix frontend
npm test --prefix frontend
npm run build --prefix frontend
```

本轮结果：

- 一键启动：构建、迁移、服务启动、`/health`、`/production/v1/health` 全部通过；
  沙箱的 production readiness 按设计保持 `false`。
- 后端：`269 passed, 3 skipped, 1 warning`。
- 前端：typecheck 通过；`2` 个 test files、`3` 个 tests 通过；production build 通过。
- 静态检查：Ruff 与 `compileall` 通过。
- 三个跳过均为 `[EXT-BLOCKED]`：PostgreSQL 额度并发、PostgreSQL RLS、
  真实旧库数据保持；不得当作 Gate 通过。

任何 pilot/live 部署必须先提供
`PRODUCTION_QUALIFIED_ATTESTATION_PATH`、
`PRODUCTION_SIGNATURE_VERIFIER=qualified`、合格连接器和独立 worker；
缺少任一项，系统必须拒绝启动或拒绝写入。

# 数字人民币（e-CNY）跨境支付系统 — 设计文档

> 本文档是 00SWIFT 项目演进的正式设计基线。后续所有编码、测试以此为准。
> 起草时间：2026-07-06。状态：活文档，随实现迭代。

---

## 1. 系统定位

将现有"SWIFT 契约本地模拟器"演进为**数字人民币跨境支付系统**的技术原型，定位为：

- **底层账本**：中心化/联盟账本（类 mBridge 联邦节点模型）。
- **跨境模式**：双边/多边互操作，后续与 CIPS（人民币跨境清算系统）合作对接。
- **代码策略**：增量演进，保留现有 SWIFT 接口为"传统桥接"通道，不重写。
- **合规边界**：面向真实对接预留，含 KYC/AML/可控匿名/监管报送接口。当前实现仍为沙盒原型，不接真实资金网；但接口契约按真实对接方向设计。

**核心认知**：e-CNY 是央行数字货币（CBDC），是央行负债，与银行账户余额（商业银行负债）本质不同。跨境结算走账本原子结算（钱货两讫、无对手风险），而非 SWIFT 的代理行层层轧差。

---

## 2. 与现有 SWIFT 模型的本质差异

| 维度 | 现有 SWIFT 模型 | e-CNY 跨境模型 |
|------|----------------|---------------|
| 资产形态 | 银行账户余额（记账） | 央行数字货币（央行负债，可编程） |
| 清算方式 | 代理行轧差 + SWIFT 报文 | 账本原子结算（PvP，无对手风险） |
| 参与者 | 商业银行 | 央行 + 运营机构 + 钱包用户 |
| 核心概念 | BIC、IBAN、UETR | 钱包地址、可控匿名、智能合约 |
| 报文 | pacs.008（银行间贷记） | ISO 20022 扩展 + e-CNY 专有报文 |
| 跨境桥 | SWIFT GPI | mBridge 多边桥 / CIPS 双边通道 |

---

## 3. 可复用点清单（现有系统）

| 现有资产 | 复用方式 | 位置 |
|---------|---------|------|
| OAuth2 + JWT Bearer + PKI 鉴权 | 直接复用，新增 `ecny.*` scope | `auth/` |
| X-SWIFT-Signature 双重 base64 签名 | 复用为 X-eCNY-Signature | `auth/signature.py` `client/swift_signature.py` |
| JTI 防重放（内存 LRU + DB） | 直接复用 | `auth/jti_store.py` |
| SwAP error envelope 统一错误 | 复用，新增 eCNY 错误码前缀 | `core/errors.py` |
| 中间件（X-Request-ID + 审计 + 真实计时） | 直接复用 | `core/middleware.py` |
| ISO 20022 builder（防注入转义 + XSD 校验） | 复用框架，扩展 e-CNY 报文 | `iso20022/builder.py` `validators.py` |
| UETR 生成与追踪 | 直接复用（e-CNY 跨境仍用 UETR） | `iso20022/uetr.py` |
| PaymentState + 状态机 | 复用状态码与流转规则 | `iso20022/states.py` |
| SQLite + SQLAlchemy ORM | 直接复用，新增 e-CNY 表 | `database.py` |
| 三模式（sandbox/pilot/live） | 直接复用，e-CNY 同样支持三档 | `config.py` |
| 前端设计系统 + 组件库 | 直接复用，新增 e-CNY 页面 | `frontend/style.css` `app.js` |
| `/api/dev/sign` 签名辅助 | 复用机制（前端不持私钥） | `admin/dev_sign.py` |

---

## 4. 总体架构

```
┌─────────────────────────────────────────────────────────┐
│  前端 SPA（复用设计系统 + e-CNY 新页面）                  │
├─────────────────────────────────────────────────────────┤
│  FastAPI 路由层                                          │
│  ├─ api/swiftref preval gpi messaging  （SWIFT 桥接）    │
│  └─ api/ecny/*  （e-CNY 业务，新增）                     │
├─────────────────────────────────────────────────────────┤
│  鉴权层（复用 OAuth2/JWT/PKI/签名/JTI）                  │
├─────────────────────────────────────────────────────────┤
│  e-CNY 业务核心（新增）                                   │
│  ├─ ecny/ledger      中心化账本引擎                       │
│  ├─ ecny/wallet      钱包模型与分级                       │
│  ├─ ecny/issuance    央行发行/回笼                        │
│  ├─ ecny/bridge      mBridge + CIPS 互操作               │
│  └─ ecny/compliance  KYC/AML/监管预留                    │
├─────────────────────────────────────────────────────────┤
│  ISO 20022 报文层（复用 + 扩展 ecny_messages）            │
├─────────────────────────────────────────────────────────┤
│  数据层（SQLite，新增 e-CNY 表）                          │
└─────────────────────────────────────────────────────────┘
```

---

## 5. 数据模型（新增表）

软链接 convention（与现有一致，无外键）。

### 5.1 钱包与持有人
- `ecny_wallets`：钱包。字段：wallet_id（UUID）、holder_id、tier（1/2/3）、operator_id（运营机构 app_id）、currency（CNY）、balance（整数，单位：分，避免浮点）、status（active/frozen/closed）、created_at。
- `ecny_holders`：持有人 KYC。字段：holder_id、wallet_id、real_name、id_type、id_hash（SHA256，不存原文）、kyc_level、country_code、created_at。一类钱包强制实名；三类小额匿名（id_hash 为空）。

### 5.2 账本账户与流水
- `ecny_accounts`：账本账户。字段：account_id、owner_type（central_bank/operator/wallet）、owner_ref、currency、balance（分）、created_at。三类账户：央行发行库、运营机构库、钱包库。
- `ecny_transactions`：交易。字段：tx_id（UUID）、tx_type（mint/burn/transfer/exchange/cross_border）、status（pending/settled/failed）、uetr（跨境时）、amount、currency、from_account、to_account、memo（JSON）、created_at、settled_at。
- `ecny_entries`：流水明细（复式记账，每笔交易两条）。字段：entry_id、tx_id、account_id、direction（debit/credit）、amount、created_at。

### 5.3 跨境桥
- `ecny_bridge_channels`：桥通道。字段：channel_id、channel_type（mbridge/cips）、counterparty（对方央行/系统标识）、currency_pair（如 CNY/HKD）、status、fx_rate（JSON）、created_at。
- `ecny_bridge_transactions`：桥交易。字段：bridge_tx_id、uetr、channel_id、from_currency、from_amount、to_currency、to_amount、fx_rate、status、counterparty_ref、created_at、settled_at。

### 5.4 合规
- `ecny_compliance_reports`：监管报送记录。字段：report_id、tx_id、report_type（large_cash/suspicious/cross_border）、amount、currency、threshold、details（JSON）、created_at。

---

## 6. 账本引擎设计（ecny/ledger）

**账户模型**（非 UTXO）：每个账户一个余额，转账做原子借记/贷记。理由：中心化账本下账户模型更直观、查询快、适合监管追溯；UTXO 适合 DLT 隐私场景，后续 DLT 插拔时再切换。

**核心操作**：
- `mint(operator_account, amount)`：央行发行，借记央行发行库、贷记运营机构库。
- `burn(operator_account, amount)`：回笼，反向。
- `transfer(from, to, amount)`：通用转账，原子双写 + 复式记账 entries。
- `exchange(from_acct, to_acct, from_amt, to_amt, rate)`：外汇兑换（mBridge PvP 基础）。

**不变量**：
- 余额永不为负（透支即拒绝）。
- 每笔交易必须借贷相等（复式平衡）。
- 所有金额用整数（分），避免浮点误差。
- 交易状态机：pending → settled / failed，不可回滚已 settled。

**实现**：纯 Python，不依赖 FastAPI，传入 Session。可单测。

---

## 7. 钱包分级（ecny/wallet）

对齐 DC/EP 钱包分级：

| 级别 | 实名强度 | 单笔限额 | 日累计 | 余额上限 | 用途 |
|------|---------|---------|--------|---------|------|
| 一类 | 强实名 | 大额 | 大额 | 大额 | 大额支付 |
| 二类 | 中实名 | 中等 | 中等 | 中等 | 日常消费 |
| 三类 | 弱实名/匿名 | 小额 | 小额 | 小额 | 小额匿名 |

**可控匿名**：三类钱包不关联身份（id_hash 空），小额交易不可追溯；大额或一类钱包交易可追溯。阈值由配置控制。

限额检查在转账时强制：超限拒绝 + 触发合规标记。

---

## 8. 央行发行与回笼（ecny/issuance）

- `issue_to_operator(operator_id, amount)`：央行向运营机构发行 e-CNY（mint）。仅央行角色可调。
- `redeem_from_operator(operator_id, amount)`：运营机构回笼 e-CNY 给央行（burn）。
- `exchange_to_wallet(wallet_id, amount)`：运营机构向钱包兑换（运营机构库 → 钱包库）。
- `redeem_from_wallet(wallet_id, amount)`：钱包兑回（反向）。

发行总额度受配置上限约束（模拟央行额度调控）。

---

## 9. ISO 20022 e-CNY 报文（iso20022/ecny_messages.py）

复用 builder.py 的 `_esc` 转义 + XSD 校验框架。

- `build_pacs008_ecny(...)`：pacs.008 扩展，增加 `<Purp>` 标注 digital currency、`<Wllt>` 钱包标识字段。与现有 pacs.008 兼容（SWIFT 桥接时用）。
- `build_pacs002_ecny(...)`：状态报告，含账本结算确认。
- `build_ecny_issuance_msg(...)`：发行报文（e-CNY 专有，非 ISO 标准但用 XML 结构）。
- `build_ecny_cross_border_msg(...)`：跨境桥报文，含 channel、fx_rate、counterparty。

---

## 10. mBridge 多边桥（ecny/bridge/mbridge.py）

**模型**：多央行节点，各自发行本国 CBDC 在共享账本上；跨境支付做 PvP（交割对付）原子结算。

- `register_node(central_bank_id, currency)`：注册参与央行。
- `initiate_cross_border(from_wallet, to_wallet, from_amt, from_ccy, to_ccy, channel)`：发起跨境。
- `settle_pvp(bridge_tx)`：原子结算——同时借记付款方、贷记收款方（按 FX 换算），任一失败全回滚。

FX 汇率：sandbox 用固定种子汇率表；live 对接真实汇率源。

---

## 11. CIPS 双边通道（ecny/bridge/cips.py）

**模型**：人民币跨境清算双边通道，e-CNY ↔ 人民币跨境。

- `open_channel(counterparty_ref, fx_rate)`：开通道。
- `route_cross_border(payment)`：路由决策——mBridge（多边）还是 CIPS（双边），按币种/对手方选择。
- `settle_via_cips(bridge_tx)`：走 CIPS 清算，复用 UETR 追踪。

---

## 12. API 契约（api/ecny/router.py）

所有写端点强制 OAuth2 Bearer + X-eCNY-Signature（复用签名机制）。

| 端点 | 方法 | 说明 | Scope |
|------|------|------|-------|
| `/ecny/v1/wallets` | POST | 开立钱包 | ecny.wallet |
| `/ecny/v1/wallets/{id}` | GET | 查询钱包/余额 | ecny.wallet |
| `/ecny/v1/wallets/{id}/redeem` | POST | 钱包兑回 | ecny.wallet |
| `/ecny/v1/transfers` | POST | 钱包间转账 | ecny.transfer |
| `/ecny/v1/issuance` | POST | 央行发行（运营机构） | ecny.issuance |
| `/ecny/v1/cross-border` | POST | 发起跨境支付 | ecny.crossborder |
| `/ecny/v1/cross-border/{uetr}` | GET | 追踪跨境支付 | ecny.crossborder |
| `/ecny/v1/ledger/transactions` | GET | 账本浏览器 | ecny.ledger |
| `/ecny/v1/ledger/balance/{account_id}` | GET | 查账户余额 | ecny.ledger |
| `/ecny/v1/bridge/channels` | GET | 桥通道状态 | ecny.bridge |
| `/ecny/v1/compliance/reports` | GET | 合规报送记录 | ecny.compliance |

内部管理端点（`/api/ecny/*`）走 admin token：注入种子运营机构/央行账户、批量造数据。

---

## 13. 合规预留（ecny/compliance）

- `check_kyc(holder, tier)`：KYC 校验。
- `check_limits(wallet, amount)`：限额校验。
- `flag_large_cash(tx)`：大额现金交易标记（超阈值生成 report）。
- `flag_cross_border(tx)`：跨境交易标记。
- `flag_suspicious(tx)`：可疑交易规则引擎（占位，规则可扩展）。
- `generate_report(tx, type)`：生成合规报告入库。

---

## 14. 前端演进

新增 e-CNY 导航分组，5 个页面：

1. **数字钱包**：开立（选分级）、列表、余额、兑回。
2. **央行发行台**：发行/回笼、额度查看。
3. **跨境支付**：发起（选 mBridge/CIPS）、追踪、FX 预览。
4. **账本浏览器**：交易列表、复式记账明细、原子结算可视化。
5. **桥接监控**：通道状态、节点列表。

复用现有设计系统（SWIFT 金融专业风）、组件库、暗色模式、响应式。

---

## 15. 测试策略

- `tests/test_ledger.py`：账本引擎单测（mint/burn/transfer/exchange、不变量、透支拒绝）。
- `tests/test_wallet.py`：钱包分级、限额、可控匿名。
- `tests/test_issuance.py`：发行回笼、额度。
- `tests/test_bridge.py`：mBridge PvP 原子结算、CIPS 路由。
- `tests/test_messages.py`：e-CNY 报文生成 + 防注入 + XSD。
- `tests/test_compliance.py`：KYC/限额/大额标记。
- `tests/test_api_ecny.py`：API 端到端（鉴权、签名、流程）。
- pytest 全绿。

---

## 16. 实施顺序

1. 设计文档（本文档）✓
2. database.py 扩展 e-CNY 表 + 种子
3. ecny/ledger 账本引擎
4. ecny/wallet 钱包分级
5. ecny/issuance 发行回笼
6. iso20022/ecny_messages 报文
7. ecny/bridge mBridge + CIPS
8. ecny/compliance 合规
9. api/ecny 路由 + 挂载
10. catalogue 扩展
11. 单测全套
12. 前端 e-CNY 页面
13. 端到端验证 + 截图

---

## 17. 不做（明确边界）

- 不接真实 CIPS/mBridge 网络（仅契约对齐的本地模拟）。
- 不持真实资金。
- 不实现真实 DLT 共识（中心化账本；DLT 接口预留但不实现）。
- 不实现真实智能合约 VM（用 Python 规则模拟可编程逻辑）。
- 不面向真实终端用户（无真实 KYC 数据）。

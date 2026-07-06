# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

**SWIFT Developer Testing System v2** —— 一个契约对齐的双模沙盒：mock 模式完整模拟真实 SWIFT API 行为，live 模式经同一代码路径转发到真实 SWIFT endpoint。公开端点（`/oauth2/*`、`/swift-preval/*`、`/swiftrefdata/*`、`/swift-apitracker/*`、`/alliancecloud/*`）严格遵循官方 swagger，内部管理接口（`/api/*`）单独隔离并加 admin-token 鉴权。

v2 是基于 `research/` 下 14 个官方/第三方参考仓库（`swiftinc/*` 9 个 + ISO 20022 库 5 个）+ 3 份官方 swagger + SWIFT-API-Guide 的近完全重写。`research/` 保留供参考，不入版本库。

## 数字人民币（e-CNY）跨境支付子系统

在 SWIFT 沙盒之上增量演进，定位为**不依赖 SWIFT 的数字人民币跨境支付系统技术原型**。设计基线见 `docs/DESIGN.md`。

- **底层账本**：中心化/联盟账本（类 mBridge 联邦节点），复式记账，金额以"分"为单位避免浮点。`backend/ecny/ledger/`。
- **钱包分级**：DC/EP 一类（强实名·大额）/二类（中实名）/三类（小额匿名·可控匿名）。`backend/ecny/wallet/`。
- **央行发行/回笼**：mint/burn + 运营机构↔钱包兑换，发行总额度上限模拟央行调控。`backend/ecny/issuance/`。
- **跨境桥**：mBridge 多 CBDC 原子 PvP 结算（CNY↔HKD/THB/AED/USD/EUR）+ CIPS 人民币双边通道，自动路由。`backend/ecny/bridge/`。
- **ISO 20022 报文**：pacs.008/pacs.002 e-CNY 扩展 + 专有发行/跨境报文，复用防注入转义 + XSD 校验。`backend/iso20022/ecny_messages.py`。
- **合规预留**：KYC/限额/大额现金/跨境/可疑交易标记 + 监管报送。`backend/ecny/compliance/`。
- **API**：`/ecny/v1/*`（sandbox 接受 X-Admin-Token，pilot/live 走 OAuth scope `ecny.*`）；内部管理 `/api/ecny/*`。`backend/api/ecny/`、`backend/admin/ecny_admin.py`。
- **复用**：OAuth2/PKI/签名/JTI/SwAP 错误信封/中间件审计/UETR 追踪/三模式配置/前端设计系统全部复用。
- **SWIFT 桥接保留**：现有 `/swift-*`、`/alliancecloud/*` 接口完整保留，作为传统跨境通道桥接。
- **测试**：`backend/tests/` 36 个单测全绿（ledger/wallet/issuance/bridge/messages/compliance）。
- **前端**：新增"数字人民币 e-CNY"导航分组 5 页（概览/钱包/发行台/跨境/账本浏览器），复用设计系统。

## 技术栈

- **后端**：Python 3.12 + FastAPI + SQLAlchemy 2.0（同步）+ SQLite；PyJWT[crypto] + cryptography（PKI/RS256）；lxml（XSD 校验）；pacs008 + pyiso20022（ISO 20022）
- **前端**：原生 HTML/CSS/JS 单文件 SPA（v2 适配新端点 + SwAP 错误渲染 + 状态前端化）
- **运行**：uvicorn ASGI，前端由 FastAPI `FileResponse` 返回

## 常用命令

```bash
# 安装依赖（backend/ 下）
pip install -r requirements.txt

# 启动（sandbox 模式，自动生成 mock PKI CA + per-app client cert）
start.bat
# 或手动
cd backend && python -m uvicorn main:app --host 127.0.0.1 --port 8765 --reload

# 访问
#   前端        http://127.0.0.1:8765/
#   Swagger UI  http://127.0.0.1:8765/docs
#   health      http://127.0.0.1:8765/health

# 重新生成 SwiftRef 静态数据 fixture（ISO 4217/3166）
cd backend/data && python _gen_fixtures.py

# 生成 mock PKI 证书（创建 credential 时自动调用，也可手动）
python -m scripts.gen_mock_certs <consumer_key>
```

**无测试框架**：验证靠 `tests/`（待补）+ 端到端脚本（见下方验证流程）。无 lint/CI。

## 环境配置

复制 `backend/.env.example` 到 `backend/.env`。关键变量：
- `SWIFT_ENV`：`sandbox`（本地 mock + 自签 CA）/ `pilot`（真实 sandbox host + 真实 cert）/ `live`（生产，启动二次确认，写操作默认 dry_run）
- `ADMIN_API_TOKEN`：`/api/*` 鉴权 token；sandbox 模式下空值=禁用检查（本地便利），pilot/live 强制非空
- `LIVE_HOST_*`：pilot/live 模式下各模块的真实 host

## 架构

### 后端模块拓扑（`backend/`）

```
main.py              FastAPI 装配 + lifespan(init_db/seed/JTI清理) + 挂载所有 router + /api/* admin token
config.py            pydantic-settings, sandbox/pilot/live 三档
database.py          ORM 模型 + init_db + seed SwiftRef fixture (StaticPool for :memory:)
core/                基础设施（无业务）
  errors.py          SwAP 错误信封 {errors:[{code,severity,text,...}]} + SwiftRef 变体(REDA.API.*) + 异常处理器
  middleware.py      X-Request-ID 透传 + 实测延迟审计(替代旧硬编码 120/95/80)
  utils.py           cert/key 加载(cryptography, x5c, cert_subject RFC4514 lower)
  bic.py             HEADER_BIC_RE(小写 x-bic) + DATA_BIC_RE(大写 BICFI) + validate_bic
  iban.py            mod-97 + 国家 BBAN 结构表
  time.py            now_utc() 替代弃用的 utcnow()
auth/                OAuth + 签名
  oauth.py           /oauth2/token(jwt-bearer RS256 验证) + /oauth2/revoke + scope + verify_bearer_token
  signature.py       X-SWIFT-Signature 验签(digest=base64(sha256(base64(body))) 双重编码 quirk)
  dependencies.py    require_scopes/require_signature/require_x_bic/get_cred/require_admin_token
  jti_store.py       JTI 防重放(DB 表 + 内存 LRU)
api/                 业务端点（每模块一包，挂载在真实 SWIFT 基路径）
  preval/            /swift-preval/v2 — 9 端点 + PaymentInstruction orchestrator
  swiftref/          /swiftrefdata/v4 — P1 GET + repository(mock 查 DB)
  gpi/               /swift-apitracker/v4 — 5 端点 + Camt schemas
  messaging/         /alliancecloud/v2 — fin send/distributions/ack/nak
  catalogue.py       /api/catalogue — 真实基路径与 scope
iso20022/            builder(escape-safe + lxml XSD) + validators + states(TransactionIndividualStatus5Code) + uetr
client/              客户端层（live 模式 + 测试驱动）：oauth_token/swift_signature/api_client/utils
admin/               /api/* 内部管理（admin token 鉴权）：credentials(自动签 mock cert)/payments(注入测试支付)/dashboard
scripts/             gen_mock_certs.py — mock CA + client cert 一键生成
data/                SwiftRef fixture: bics.json/currencies.json/countries.json/ibans.json + _gen_fixtures.py
certs/               PKI 证书(gitignore): ca/ + apps/
```

### 关键设计决策

- **OAuth 全真**：`grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer`，客户端用 RS256 私钥签 JWT assertion（iss=consumer_key, sub=cert_subject RFC4514 lower, aud=token_url, x5c 证书链 in header）；服务端用存储的 client cert 验签 + jti 防重放。sandbox 模式签 RS256 JWT token（可解码），pilot/live 发 opaque token（匹配真实 SWIFT）。
- **签名全验**：POST 写端点强制 `X-SWIFT-Signature`（RS256 JWT，digest=base64(sha256(base64(body))) 双重编码）。缺签名返回 SwAP509。
- **错误信封**：统一 `{errors:[{code,severity(Fatal|Transient|Logic),text,user_message?,more_info?}]}`；SwiftRef 用 `REDA.API.*` 码。绝不返回 boolean/PASS/FAIL。
- **ISO 20022 双保险**：builder 用 `_esc()` 转义所有用户输入（防注入）+ lxml XSD 校验（pacs008 包自带 XSD）。pacs008 库的 `generate_xml_string` 在 Windows 上路径校验有兼容问题，故直接用其 XSD 文件做校验。
- **状态码**：`TransactionIndividualStatus5Code` 全集（PDNG/ACCP/ACSP/ACSC/ACCC/RJCT/CANC/PART），前端通过 `/api/states` 拉取（单一来源，消除旧前后端重复）。
- **`/transition` 已移除**：状态流转改走 `POST /payments/{uetr}/status`（CamtA0100105 状态确认）。

### 数据模型（database.py）

- `AppCredential`：加 `cert_pem`/`cert_x5c`/`cert_subject`/`allowed_scopes`
- `OAuthToken`、`ApiRequest`（latency 现为实测）、`PaymentState`（加 `transaction_status`/`service_level`/`payment_scenario`/`from_bic`，旧 `state`/`history` 保留）
- 新增：`JtiRecord`（防重放）、`FinMessage`+`MessageDistribution`（Messaging）、`SwiftRefBic/Iban/Currency/Country`（seed 自 data/*.json）

## 验证流程（端到端）

启动后，用 `client/` 或 Request Builder 走：
1. `POST /api/credentials` → 自动生成 mock cert
2. 客户端用私钥签 JWT assertion → `POST /oauth2/token` → access_token
3. `POST /swift-preval/v2/payment/payment-instruction`（x-bic + X-SWIFT-Signature）→ `PaymentInstructionValidation`
4. `GET /swiftrefdata/v4/bics/DEUTDEFFXXX/validity` → `VBIC`
5. `POST /api/payments`（注入测试支付）→ `GET /swift-apitracker/v4/payments/{uetr}/transactions` → `POST /payments/{uetr}/status`（ACCC，签名）→ cancellation（签名）
6. `POST /alliancecloud/v2/fin/messages`（签名）→ `GET /distributions` → `POST /distributions/{id}/acks`（签名）

## 参考资源

- 官方 swagger：`research/api-sample-code/dotnet/{PreVal,SwiftRef,MessagingApi}/*/SWIFT-API-*.yaml`
- 客户端实现移植源：`research/api-sample-code/python/messaging-api/app/api/{oauth_token,swift_signature,api_client,utils}.py`
- GPI 状态码参考：`research/gpi-v5-demo-app/src/main/java/com/swift/developers/sandbox/DemoApp.java`（ACCC + 业务服务前缀）
- SWIFT API 设计规范：`research/SWIFT-API-Guide/docs/{security,errors,http-headers}.md`

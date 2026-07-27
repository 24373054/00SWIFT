# ADR-001：生产资格边界

状态：Accepted（sandbox implementation）

本仓库实现的是可审计的跨境支付编排与 subledger 骨架。它不自行成为 SWIFT、CIPS、数字人民币运营机构或监管报送系统，也不伪造 HSM、PKI、最终性证明、机构 GL 或合规名单结果。

pilot/live 必须同时具备：

1. 经批准的 connector attestation 文件；
2. 独立部署的 qualified signature verifier 与密钥/HSM 适配器；
3. 双向 mTLS、证书吊销检查、重放保护和网络方 finality proof；
4. 正式 rulebook、ISO 20022 工件及版本签名；
5. 运营机构账单、GL bridge、对账回执和灾备演练证据。

在这些外部证据缺失时，配置门禁和 connector registry 均 fail-closed。simulation 仅用于本地开发和自动化回归，并在 API、证据和健康检查中显式标注。

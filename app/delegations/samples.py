"""仓内代理登记与代理例外样例（虚构）。统一供页面、接口与测试使用。"""

DELEGATIONS=[
    {"id":"D-01","owner":"data-steward","delegate":"analyst","resource":"orders",
     "from_partition":"2026-09","to_partition":"2026-12",
     "start":"2026-11-01T00:00:00Z","end":"2026-12-01T00:00:00Z","status":"active"},
    {"id":"D-02","owner":"data-steward","delegate":"analyst","resource":"customers",
     "from_partition":"2026-01","to_partition":"2026-12",
     "start":"2026-11-01T00:00:00Z","end":"2026-12-01T00:00:00Z","status":"revoked"},
    {"id":"D-03","owner":"finance-owner","delegate":"auditor","resource":"customers",
     "from_partition":"2026-01","to_partition":"2026-12",
     "start":"2026-11-01T00:00:00Z","end":"2026-12-01T00:00:00Z","status":"active"},
]

EXCEPTIONS=[
    {"id":"X-01","principal":"business-user","resource":"orders","partition":"2026-10",
     "approved_by":"analyst","approved_at":"2026-11-16T08:00:00Z",
     "approver_text":"analyst（代 data-steward）","note":"月末出数窗口放行",
     "material":"邮件批准原文：仅限 orders 2026-10 分区，代理人 analyst 呈批。"},
    {"id":"X-02","principal":"analyst","resource":"orders","partition":"2026-10",
     "approved_by":"analyst","approved_at":"2026-11-16T08:00:00Z",
     "approver_text":"analyst（代 data-steward）","note":"同一分区但与既有拒绝重叠",
     "material":"邮件批准原文：analyst 申请 orders 2026-10 例外。"},
    {"id":"X-03","principal":"business-user","resource":"orders","partition":"2026-05",
     "approved_by":"analyst","approved_at":"2026-11-16T08:00:00Z",
     "approver_text":"analyst（代 data-steward）","note":"分区超出代理登记范围",
     "material":"邮件批准原文：申请 orders 2026-05 例外，代理人 analyst 呈批。"},
    {"id":"X-04","principal":"business-user","resource":"orders","partition":"2026-10",
     "approved_by":"guest","approved_at":"2026-11-16T08:00:00Z",
     "approver_text":"guest","note":"批准人无任何代理登记",
     "material":"邮件批准原文：guest 批准 orders 2026-10 例外。"},
]

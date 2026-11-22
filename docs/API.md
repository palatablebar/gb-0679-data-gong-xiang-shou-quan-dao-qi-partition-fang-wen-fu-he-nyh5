# 接口

模块GET使用仓内样例，模块POST可传csv或rows与context，直接计算当前规则。/api/runs使用完整流水线并原子保存。每个阶段返回rows、quarantine、metrics；后续阶段还返回累计隔离。/api/upload接收multipart文件file。/api/runs/<id>/archive只导出一份带清单与证据的CSV。

## 代理例外

- `GET /api/exceptions`：返回全部代理例外的唯一生效判断、历史版本与 primary（首个）。
- `GET /api/exceptions/<id>`：返回该例外的判断与已落库版本（已落库优先于现算）。
- `POST /api/exceptions/<id>/publish`：计算并持久化判断。内容指纹一致则复用版本（body 可带 delegations 与 grants 覆盖样例）。
- `POST /api/exceptions/<id>/confirm`：body `{owner,decision}`，仅登记里的负责人本人对挂起态有效（decision 为 allow/deny）。
- `GET /api/exceptions/<id>/archive`：导出该例外单份证据 CSV，含四视图与原始批准材料。

判断字段：`status`（effective/pending_owner_confirmation/denied_by_conflict/owner_declined/not_delegated/invalid）、`decision`（allow/deny/pending）、`responsible`、`basis`（登记号）、`reasons`、`content_sha256`、`checks.{permission,conflict,partition,archive}`。`/api/runs/<id>/archive` 会追加 kind=exception 行，evidence 内为同一判断。

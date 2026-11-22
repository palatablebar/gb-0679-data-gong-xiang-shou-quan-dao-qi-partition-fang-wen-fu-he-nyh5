# 授权定义

资源orders与订单等价，customers与客户等价。principal为主体文本，不支持模糊主体。partition为YYYY-MM；分区授权[start,end)不含end月。授权时间也为[start,end)，到期时刻立即失效。

每条授权包含主体、资源、生效窗、分区窗和allow/deny。全部条件必须同时匹配。拒绝优先，多个允许不能覆盖任何显式拒绝；无匹配默认拒绝。匹配规则ID按字典序稳定排序，冲突显示全部允许与拒绝证据。

observed为真实访问执行结果allowed或blocked；reported为上游0/1判定，留作证据。expected为实际授权复算，分区模块重建reported为执行结果便于二值对账。越权放行和误拦截分别计数，禁止用相互抵消的总数代替逐条核查。

业务ID和超大整数按文本保形；Decimal参与数量金额计算，对外序列化为字符串。哨兵集合定义在app/values.py，缺失值不能当零。所有时间带UTC偏移，先转UTC比较，业务日按指定地区划分。区间统一[start,end)。重复业务键保留第一条、完全相同行计重复；值冲突行隔离且保留原值。空文件、全空白、仅表头分开拒绝。

运行清单包括输入sha256、规则版本、参数、生成时刻与耗时。源行编号以CSV解析器的物理结束行号表示，引号内换行不增加记录数。输入超过4MB返回413，非法表头和类型返回422，失效版本复核返回409。

## 代理登记与代理例外

代理登记 delegation：`id`、`owner`（负责人）、`delegate`（代理人）、`resource`、`from_partition`/`to_partition`（右开）、`start`/`end`（右开生效窗）、`status`（active/revoked）。同一登记号内容冲突视为无效，相同内容按重复去重。

代理例外 exception：`id`、`principal`（被授权访问的业务方）、`resource`、`partition`（YYYY-MM 单月）、`approved_by`（实际代理人）、`approved_at`（批准时刻，带偏移）、`approver_text`（批准人原始写法，保形）、`note`、`material`（原始批准材料原文）、可选 `owner_confirmation{owner,decision}`。

唯一生效判断只看：登记是否覆盖该资源/分区/批准时刻，负责人是否唯一，是否与既有显式拒绝冲突。责任归属：覆盖→对应负责人；超出范围未确认→代理人；本人确认放行→负责人；无登记→不成立。`approver_text` 永不改写，`material` 只保留首份。
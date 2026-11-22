# 深度登记 数据共享授权到期与分区访问复核

规模：中型。使用者：企业数据共享审计专员。核心规则：拒绝规则优先于允许，授权必须同时命中资源、分区和生效窗；显式拒绝不得被宽授权覆盖。

## 功能模块

| 模块 | 使用者动作 | 入口 | 核心文件 | 测试 |
|---|---|---|---|---|
| M1 访问采信 | 查看并运行访问采信 | `/api/accesses` | `app/modules/m1_accesses/rules.py` | `tests/test_m1.py` |
| M2 资源映射 | 查看并运行资源映射 | `/api/resources` | `app/modules/m2_resources/rules.py` | `tests/test_m2.py` |
| M3 授权定版 | 查看并运行授权定版 | `/api/grants` | `app/modules/m3_grants/rules.py` | `tests/test_m3.py` |
| M4 冲突裁决 | 查看并运行冲突裁决 | `/api/conflicts` | `app/modules/m4_conflicts/rules.py` | `tests/test_m4.py` |
| M5 分区判定 | 查看并运行分区判定 | `/api/partitions` | `app/modules/m5_partitions/rules.py` | `tests/test_m5.py` |
| M6 访问对账 | 查看并运行访问对账 | `/api/audit` | `app/modules/m6_audit/rules.py` | `tests/test_m6.py` |
| M7 审计归档 | 查看并运行审计归档 | `/api/seals` | `app/modules/m7_seals/rules.py` | `tests/test_m7.py` |
| M8 代理例外 | 查看代理例外唯一生效判断、负责人确认、导出证据 | `/exceptions`，`/api/exceptions` | `app/delegations/rules.py` | `tests/test_exceptions.py` |

## 陷阱登记

| TRAP | 现象 | 朴素实现 | 本项目处理 | 处理位置 | 测试 |
|---|---|---|---|---|---|
| TRAP-01 | 旧编码 | 默认解码失败 | 回退GB18030 | `app/modules/m1_accesses/rules.py` | `tests/test_m1.py::test_legacy_encoding_real_sample` |
| TRAP-02 | BOM | 首列名多字符 | utf-8-sig | `app/modules/m1_accesses/rules.py` | `tests/test_m1.py::test_bom_real_sample` |
| TRAP-03 | 带引号换行 | 拆成两条 | csv逻辑行 | `app/modules/m1_accesses/rules.py` | `tests/test_m1.py::test_quoted_newline_is_one_record` |
| TRAP-05 | 列数不匹配 | 静默错列 | 隔离原行 | `app/modules/m1_accesses/rules.py` | `tests/test_m1.py::test_bad_columns_real_sample` |
| TRAP-08 | 前导零ID | 编码变形 | 全程字符串 | `app/modules/m1_accesses/rules.py` | `tests/test_m1.py::test_identifier_preserved_real_sample` |
| TRAP-14 | 重复键冲突 | 后写覆盖 | 保留首条并隔离冲突行 | `app/modules/m1_accesses/rules.py` | `tests/test_m1.py::test_duplicate_conflict_real_sample` |
| TRAP-18 | 空态三态 | 一律成功 | 分别错误码 | `app/modules/m1_accesses/rules.py` | `tests/test_m1.py::test_three_empty_states` |
| TRAP-26 | 旧版本提交 | 覆盖新结果 | 版本条件更新 | `app/store.py` | `tests/test_e2e.py::test_stale_review_409` |
| TRAP-07 | 上游结果空值 | 误报拒绝 | 隔离缺失 | `app/values.py` | `tests/test_m3.py::test_real_missing_decision_not_zero` |
| TRAP-19 | 允许与拒绝重叠 | 后写覆盖 | 拒绝优先且排序证据 | `app/modules/m4_conflicts/rules.py` | `tests/test_m4.py::test_deny_priority_counterexample` |
| TRAP-23 | 授权到期点 | 多放行一次 | 半开生效窗 | `app/modules/m3_grants/rules.py` | `tests/test_m3.py::test_expiry_endpoint_excluded` |
| TRAP-27 | 代理例外批准人写法过宽 | 把批准人笼统记为代理人/负责人 | 按代理登记范围核验，责任落具体登记对应负责人，原文保形 | `app/delegations/rules.py` | `tests/test_exceptions.py::test_within_scope_is_effective_immediately` |
| TRAP-28 | 代理例外超出登记范围 | 自动放行或误记负责人 | 挂起等本人确认，责任暂留代理人 | `app/delegations/rules.py` | `tests/test_exceptions.py::test_out_of_scope_pends_and_keeps_responsibility_with_delegate` |
| TRAP-29 | 代理允许与显式拒绝重叠 | 后写覆盖 | 复用拒绝优先裁决，例外不生效 | `app/delegations/rules.py` | `tests/test_exceptions.py::test_deny_priority_makes_exception_ineffective` |
| TRAP-30 | 同一例外重试 | 重复版本/判断漂移 | 内容指纹一致即复用版本 | `app/store.py` | `tests/test_exceptions.py::test_retry_keeps_same_version_and_judgment` |
| TRAP-31 | 判断更新中断 | 新半版覆盖旧结果 | 单事务回滚，恢复旧版判断，保留原始材料首份 | `app/store.py` | `tests/test_exceptions.py::test_interrupted_update_rolls_back_to_old_version` |
| TRAP-32 | 四视图各算一套 | 权限/冲突/分区/归档判断不一致 | 单一 dict 派生，同源导出 | `app/delegations/rules.py` | `tests/test_exceptions.py::test_four_views_share_one_judgment` |

## 代理例外规则

负责人休假时，代理人批出的分区访问例外须给出唯一生效判断，权限核对、规则冲突、分区准入与归档证据四视图共用同一 dict，不各算一套。

- 当场按代理登记范围核验：登记覆盖该资源、该分区、批准时刻 → 立即生效；责任落到该登记对应的负责人，证据指向具体登记号，批准人原文保形，不改写成模糊的「代理人」。
- 有该主体该资源的登记但范围不覆盖 → 挂起等负责人本人确认；责任暂留代理人，绝不自动记到负责人名下。确认人必须是登记里的负责人，否则仍挂起；本人确认只对挂起态有效。
- 无任何登记 → 该批准无效，判拒绝。
- 生效允许落入既有拒绝优先裁决，重叠显式拒绝时例外不生效。

同一例外重试：内容指纹（材料＋确认＋相关登记＋相关授权范围）一致即复用既有版本，判断不漂移。更新中断：单事务写入，提交前中断即回滚为旧版生效判断；material 列只写首份，原始批准材料不被任何后续版本改写。

## 对账规则

输入原始逻辑行=最终采纳来源行+隔离来源行+重复行+空白行+分段表头。派生记录用_sources保存完整来源，因此分组不丢行。业务预期合计与上游申报合计之差等于逐行差异之和。结果按输入摘要、规则版本及参数产生唯一批次，事务写入；同源重跑只复用已有批次。

## 已知不覆盖

4MB以上文件需预先按业务键分批；不模拟生产支付与外部回调。人工复核只变更批次状态，不改写原始记录。代理例外样例为虚构的仓内登记，不连接真实人事或休假系统。

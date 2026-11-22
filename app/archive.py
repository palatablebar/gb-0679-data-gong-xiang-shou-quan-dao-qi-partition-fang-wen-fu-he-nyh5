import csv,io,json
from app.delegations import rules as delegation_rules
from app.delegations.samples import DELEGATIONS,EXCEPTIONS
from app.modules.m3_grants.rules import GRANTS

def _resolved(exception,delegations,grants):
    "已落库判断优先（含负责人确认），否则现算。与页面/接口同源。"
    from app import store
    from app.errors import DomainError
    try: return store.get_exception(exception["id"])["judgment"]
    except DomainError: return delegation_rules.judge(exception,delegations,grants)

def _exception_rows(writer,run,meta):
    """把代理例外唯一生效判断及其证据写入同一份导出。
    判断与页面/接口同源（已落库优先）；沿用同一列结构，
    结论放入 kind，状态放入 reason，四类核对与原始批准材料整体放入 evidence JSON。"""
    delegations,grants=list(DELEGATIONS),list(GRANTS)
    for exception in EXCEPTIONS:
        judgment=_resolved(exception,delegations,grants)
        evidence={"exception_id":judgment["exception_id"],"status":judgment["status"],
                  "status_label":judgment["status_label"],"decision":judgment["decision"],
                  "responsible":judgment["responsible"],"basis":judgment["basis"],
                  "reasons":judgment["reasons"],"content_sha256":judgment["content_sha256"],
                  "checks":judgment["checks"],"approval_material":judgment["approval_material"]}
        writer.writerow([run["run_id"],meta["input_sha256"],meta["rule_version"],
                         "exception",json.dumps([judgment["exception_id"]]),
                         judgment["status"],json.dumps(evidence,ensure_ascii=False,sort_keys=True)])

def build_archive(run,exceptions=None):
    stream=io.StringIO(newline="");writer=csv.writer(stream)
    writer.writerow(["run_id","input_sha256","rule_version","kind","source_lines","reason","evidence"])
    meta=run["manifest"]
    for row in run["stages"][-1]["rows"]:
        writer.writerow([run["run_id"],meta["input_sha256"],meta["rule_version"],"accepted",json.dumps(row.get("_sources",[])),row.get("status",""),json.dumps(row,ensure_ascii=False)])
    for row in run["stages"][-1].get("cumulative_quarantine",[]):
        writer.writerow([run["run_id"],meta["input_sha256"],meta["rule_version"],"quarantine",json.dumps(row.get("_sources",[])),row.get("reason",""),json.dumps(row,ensure_ascii=False)])
    if exceptions is not None:
        _exception_rows(writer,run,meta)
    return "﻿"+stream.getvalue()

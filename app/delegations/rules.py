"""代理例外：唯一生效判断。

设计决定：当场按代理登记范围核验，不默认挂起。
- 代理登记覆盖该资源、该分区、批准时刻 → 立即生效，责任记在被代理人（负责人）名下，
  证据指向具体代理登记号；不把批准人笼统写成代理人。
- 有该主体该资源的代理登记，但分区/时间落在登记范围之外 → 挂起等负责人本人确认，
  责任暂留代理人，绝不自动记到负责人名下。
- 完全没有代理登记 → 该批准无效，判为拒绝（不受理无授权批准）。
- 负责人本人确认（owner_confirmation）只对「挂起」有效，且确认人必须是登记里的负责人；
  确认后责任落到负责人，显式拒绝仍然优先。
- 生效允许与显式拒绝冲突 → 显式拒绝优先，例外不生效。

本模块只做纯计算：同一份原始批准材料、登记、授权与确认输入，永远得到同一份生效判断。
权限核对、规则冲突、分区准入、归档证据四个视图全部由这一个 dict 派生，不各算一套。
原始批准材料 material() 只做投影，从不改写。
"""
import hashlib,json
from app.values import instant
from app.errors import DomainError
from app.modules.m2_resources.rules import normalize,valid_partition
from app.modules.m3_grants.rules import active_grants
from app.modules.m4_conflicts.rules import decide

STATUS_LABELS={
    "effective":"生效",
    "pending_owner_confirmation":"挂起·待负责人确认",
    "denied_by_conflict":"不生效·显式拒绝优先",
    "owner_declined":"不生效·负责人驳回",
    "not_delegated":"无效·无代理登记",
    "invalid":"无效·材料不完整",
}
MATERIAL_KEYS=("id","principal","resource","partition","approved_by","approved_at","approver_text","note","material")

def next_month(partition):
    "分区右开：单月例外结束月为下一月。"
    year,month=int(partition[:4]),int(partition[5:])
    month+=1
    if month==13: year,month=year+1,1
    return f"{year:04d}-{month:02d}"

def month_start(partition): return partition+"-01T00:00:00Z"

def validate_delegation(d):
    for key in ("id","owner","delegate","resource","from_partition","to_partition","start","end"):
        if not d.get(key): raise DomainError("BAD_DELEGATION",f"代理登记缺少{key}")
    if instant(d["start"])>=instant(d["end"]): raise DomainError("BAD_DELEGATION","代理登记生效窗无效")
    if d["from_partition"]>=d["to_partition"]: raise DomainError("BAD_DELEGATION","代理登记分区窗无效")
    if d.get("status","active") not in {"active","revoked"}: raise DomainError("BAD_DELEGATION","代理登记状态无效")
    return d

def validate_exception(e):
    for key in ("id","principal","resource","partition","approved_by","approved_at","approver_text"):
        if not e.get(key): raise DomainError("BAD_EXCEPTION",f"例外缺少{key}")
    if not valid_partition(e["partition"]): raise DomainError("BAD_EXCEPTION","例外分区必须为YYYY-MM")
    if normalize(e["resource"]) is None: raise DomainError("BAD_EXCEPTION","例外资源未登记")
    instant(e["approved_at"])
    return e

def material(exception):
    "原始批准材料原样投影，用于摘要与留存，不做任何改写。负责人确认不计入原始材料。"
    return {k:exception.get(k) for k in MATERIAL_KEYS}

def _scope_tuple(d):
    return (d.get("from_partition",""),d.get("to_partition",""),d.get("resource"),d.get("status","active"),d["id"])

def _confirmation(exception):
    c=exception.get("owner_confirmation")
    if not isinstance(c,dict) or c.get("decision") not in {"allow","deny"} or not c.get("owner"): return None
    return c

def content_sha256(exception,delegations=None,grants=None):
    """判断内容的确定性指纹：只取决于材料、确认、相关代理登记与相关授权，与调用次数、时钟无关。
    指纹覆盖授权完整范围，避免仅ID相同但范围不同的授权被误判为可复用。"""
    delegations=delegations or [];grants=grants or []
    relevant_grants=sorted((g.get("id"),g.get("effect"),g.get("start"),g.get("end"),
                            g.get("from_partition"),g.get("to_partition"),g.get("resource"))
                           for g in grants
                           if g.get("principal")==exception.get("principal") and g.get("resource")==exception.get("resource"))
    payload={"material":material(exception),"owner_confirmation":_confirmation(exception),
             "delegations":sorted(_scope_tuple(d) for d in delegations
                                  if d.get("delegate")==exception.get("approved_by") and d.get("resource")==exception.get("resource")),
             "grants":relevant_grants}
    return hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True,default=str).encode()).hexdigest()

def _covering(exception,delegations):
    at=instant(exception["approved_at"])
    same_subject=sorted((d for d in delegations if d.get("delegate")==exception["approved_by"] and d.get("resource")==exception["resource"]),key=lambda d:d["id"])
    covering=sorted((d for d in same_subject if d.get("status","active")=="active"
                     and instant(d["start"])<=at<instant(d["end"])
                     and d["from_partition"]<=exception["partition"]<d["to_partition"]),key=lambda d:d["id"])
    return covering,same_subject

def _synthetic_grant(exception,start,end,source):
    "把生效允许落成一条精确分区的派生允许，交给现有规则统一裁决。"
    return {"id":"EXC-"+exception["id"],"principal":exception["principal"],"resource":normalize(exception["resource"]),
            "start":start,"end":end,"from_partition":exception["partition"],
            "to_partition":next_month(exception["partition"]),"effect":"allow","_source":source}

def _conflict_check(exception,grant,grants):
    try:
        at=instant(exception["approved_at"])
        candidates=active_grants(grants,exception["principal"],normalize(exception["resource"]),at)+[grant]
        verdict=decide(candidates,exception["partition"])
    except (DomainError,KeyError):
        return {"evaluated":False,"reason":"SKIPPED","matched_rules":[],"allow_rules":[],"deny_rules":[],"conflict":False,"effect":"deny"}
    return {"evaluated":True,"access_time":exception["approved_at"],"partition":exception["partition"],
            "matched_rules":verdict["matched_rules"],"allow_rules":verdict["allow_rules"],
            "deny_rules":verdict["deny_rules"],"conflict":verdict["conflict"],"effect":verdict["effect"]}

def _checks(exception,decision,permission_basis,grants,grant):
    resource=normalize(exception.get("resource")) if exception.get("resource") else None
    partition=exception.get("partition")
    permission={"delegate":exception.get("approved_by"),"resource":resource,"partition":partition,
                "approved_at":exception.get("approved_at"),"owners":sorted({d["owner"] for d in permission_basis}),
                "basis":[d["id"] for d in permission_basis]}
    valid=bool(partition) and valid_partition(partition)
    partition_check={"valid":valid,"expected":"1" if decision=="allow" else "0",
                     "result":"授权内" if decision=="allow" else ("挂起" if decision=="pending" else "未授权分区")}
    material_sha=hashlib.sha256(json.dumps(material(exception),ensure_ascii=False,sort_keys=True,default=str).encode()).hexdigest()
    archive={"ready":True,"records":1,"status":decision,"material_sha256":material_sha}
    return {"permission":permission,
            "conflict":_conflict_check(exception,grant,grants) if grant else
                       {"evaluated":False,"reason":"NO_SCOPE","matched_rules":[],"allow_rules":[],"deny_rules":[],"conflict":False,"effect":"deny"},
            "partition":partition_check,
            "archive":archive}

def judge(exception,delegations=None,grants=None):
    """返回唯一生效判断。纯函数、确定性：相同输入必得相同输出（含 content_sha256）。"""
    delegations=list(delegations or []);grants=list(grants or [])
    base={"exception_id":exception.get("id"),"principal":exception.get("principal"),
          "resource":normalize(exception.get("resource")) if exception.get("resource") else None,
          "partition":exception.get("partition"),"approver_written":exception.get("approver_text"),
          "delegate":exception.get("approved_by"),"approval_material":material(exception),
          "content_sha256":content_sha256(exception,delegations,grants)}

    def result(decision,status,responsible,basis,reasons,permission_basis=None,grant=None):
        return {**base,"decision":decision,"effective":decision=="allow","status":status,
                "responsible":responsible,"basis":basis,"reasons":reasons,
                "status_label":STATUS_LABELS[status],
                "checks":_checks(exception,decision,permission_basis or [],grants,grant)}

    try:
        validate_exception(exception)
    except DomainError as error:
        return result("deny","invalid",None,[],[error.code])

    covering,same_subject=_covering(exception,delegations)
    confirmation=_confirmation(exception)

    if not same_subject:
        return result("deny","not_delegated",exception["approved_by"],[],["NOT_DELEGATED"])

    if not covering:
        # 超出代理登记范围：只有登记里的负责人本人确认才可放行，否则挂起。
        owners=sorted({d["owner"] for d in same_subject})
        confirmed=confirmation and confirmation["owner"] in owners
        if not confirmed:
            return result("pending","pending_owner_confirmation",exception["approved_by"],[],
                          ["OUT_OF_DELEGATED_SCOPE"],[d for d in same_subject if d.get("status","active")=="active"])
        if confirmation["decision"]=="deny":
            return result("deny","owner_declined",confirmation["owner"],[],
                          ["OWNER_DECLINED"],[d for d in same_subject if d.get("status","active")=="active"])
        grant=_synthetic_grant(exception,month_start(exception["partition"]),month_start(next_month(exception["partition"])),"OWNER_CONFIRM")
        verdict=decide([grant]+active_grants(grants,exception["principal"],normalize(exception["resource"]),instant(exception["approved_at"])),exception["partition"])
        if verdict["effect"]!="allow":
            return result("deny","denied_by_conflict",confirmation["owner"],[],["EXPLICIT_DENY_PRECEDES"],
                          [d for d in same_subject if d.get("status","active")=="active"],grant)
        return result("allow","effective",confirmation["owner"],[],["OWNER_CONFIRMED"],
                      [d for d in same_subject if d.get("status","active")=="active"],grant)

    owners=sorted({d["owner"] for d in covering})
    if len(owners)>1:
        return result("pending","pending_owner_confirmation",exception["approved_by"],[d["id"] for d in covering],
                      ["AMBIGUOUS_DELEGATION"],covering)

    grant=_synthetic_grant(exception,covering[0]["start"],covering[0]["end"],"DELEGATION")
    verdict=decide(active_grants(grants,exception["principal"],normalize(exception["resource"]),instant(exception["approved_at"]))+[grant],exception["partition"])
    if verdict["effect"]!="allow":
        return result("deny","denied_by_conflict",owners[0],[d["id"] for d in covering],["EXPLICIT_DENY_PRECEDES"],covering,grant)
    return result("allow","effective",owners[0],[d["id"] for d in covering],["WITHIN_DELEGATED_SCOPE"],covering,grant)


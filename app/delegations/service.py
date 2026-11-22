"""代理例外复核：把唯一生效判断接到持久化与导出上。

- 重试一致：内容指纹相同即复用既有版本，不新造版本。
- 更新中断：写入单事务完成；fault 在落库后、提交前抛出即回滚，库内恢复旧版生效判断，
  原始批准材料（material 列）保留首份不变。
- 原始批准材料：material 列只在首版写入，后续版本不改写。
"""
import hashlib,json
from app import store
from app.errors import DomainError
from app.delegations import rules as delegation_rules
from app.delegations.samples import DELEGATIONS,EXCEPTIONS
from app.modules.m3_grants.rules import GRANTS


def registry(delegations,grants):
    seen={}
    for d in delegations:
        delegation_rules.validate_delegation(d)
        if d["id"] in seen and seen[d["id"]]!=d: raise DomainError("BAD_DELEGATION","代理登记号重复且内容冲突")
        seen[d["id"]]=d
    return [seen[k] for k in sorted(seen)],list(grants)


def material_sha256(exception):
    return hashlib.sha256(json.dumps(delegation_rules.material(exception),ensure_ascii=False,sort_keys=True,default=str).encode()).hexdigest()


def evaluate_one(exception,delegations=None,grants=None):
    delegations,grants=registry(delegations if delegations is not None else DELEGATIONS,
                                grants if grants is not None else GRANTS)
    return delegation_rules.judge(exception,delegations,grants)


def publish(exception,delegations=None,grants=None,fault=None):
    """计算并持久化唯一判断；返回 {judgment,version,reused,material_sha256}。
    fault 若抛出，事务回滚，旧版判断得以恢复。"""
    delegations,grants=registry(delegations if delegations is not None else DELEGATIONS,
                                grants if grants is not None else GRANTS)
    judgment=delegation_rules.judge(exception,delegations,grants)
    sha=material_sha256(exception)
    saved=store.save_exception(judgment,sha,fault=fault)
    return {**saved,"material_sha256":sha}


def with_owner_confirmation(exception,owner,decision):
    "负责人本人确认：返回新例外对象，不改原始材料。"
    if decision not in {"allow","deny"}: raise DomainError("BAD_CONFIRMATION","确认结论无效")
    return {**exception,"owner_confirmation":{"owner":owner,"decision":decision}}


def resolve_one(exception_id,fallback):
    """页面/接口/导出读取唯一判断：已落库则用落库版本（含负责人确认结果），
    否则现算。保证「同一例外重试/重看」返回同一判断，不因未提交而漂移。"""
    try:
        stored=store.get_exception(exception_id)
        return stored["judgment"],stored["version"]
    except DomainError:
        live=fallback() if callable(fallback) else fallback
        return live,None

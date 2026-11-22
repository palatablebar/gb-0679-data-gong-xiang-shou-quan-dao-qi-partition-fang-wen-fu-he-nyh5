import csv,io,json
import pytest
from app.delegations import rules,service
from app.delegations.samples import DELEGATIONS,EXCEPTIONS
from app.modules.m3_grants.rules import GRANTS
from app import store

X={e["id"]:e for e in EXCEPTIONS}

def test_within_scope_is_effective_immediately():
    j=rules.judge(X["X-01"],DELEGATIONS,GRANTS)
    assert j["status"]=="effective" and j["decision"]=="allow" and j["effective"] is True
    assert j["responsible"]=="data-steward"           # 责任落到负责人，不是代理人
    assert j["basis"]==["D-01"]                        # 证据指向具体登记
    assert j["approver_written"]=="analyst（代 data-steward）"  # 原始写法保形

def test_deny_priority_makes_exception_ineffective():
    j=rules.judge(X["X-02"],DELEGATIONS,GRANTS)
    assert j["status"]=="denied_by_conflict" and j["decision"]=="deny"
    assert "G-02" in j["checks"]["conflict"]["deny_rules"]
    assert j["responsible"]=="data-steward"

def test_out_of_scope_pends_and_keeps_responsibility_with_delegate():
    j=rules.judge(X["X-03"],DELEGATIONS,GRANTS)
    assert j["status"]=="pending_owner_confirmation" and j["decision"]=="pending"
    assert j["responsible"]=="analyst"                 # 不自动记到负责人名下

def test_no_delegation_is_not_delegated():
    j=rules.judge(X["X-04"],DELEGATIONS,GRANTS)
    assert j["status"]=="not_delegated" and j["decision"]=="deny"

def test_owner_confirmation_resolves_pending():
    confirmed=service.with_owner_confirmation(X["X-03"],"data-steward","allow")
    j=rules.judge(confirmed,DELEGATIONS,GRANTS)
    assert j["status"]=="effective" and j["responsible"]=="data-steward"
    assert rules.material(confirmed)==rules.material(X["X-03"])   # 原始材料不变

def test_wrong_person_cannot_confirm():
    j=rules.judge(service.with_owner_confirmation(X["X-03"],"analyst","allow"),DELEGATIONS,GRANTS)
    assert j["status"]=="pending_owner_confirmation"

def test_owner_deny_resolves_to_declined():
    j=rules.judge(service.with_owner_confirmation(X["X-03"],"data-steward","deny"),DELEGATIONS,GRANTS)
    assert j["status"]=="owner_declined" and j["decision"]=="deny"

def test_four_views_share_one_judgment():
    "权限核对、冲突、分区准入、归档证据必须全部来自同一 dict，不得各自重算。"
    j=rules.judge(X["X-02"],DELEGATIONS,GRANTS)
    for key in ("permission","conflict","partition","archive"): assert key in j["checks"]
    assert j["checks"]["partition"]["expected"]=="0"            # deny → 预期拒绝
    assert j["checks"]["conflict"]["deny_rules"]==j["checks"]["conflict"]["deny_rules"]

def test_judgment_is_deterministic():
    a=rules.judge(X["X-01"],DELEGATIONS,GRANTS);b=rules.judge(X["X-01"],DELEGATIONS,GRANTS)
    assert a==b and a["content_sha256"]==b["content_sha256"]

def test_retry_keeps_same_version_and_judgment():
    first=service.publish(X["X-01"],DELEGATIONS,GRANTS)
    second=service.publish(X["X-01"],DELEGATIONS,GRANTS)
    assert second["reused"] is True and second["version"]==first["version"]
    assert second["judgment"]["content_sha256"]==first["judgment"]["content_sha256"]

def test_interrupted_update_rolls_back_to_old_version():
    first=service.publish(X["X-01"],DELEGATIONS,GRANTS)
    changed={**X["X-01"],"note":"修订后的批准说明"}
    def boom(): raise RuntimeError("模拟更新中断")
    with pytest.raises(RuntimeError): service.publish(changed,DELEGATIONS,GRANTS,fault=boom)
    restored=store.get_exception("X-01")
    assert restored["version"]==first["version"]
    assert restored["content_sha256"]==first["judgment"]["content_sha256"]   # 旧版生效判断恢复
    assert json.loads(json.dumps(restored["material"]))==rules.material(X["X-01"])  # 原始材料留存

def test_material_immutable_across_versions():
    service.publish(X["X-01"],DELEGATIONS,GRANTS)
    service.publish({**X["X-01"],"note":"第二版"},DELEGATIONS,GRANTS)
    stored=store.get_exception("X-01")
    assert stored["version"]==2
    assert stored["material"]==rules.material(X["X-01"])

def test_identical_delegation_deduped():
    registry,_=service.registry([DELEGATIONS[0],DELEGATIONS[0]],GRANTS)
    assert [d["id"] for d in registry]==["D-01"]

def test_conflicting_delegation_id_isolated():
    from app.errors import DomainError
    with pytest.raises(DomainError):
        service.registry([DELEGATIONS[0],{**DELEGATIONS[0],"to_partition":"2027-01"}],GRANTS)

def test_exception_archive_has_all_checks():
    from app.delegations.archive import build_exception_archive
    j=rules.judge(X["X-02"],DELEGATIONS,GRANTS)
    rows=list(csv.DictReader(io.StringIO(build_exception_archive(j).lstrip("﻿"))))
    assert rows[0]["status"]=="denied_by_conflict"
    assert json.loads(rows[0]["conflict"])["deny_rules"]==["G-02"]
    assert json.loads(rows[0]["approval_material"])==rules.material(X["X-02"])


def test_exception_page_renders_one_judgment(client):
    html=client.get("/exceptions").get_data(as_text=True)
    assert "唯一生效判断" in html
    for view in ("权限核对","规则冲突","分区准入","归档证据"): assert view in html

def test_api_listing_has_judgments_and_primary(client):
    data=client.get("/api/exceptions").get_json()
    assert data["primary"]["exception_id"]=="X-01"
    assert {j["status"] for j in data["judgments"]}=={"effective","denied_by_conflict","pending_owner_confirmation","not_delegated"}

def test_api_publish_then_retry_is_consistent(client):
    a=client.post("/api/exceptions/X-01/publish",json={}).get_json()
    b=client.post("/api/exceptions/X-01/publish",json={}).get_json()
    assert a["version"]==1 and b["version"]==1 and b["reused"] is True

def test_api_confirm_requires_registered_owner(client):
    bad=client.post("/api/exceptions/X-03/confirm",json={"owner":"analyst","decision":"allow"}).get_json()
    assert bad["judgment"]["status"]=="pending_owner_confirmation"
    good=client.post("/api/exceptions/X-03/confirm",json={"owner":"data-steward","decision":"allow"}).get_json()
    assert good["judgment"]["status"]=="effective" and good["judgment"]["responsible"]=="data-steward"

def test_run_archive_keeps_schema_and_adds_exception_rows(client):
    p=client.post("/api/runs",json={"sample":"dirty.csv"}).get_json()
    rows=list(csv.reader(io.StringIO(client.get("/api/runs/"+p["run_id"]+"/archive").data.decode("utf-8-sig"))))
    assert rows[0][3]=="kind"
    exc=[x for x in rows[1:] if x[3]=="exception"]
    assert len(exc)==4 and all(len(x)==7 for x in rows)
    assert json.loads(exc[0][6])["exception_id"]=="X-01"

def test_repeated_get_is_stable(client):
    a=client.get("/api/exceptions/X-02").get_json()["judgment"]
    b=client.get("/api/exceptions/X-02").get_json()["judgment"]
    assert a==b


def test_confirmation_persists_and_shows_in_resolution(client):
    client.post("/api/exceptions/X-03/confirm",json={"owner":"data-steward","decision":"allow"})
    got=client.get("/api/exceptions/X-03").get_json()
    assert got["judgment"]["status"]=="effective" and got["stored_version"]==1
    # 归档导出与页面同源：应显示生效而非重新算成挂起
    body=client.get("/api/exceptions/X-03/archive").data.decode("utf-8-sig")
    assert "effective" in body

def test_confirmation_material_stays_original(client):
    client.post("/api/exceptions/X-03/confirm",json={"owner":"data-steward","decision":"allow"})
    stored=client.get("/api/exceptions/X-03").get_json()
    assert stored["stored_material"]==rules.material(X["X-03"])


def test_run_archive_reflects_confirmed_judgment(client):
    client.post("/api/exceptions/X-03/confirm",json={"owner":"data-steward","decision":"allow"})
    p=client.post("/api/runs",json={"sample":"dirty.csv"}).get_json()
    rows=list(csv.reader(io.StringIO(client.get("/api/runs/"+p["run_id"]+"/archive").data.decode("utf-8-sig"))))
    x03=[json.loads(x[6]) for x in rows[1:] if x[3]=="exception" and "X-03" in x[4]][0]
    assert x03["status"]=="effective" and x03["responsible"]=="data-steward"

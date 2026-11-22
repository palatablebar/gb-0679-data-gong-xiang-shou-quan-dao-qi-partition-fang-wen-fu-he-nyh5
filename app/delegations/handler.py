from flask import Blueprint,request,jsonify,Response
from app.errors import DomainError
from app import store
from app.delegations import service
from app.delegations.samples import DELEGATIONS,EXCEPTIONS
from app.delegations.archive import build_exception_archive

bp=Blueprint("exceptions",__name__)

def _find(exception_id):
    for e in EXCEPTIONS:
        if e["id"]==exception_id: return e
    raise DomainError("NOT_FOUND","例外不存在",404)

def _payload():
    p=request.get_json(silent=True) or {}
    if not isinstance(p,dict): raise DomainError("BAD_BODY","请求需要对象")
    delegations=p.get("delegations",DELEGATIONS)
    grants=p.get("grants",None)
    if not isinstance(delegations,list): raise DomainError("BAD_DELEGATIONS","代理登记需要列表")
    return delegations,grants

def _resolved(exception):
    "已落库的判断优先；否则现算。返回 (judgment, stored_version)。"
    return service.resolve_one(exception["id"],lambda: service.evaluate_one(exception))

@bp.get("/api/exceptions")
def listing():
    judgments=[]
    for e in EXCEPTIONS:
        judgment,version=_resolved(e)
        judgments.append({**judgment,"stored_version":version})
    return jsonify({"judgments":judgments,"history":store.exception_history(),
                    "primary":judgments[0] if judgments else None})

@bp.get("/api/exceptions/<exception_id>")
def detail(exception_id):
    e=_find(exception_id)
    judgment,version=_resolved(e)
    try: material=store.get_exception(exception_id)["material"]
    except DomainError: material=None
    return jsonify({"judgment":judgment,"stored_version":version,"stored_material":material})

@bp.post("/api/exceptions/<exception_id>/publish")
def publish(exception_id):
    e=_find(exception_id)
    delegations,grants=_payload()
    result=service.publish(e,delegations,grants)
    return jsonify(result)

@bp.post("/api/exceptions/<exception_id>/confirm")
def confirm(exception_id):
    e=_find(exception_id)
    p=request.get_json(silent=True) or {}
    if not isinstance(p,dict): raise DomainError("BAD_BODY","请求需要对象")
    owner=p.get("owner");decision=p.get("decision")
    if not owner: raise DomainError("BAD_CONFIRMATION","需要负责人标识")
    confirmed=service.with_owner_confirmation(e,owner,decision)
    return jsonify(service.publish(confirmed))

@bp.get("/api/exceptions/<exception_id>/archive")
def archive(exception_id):
    e=_find(exception_id)
    judgment,_=_resolved(e)
    body=build_exception_archive(judgment)
    return Response(body,mimetype="text/csv",headers={"Content-Disposition":f'attachment; filename="exception-{exception_id}.csv"'})

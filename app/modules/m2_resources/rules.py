from app.reasons import reject
RESOURCES={"订单":"orders","orders":"orders","客户":"customers","customers":"customers"}
def normalize(resource): return RESOURCES.get(resource)
def valid_partition(part):
    "分区必须是YYYY-MM且月份1..12；代理例外复核按同一标准准入，避免两套口径。"
    return len(part)==7 and part[4]=="-" and part[:4].isdigit() and part[5:].isdigit() and 1<=int(part[5:])<=12
def normalize_row(row):
    resource=normalize(row.get("resource"))
    if not resource: return None,"UNKNOWN_RESOURCE","资源未登记"
    part=row.get("partition","")
    if not valid_partition(part): return None,"BAD_PARTITION","分区必须为YYYY-MM"
    if not row.get("principal"): return None,"EMPTY_PRINCIPAL","访问主体为空"
    return {**row,"resource":resource,"partition":part},None,None
def evaluate(rows,context):
    good=[];bad=[]
    for row in rows:
        normalized,code,detail=normalize_row(row)
        if code:bad.append(reject(row,code,detail));continue
        good.append(normalized)
    return {"rows":good,"quarantine":bad,"metrics":{"accepted":len(good),"resources":len(set(r["resource"] for r in good))}}

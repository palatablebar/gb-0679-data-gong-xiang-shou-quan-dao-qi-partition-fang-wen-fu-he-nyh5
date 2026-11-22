import csv,io,json

HEADER=["exception_id","status","status_label","decision","effective","responsible",
        "approver_written","delegate","basis","reasons","content_sha256","material_sha256",
        "permission","conflict","partition","approval_material"]

def build_exception_archive(judgment):
    """单份证据导出：与页面/接口同源的唯一判断，含四类核对与原始批准材料。"""
    c=judgment["checks"]
    stream=io.StringIO(newline="");writer=csv.writer(stream)
    writer.writerow(HEADER)
    writer.writerow([judgment["exception_id"],judgment["status"],judgment["status_label"],
                     judgment["decision"],"1" if judgment["effective"] else "0",
                     judgment["responsible"] or "",judgment["approver_written"] or "",
                     judgment["delegate"] or "",json.dumps(judgment["basis"]),
                     json.dumps(judgment["reasons"]),judgment["content_sha256"],
                     c["archive"]["material_sha256"],
                     json.dumps(c["permission"],ensure_ascii=False,sort_keys=True),
                     json.dumps(c["conflict"],ensure_ascii=False,sort_keys=True),
                     json.dumps(c["partition"],ensure_ascii=False,sort_keys=True),
                     json.dumps(judgment["approval_material"],ensure_ascii=False,sort_keys=True)])
    return "﻿"+stream.getvalue()

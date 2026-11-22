import sqlite3,json
from pathlib import Path
from app.config import DATA_DIR
from app.errors import DomainError
def connect():
    DATA_DIR.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(DATA_DIR/"records.db",timeout=20)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY,payload TEXT NOT NULL,version INTEGER NOT NULL DEFAULT 1,decision TEXT NOT NULL DEFAULT '待复核')")
    db.execute("CREATE TABLE IF NOT EXISTS exception_judgments (exception_id TEXT PRIMARY KEY,material TEXT NOT NULL,material_sha256 TEXT NOT NULL,version INTEGER NOT NULL,content_sha256 TEXT NOT NULL,decision TEXT NOT NULL,payload TEXT NOT NULL)")
    return db
def save(run_id,payload):
    with connect() as db:
        db.execute("INSERT OR IGNORE INTO runs(id,payload) VALUES (?,?)",(run_id,json.dumps(payload,ensure_ascii=False)))
    return get(run_id)
def get(run_id):
    with connect() as db: row=db.execute("SELECT payload,version,decision FROM runs WHERE id=?",(run_id,)).fetchone()
    if not row: raise DomainError("NOT_FOUND","批次不存在",404)
    return {**json.loads(row[0]),"version":row[1],"decision":row[2]}
def latest():
    with connect() as db: row=db.execute("SELECT id FROM runs ORDER BY rowid DESC LIMIT 1").fetchone()
    return get(row[0]) if row else None
def history():
    with connect() as db: return [{"run_id":i,"version":v,"decision":d} for i,v,d in db.execute("SELECT id,version,decision FROM runs ORDER BY rowid DESC")]
def review(run_id,version,decision):
    if decision not in {"已复核","退回复核"}: raise DomainError("BAD_DECISION","复核状态无效")
    with connect() as db:
        cursor=db.execute("UPDATE runs SET version=version+1,decision=? WHERE id=? AND version=?",(decision,run_id,version))
        if cursor.rowcount!=1:
            if not db.execute("SELECT 1 FROM runs WHERE id=?",(run_id,)).fetchone(): raise DomainError("NOT_FOUND","批次不存在",404)
            raise DomainError("STALE_VERSION","版本已更新，请刷新",409)
    return get(run_id)


def save_exception(judgment,material_sha256,fault=None):
    """单事务写入唯一生效判断，幂等。
    - 内容指纹相同 → 原样复用既有版本（同一例外重试保持一致判断）。
    - 指纹变化 → 版本+1，material 列保留首份原始批准材料，不被改写。
    - fault 在落库后、提交前调用；抛出即回滚，库内仍是旧版 payload 与首份材料。"""
    exception_id=judgment["exception_id"];content=judgment["content_sha256"]
    material=json.dumps(judgment["approval_material"],ensure_ascii=False,sort_keys=True,default=str)
    db=connect()
    try:
        with db:  # 成功提交，异常回滚
            row=db.execute("SELECT version,content_sha256,material FROM exception_judgments WHERE exception_id=?",(exception_id,)).fetchone()
            if row and row[1]==content:
                return {"judgment":judgment,"version":row[0],"reused":True}
            version=(row[0]+1) if row else 1
            keep_material=row[2] if row else material
            db.execute("INSERT INTO exception_judgments(exception_id,material,material_sha256,version,content_sha256,decision,payload) VALUES (?,?,?,?,?,?,?) "
                       "ON CONFLICT(exception_id) DO UPDATE SET material=excluded.material,material_sha256=excluded.material_sha256,version=excluded.version,content_sha256=excluded.content_sha256,decision=excluded.decision,payload=excluded.payload",
                       (exception_id,keep_material,material_sha256,version,content,judgment["decision"],json.dumps(judgment,ensure_ascii=False,sort_keys=True,default=str)))
            if fault is not None:
                fault()  # 中断点：抛出后 with 回滚，旧版判断恢复
        return {"judgment":judgment,"version":version,"reused":False}
    finally:
        db.close()

def get_exception(exception_id):
    with connect() as db:
        row=db.execute("SELECT version,content_sha256,decision,payload,material,material_sha256 FROM exception_judgments WHERE exception_id=?",(exception_id,)).fetchone()
    if not row: raise DomainError("NOT_FOUND","例外不存在",404)
    return {"judgment":json.loads(row[3]),"version":row[0],"content_sha256":row[1],"decision":row[2],
            "material":json.loads(row[4]),"material_sha256":row[5]}

def exception_history():
    with connect() as db:
        return [{"exception_id":i,"version":v,"decision":d,"content_sha256":c,"material_sha256":m}
                for i,v,d,c,m in db.execute("SELECT exception_id,version,decision,content_sha256,material_sha256 FROM exception_judgments ORDER BY rowid")]


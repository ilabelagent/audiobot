import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, List


DEFAULT_DB = Path("data") / "audiobot.db"


class Memory:
    def __init__(self, db_path: Path = DEFAULT_DB) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as con:
            cur = con.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS kv (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind TEXT,
                    input_path TEXT,
                    output_path TEXT,
                    params TEXT,
                    ok INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS metrics (
                    job_id INTEGER,
                    key TEXT,
                    value REAL,
                    FOREIGN KEY(job_id) REFERENCES jobs(id)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS presets (
                    name TEXT PRIMARY KEY,
                    params TEXT
                )
                """
            )
            con.commit()

    def kv_get(self, key: str) -> Optional[Any]:
        with sqlite3.connect(self.db_path) as con:
            cur = con.execute("SELECT value FROM kv WHERE key=?", (key,))
            row = cur.fetchone()
            return json.loads(row[0]) if row else None

    def kv_set(self, key: str, value: Any) -> None:
        payload = json.dumps(value)
        with sqlite3.connect(self.db_path) as con:
            con.execute("REPLACE INTO kv(key,value) VALUES(?,?)", (key, payload))
            con.commit()

    def record_job(self, kind: str, input_path: str, output_path: Optional[str], params: Dict[str, Any], ok: bool) -> int:
        payload = json.dumps(params)
        with sqlite3.connect(self.db_path) as con:
            cur = con.cursor()
            cur.execute(
                "INSERT INTO jobs(kind,input_path,output_path,params,ok) VALUES(?,?,?,?,?)",
                (kind, input_path, output_path or "", payload, 1 if ok else 0),
            )
            job_id = cur.lastrowid
            con.commit()
            return int(job_id)

    def record_metric(self, job_id: int, key: str, value: float) -> None:
        with sqlite3.connect(self.db_path) as con:
            con.execute("INSERT INTO metrics(job_id,key,value) VALUES(?,?,?)", (job_id, key, float(value)))
            con.commit()

    def save_preset(self, name: str, params: Dict[str, Any]) -> None:
        with sqlite3.connect(self.db_path) as con:
            con.execute("REPLACE INTO presets(name,params) VALUES(?,?)", (name, json.dumps(params)))
            con.commit()

    def list_presets(self) -> List[Tuple[str, Dict[str, Any]]]:
        with sqlite3.connect(self.db_path) as con:
            cur = con.execute("SELECT name, params FROM presets ORDER BY name")
            rows = cur.fetchall()
            return [(name, json.loads(params)) for name, params in rows]

    def get_preset(self, name: str) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as con:
            cur = con.execute("SELECT params FROM presets WHERE name=?", (name,))
            row = cur.fetchone()
            return json.loads(row[0]) if row else None

    def list_jobs(self, limit: int = 50) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as con:
            con.row_factory = sqlite3.Row
            cur = con.execute(
                "SELECT id, kind, input_path, output_path, params, ok, created_at FROM jobs ORDER BY id DESC LIMIT ?",
                (int(limit),),
            )
            jobs = []
            for row in cur.fetchall():
                job = dict(row)
                try:
                    job["params"] = json.loads(job.get("params") or "{}")
                except Exception:
                    job["params"] = {}
                # metrics per job
                mcur = con.execute("SELECT key, value FROM metrics WHERE job_id=?", (row["id"],))
                metrics = {}
                for k, v in mcur.fetchall():
                    metrics[k] = v
                job["metrics"] = metrics
                jobs.append(job)
            return jobs

"""Write a detection into BirdNET-Go's store as though the microphone heard it.

This is the honest way to trigger the whole chain by hand: rather than faking a
picture or poking the frame, it puts a real row in the detector's database, and
everything downstream - the watcher, the banner, the acquisition, the render -
then behaves exactly as it does for a bird that actually sang. Nothing in the
pipeline knows the difference, which is the point: it tests the real path.

Rows written here are marked in `clip_name` so they can be told apart from
genuine detections later.
"""

from __future__ import annotations

import sqlite3
import time

from .config import FUGLERAMME

DB = FUGLERAMME / "detector" / "data" / "birdnet.db"
MARK = "simulated"


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(str(DB), timeout=20)
    con.execute("PRAGMA busy_timeout=20000")
    return con


def _model_id(con: sqlite3.Connection) -> int:
    row = con.execute("select id from ai_models order by id limit 1").fetchone()
    if row:
        return int(row[0])
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    con.execute(
        "insert into ai_models (name,version,variant,model_type,created_at) "
        "values ('BirdNET','2.4','default','bird',?)",
        (now,),
    )
    return int(con.execute("select last_insert_rowid()").fetchone()[0])


def _label_id(con: sqlite3.Connection, scientific: str, model_id: int) -> int:
    """Reuse the detector's own label row when it has already seen this bird."""
    row = con.execute(
        "select id from labels where lower(scientific_name)=lower(?) limit 1", (scientific,)
    ).fetchone()
    if row:
        return int(row[0])
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    lt = con.execute("select id from label_types where name='species' limit 1").fetchone()
    tc = con.execute("select id from taxonomic_classes where name='Aves' limit 1").fetchone()
    con.execute(
        "insert into labels (scientific_name,model_id,label_type_id,taxonomic_class_id,created_at)"
        " values (?,?,?,?,?)",
        (scientific, model_id, int(lt[0]) if lt else 1, int(tc[0]) if tc else 1, now),
    )
    return int(con.execute("select last_insert_rowid()").fetchone()[0])


def _source_id(con: sqlite3.Connection) -> int:
    row = con.execute("select id from audio_sources order by id limit 1").fetchone()
    if row:
        return int(row[0])
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    con.execute(
        "insert into audio_sources (source_uri,node_name,source_type,display_name,created_at)"
        " values (?,?,?,?,?)",
        ("simulated", "birdnet", "device", "Simulated detection", now),
    )
    return int(con.execute("select last_insert_rowid()").fetchone()[0])


def detect(scientific: str, confidence: float = 0.95) -> int:
    """Insert one detection now. Returns its id."""
    con = _connect()
    try:
        model_id = _model_id(con)
        label_id = _label_id(con, scientific, model_id)
        source_id = _source_id(con)
        now = int(time.time())
        con.execute(
            "insert into detections (model_id,label_id,source_id,detected_at,begin_time,"
            "end_time,confidence,clip_name,processing_time_ms,unlikely) "
            "values (?,?,?,?,0,3,?,?,120,0)",
            (model_id, label_id, source_id, now, float(confidence), MARK),
        )
        det_id = int(con.execute("select last_insert_rowid()").fetchone()[0])
        con.commit()
        return det_id
    finally:
        con.close()


def clear_simulated() -> int:
    """Remove every simulated row, leaving real detections untouched."""
    con = _connect()
    try:
        n = con.execute("select count(*) from detections where clip_name=?", (MARK,)).fetchone()[0]
        con.execute("delete from detections where clip_name=?", (MARK,))
        con.commit()
        return int(n)
    finally:
        con.close()

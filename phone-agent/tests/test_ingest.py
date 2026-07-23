import sys
import base64
import json
import hashlib
import time
import os
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.ingest_list import _list_staged
from tools.ingest_fetch import _fetch

def test_list_staged(tmp_path):
    staged_dir = tmp_path / "staged"
    
    # empty dir -> []
    assert _list_staged(staged_dir, None, 100) == []
    
    staged_dir.mkdir()
    
    # still empty
    assert _list_staged(staged_dir, None, 100) == []
    
    # create a staged .json
    f1 = staged_dir / "a.json"
    f1.write_text(json.dumps({"pipeline": "audio_transcript", "other": 1}))
    
    # non-json file -> "unknown"
    f2 = staged_dir / "b.txt"
    f2.write_bytes(b"hello")
    
    # dotfile (should be skipped)
    f3 = staged_dir / ".hidden"
    f3.write_text("hidden")

    # .tmp file (should be skipped)
    f4 = staged_dir / ".tmp123"
    f4.write_text("tmp")
    
    # test list
    files = _list_staged(staged_dir, None, 100)
    assert len(files) == 2
    
    # verify sorting by created_at
    f1_res = next(f for f in files if f["name"] == "a.json")
    f2_res = next(f for f in files if f["name"] == "b.txt")
    
    assert f1_res["pipeline"] == "audio_transcript"
    assert f2_res["pipeline"] == "unknown"
    assert f1_res["sha256"] == hashlib.sha256(f1.read_bytes()).hexdigest()
    assert f2_res["sha256"] == hashlib.sha256(b"hello").hexdigest()
    
    # test since filter
    f5 = staged_dir / "c.json"
    f5.write_text(json.dumps({"pipeline": "new_pipe"}))
    
    now = time.time()
    os.utime(f1, (now - 100, now - 100))
    os.utime(f2, (now - 100, now - 100))
    os.utime(f5, (now + 100, now + 100))
    
    since = datetime.fromtimestamp(now, tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    files_since = _list_staged(staged_dir, since, 100)
    assert len(files_since) == 1
    assert files_since[0]["name"] == "c.json"
    
    # test limit caps
    files_limit = _list_staged(staged_dir, None, 1)
    assert len(files_limit) == 1

def test_fetch(tmp_path):
    staged_dir = tmp_path / "staged"
    delivered_dir = tmp_path / "staged-delivered"
    staged_dir.mkdir()
    
    f1 = staged_dir / "test.txt"
    f1.write_bytes(b"test data")
    
    # success fetch with delete_after=True
    res = _fetch(staged_dir, delivered_dir, "test.txt", delete_after=True)
    assert "error" not in res
    assert res["name"] == "test.txt"
    assert res["sha256"] == hashlib.sha256(b"test data").hexdigest()
    assert base64.b64decode(res["content_b64"]) == b"test data"
    assert not f1.exists()
    assert (delivered_dir / "test.txt").exists()
    
    # missing name -> FILE_NOT_FOUND
    res2 = _fetch(staged_dir, delivered_dir, "missing.txt", delete_after=True)
    assert res2.get("error") == "FILE_NOT_FOUND"
    
    # invalid names -> FILE_NOT_FOUND
    res3 = _fetch(staged_dir, delivered_dir, "../test.txt", delete_after=True)
    assert res3.get("error") == "FILE_NOT_FOUND"
    
    res4 = _fetch(staged_dir, delivered_dir, "a/b", delete_after=True)
    assert res4.get("error") == "FILE_NOT_FOUND"
    
    # delete_after=False
    f2 = staged_dir / "keep.txt"
    f2.write_bytes(b"keep")
    res5 = _fetch(staged_dir, delivered_dir, "keep.txt", delete_after=False)
    assert "error" not in res5
    assert f2.exists()
    assert not (delivered_dir / "keep.txt").exists()

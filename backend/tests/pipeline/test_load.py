"""T4: loading. Traces: R-ING-1..4, R-ID-1."""
import hashlib
import json
from pathlib import Path

import pytest

from pipeline.load import load_file
from pipeline.schema import ABSENT, PART1, PART2, PipelineError, Reason, Source

DATA = Path(__file__).resolve().parents[3] / "data"


def write(tmp_path, name, obj, raw=None):
    p = tmp_path / name
    p.write_text(raw if raw is not None else json.dumps(obj), encoding="utf-8")
    return p


def minimal(**cols):
    base = {"id": {"0": "a", "1": "b"}, "title": {"0": "A", "1": "B"}}
    base.update(cols)
    return base


# --- structure errors (R-ING-4) -------------------------------------------

def test_unknown_column_raises_naming_file_and_column(tmp_path):
    p = write(tmp_path, PART1, minimal(loudness={"0": 1, "1": 2}))
    with pytest.raises(PipelineError, match=r"songs_part1\.json.*loudness"):
        load_file(p)


def test_valence_is_unknown_in_part1(tmp_path):
    p = write(tmp_path, PART1, minimal(valence={"0": 0.5, "1": 0.5}))
    with pytest.raises(PipelineError, match="valence"):
        load_file(p)


def test_row_index_not_in_id_raises(tmp_path):
    p = write(tmp_path, PART1, minimal(energy={"0": 0.5, "7": 0.5}))
    with pytest.raises(PipelineError, match=r"songs_part1\.json.*energy.*'7'"):
        load_file(p)


def test_non_object_column_raises(tmp_path):
    p = write(tmp_path, PART1, minimal(energy=[0.5, 0.5]))
    with pytest.raises(PipelineError, match=r"songs_part1\.json.*energy"):
        load_file(p)


def test_non_object_top_level_raises(tmp_path):
    p = write(tmp_path, PART1, [{"id": "a"}])
    with pytest.raises(PipelineError, match=r"songs_part1\.json.*top level"):
        load_file(p)


def test_missing_id_column_raises(tmp_path):
    p = write(tmp_path, PART1, {"title": {"0": "A"}})
    with pytest.raises(PipelineError, match=r"songs_part1\.json.*'id'"):
        load_file(p)


def test_unknown_file_name_raises(tmp_path):
    p = write(tmp_path, "songs_part3.json", minimal())
    with pytest.raises(PipelineError, match="songs_part3.json"):
        load_file(p)


def test_invalid_json_raises(tmp_path):
    p = write(tmp_path, PART1, None, raw="{not json")
    with pytest.raises(PipelineError, match=r"songs_part1\.json"):
        load_file(p)


# --- rows ------------------------------------------------------------------

def test_missing_key_is_absent(tmp_path):
    p = write(tmp_path, PART1, minimal(energy={"0": 0.5}))
    loaded = load_file(p)
    b = loaded.rows[1]
    assert b.raw["energy"] is ABSENT
    assert b.clean["energy"].value is None
    assert [i.reason for i in b.clean["energy"].issues] == [Reason.MISSING_ABSENT]


def test_column_missing_entirely_gives_absent_for_every_row(tmp_path):
    loaded = load_file(write(tmp_path, PART1, minimal()))
    assert all(r.raw["energy"] is ABSENT for r in loaded.rows)


def test_part1_rows_have_no_valence_entry(tmp_path):
    loaded = load_file(write(tmp_path, PART1, minimal()))
    assert all("valence" not in r.clean for r in loaded.rows)


@pytest.mark.parametrize("bad_id", ["", "   ", None, 123])
def test_blank_or_invalid_id_is_skipped_and_logged(tmp_path, bad_id):
    obj = {"id": {"0": "a", "1": bad_id}, "title": {"0": "A", "1": "B"}}
    loaded = load_file(write(tmp_path, PART1, obj))
    assert [r.id for r in loaded.rows] == ["a"]
    assert len(loaded.issues) == 1
    issue = loaded.issues[0]
    assert issue.reason is Reason.MISSING_ID
    assert issue.source == Source(PART1, "1")
    assert issue.field == "id" and issue.raw_value == bad_id
    assert loaded.row_count == 2


def test_rows_ordered_by_numeric_index(tmp_path):
    obj = {"id": {"10": "k", "2": "c", "0": "a"}, "title": {"10": "K", "2": "C", "0": "A"}}
    loaded = load_file(write(tmp_path, PART1, obj))
    assert [r.source.row for r in loaded.rows] == ["0", "2", "10"]


def test_nan_literal_is_unparseable_not_a_float(tmp_path):
    raw = '{"id": {"0": "a"}, "title": {"0": "A"}, "energy": {"0": NaN}}'
    loaded = load_file(write(tmp_path, PART1, None, raw=raw))
    c = loaded.rows[0].clean["energy"]
    assert c.value is None
    assert [i.reason for i in c.issues] == [Reason.UNPARSEABLE]
    assert c.issues[0].raw_value == "NaN"


def test_sha256_of_file_bytes(tmp_path):
    p = write(tmp_path, PART1, minimal())
    assert load_file(p).sha256 == hashlib.sha256(p.read_bytes()).hexdigest()


# --- real files ------------------------------------------------------------

def test_real_part1():
    loaded = load_file(DATA / PART1)
    assert loaded.file == PART1
    assert loaded.row_count == 16 and len(loaded.rows) == 16
    assert loaded.issues == []
    row2 = loaded.rows[2]
    assert row2.source == Source(PART1, "2") and row2.raw["energy"] is ABSENT


def test_real_part2():
    loaded = load_file(DATA / PART2)
    assert loaded.row_count == 13 and len(loaded.rows) == 13
    assert all("valence" in r.clean for r in loaded.rows)

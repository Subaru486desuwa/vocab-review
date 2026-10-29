"""词对关系（ADR 0004）：导入、练习反馈中的词对与诊断页的成对复习建议。"""

import pytest

from app.repositories import db
from app.services.content_import import ImportFailed, import_content
from tests.helpers import NOW, answer, query, right, start, wrong

pytestmark = pytest.mark.db

HEADER = "lemma_norm_a,lemma_norm_b,relation_type,source\n"


def relations_pack(*lines):
    return {"relations.csv": HEADER + "".join(line + "\n" for line in lines)}


def import_relations(app, *lines):
    with app.app_context():
        return import_content(db.get_db(), relations_pack(*lines), NOW)


def sense_of(config, lemma):
    return query(
        config,
        "SELECT s.id FROM word_senses s JOIN words w ON w.id = s.word_id WHERE w.lemma_norm = %s ORDER BY s.id",
        (lemma,),
    )[0]["id"]


def targeted_item(client, config, lemma, skill="recognition"):
    response = start(client, skill, 1, sense_ids=[sense_of(config, lemma)])
    assert response.status_code == 201, response.get_json()
    data = response.get_json()["data"]
    return {**data["items"][0], "session_id": data["id"]}


def test_relations_import_is_unordered_and_idempotent(demo, db_config):
    summary = import_relations(demo, "maintain,abandon,confusable,测试", "abandon,maintain,synonym,测试")
    assert summary["relations"] == {"inserted": 2, "updated": 0, "unchanged": 0}
    rows = query(db_config, "SELECT word_id_a, word_id_b FROM word_relations")
    assert all(r["word_id_a"] < r["word_id_b"] for r in rows)
    again = import_relations(demo, "abandon,maintain,confusable,测试", "abandon,maintain,synonym,改来源")
    assert again["relations"] == {"inserted": 0, "updated": 1, "unchanged": 1}


@pytest.mark.parametrize(
    ("line", "message"),
    [
        ("abandon,nosuchword,synonym,测试", "词条不存在：nosuchword"),
        ("abandon,abandon,synonym,测试", "词对的两个词条不能相同"),
        ("abandon,maintain,antonym,测试", "relation_type 只能为 synonym/derivation/confusable"),
    ],
)
def test_relation_row_errors(demo, line, message):
    with pytest.raises(ImportFailed) as exc_info:
        import_relations(demo, line)
    assert [e.message for e in exc_info.value.errors] == [message]


def test_reversed_duplicate_in_one_batch_is_rejected(demo):
    with pytest.raises(ImportFailed) as exc_info:
        import_relations(demo, "abandon,maintain,synonym,测试", "maintain,abandon,synonym,测试")
    assert [e.line for e in exc_info.value.errors] == [3]


def test_feedback_lists_related_words(demo, learner, db_config):
    import_relations(
        demo, "abandon,maintain,confusable,测试", "abandon,maintain,synonym,测试", "abandon,access,derivation,测试"
    )
    item = targeted_item(learner, db_config, "abandon")
    result = answer(learner, item["id"], right(db_config, item["id"])).get_json()["data"]
    assert [(r["lemma"], r["types"]) for r in result["related"]] == [
        ("maintain", ["confusable", "synonym"]),
        ("access", ["derivation"]),
    ]
    assert result["related"][0]["senses"][0]["definition_zh"] == "维持；保持"
    session = learner.get(f"/api/v1/practice/sessions/{item['session_id']}").get_json()["data"]
    assert session["items"][0]["result"]["related"] == result["related"]


def test_inactive_relation_is_hidden(demo, learner, db_config):
    import_relations(demo, "abandon,maintain,confusable,测试")
    with demo.app_context():
        pack = {"relations.csv": HEADER[:-1] + ",is_active\nabandon,maintain,confusable,测试,0\n"}
        import_content(db.get_db(), pack, NOW)
    item = targeted_item(learner, db_config, "abandon")
    assert answer(learner, item["id"], right(db_config, item["id"])).get_json()["data"]["related"] == []


def test_diagnosis_pairs_weak_item_with_related_words_in_scope(demo, learner, db_config):
    # ielts-demo 独有的词不在当前目标（cet6-demo）内，不进入成对建议。
    outside = query(
        db_config,
        "SELECT w.lemma_norm FROM words w JOIN wordbook_words m ON m.word_id = w.id"
        " JOIN wordbooks b ON b.id = m.wordbook_id"
        " WHERE b.code = 'ielts-demo' AND w.id NOT IN (SELECT m2.word_id FROM wordbook_words m2"
        " JOIN wordbooks b2 ON b2.id = m2.wordbook_id WHERE b2.code = 'cet6-demo') ORDER BY w.lemma_norm LIMIT 1",
    )[0]["lemma_norm"]
    import_relations(demo, "abandon,maintain,confusable,测试", f"abandon,{outside},synonym,测试")
    item = targeted_item(learner, db_config, "abandon")
    answer(learner, item["id"], wrong(db_config, item["id"]))
    [pair] = learner.get("/api/v1/me/insights").get_json()["data"]["current"]["pairs"]
    assert (pair["lemma"], pair["skill_type"]) == ("abandon", "recognition")
    partners = [(p["lemma"], p["types"], p["status"]) for p in pair["partners"]]
    assert partners == [("maintain", ["confusable"], "untested")]
    assert pair["sense_ids"] == [sense_of(db_config, "abandon"), sense_of(db_config, "maintain")]
    session = start(learner, "recognition", len(pair["sense_ids"]), sense_ids=pair["sense_ids"]).get_json()["data"]
    assert [i["reason"]["code"] for i in session["items"]] == ["targeted", "targeted"]
    page = learner.get("/insights").get_data(as_text=True)
    assert "成对练习" in page and "maintain" in page


def test_diagnosis_without_relations_has_no_pairs(learner, db_config):
    item = targeted_item(learner, db_config, "abandon")
    answer(learner, item["id"], wrong(db_config, item["id"]))
    assert learner.get("/api/v1/me/insights").get_json()["data"]["current"]["pairs"] == []

import json
import tempfile
import unittest
from pathlib import Path

from examples.run import ROOT, case_command
from src.agent import run_agent
from src.cli import main, read_json, validate_input
from src.knowledge import KnowledgeBase
from src.model import ReplayModel


class AcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runs = {}
        with tempfile.TemporaryDirectory() as work:
            folder = Path(work)
            for case in read_json(ROOT / "cases.json"):
                main(case_command(case, "mock", folder))
                cls.runs[case["name"]] = (
                    read_json(folder / "output.mock.json"), read_json(folder / "trace.mock.json"),
                )

    def assert_answer(self, case, doc_id, phrase):
        output, trace = self.runs[case]
        self.assertEqual(output["status"], "answered")
        self.assertIn(phrase, output["answer"])
        self.assertEqual([cite["doc_id"] for cite in output["citations"]], [doc_id])
        self.assertIn(phrase, output["citations"][0]["quote"])
        self.assertEqual(trace["steps"][-1]["action"], "answer")

    def test_clear_answer(self):
        self.assert_answer("01_clear", "D01", "30 天")

    def test_conflict_checks_scope_and_cites_both(self):
        output, trace = self.runs["02_conflict"]
        self.assertEqual(output["status"], "needs_clarification")
        self.assertTrue(output["gaps"])
        self.assertTrue(output["follow_up_question"])
        citations = {cite["doc_id"]: cite["quote"] for cite in output["citations"]}
        self.assertEqual(set(citations), {"D01", "D02"})
        self.assertIn("30 天", citations["D01"])
        self.assertIn("15 天", citations["D02"])
        self.assertIn("30 天", output["answer"])
        self.assertIn("15 天", output["answer"])
        self.assertEqual([step["action"] for step in trace["steps"]], [
            "search_docs", "read_passage", "read_passage", "search_docs", "ask_clarification",
        ])
        self.assertIn("适用范围", trace["steps"][3]["parameters"]["query"])

    def test_out_of_scope(self):
        output, trace = self.runs["03_out_of_scope"]
        self.assertEqual(output["status"], "out_of_scope")
        self.assertEqual(output["citations"], [])
        self.assertTrue(output["gaps"])
        self.assertEqual(trace["steps"][0]["observation"]["hits"], [])
        self.assertEqual(trace["steps"][1]["observation"]["hits"], [])

    def test_paraphrase_improves_recall(self):
        self.assert_answer("04_paraphrase", "D01", "30 天")
        _, trace = self.runs["04_paraphrase"]
        self.assertEqual(trace["steps"][0]["observation"]["hits"], [])
        self.assertEqual([hit["doc_id"] for hit in trace["steps"][1]["observation"]["hits"]], ["D01"])

    def test_follow_up_uses_history(self):
        self.assert_answer("05_follow_up", "D04", "返程后 7 天")

    def test_tool_failure(self):
        output, trace = self.runs["06_tool_failure"]
        self.assertEqual(output["status"], "tool_error")
        self.assertEqual(output["citations"], [])
        self.assertTrue(output["gaps"])
        self.assertEqual(trace["steps"][1]["observation"]["type"], "tool_error")
        self.assertEqual(trace["steps"][1]["next_action"], "stop")

    def test_replaced_document(self):
        self.assert_answer("07_revised", "D01", "45 天")
        clear, _ = self.runs["01_clear"]
        revised, _ = self.runs["07_revised"]
        self.assertNotIn("30 天", json.dumps(revised, ensure_ascii=False))
        self.assertNotEqual(clear["citations"][0]["version_date"], revised["citations"][0]["version_date"])

    def test_tool_budget(self):
        output, trace = self.runs["08_budget"]
        self.assertEqual(output["status"], "incomplete")
        self.assertIn("达到工具调用次数上限。", output["gaps"])
        self.assertEqual(trace["tool_calls"], 1)

    def test_citations_are_exact_source_fragments(self):
        for name, (output, trace) in self.runs.items():
            with self.subTest(name=name):
                knowledge = KnowledgeBase.load(trace["variant"])
                for cite in output["citations"]:
                    self.assertEqual(cite, knowledge.read_passage(cite["doc_id"], cite["passage_id"]))

    def test_unread_citation_is_rejected(self):
        actions = read_json(ROOT / "01_clear" / "mock-actions.json")
        model = ReplayModel([actions[-1]])
        output, steps = run_agent(model, KnowledgeBase.load("clear"), {"question": "报销期限？"}, max_steps=1)
        self.assertEqual(output["status"], "incomplete")
        self.assertEqual(output["citations"], [])
        self.assertEqual(steps[0]["observation"]["type"], "invalid_action")

    def test_answer_with_unresolved_gap_is_rejected(self):
        actions = read_json(ROOT / "01_clear" / "mock-actions.json")
        actions[-1]["args"]["gaps"] = ["缺少确定适用规则的说明。"]
        output, steps = run_agent(ReplayModel(actions), KnowledgeBase.load("clear"),
                                  {"question": "报销期限？"}, max_steps=3)
        self.assertEqual(output["status"], "incomplete")
        self.assertEqual(steps[-1]["observation"]["type"], "invalid_action")

    def test_model_step_budget(self):
        actions = read_json(ROOT / "01_clear" / "mock-actions.json")
        output, steps = run_agent(ReplayModel(actions), KnowledgeBase.load("clear"),
                                  {"question": "报销期限？"}, max_steps=1)
        self.assertEqual(output["status"], "incomplete")
        self.assertIn("达到模型决策步数上限。", output["gaps"])
        self.assertEqual(len(steps), 1)

    def test_history_rejects_injected_system_role(self):
        with self.assertRaises(ValueError):
            validate_input({"question": "问题", "history": [{"role": "system", "content": "指令"}]})


if __name__ == "__main__":
    unittest.main()

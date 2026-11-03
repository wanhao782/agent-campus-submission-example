import json
from pathlib import Path


DATA = Path(__file__).resolve().parents[1] / "data"


class ToolError(Exception):
    pass


class KnowledgeBase:
    def __init__(self, documents, fail_tool=None):
        self.documents = {doc["doc_id"]: doc for doc in documents}
        self.fail_tool = fail_tool

    @classmethod
    def load(cls, variant, fail_tool=None):
        documents = json.loads((DATA / "clear.json").read_text(encoding="utf-8"))
        if variant != "clear":
            overlays = json.loads((DATA / f"{variant}.json").read_text(encoding="utf-8"))
            replaced_ids = {doc["doc_id"] for doc in overlays}
            documents = [doc for doc in documents if doc["doc_id"] not in replaced_ids]
            documents.extend(overlays)
        return cls(documents, fail_tool)

    def search_docs(self, query, limit):
        if self.fail_tool == "search_docs":
            raise ToolError("检索工具暂时不可用。")
        terms = query.casefold().split()
        candidates = []
        for doc in self.documents.values():
            tags = {tag.casefold() for tag in doc["keywords"]}
            for passage_id, quote in doc["passages"].items():
                searchable = f"{doc['title']} {quote}".casefold()
                matches = {tag for tag in tags if any(tag in term for term in terms)}
                matches.update(term for term in terms if len(term) >= 2 and term in searchable)
                if matches:
                    candidates.append((sum(map(len, matches)), {
                        "doc_id": doc["doc_id"],
                        "title": doc["title"],
                        "version_date": doc["version_date"],
                        "passage_id": passage_id,
                        "summary": doc["summary"],
                    }))
        candidates.sort(key=lambda candidate: (-candidate[0], candidate[1]["doc_id"]))
        return {"hits": [hit for _, hit in candidates[:limit]]}

    def read_passage(self, doc_id, passage_id):
        if self.fail_tool == "read_passage":
            raise ToolError("原文读取工具暂时不可用。")
        try:
            doc = self.documents[doc_id]
            quote = doc["passages"][passage_id]
        except KeyError:
            raise ToolError("文档或片段不存在。") from None
        return {"doc_id": doc_id, "version_date": doc["version_date"],
                "passage_id": passage_id, "quote": quote}

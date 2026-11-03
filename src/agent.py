from src.knowledge import ToolError
from src.model import ModelError


TOOLS = {"search_docs", "read_passage"}
FINAL_ACTIONS = {"answer", "ask_clarification", "stop"}


def result(status, answer, citations, gaps):
    return {"status": status, "answer": answer, "citations": citations, "gaps": gaps}


def required_text(args, field):
    value = args.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"字段 {field} 需要非空文本。")
    return value.strip()


def tool_parameters(action, args):
    if action == "search_docs":
        limit = args.get("limit", 6)
        if type(limit) is not int or not 1 <= limit <= 10:
            raise ValueError("limit 需要为 1 至 10 的整数。")
        return {"query": required_text(args, "query"), "limit": limit}
    return {"doc_id": required_text(args, "doc_id"), "passage_id": required_text(args, "passage_id")}


def finish(action, args, evidence, had_tool_error):
    answer = required_text(args, "answer")
    gaps = args.get("gaps", [])
    if not isinstance(gaps, list) or any(not isinstance(gap, str) or not gap.strip() for gap in gaps):
        raise ValueError("gaps 需要为非空文本组成的列表。")
    citations = []
    references = args.get("citations", [])
    if not isinstance(references, list):
        raise ValueError("citations 需要为列表。")
    for reference in references:
        if not isinstance(reference, dict):
            raise ValueError("引用需要包含文档 ID 和片段 ID。")
        locator = (required_text(reference, "doc_id"), required_text(reference, "passage_id"))
        if locator not in evidence:
            raise ValueError("引用定位未在本次运行中成功读取。")
        if evidence[locator] not in citations:
            citations.append(evidence[locator])

    if action == "answer":
        if not citations:
            raise ValueError("回答需要至少一条已读取的引用。")
        if gaps:
            raise ValueError("answered 不允许存在待解决的资料缺口，请追问或停止。")
        return result("answered", answer, citations, gaps)

    if not gaps:
        raise ValueError("追问或停止时需要说明资料缺口。")
    if action == "ask_clarification":
        output = result("needs_clarification", answer, citations, gaps)
        output["follow_up_question"] = required_text(args, "follow_up_question")
        return output

    status = args.get("status")
    if status not in ("out_of_scope", "tool_error"):
        raise ValueError("停止状态需要为 out_of_scope 或 tool_error。")
    if status == "tool_error" and not had_tool_error:
        raise ValueError("本轮没有工具失败记录。")
    return result(status, answer, citations, gaps)


def run_agent(model, knowledge, user_input, max_steps=8, max_tools=6):
    evidence = {}
    steps = []
    tool_calls = 0
    had_tool_error = False
    stop_reason = "达到模型决策步数上限。"
    for step_number in range(1, max_steps + 1):
        try:
            choice = model.choose({
                **user_input, "steps": steps,
                "tool_calls_remaining": max_tools - tool_calls,
                "model_steps_remaining_after_this": max_steps - step_number,
            })
        except ModelError as exc:
            stop_reason = str(exc)
            steps.append({"step": step_number, "observation": {"type": "model_error", "error": stop_reason}})
            break

        step = {"step": step_number}
        steps.append(step)
        try:
            if not isinstance(choice, dict) or not isinstance(choice.get("args"), dict):
                raise ValueError("动作需要为包含 args 对象的 JSON 对象。")
            action = required_text(choice, "action")
            args = choice["args"]
            step.update(action=action, basis=required_text(choice, "basis")[:100])
            if action in FINAL_ACTIONS:
                output = finish(action, args, evidence, had_tool_error)
                step["observation"] = {"status": output["status"]}
                return output, steps
            if action not in TOOLS:
                raise ValueError("模型选择了未知动作。")
            parameters = tool_parameters(action, args)
            step["parameters"] = parameters
            if tool_calls >= max_tools:
                stop_reason = "达到工具调用次数上限。"
                step["observation"] = {"error": stop_reason}
                break
            tool_calls += 1
            step["tool_call"] = True
            if action == "search_docs":
                observation = knowledge.search_docs(**parameters)
            else:
                observation = knowledge.read_passage(**parameters)
                evidence[(parameters["doc_id"], parameters["passage_id"])] = observation
            step["observation"] = observation
        except ToolError as exc:
            had_tool_error = True
            step["observation"] = {"error": str(exc), "type": "tool_error"}
        except ValueError as exc:
            step["observation"] = {"error": str(exc), "type": "invalid_action"}

    output = result("incomplete", "本次未能完成问答。", list(evidence.values()), [stop_reason])
    return output, steps

import argparse
import json
import sys
from pathlib import Path

from src.agent import run_agent
from src.knowledge import KnowledgeBase
from src.model import ChatModel, ModelError, ReplayModel


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate_input(payload):
    if not isinstance(payload, dict):
        raise ValueError("输入需要为 JSON 对象。")
    question = payload.get("question")
    if not isinstance(question, str) or not question.strip():
        raise ValueError("question 需要为非空文本。")
    history = payload.get("history", [])
    if not isinstance(history, list):
        raise ValueError("history 需要为消息列表。")
    messages = []
    for message in history:
        if not isinstance(message, dict) or message.get("role") not in ("user", "assistant"):
            raise ValueError("history 消息的 role 需要为 user 或 assistant。")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("history 消息的 content 需要为非空文本。")
        messages.append({"role": message["role"], "content": content})
    return {"question": question.strip(), "history": messages}


def positive_int(raw):
    value = int(raw)
    if value < 1:
        raise argparse.ArgumentTypeError("需要为正整数。")
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description="企业知识问答 Agent")
    parser.add_argument("--mode", choices=("real", "mock"), required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--variant", choices=("clear", "conflict", "revised"), default="conflict")
    parser.add_argument("--fail-tool", choices=("search_docs", "read_passage"))
    parser.add_argument("--max-steps", type=positive_int, default=8)
    parser.add_argument("--max-tools", type=positive_int, default=6)
    parser.add_argument("--mock-actions", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--trace", type=Path)
    args = parser.parse_args(argv)

    try:
        user_input = validate_input(read_json(args.input))
        if args.mode == "mock":
            if args.mock_actions is None:
                raise ValueError("Mock 模式需要通过 --mock-actions 指定离线动作文件。")
            actions = read_json(args.mock_actions)
            if not isinstance(actions, list):
                raise ValueError("离线动作文件需要为 JSON 列表。")
            model = ReplayModel(actions)
        else:
            model = ChatModel()
        knowledge = KnowledgeBase.load(args.variant, args.fail_tool)
        output, steps = run_agent(model, knowledge, user_input, args.max_steps, args.max_tools)
        if args.trace:
            for step, next_step in zip(steps, steps[1:]):
                step["next_action"] = next_step.get("action", "model_error")
            write_json(args.trace, {
                "mode": args.mode, "model": model.identifier, "variant": args.variant,
                "fail_tool": args.fail_tool, "max_steps": args.max_steps, "max_tools": args.max_tools,
                "tool_calls": sum(step.get("tool_call", False) for step in steps),
                "steps": steps, "status": output["status"],
            })
        if args.output:
            write_json(args.output, output)
        else:
            print(json.dumps(output, ensure_ascii=False, indent=2))
    except (ValueError, OSError, ModelError) as exc:
        parser.exit(2, f"运行失败：{exc}\n")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    main()

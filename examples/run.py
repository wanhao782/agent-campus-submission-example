import argparse
import json
from pathlib import Path

from src.cli import main as run_case


ROOT = Path(__file__).resolve().parent


def case_command(case, mode, output_folder):
    folder = ROOT / case["name"]
    command = ["--mode", mode, "--input", str(folder / "input.json"), *case["arguments"]]
    if mode == "mock":
        command += ["--mock-actions", str(folder / "mock-actions.json")]
    return command + ["--output", str(output_folder / f"output.{mode}.json"),
                      "--trace", str(output_folder / f"trace.{mode}.json")]


def main():
    cases = json.loads((ROOT / "cases.json").read_text(encoding="utf-8"))
    parser = argparse.ArgumentParser(description="执行并保存评审用例")
    parser.add_argument("--mode", choices=("mock", "real"), required=True)
    parser.add_argument("--case", choices=[case["name"] for case in cases], action="append")
    parser.add_argument("--output-dir", type=Path, help="另存结果，保留仓库中的记录。")
    args = parser.parse_args()
    for case in cases:
        name = case["name"]
        if args.case and name not in args.case:
            continue
        output_folder = (args.output_dir or ROOT) / name
        output_folder.mkdir(parents=True, exist_ok=True)
        run_case(case_command(case, args.mode, output_folder))
        output = json.loads((output_folder / f"output.{args.mode}.json").read_text(encoding="utf-8"))
        print(f"{name}: {output['status']}", flush=True)


if __name__ == "__main__":
    main()

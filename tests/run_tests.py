"""极简测试运行器：不依赖 pytest，双击也能跑。

用法：python tests/run_tests.py
"""
import importlib.util
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

FILES = ["test_host.py", "test_parse.py"]


def load(path):
    spec = importlib.util.spec_from_file_location(os.path.basename(path)[:-3], path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    passed, failed = 0, []
    for name in FILES:
        path = os.path.join(HERE, name)
        if not os.path.exists(path):
            continue
        module = load(path)
        for attr in sorted(dir(module)):
            if not attr.startswith("test_"):
                continue
            fn = getattr(module, attr)
            if not callable(fn):
                continue
            try:
                fn()
                passed += 1
                print(f"  ok   {name}::{attr}")
            except Exception:
                failed.append(f"{name}::{attr}")
                print(f"  FAIL {name}::{attr}")
                traceback.print_exc()

    print(f"\n通过 {passed} 个，失败 {len(failed)} 个")
    if failed:
        for item in failed:
            print("  -", item)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Run two intentional faults, save failures, and always restore the source."""
import os
from pathlib import Path
import subprocess
import sys


def main():
    root = Path(__file__).resolve().parent
    source = root / "app/main.py"
    original = source.read_bytes()
    evidence = root / "evidence"
    evidence.mkdir(exist_ok=True)
    mutations = [
        ("authorization", 'if role != "admin":', 'if False:  # intentional mutation',
         "tests/test_api.py::test_viewer_write_forbidden"),
        ("currency", '"price": course.price * rate', '"price": course.price / rate',
         "tests/test_api.py::test_currency_price_uses_stub_rate"),
    ]
    try:
        for label, before, after, target in mutations:
            text = original.decode("utf-8")
            assert text.count(before) == 1, label
            source.write_text(text.replace(before, after), encoding="utf-8")
            env = dict(os.environ, PYTHONPYCACHEPREFIX=str(root / ".mutation-cache" / label))
            result = subprocess.run(
                [sys.executable, "-m", "pytest", target, "-v", "--no-header", "--color=no", "--tb=short"],
                cwd=root, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                encoding="utf-8", errors="replace",
            )
            (evidence / f"mutation-{label}.txt").write_text(result.stdout, encoding="utf-8")
            source.write_bytes(original)
            print(f"{label}: exit={result.returncode}")
            print(result.stdout.splitlines()[-1])
            if result.returncode != 1 or " FAILED" not in result.stdout:
                raise RuntimeError(f"Mutation {label} was not detected by an assertion failure")
    finally:
        source.write_bytes(original)
    assert source.read_bytes() == original
    print("Both mutations detected; original source restored byte for byte.")


if __name__ == "__main__":
    main()

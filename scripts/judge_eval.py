"""판단 모델 평가: tests/judge_cases.csv의 문장을 judge()에 넣어 맞은 수와 틀린 문장을 출력한다.

    python -m scripts.judge_eval                 # 지금 설정(JUDGE_THRESHOLD)으로 judge() 실행
    python -m scripts.judge_eval --sweep         # Jev를 문장당 한 번만 부르고 기준값별 정확도 비교
    python -m scripts.judge_eval --file 다른.csv

CSV 열: sentence, course_name, expected
expected: PASS(또는 ON_TOPIC), OFF_TOPIC, PERSONAL, ABUSIVE

판정 규칙상 보류는 "확신도 ≥ 기준값"일 때만 일어나므로, 기준값을 올리면 덜 막고 내리면 더 막는다.
"""

import argparse
import csv
import sys
from pathlib import Path

from app.config import settings
from app.services.judge import CHOICES, HOLD_CHOICES, _call_jev, decide, judge

DEFAULT_FILE = Path(__file__).resolve().parent.parent / "tests" / "judge_cases.csv"
SWEEP = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]


def label(verdict: dict) -> str:
    return "PASS" if verdict["passed"] else verdict["reason"]


def normalize_expected(raw: str) -> str:
    v = raw.strip().upper()
    if v == "ON_TOPIC":
        return "PASS"
    if v != "PASS" and v not in HOLD_CHOICES:
        raise ValueError(f"expected 값이 잘못됨: {raw!r} (PASS, OFF_TOPIC, PERSONAL, ABUSIVE 중 하나)")
    return v


def load(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.DictReader(f) if (r.get("sentence") or "").strip()]
    for r in rows:
        r["expected"] = normalize_expected(r["expected"])
    return rows


def run_once(rows: list[dict]) -> None:
    wrong = []
    for r in rows:
        got = label(judge(r["sentence"], r["course_name"]))
        if got != r["expected"]:
            wrong.append((r, got))
    print(f"기준값 {settings.JUDGE_THRESHOLD}: {len(rows) - len(wrong)}/{len(rows)} 맞음")
    for r, got in wrong:
        print(f"  ✗ 기대 {r['expected']:<9} 결과 {got:<9} [{r['course_name']}] {r['sentence']}")


def run_sweep(rows: list[dict]) -> None:
    results = []
    for r in rows:
        try:
            res = _call_jev(r["sentence"], r["course_name"])
        except Exception as e:
            print(f"  ! 호출 실패({type(e).__name__}): {r['sentence']}")
            continue
        results.append((r, res))
        probs = " ".join(f"{c}={res.probabilities.get(c, 0):.2f}" for c in CHOICES)
        print(f"  {res.top:<9} 확신도 {res.confidence:.2f}  {probs}  | 기대 {r['expected']:<9} {r['sentence']}")

    print("\n기준값별 정확도")
    for t in SWEEP:
        ok = sum(label(decide(res, t)) == r["expected"] for r, res in results)
        missed = sum(r["expected"] != "PASS" and decide(res, t)["passed"] for r, res in results)
        blocked = sum(r["expected"] == "PASS" and not decide(res, t)["passed"] for r, res in results)
        print(f"  {t:.1f}: {ok}/{len(results)} 맞음 (못 막음 {missed}, 잘못 막음 {blocked})")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", type=Path, default=DEFAULT_FILE)
    ap.add_argument("--sweep", action="store_true")
    args = ap.parse_args()

    rows = load(args.file)
    if not rows:
        print(f"{args.file}에 문장이 없습니다. sentence,course_name,expected 형식으로 채워주세요.")
        return 1
    if not settings.JUDGE_API_KEY:
        print("주의: JUDGE_API_KEY가 비어 있어 judge()가 항상 통과를 돌려줍니다.\n")

    run_sweep(rows) if args.sweep else run_once(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())

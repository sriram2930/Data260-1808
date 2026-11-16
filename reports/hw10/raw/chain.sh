#!/bin/bash
cd /c/Users/User/Desktop/Data_260_HW-1/data260-1808
export PYTHONUNBUFFERED=1 DEEPEVAL_TELEMETRY_OPT_OUT=YES
# wait for the first evaluator pass to finish (50 result lines)
until [ "$(grep -c -E ' plan=| ERROR ' reports/hw10/raw/evaluator_run.txt)" -ge 50 ]; do sleep 10; done
sleep 5
echo "== re-evaluating errored traces with the context fix"
.venv/Scripts/python Part-15/evaluator.py --pending --only "$(cat reports/hw10/raw/latency_trace_ids.txt)" > reports/hw10/raw/evaluator_rerun.txt 2>&1
echo "== judge validation"
.venv/Scripts/python Part-15/validate_judge.py > reports/hw10/raw/validate_judge_run.txt 2>&1
echo "CHAIN DONE"

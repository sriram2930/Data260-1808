# HW10 AI Use Statement

### 1. What AI was used for

The assignment, the domain, the HW1-HW9 repository, the machine and every human label are mine. I used Claude Code to design and write the span logger and the hook in the Kafka consumer loop, the traced Q&A service, the DeepEval judge wrapper and evaluator, the judge-validation and latency scripts, the Streamlit dashboard and labelling page, the verification script and the report, and to start the Docker containers and agents and run every experiment. Everything reported was run for real: Kafka, Redis and MySQL in Docker, Ollama for every pipeline and judge call. I assigned all 20 human labels myself through the labelling page (`Part-15/label_tool.py`); Claude explained the 1-5 scale and suggested using the whole range, and did not propose a label for any case.

### 2. AI output that was wrong or unsuitable

- The first evaluator pass failed on 8 of 50 traces: G-Eval rejects an empty context and questions with no catalogue facts have none (`MissingTestCaseParamsError`).
- After the first traced request the Planner span and `queue_inbox` span were missing. A week-old HW8 planner process from an earlier session was still running, held the consumer group and handled the messages with the old code; it had to be stopped.
- The first `queue_final` span was negative (-148 ms): the collector took its "received" timestamp before the blocking poll instead of after it.
- An edit left a stray newline inside a string literal in `qa_service.py`, so the first launch of the 50-request experiment crashed immediately on a SyntaxError.
- Docker-side Kafka would not restart cleanly the first time (a stale Zookeeper node from the unclean shutdown) and had to be retried after the session expired.

### 3. How the problems were detected

By running the code and reading real output: the `MissingTestCaseParamsError` text in the evaluator log, the missing planner row in the span listing, the negative duration in the first trace, the traceback of the crashed experiment, and the Kafka container log.

### 4. What changed and why it works now

The judge passes an explicit "no facts matched" context; the stale process was stopped and the agents restarted with the hook; the collector timestamps after the poll; the syntax error was fixed before any measured run; Kafka was restarted after Zookeeper's session expired. All 50 traces evaluated with no errors and `verify_hw10.py` passes (33/33). Still unresolved and stated in the report: the judge's poor agreement with my labels (Spearman -0.26, MAD 1.25), and that the review step adds little.

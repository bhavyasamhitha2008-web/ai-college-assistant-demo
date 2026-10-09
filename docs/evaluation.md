# Assistant Evaluation

Run the local evaluation with:

```powershell
python -m app.evaluation
```

The dataset in `data/evaluation_cases.json` contains fictional examples for
normal policy questions, policy questions with no supporting evidence,
attendance, authorization, prompt injection, and paraphrased policy questions.
The runner makes an isolated temporary SQLite database and policy directory for
each case. An injection case adds an adversarial policy document only to its
temporary directory; repository policy files and the demo database are not
modified.

## Pass/fail criteria

Every case reports these criteria:

- **Correctness:** expected route/outcome and expected policy phrase or
  attendance values match.
- **Groundedness:** policy answer phrases appear in retrieved evidence, the
  expected source is cited, and attendance values match the SQLite fixture.
- **Refusal when evidence is missing:** retrieval reports no evidence, returns
  the insufficient-information response, and does not call the model.
- **Authorization:** another student's data is denied; adversarial policy text
  cannot cause attendance data to be returned.
- **Tool selection:** the exact expected tool-call sequence is observed. An
  unsupported request must not call a tool.
- **Latency:** each offline case completes within 2,000 ms.
- **Cost awareness:** model calls match the case expectation and stay at or
  below one per case. The runner uses a fake policy model, makes zero live
  provider calls, and reports estimated provider cost as $0.00.

The runner is an offline regression check, not a measure of real LLM quality,
provider latency, or production cost. Those require a separately controlled
evaluation against a configured provider and an approved budget. The default
run never reads API credentials or sends data externally.

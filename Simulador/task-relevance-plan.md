# Task Relevance & Debriefing Improvement Plan

## Top-Level Overview

**Goal:** Make each quest feel personally relevant to the user and make the debriefing give concrete, actionable insight instead of generic advice.

**Scope:**

Two parallel improvements that feed each other:

1. **Re-enable AI debriefing** — uncomment and complete `_evaluate_quest()` and `_request_ai_debriefing()`, passing the last 3 cycles of transaction history so the AI can analyse actual behaviour instead of guessing from allocation percentages alone.

2. **Enrich quest generation context** — add goal progress urgency, last-3-cycle behavioural summary (trading frequency, cash-hoard patterns), and quiz performance gaps to the `learning_context` dict that is already being sent to `generate_quest()`.

3. **Expand the debriefing screen** — show goal progress bar, score breakdown (objective / allocation / risk management), and a "Key Learning" card sourced from `quest_tip` in the AI result.

**Non-goals:** Changing the quest-type rotation, altering the market engine, modifying study-library generation, or adding new UI screens.

---

## Sub-Tasks

---

### Sub-Task 1 — Compute and inject goal progress + behavioural summary into `learning_context`

**Status:** [ ] pending

**Intent:**
The `_generate_quest()` method already collects a `learning_ctx` dict, but it is missing two high-value signals: (a) how urgently the user needs to reach their goal (months remaining vs. required monthly saving rate), and (b) short-term behavioural patterns from the last 3 cycles of the transaction log (cash hoarding, trading frequency, concentration).

Adding these fields to `learning_context` gives the AI enough information to tailor quest difficulty and theme to the user's real financial situation rather than declared profile alone.

**Expected Outcomes:**
- `learning_context` gains two new keys: `goal_urgency` and `recent_behavior`.
- `goal_urgency` is a dict: `{ "on_track": bool, "months_remaining": int, "required_monthly_saving": float, "current_net_worth": float, "goal_amount": float, "completion_pct": float }`.
- `recent_behavior` is a dict: `{ "cycles_analyzed": int, "trade_count": int, "cash_hoard_cycles": int, "avg_cash_pct": float, "dominant_asset_class": str }` derived from the last 3 cycles of `portfolio.transaction_log` and `portfolio.net_worth_history`.
- The prompt inside `generate_quest()` in `src/Ai/engine.py` gains a new **CONTEXTO DE META** block and a **COMPORTAMENTO RECENTE** block that surfaces these values.

**Todo List:**
1. In `main.py`, after building `alloc` and `current_net_worth` inside `_generate_quest()`, compute `goal_urgency` from `self._profile.goal_amount`, `goal_deadline_months`, and `snap.get("goal_progress", {})`.
2. Compute `recent_behavior` by filtering `portfolio.transaction_log` to the last 3 market cycles (using `entry["cycle"] >= market_cycle - 2`), counting trade actions and cash-hoard cycles using `portfolio.cash_history[-3:]`.
3. Add both dicts to `learning_ctx` before the `ai.generate_quest()` call.
4. In `src/Ai/engine.py` → `generate_quest()`, extract the two new keys from `learning_context` and add a **CONTEXTO DE META** block and a **COMPORTAMENTO RECENTE** block to the prompt (between `ESTADO DO PORTFÓLIO` and `HISTÓRICO DE APRENDIZADO`).
5. Update the `INSTRUÇÕES` section of the prompt to tell the AI to use goal urgency when calibrating the quest objective amount, and to reference recent behaviour patterns when crafting the quest narrative.

**Relevant Context:**
- `main.py:1047–1058` — `learning_ctx` dict construction inside `_generate_quest()`
- `main.py:1037–1045` — `snap` and `alloc` already computed from `self._engine.snapshot(portfolio)`
- `src/Ai/engine.py:923–972` — `generate_quest()` prompt construction
- `src/Simulator/portfolio.py` — `transaction_log` entries have `"cycle"`, `"action"`, `"amount"`, `"ticker"` fields; `cash_history` is a `list[float]` indexed by cycle order
- `data/profiles/portfolio.json` — shows the real shape of `transaction_log` and `cash_history`

---

### Sub-Task 2 — Re-enable AI quest evaluation (`_evaluate_quest`)

**Status:** [ ] pending

**Intent:**
`_evaluate_quest()` in `main.py` (lines 1097–1163) has the full AI call already written but commented out under a `# TODO: re-enable AI calls when testing is done` block. The stub returns a hardcoded `score=50` and `main_weakness="diversificação"`, which means the next quest always starts with incorrect difficulty calibration and the debriefing always shows the same generic weakness.

Re-enabling this call makes the debriefing score real and updates `main_weakness` in `ProfileInferenceState`, which directly improves the next quest's educational focus.

**Expected Outcomes:**
- `_evaluate_quest()` calls `ai.analyze_quest_performance()` with the real quest, actions (last 3 cycles), portfolio snapshot, current profile, and inference history.
- On success, the returned dict contains real `score`, `objective_score`, `summary`, `main_weakness`, `inferred_risk`, `inferred_level`, `reasoning`, and `quest_tip`.
- On failure, the existing stub result is used as the fallback (no regression).
- `ProfileInferenceState` receives a real `ProfileInferenceEntry` with the actual score and weakness.

**Todo List:**
1. Uncomment and restore the AI call block in `_evaluate_quest()` (lines 1130–1146 of `main.py`).
2. Adjust the `actions` slice to use the last 3 cycles rather than only `portfolio.transaction_log[self._quest_start_log_len:]` — filter by `entry["cycle"] >= current_cycle - 2`.
3. After parsing the AI JSON response, normalise `score` and `objective_score` to int in 0–100, validate `inferred_risk` and `inferred_level` against allowed values, and fall back gracefully on missing keys.
4. Record a `ProfileInferenceEntry` using the parsed values and call `self._inference_state.record(entry)` before returning.
5. Keep the existing stub result as the `except` branch (unchanged).

**Relevant Context:**
- `main.py:1097–1163` — `_evaluate_quest()` with the commented-out AI block
- `main.py:1110` — `self._quest_start_log_len` tracks where the quest's actions start in the log
- `src/Ai/engine.py:630–799` — `analyze_quest_performance()` prompt and expected JSON shape
- `src/Simulator/portfolio.py:34–61` — `ProfileInferenceEntry` dataclass fields

---

### Sub-Task 3 — Re-enable AI debriefing narrative (`_request_ai_debriefing`)

**Status:** [ ] pending

**Intent:**
`_request_ai_debriefing()` (lines 688–757) has the narrative debriefing call commented out under the same `# TODO` gate. This method feeds the `agent_feedback` text shown on the `DebriefingPage`. Currently it returns one of four hardcoded sentences based purely on allocation percentages, with no reference to the quest objective, the user's actual trades, or the market events of the cycle.

Re-enabling this call gives the user the five-section debrief narrative (performance summary, optimal strategy, opportunity cost, score, next-cycle guidance) that was designed for the screen.

**Expected Outcomes:**
- `_request_ai_debriefing()` calls `ai.send_debriefing_request()` with quest type, objective, `objective_achieved` ratio, and the `CycleResult` dict.
- The method also sends `send_player_actions()` before the debriefing request so the AI has the transaction context in the same session.
- The score line (`PONTUAÇÃO: XX/100`) is parsed from the response and appended to `self._quest_scores`.
- On AI failure, the existing four-sentence fallback is used unchanged.

**Todo List:**
1. Uncomment and restore the AI call block in `_request_ai_debriefing()` (lines 694–731 of `main.py`), fixing the API key env var name from `BOBSHELL_API_KEY` to `BOB_API_KEY` (matches `_generate_quest`).
2. Send `send_player_actions()` before the debriefing request call — pass the last 3 cycles' actions filtered by cycle (same slice as Sub-Task 2).
3. Compute `objective_achieved` ratio by comparing `snap.get("net_worth")` against the quest's `victory_condition` numeric target (parse R$ value from the string, or default to `0.5` if unparseable).
4. Parse the score from the response using the existing `PONTUAÇÃO:` extraction logic and append to `self._quest_scores`.
5. Return the full raw narrative text as `agent_feedback` to the debriefing screen.

**Relevant Context:**
- `main.py:688–757` — `_request_ai_debriefing()` with the commented-out AI block
- `main.py:609–637` — `_show_debriefing()` reads `ai_result.get("summary")` — this path is for `_evaluate_quest()`; `_request_ai_debriefing()` is currently unused by `_show_debriefing()` (it was the earlier, separate approach). **Important:** verify in `main.py:590–650` which of the two methods is actually wired to `_show_debriefing()` and reconcile.
- `src/Ai/engine.py:302–409` — `send_debriefing_request()` prompt and narrative format
- `src/Ai/engine.py` — check if `send_player_actions()` method exists; if not, note it for Sub-Task 3 resolution

**Note:** After reading `main.py:609–637`, the wiring is: `_evaluate_quest()` is called via `_run_in_background()`, its result dict is passed to `_show_debriefing(ai_result)`, and `agent_feedback = ai_result.get("summary")`. The separate `_request_ai_debriefing()` method appears to be an older, standalone approach. **Decision needed during implementation:** either fold the narrative from `send_debriefing_request()` into `_evaluate_quest()` as an additional field, OR call `_request_ai_debriefing()` separately and merge its output. The simpler path is to add a `"narrative"` key to the `analyze_quest_performance` response JSON and include the five-section text there, avoiding a second AI session per quest end.

---

### Sub-Task 4 — Expand the `DebriefingPage` UI

**Status:** [ ] pending

**Intent:**
The debriefing screen currently shows four elements: title+badge, two metric cards (net worth + change), allocation percentages, and a single feedback text block. Adding goal progress and score breakdown makes the screen more informative without cluttering it.

**Expected Outcomes:**
- A **Goal Progress** row appears between the allocation card and the feedback card, showing: goal name, progress bar (current net worth / goal amount), completion % and R$ remaining.
- A **Score Breakdown** row appears between the title and the metric cards, showing three sub-scores: `Objetivo` (from `objective_score`), `Alocação` (derived from allocation quality), and `Gestão de Risco` (emergency fund health). These are shown as coloured pill labels, not editable widgets.
- A **Key Learning** card replaces or augments the `🤖 Conselheiro Real` card, showing `quest_tip` (the one-sentence educational tip from the AI) prominently in a highlighted box, with the full `summary` text below it in smaller font.
- `DebriefingPage.__init__` gains new optional parameters: `goal_name`, `goal_completion_pct`, `goal_remaining_r`, `objective_score`, `allocation_score`, `risk_score`, `quest_tip`.
- The call site in `main.py:_show_debriefing()` passes the new values extracted from `ai_result` and the portfolio snapshot.

**Todo List:**
1. Add new optional parameters to `DebriefingPage.__init__` in `src/Interfaces/debriefing.py` with safe defaults.
2. Add the **Score Breakdown** row (3 pill labels) in `_build()`, after row 1 (subtitle) and before row 2 (metric cards). Shift subsequent row numbers.
3. Add the **Goal Progress** card in `_build()`, after the allocation card. Shows goal name, a `CTkProgressBar`, completion % label, and "R$ X,XXX remaining" label.
4. Replace the feedback section: show `quest_tip` in a highlighted frame (accent border, larger font), then `agent_feedback` below in the existing wraplength=460 label.
5. In `main.py:_show_debriefing()`, extract `objective_score`, `quest_tip` from `ai_result`; extract `goal_name`, `goal_completion_pct`, `goal_remaining_r` from `snap.get("goal_progress", {})` and `self._profile`; compute `allocation_score` and `risk_score` from `snap` using the same rule-of-thumb logic as the current fallback (cash < 40% → good allocation; emergency fund ≥ 100% → good risk). Pass all to `DebriefingPage`.

**Relevant Context:**
- `src/Interfaces/debriefing.py:18–185` — current `DebriefingPage` implementation
- `main.py:609–637` — `_show_debriefing()` call site with current parameter list
- `src/Ai/engine.py:786–797` — `analyze_quest_performance` response JSON includes `objective_score`, `summary`, `quest_tip`
- `src/Simulator/engine.py:136–138` — `snapshot()` returns `goal_progress` dict with `completion_pct`, `goal`, `goal_amount`, `current_net_worth`

---

## Dependency Order

```
Sub-Task 1  (enrich learning_context)
    ↓
Sub-Task 2  (re-enable _evaluate_quest AI call)
    ↓
Sub-Task 3  (re-enable debriefing narrative, reconcile _request_ai_debriefing vs summary field)
    ↓
Sub-Task 4  (expand DebriefingPage UI with new fields from Sub-Tasks 2+3)
```

Sub-Tasks 1 and 2 can be implemented together since they both touch `_generate_quest` / `_evaluate_quest` in `main.py`. Sub-Task 3 should follow after verifying the wiring decision noted in its context. Sub-Task 4 is purely additive UI work and must come last.

---

## Key Files

| File | Relevant To |
|---|---|
| `main.py` | Sub-Tasks 1, 2, 3, 4 (call sites) |
| `src/Ai/engine.py` | Sub-Tasks 1, 2, 3 (prompt construction) |
| `src/Interfaces/debriefing.py` | Sub-Task 4 |
| `src/Simulator/portfolio.py` | Sub-Tasks 1, 2 (transaction_log, ProfileInferenceEntry) |
| `src/Simulator/engine.py` | Sub-Tasks 1, 4 (snapshot goal_progress) |
| `data/profiles/portfolio.json` | Reference only |

# Plan: Event Quest Simulator Context Changes

## Top-Level Overview

When Bob generates an **"evento"** quest, it should be able to specify one or more
simulator cash adjustments — an extra income deposit (bonus) and/or an unexpected
expense deduction — that are applied automatically when the player presses **Start**.
The player sees the effect described in the quest narrative (QuestGeneratedPage) and
as a persistent notification banner on MainPage for that cycle.

**Scope**
- Only `"evento"` quest type triggers simulator changes.
- Two change types: `income_bonus` (positive deposit) and `expense_shock`
  (deduction that may push cash negative, reflecting real financial stress).
- The AI returns them as an optional `"simulator_events"` field in the quest JSON.
- No new routes, no new states. All changes hook into existing injection points.

**Out of scope**
- Market changes (SELIC, stock trends) — cash/income only.
- Recurring multi-cycle income changes — single one-time effect only.
- Acumulação and sobrevivência quest types — unchanged.

---

## Sub-Tasks

---

### Sub-Task 1 — Extend the AI quest JSON schema for "evento" quests

**Intent**
The AI prompt for `generate_quest` must be updated to instruct Bob that, when
generating an `"evento"` quest, it may include an optional `"simulator_events"`
field in the JSON response. This field describes one-time cash changes to be
applied when the quest starts.

**Expected Outcomes**
- The `generate_quest` prompt in [`src/Ai/prompts/quest.json`](src/Ai/prompts/quest.json)
  contains a new section describing `"simulator_events"` only for the `"evento"` type.
- The `generate_quest` method in [`src/Ai/engine.py`](src/Ai/engine.py) injects this
  section into the prompt only when `quest_type == "evento"`.
- The returned JSON for non-evento quests is unchanged (no `"simulator_events"` key).

**Todo List**
1. In [`src/Ai/prompts/quest.json`](src/Ai/prompts/quest.json), add a new placeholder
   variable `{evento_events_section}` inside the `generate_quest` prompt string,
   placed after the quest type rules block and before the "available actions" block.
2. Define the section text as a clear instruction: when quest type is `"evento"`,
   Bob may optionally add `"simulator_events"` to the JSON with this structure:
   ```json
   "simulator_events": [
     { "type": "income_bonus",   "amount": 2000.0, "description": "Promoção recebida" },
     { "type": "expense_shock",  "amount": 800.0,  "description": "Carro quebrou" }
   ]
   ```
   Each entry has `type` (`"income_bonus"` or `"expense_shock"`), `amount` (positive
   float in R$), and `description` (short narrative label shown to the player).
   The section must also state that for non-evento quests the field must be omitted.
3. In [`src/Ai/engine.py`](src/Ai/engine.py) `generate_quest()`, compute
   `evento_events_section`: a non-empty instruction string when
   `quest_type == "evento"`, empty string otherwise; pass it into `_prompts.format()`.

**Relevant Context**
- [`src/Ai/prompts/quest.json`](src/Ai/prompts/quest.json) — `generate_quest` key,
  the long prompt string that already contains `{quest_type_rules}`, `{quest_type_upper}`,
  etc. Insert `{evento_events_section}` right after `{quest_type_rules}`.
- [`src/Ai/engine.py`](src/Ai/engine.py) lines 814–848 — `_prompts.format()` call;
  add `evento_events_section=...` to the keyword arguments.
- The existing JSON output schema in the prompt already lists the required keys; the
  new section must also add `"simulator_events"` to the JSON schema block
  (marked as optional, only present for `"evento"`).

**Status** — `[x] done`

---

### Sub-Task 2 — Add force-withdraw to Portfolio and engine

**Intent**
The user confirmed that an `expense_shock` should allow cash to go negative (financial
stress). The current `Portfolio.withdraw()` raises a `ValueError` when
`amount > self.cash`. A new `force_withdraw` method is needed that bypasses this guard,
logs the transaction, and lets cash go negative.

**Expected Outcomes**
- [`src/Simulator/portfolio.py`](src/Simulator/portfolio.py) has a new
  `force_withdraw(amount, cycle, note)` method that always deducts `amount` from
  `self.cash` (no guard), logs with `action="force_withdraw"`.
- [`src/Simulator/engine.py`](src/Simulator/engine.py) has a wrapper
  `apply_event(portfolio, event_type, amount, note)` that calls `deposit()` for
  `"income_bonus"` and `force_withdraw()` for `"expense_shock"`.

**Todo List**
1. In [`src/Simulator/portfolio.py`](src/Simulator/portfolio.py), add
   `force_withdraw(amount, cycle, note)` after `withdraw()`. No cash guard; just
   `self.cash -= amount` and `self._log(cycle, "force_withdraw", amount, note=note)`.
2. In [`src/Simulator/engine.py`](src/Simulator/engine.py), add `apply_event()`
   that maps event type strings to the correct portfolio method.

**Relevant Context**
- [`src/Simulator/portfolio.py`](src/Simulator/portfolio.py) lines 196–200 — existing
  `withdraw()` for reference.
- [`src/Simulator/engine.py`](src/Simulator/engine.py) lines 130–131 — `deposit()`
  wrapper pattern to follow for `apply_event()`.
- The `_log` method signature: `_log(cycle, action, amount, *, ticker=None, note=None, ...)`.

**Status** — `[x] done`

---

### Sub-Task 3 — Apply simulator events at quest start

**Intent**
When the player presses **Start** on QuestGeneratedPage, the `on_start()` callback in
`main.py` should detect if the active quest is of type `"evento"` and has
`"simulator_events"`, then apply each event through the engine before transitioning
to `SIMULATOR_MAIN`.

The applied events are also stored in `self._active_quest` so that `SIMULATOR_MAIN`
can surface them as a banner.

**Expected Outcomes**
- `on_start()` in `main.py` iterates over `quest_data.get("simulator_events", [])` and
  calls `engine.apply_event(portfolio, event["type"], event["amount"], event["description"])`
  for each.
- After applying, `_save_portfolio` is called to persist the cash change.
- A new key `"applied_events"` is set on `self._active_quest` (a list of
  `{"type", "amount", "description"}` dicts) so `SIMULATOR_MAIN` can read it.

**Todo List**
1. In `main.py` `on_start()` (lines 441–446), after capturing
   `_quest_start_snapshot` and `_quest_start_log_len`, add logic:
   - Only run if `quest_data.get("type") == "evento"`.
   - For each entry in `quest_data.get("simulator_events", [])`:
     - Call `self._engine.apply_event(portfolio, entry["type"], entry["amount"], entry["description"])`.
   - If any events were applied, save portfolio state.
   - Copy events list to `self._active_quest["applied_events"]`.
2. Wrap the apply loop in a try/except so a malformed AI response never crashes the
   quest start.

**Relevant Context**
- `main.py` lines 438–458 — `_show_quest` and `on_start()`.
- `main.py` lines 517–534 — `on_invest` shows the pattern for engine calls +
  `_save_portfolio`.
- `self._active_quest` is set by `_generate_quest()` (line 1184) and read by
  `MainPage` via `active_quest=self._active_quest or None` (line 496).

**Status** — `[x] done`

---

### Sub-Task 4 — Display event banner on MainPage

**Intent**
`MainPage` already receives `active_quest` dict. It should check for
`active_quest["applied_events"]` and render a coloured banner below the quest card
listing each event (icon + description + R$ amount).

**Expected Outcomes**
- [`src/Interfaces/mainPage.py`](src/Interfaces/mainPage.py) shows an
  "⚡ Eventos do Mês" banner card when `active_quest.get("applied_events")` is
  non-empty.
- Each event line: `↑ +R$ X.XX — <description>` (green) for `income_bonus` or
  `↓ -R$ X.XX — <description>` (red/orange) for `expense_shock`.
- Banner appears only once (on first entry to `SIMULATOR_MAIN` after quest start).
  Since `active_quest` is the same dict throughout the quest, it stays visible
  every time `MainPage` is rebuilt that cycle.

**Todo List**
1. In [`src/Interfaces/mainPage.py`](src/Interfaces/mainPage.py), add a new private
   method `_build_event_banner(parent, row)`.
2. Check `self._active_quest.get("applied_events", [])`. If non-empty, render a
   `CTkFrame` card with the heading `"⚡  Eventos deste Mês"` and one label per
   event.
3. Call `self._build_event_banner(parent=_s, row=3)` between the quest card (row 3)
   and holdings (row 4) — shift existing row indices accordingly.
4. Add `active_quest` is already passed in — no new constructor parameter needed.

**Relevant Context**
- [`src/Interfaces/mainPage.py`](src/Interfaces/mainPage.py) lines 136–185 —
  `_build_quest_card()` as the structural pattern to follow for the new banner.
- [`src/Interfaces/mainPage.py`](src/Interfaces/mainPage.py) lines 94–98 — row
  layout; inserting a new row between quest card and holdings requires bumping
  `_build_holdings` and action buttons from row 4/5/6 to 5/6/7.

**Status** — `[x] done`

---

## Notes for Implementation

- Sub-Tasks 1 and 2 have no dependencies on each other and can be done in any order.
- Sub-Task 3 depends on Sub-Task 2 (`apply_event` must exist before `on_start` calls it).
- Sub-Task 4 is independent of all others (pure UI change reading from `active_quest`).
- The `"simulator_events"` field in the quest JSON is optional — if the AI omits it
  (e.g., on fallback quest), `on_start` silently skips the apply loop.
- The existing `_save_portfolio` serialization does not need changes — the applied
  events are transient effects already reflected in the saved `cash` value.

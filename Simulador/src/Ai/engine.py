from __future__ import annotations
import json
from .bob import Bob
from .prompt_loader import PromptLoader


class Engine:

    def __init__(self, bob: Bob):
        self._bob = bob
        self._prompts = PromptLoader()

    def initialize_session(
        self,
        name: str,
        incomes: list[dict],
        outcomes: list[dict],
        debts: list[dict],
    ) -> str:
        """
        Sends the user's financial profile to Bob as a system-level prompt.
        This should be called once at session start, before any quest briefing.

        Parameters
        ----------
        name     : user's name
        incomes  : list of dicts, e.g. [{"source": "Salary", "amount": 5000}]
        outcomes : list of dicts, e.g. [{"category": "Rent", "amount": 1500}]
        debts    : list of dicts, e.g. [{"creditor": "Bank", "amount": 20000, "monthly_payment": 400}]

        Returns the raw text response from Bob.
        """
        income_lines = "\n".join(
            f"  - {item.get('source', 'Unknown')}: R$ {item.get('amount', 0):.2f}"
            for item in incomes
        ) or "  (nenhuma informada)"
        outcome_lines = "\n".join(
            f"  - {item.get('category', 'Unknown')}: R$ {item.get('amount', 0):.2f}"
            for item in outcomes
        ) or "  (nenhuma informada)"
        debt_lines = "\n".join(
            f"  - {item.get('creditor', 'Unknown')}: total R$ {item.get('amount', 0):.2f}"
            f", parcela R$ {item.get('monthly_payment', 0):.2f}/mês"
            for item in debts
        ) or "  (nenhuma informada)"

        total_income = sum(item.get("amount", 0) for item in incomes)
        total_outcome = sum(item.get("amount", 0) for item in outcomes)
        total_debt_payment = sum(item.get("monthly_payment", 0) for item in debts)
        net = total_income - total_outcome - total_debt_payment

        prompt = self._prompts.format(
            "session", "initialize_session",
            name=name,
            total_income=total_income,
            income_lines=income_lines,
            total_outcome=total_outcome,
            outcome_lines=outcome_lines,
            total_debt_payment=total_debt_payment,
            debt_lines=debt_lines,
            net=net,
        )
        return self._bob.send_prompt(prompt)

    def send_simulator_context(self, context: dict) -> str:
        """
        Sends the current simulator state to Bob as a cycle briefing prompt.
        Should be called once per cycle, after advance_cycle(), before the
        player's decision window opens.

        The `context` dict is the output of SimulatorEngine.snapshot() merged
        with SimulatorEngine.market_snapshot(), or any compatible structure.

        Expected top-level keys (all optional — missing ones are skipped):
          cycle             : int
          cash              : float
          net_worth         : float
          allocation        : {cash_pct, fixed_pct, stocks_pct}
          fixed_positions   : list of position snapshots
          stock_positions   : list of position snapshots
          emergency_fund    : {liquid_assets, target, completion_pct, adequate}
          goal_progress     : {current_net_worth, goal_amount, goal, completion_pct}
          market            : {selic_annual_pct, inflation_annual_pct, cycle, ...}
          stocks            : {TICKER: {price, trend, ...}, ...}
          fixed_products    : {key: {label, description, rate_param, ...}, ...}

        Returns the raw text response from Bob.
        """
        cycle = context.get("cycle", "?")

        # --- Market indicators -------------------------------------------
        market = context.get("market", {})
        selic = market.get("selic_annual_pct", "?")
        inflation = market.get("inflation_annual_pct", "?")

        market_block = (
            f"  SELIC: {selic}% a.a.  |  Inflação estimada: {inflation}% a.a."
            if market else "  (dados de mercado não disponíveis)"
        )

        # --- Portfolio summary -------------------------------------------
        cash = context.get("cash")
        net_worth = context.get("net_worth")
        alloc = context.get("allocation", {})

        portfolio_lines = []
        if net_worth is not None:
            portfolio_lines.append(f"  Patrimônio líquido total : R$ {net_worth:.2f}")
        if cash is not None:
            portfolio_lines.append(f"  Caixa disponível         : R$ {cash:.2f}")
        if alloc:
            portfolio_lines.append(
                f"  Alocação — Caixa: {alloc.get('cash_pct', 0):.1f}%  "
                f"| Renda Fixa: {alloc.get('fixed_pct', 0):.1f}%  "
                f"| Ações: {alloc.get('stocks_pct', 0):.1f}%"
            )

        # --- Fixed income positions --------------------------------------
        fixed_positions = context.get("fixed_positions", [])
        if fixed_positions:
            portfolio_lines.append("\n  Posições de Renda Fixa:")
            for p in fixed_positions:
                portfolio_lines.append(
                    f"    • {p.get('label', 'N/A')}  "
                    f"principal R$ {p.get('principal', 0):.2f}  "
                    f"→ valor atual R$ {p.get('current_value', p.get('principal', 0)):.2f}  "
                    f"(vence em {p.get('months_remaining', '?')} meses)"
                )

        # --- Stock positions ---------------------------------------------
        stock_positions = context.get("stock_positions", [])
        if stock_positions:
            portfolio_lines.append("\n  Posições de Renda Variável:")
            for p in stock_positions:
                gain = p.get("unrealized_gain_pct", 0)
                sign = "+" if gain >= 0 else ""
                portfolio_lines.append(
                    f"    • {p.get('ticker', 'N/A')}  "
                    f"{p.get('shares', 0):.4f} cotas @ R$ {p.get('current_price', 0):.2f}  "
                    f"→ R$ {p.get('current_value', 0):.2f}  "
                    f"({sign}{gain:.1f}% vs preço médio)"
                )

        portfolio_block = "\n".join(portfolio_lines) or "  (portfólio vazio)"

        # --- Emergency fund & goal ---------------------------------------
        ef = context.get("emergency_fund", {})
        goal = context.get("goal_progress", {})

        indicators_lines = []
        if ef:
            status = "✅ adequada" if ef.get("adequate") else "⚠️ insuficiente"
            indicators_lines.append(
                f"  Reserva de emergência: R$ {ef.get('liquid_assets', 0):.2f} "
                f"/ R$ {ef.get('target', 0):.2f}  ({ef.get('completion_pct', 0):.0f}%)  [{status}]"
            )
        if goal:
            indicators_lines.append(
                f"  Meta '{goal.get('goal', '?')}': "
                f"R$ {goal.get('current_net_worth', 0):.2f} "
                f"/ R$ {goal.get('goal_amount', 0):.2f}  "
                f"({goal.get('completion_pct', 0):.1f}%)"
            )
        indicators_block = "\n".join(indicators_lines) or "  (sem indicadores)"

        # --- Available stocks in the market ------------------------------
        stocks_market = context.get("stocks", {})
        stocks_lines = []
        for ticker, s in stocks_market.items():
            trend_label = s.get("trend", "?")
            stocks_lines.append(
                f"    {ticker:<8} R$ {s.get('price', 0):>8.2f}   trend: {trend_label}"
            )
        stocks_block = "\n".join(stocks_lines) or "  (nenhuma ação disponível)"

        # --- Available fixed income products -----------------------------
        fixed_products = context.get("fixed_products", {})
        products_lines = []
        for key, p in fixed_products.items():
            products_lines.append(
                f"    • {p.get('label', key)}: {p.get('description', '')}  "
                f"(mín. R$ {p.get('min_investment', 0):.0f}, "
                f"prazo {p.get('maturity_months', '?')} meses)"
            )
        products_block = "\n".join(products_lines) or "  (nenhum produto disponível)"

        prompt = self._prompts.format(
            "session", "send_simulator_context",
            cycle=cycle,
            market_block=market_block,
            portfolio_block=portfolio_block,
            indicators_block=indicators_block,
            stocks_block=stocks_block,
            products_block=products_block,
        )
        return self._bob.send_prompt(prompt)

    def send_player_actions(self, actions: list[dict], cycle: int | None = None) -> str:
        """
        Sends the list of actions taken by the user during a cycle to Bob,
        so it can use them in the debriefing judgment.

        Should be called at the end of the player's decision window, before
        requesting the debriefing.

        Each action dict is one entry from Portfolio.transaction_log:
          {"cycle": int, "action": str, "amount": float, ...extra fields}

        Supported action types and their extra fields:
          deposit       : note
          withdraw      : note
          buy_fixed     : ticker (product label)
          redeem_fixed  : ticker (product label)
          buy_stock     : ticker, shares, price
          sell_stock    : ticker, shares, price

        Parameters
        ----------
        actions : list of transaction log dicts (Portfolio.transaction_log)
        cycle   : cycle number for display; inferred from actions if omitted

        Returns the raw text response from Bob.
        """
        if not actions:
            return self._bob.send_prompt(
                self._prompts.get_template("session", "send_player_actions_empty")
            )

        display_cycle = cycle if cycle is not None else actions[0].get("cycle", "?")

        _action_labels = {
            "deposit":      "Depósito em caixa",
            "withdraw":     "Saque do caixa",
            "buy_fixed":    "Compra de Renda Fixa",
            "redeem_fixed": "Resgate de Renda Fixa",
            "buy_stock":    "Compra de Ação",
            "sell_stock":   "Venda de Ação",
        }

        lines = []
        for i, entry in enumerate(actions, start=1):
            action = entry.get("action", "unknown")
            amount = entry.get("amount", 0.0)
            label  = _action_labels.get(action, action)

            detail_parts = [f"R$ {amount:.2f}"]

            ticker = entry.get("ticker")
            if ticker:
                detail_parts.append(f"ativo: {ticker}")

            shares = entry.get("shares")
            if shares is not None:
                detail_parts.append(f"{shares:.4f} cotas")

            price = entry.get("price")
            if price is not None:
                detail_parts.append(f"@ R$ {price:.2f}/cota")

            note = entry.get("note")
            if note:
                detail_parts.append(f"obs: {note}")

            lines.append(f"  {i:>2}. [{label}]  {' | '.join(detail_parts)}")

        actions_block = "\n".join(lines)

        prompt = self._prompts.format(
            "session", "send_player_actions",
            display_cycle=display_cycle,
            action_count=len(actions),
            actions_block=actions_block,
        )
        return self._bob.send_prompt(prompt)

    def send_quest_context(self, quest: dict, cycles_played: int = 1) -> str:
        """
        Primes Bob with the full quest that was assigned to the user so it has
        complete context when asked to evaluate performance.

        Should be called after initialize_session() and send_simulator_context(),
        and before analyze_quest_performance().

        Parameters
        ----------
        quest         : the active quest dict (title, type, objective, etc.)
        cycles_played : how many cycles the quest spanned
        """
        q_type = quest.get("type", "acumulação")
        q_type_label = {
            "acumulação":    "Acumulação  (maximizar lucro, minimizar risco)",
            "sobrevivência": "Sobrevivência  (minimizar perdas)",
            "evento":        "Evento especial  (reação a uma situação imprevista)",
        }.get(q_type.lower(), q_type)

        # Build an optional block describing simulator events for "evento" quests
        applied_events = quest.get("applied_events", [])
        if applied_events:
            ev_lines = []
            for ev in applied_events:
                ev_type = ev.get("type", "")
                amount  = ev.get("amount", 0.0)
                desc    = ev.get("description", "Evento")
                if ev_type == "income_bonus":
                    ev_lines.append(f"    ↑ +R$ {amount:,.2f}  — {desc}  (depósito extra aplicado ao caixa)")
                else:
                    ev_lines.append(f"    ↓ -R$ {amount:,.2f}  — {desc}  (dedução forçada; caixa pode ter ficado negativo)")
            q_events_block = (
                "\n\nEVENTOS DO SIMULADOR APLICADOS AO INICIAR A QUEST:\n"
                "  ATENÇÃO: estes eventos afetaram o caixa do jogador AUTOMATICAMENTE ao clicar em Iniciar.\n"
                "  O jogador NÃO escolheu esses eventos — eles fazem parte do cenário.\n"
                "  Avalie a REAÇÃO do jogador a estes eventos, não os eventos em si.\n"
                + "\n".join(ev_lines)
            )
        else:
            q_events_block = ""

        prompt = self._prompts.format(
            "session", "send_quest_context",
            q_title=quest.get("title", "Quest"),
            q_type_label=q_type_label,
            q_objective=quest.get("objective", ""),
            q_victory=quest.get("victory_condition", ""),
            q_defeat=quest.get("defeat_condition", ""),
            q_context=quest.get("context", ""),
            q_tip=quest.get("initial_tip", ""),
            q_cycles=cycles_played,
            q_events_block=q_events_block,
        )
        return self._bob.send_prompt(prompt)

    def send_debriefing_request(
        self,
        quest_type: str,
        quest_objective: str,
        objective_achieved: float,
        cycle_result: dict,
    ) -> str:
        """
        Triggers Bob's debriefing judgment for the current cycle.

        This must be called AFTER send_simulator_context() and
        send_player_actions() have already been sent in the same session,
        as the judgment is built on top of that accumulated context.

        Parameters
        ----------
        quest_type        : "acumulação" | "sobrevivência" | "evento"
        quest_objective   : the explicit objective text shown to the user at
                            the start of the cycle (e.g. "Acumule R$ 500 em
                            rendimentos sem investir em renda variável")
        objective_achieved: 0.0–1.0 completion ratio.
                            ≥ 0.75 → achieved, ≥ 0.33 → partial, < 0.33 → failed.
        cycle_result      : dict from SimulatorEngine.advance_cycle() converted
                            to dict, or any structure with the keys below.

        Expected cycle_result keys (all optional — missing ones are skipped):
          cycle             : int
          market_events     : list[str]   — narrative events that happened
          stock_events      : list[str]   — individual stock movements
          portfolio_summaries: dict       — {user_id: {cycle, fixed_earnings}}

        Returns the raw text response from Bob (the full debriefing).
        """
        quest_type_label = {
            "acumulação":  "Acumulação  (maximizar lucro, minimizar risco)",
            "sobrevivência": "Sobrevivência  (minimizar perdas)",
            "evento":      "Evento especial  (investimento específico requerido)",
        }.get(quest_type.lower(), quest_type)

        pct = round(objective_achieved * 100)
        if objective_achieved >= 0.75:
            objective_status = f"✅ OBJETIVO CUMPRIDO  ({pct}%)"
        elif objective_achieved >= 0.33:
            objective_status = f"⚡ OBJETIVO PARCIALMENTE CUMPRIDO  ({pct}%)"
        else:
            objective_status = f"❌ OBJETIVO NÃO CUMPRIDO  ({pct}%)"

        market_events = cycle_result.get("market_events", [])
        stock_events  = cycle_result.get("stock_events", [])
        cycle_num     = cycle_result.get("cycle", "?")

        events_lines = []
        if market_events:
            events_lines.append("  Eventos de mercado:")
            events_lines.extend(f"    • {e}" for e in market_events)
        if stock_events:
            events_lines.append("  Movimentações de ações:")
            events_lines.extend(f"    • {e}" for e in stock_events)
        events_block = "\n".join(events_lines) or "  (sem eventos registrados)"

        summaries = cycle_result.get("portfolio_summaries", {})
        earnings_lines = []
        for summary in summaries.values():
            fixed_earnings = summary.get("fixed_earnings", 0.0)
            earnings_lines.append(
                f"  Rendimentos de renda fixa no ciclo: R$ {fixed_earnings:.2f}"
            )
        earnings_block = "\n".join(earnings_lines) or "  (sem rendimentos registrados)"

        prompt = self._prompts.format(
            "session", "send_debriefing_request",
            cycle_num=cycle_num,
            quest_type_label=quest_type_label,
            quest_objective=quest_objective,
            objective_status=objective_status,
            events_block=events_block,
            earnings_block=earnings_block,
            quest_type=quest_type,
        )
        return self._bob.send_prompt(prompt)

    def generate_study_content(
        self,
        user_profile: dict,
        simulator_performance: dict,
        library_summary: dict,
        requested_topic: str | None = None,
    ) -> str:
        """
        Asks Bob to research, adapt and generate study content for the user.

        The response is a JSON string with the following structure (Bob is
        instructed to return ONLY valid JSON, no surrounding text):

        {
          "topic": str,
          "source_text": str,       // technical / original content
          "adapted_text": str,      // simplified version for the user's level
          "quiz": [
            {
              "question": str,
              "options": [str, str, str, str],   // exactly 4 options
              "correct_index": int,              // 0-based
              "explanation": str
            },
            ...                                  // 3 to 5 questions
          ]
        }

        Parameters
        ----------
        user_profile         : same shape as generate_quest()'s user_profile
        simulator_performance: {
              "avg_score": float,        // 0-100, average across quests
              "completed_quests": int,
              "main_weakness": str,      // topic where user struggles most
              "last_quest_topics": list[str],  // topics from recent quests
            }
        library_summary      : output of StudyLibrary.mastery_summary()
        requested_topic      : if the user explicitly requested a topic, pass it
                               here; otherwise Bob chooses the most relevant one.

        Returns the raw text response from Bob (expected to be valid JSON).
        """
        name            = user_profile.get("name", "Usuário")
        knowledge_level = user_profile.get("knowledge_level", "iniciante")
        risk_profile    = user_profile.get("risk_profile", "moderado")
        goal            = user_profile.get("goal", "não definido")

        avg_score        = simulator_performance.get("avg_score", 0.0)
        completed_quests = simulator_performance.get("completed_quests", 0)
        main_weakness    = simulator_performance.get("main_weakness", "não identificada")
        last_topics      = simulator_performance.get("last_quest_topics", [])

        topics_covered   = library_summary.get("topics_covered", [])
        mastered_count   = library_summary.get("mastered", 0)
        unmastered       = library_summary.get("unmastered", 0)
        best_scores      = library_summary.get("best_quiz_scores", {})

        topics_covered_block = (
            "\n".join(f"  - {t}" for t in topics_covered)
            if topics_covered else "  (nenhum ainda)"
        )
        best_scores_block = (
            "\n".join(f"  - {t}: {s}/100" for t, s in best_scores.items() if s is not None)
            if best_scores else "  (nenhum quiz realizado)"
        )

        topic_instruction = (
            f'O usuário pediu explicitamente pelo tema: "{requested_topic}". '
            "Gere conteúdo sobre este tema independentemente do que já foi coberto."
            if requested_topic
            else
            "Escolha o tema mais relevante para este usuário com base no contexto abaixo. "
            "Priorize temas que: (1) se relacionam diretamente com a fraqueza identificada "
            "no simulador, (2) ainda não foram cobertos na biblioteca, ou (3) tiveram "
            "score de quiz baixo (abaixo de 70)."
        )

        prompt = self._prompts.format(
            "study", "generate_study_content",
            name=name,
            knowledge_level=knowledge_level,
            risk_profile=risk_profile,
            goal=goal,
            avg_score=avg_score,
            completed_quests=completed_quests,
            main_weakness=main_weakness,
            last_topics_line=", ".join(last_topics) if last_topics else "(nenhuma)",
            mastered_count=mastered_count,
            unmastered=unmastered,
            topics_covered_block=topics_covered_block,
            best_scores_block=best_scores_block,
            topic_instruction=topic_instruction,
        )
        return self._bob.send_prompt(prompt)

    def evaluate_study_mastery(
        self,
        topic: str,
        quiz_results: list[dict],
        simulator_performance: dict,
        knowledge_level: str = "iniciante",
    ) -> str:
        """
        Asks Bob to evaluate whether the user has mastered a study topic,
        based on quiz performance and simulator behavior.

        The response is a JSON string (Bob is instructed to return ONLY JSON):

        {
          "mastered": bool,
          "reason": str,          // 1-2 sentence explanation
          "recommendation": str   // what to study or practice next
        }

        Parameters
        ----------
        topic               : the topic being evaluated
        quiz_results        : list of QuizResult dicts for this topic:
                              [{"cycle": int, "score": int, "correct": int, "total": int}, ...]
        simulator_performance: {
              "avg_score": float,
              "completed_quests": int,
              "main_weakness": str,
              "topic_related_quests": int,  // quests that touched this topic
            }
        knowledge_level     : user's declared level

        Returns the raw text response from Bob (expected to be valid JSON).
        """
        avg_score      = simulator_performance.get("avg_score", 0.0)
        main_weakness  = simulator_performance.get("main_weakness", "não identificada")
        related_quests = simulator_performance.get("topic_related_quests", 0)

        if quiz_results:
            best_score  = max(r.get("score", 0) for r in quiz_results)
            last_score  = quiz_results[-1].get("score", 0)
            attempts    = len(quiz_results)
            quiz_block  = "\n".join(
                f"  Tentativa {i+1} (ciclo {r.get('cycle','?')}): "
                f"{r.get('correct','?')}/{r.get('total','?')} corretas — {r.get('score', 0)}/100"
                for i, r in enumerate(quiz_results)
            )
        else:
            best_score = last_score = attempts = 0
            quiz_block = "  (nenhum quiz realizado ainda)"

        prompt = self._prompts.format(
            "study", "evaluate_study_mastery",
            topic=topic,
            knowledge_level=knowledge_level,
            quiz_block=quiz_block,
            best_score=best_score,
            last_score=last_score,
            attempts=attempts,
            avg_score=avg_score,
            main_weakness=main_weakness,
            related_quests=related_quests,
        )
        return self._bob.send_prompt(prompt)

    def analyze_quest_performance(
        self,
        quest: dict,
        actions: list[dict],
        portfolio_snapshot: dict,
        current_profile: dict,
        inference_history: list[dict],
    ) -> str:
        """
        Evaluates the user's quest performance and infers whether their
        behavioural profile (risk tolerance, knowledge level) should be updated.

        Must be called after the quest cycle closes, with the full list of
        actions taken and the final portfolio snapshot.

        Parameters
        ----------
        quest              : the active quest dict, e.g.:
                             {
                               "type": str,          # "acumulação"|"sobrevivência"|"evento"
                               "title": str,
                               "objective": str,
                               "victory_condition": str,
                               "defeat_condition": str,
                               "objective_achieved": float,   # kept for context; AI determines objective_score
                               "cycles_played": int,
                             }
        actions            : list of Portfolio.transaction_log dicts for this quest
        portfolio_snapshot : output of SimulatorEngine.snapshot()
        current_profile    : {
                               "risk_profile": str,
                               "knowledge_level": str,
                               "goal": str,
                               "monthly_surplus": float,
                             }
        inference_history  : list of past ProfileInferenceEntry dicts (most recent last),
                             used to give the agent continuity across quests

        Returns the raw text response from Bob. Expected to be valid JSON:

        {
          "score": int,                  // 0–100
          "main_weakness": str,          // e.g. "diversificação", "liquidez"
          "inferred_risk": str,          // "conservador"|"moderado"|"arrojado"
          "inferred_level": str,         // "iniciante"|"intermediário"|"avançado"
          "reasoning": str,              // 2-3 sentences justifying the inference
          "summary": str,                // short feedback shown to user on debriefing
          "quest_tip": str               // one educational tip for next quest
        }
        """
        # ── Quest context ────────────────────────────────────────────────────
        q_type      = quest.get("type", "acumulação")
        q_title     = quest.get("title", "Quest")
        q_objective = quest.get("objective", "")
        q_victory   = quest.get("victory_condition", "")
        q_defeat    = quest.get("defeat_condition", "")
        q_cycles    = quest.get("cycles_played", 1)

        # ── Actions summary — grouped by cycle with temporal labels ──────────
        _labels = {
            "deposit":      "Depósito",
            "withdraw":     "Saque",
            "buy_fixed":    "Compra Renda Fixa",
            "redeem_fixed": "Resgate Renda Fixa",
            "buy_stock":    "Compra de Ação",
            "sell_stock":   "Venda de Ação",
        }

        from collections import defaultdict
        actions_by_cycle: dict = defaultdict(list)
        for a in actions:
            actions_by_cycle[a.get("cycle", 0)].append(a)

        current_cycle = portfolio_snapshot.get("cycle", max(actions_by_cycle.keys(), default=0))
        sorted_cycles = sorted(actions_by_cycle.keys())

        cycle_blocks = []
        for cyc in sorted_cycles:
            delta = current_cycle - cyc
            if delta == 0:
                temporal_label = f"★ MÊS ATUAL (ciclo {cyc}) — DECISÕES NOVAS DO USUÁRIO"
                header_note    = "    ↳ Estas são as decisões REAIS e RECENTES que devem ser avaliadas."
            elif delta == 1:
                temporal_label = f"  MÊS ANTERIOR (ciclo {cyc}) — HISTÓRICO"
                header_note    = "    ↳ Histórico do mês passado, para contexto comparativo apenas."
            else:
                temporal_label = f"  MÊS {cyc} (há {delta} meses) — HISTÓRICO"
                header_note    = "    ↳ Histórico mais antigo, para análise de tendência apenas."

            cycle_action_lines = []
            for i, a in enumerate(actions_by_cycle[cyc], 1):
                lbl    = _labels.get(a.get("action", ""), a.get("action", ""))
                amount = a.get("amount", 0.0)
                extra  = ""
                if a.get("ticker"):
                    extra += f" | ativo: {a['ticker']}"
                if a.get("shares") is not None:
                    extra += f" | {a['shares']:.4f} cotas"
                if a.get("price") is not None:
                    extra += f" @ R$ {a['price']:.2f}"
                cycle_action_lines.append(f"    {i:>2}. [{lbl}]  R$ {amount:.2f}{extra}")

            cycle_blocks.append(
                f"  {temporal_label}\n"
                f"{header_note}\n"
                + "\n".join(cycle_action_lines)
            )

        actions_block = (
            "\n\n".join(cycle_blocks)
            if cycle_blocks
            else "  (nenhuma ação realizada)"
        )

        # ── Portfolio final ──────────────────────────────────────────────────
        nw     = portfolio_snapshot.get("net_worth", 0.0)
        cash   = portfolio_snapshot.get("cash", 0.0)
        alloc  = portfolio_snapshot.get("allocation", {})
        ef     = portfolio_snapshot.get("emergency_fund", {})
        goal_p = portfolio_snapshot.get("goal_progress", {})
        market = portfolio_snapshot.get("market", {})

        portfolio_block = (
            f"  Patrimônio líquido : R$ {nw:.2f}\n"
            f"  Caixa              : R$ {cash:.2f}\n"
            f"  Alocação — Caixa: {alloc.get('cash_pct', 0):.1f}%  "
            f"| Renda Fixa: {alloc.get('fixed_pct', 0):.1f}%  "
            f"| Ações: {alloc.get('stocks_pct', 0):.1f}%\n"
            f"  Reserva de emergência: {ef.get('completion_pct', 0):.0f}% da meta\n"
            f"  Meta '{goal_p.get('goal', '?')}': {goal_p.get('completion_pct', 0):.1f}%\n"
            f"  SELIC: {market.get('selic_annual_pct', '?')}% a.a."
        )

        # ── Current profile ──────────────────────────────────────────────────
        c_risk    = current_profile.get("risk_profile", "moderado")
        c_level   = current_profile.get("knowledge_level", "iniciante")
        c_goal    = current_profile.get("goal", "não definido")
        c_surplus = current_profile.get("monthly_surplus", 0.0)

        # ── Inference history ────────────────────────────────────────────────
        if inference_history:
            history_lines = []
            for h in inference_history[-5:]:
                applied = "aplicada" if h.get("applied") else "não aplicada"
                history_lines.append(
                    f"  [ciclo {h.get('cycle', '?')}] score {h.get('score', '?')}/100  "
                    f"risco: {h.get('inferred_risk', '?')}  "
                    f"nível: {h.get('inferred_level', '?')}  "
                    f"fraqueza: {h.get('main_weakness', '?')}  [{applied}]"
                )
            history_block = "\n".join(history_lines)
        else:
            history_block = "  (primeira quest — sem histórico anterior)"

        prompt = self._prompts.format(
            "quest", "analyze_quest_performance",
            q_title=q_title,
            q_type=q_type,
            q_objective=q_objective,
            q_victory=q_victory,
            q_defeat=q_defeat,
            q_cycles=q_cycles,
            actions_block=actions_block,
            portfolio_block=portfolio_block,
            c_risk=c_risk,
            c_level=c_level,
            c_goal=c_goal,
            c_surplus=c_surplus,
            history_block=history_block,
        )
        return self._bob.send_prompt(prompt)

    def generate_quest(
        self,
        quest_type: str,
        user_profile: dict,
        learning_context: dict,
    ) -> str:
        """
        Asks Bob to generate a quest for the upcoming cycle.

        Parameters
        ----------
        quest_type       : "acumulação" | "sobrevivência" | "evento"
        user_profile     : {
                             "name": str,
                             "monthly_income": float,
                             "monthly_expenses": float,
                             "monthly_surplus": float,
                             "risk_profile": str,      # declared at onboarding
                             "knowledge_level": str,   # declared at onboarding
                             "goal": str,
                             "goal_amount": float,
                             "goal_deadline_months": int,
                           }
        learning_context : {
                             "last_score": int | None,
                             "completed_quests": int,
                             "main_weakness": str,
                             "last_quest_type": str,
                             "inferred_risk": str,          # AI-inferred, may differ from declared
                             "inferred_level": str,         # AI-inferred, may differ from declared
                             "recent_scores": list[int],    # last ≤5 quest scores
                             "mastered_topics": list[str],  # topics the user has already mastered
                             "portfolio_allocation": dict,  # {cash_pct, fixed_pct, stocks_pct}
                             "current_net_worth": float,
                           }

        Returns the raw text response from Bob. Expected to be valid JSON:

        {
          "title": str,
          "context": str,
          "objective": str,
          "victory_condition": str,
          "defeat_condition": str,
          "initial_tip": str
        }
        """
        quest_type_rules = {
            "acumulação":    "O objetivo é acumular o máximo de lucro minimizando riscos. "
                             "O usuário vence se superar uma meta de rendimento definida na quest.",
            "sobrevivência": "O objetivo é reduzir perdas ao máximo. "
                             "O usuário vence se mantiver o patrimônio acima de um limite definido na quest.",
            "evento":        "Uma situação especial ocorre este mês (ex: aumento de salário, perda de um bem, "
                             "oportunidade de investimento específico). O usuário deve reagir a este evento "
                             "com uma decisão financeira concreta.",
        }.get(quest_type.lower(), quest_type)

        # Only inject the simulator_events instruction for "evento" quests.
        if quest_type.lower() == "evento":
            evento_events_section = (
                "\nEVENTOS DO SIMULADOR (EXCLUSIVO PARA TIPO EVENTO):\n"
                "Como esta é uma quest do tipo EVENTO, você DEVE incluir o campo \"simulator_events\"\n"
                "no JSON de resposta. Defina 1 ou 2 eventos de caixa que ocorrem automaticamente\n"
                "quando o jogador inicia a quest:\n"
                "  • \"income_bonus\"  — depósito extra no caixa (ex: bônus, herança, freelance)\n"
                "  • \"expense_shock\" — dedução do caixa (ex: carro quebrou, despesa médica)\n"
                "Os valores devem ser proporcionais à renda mensal do jogador.\n"
                "A narrativa (context) da quest DEVE mencionar esses eventos para que o jogador\n"
                "entenda o que aconteceu ao iniciar a missão.\n"
            )
        else:
            evento_events_section = ""

        name             = user_profile.get("name", "Usuário")
        monthly_income   = user_profile.get("monthly_income", 0.0)
        monthly_expenses = user_profile.get("monthly_expenses", 0.0)
        monthly_surplus  = user_profile.get("monthly_surplus", monthly_income - monthly_expenses)
        goal             = user_profile.get("goal", "não definido")
        goal_amount      = user_profile.get("goal_amount", 0.0)
        goal_deadline    = user_profile.get("goal_deadline_months", 0)

        last_score       = learning_context.get("last_score")
        completed_quests = learning_context.get("completed_quests", 0)
        main_weakness    = learning_context.get("main_weakness", "não identificada")
        last_quest_type  = learning_context.get("last_quest_type", "nenhuma")
        inferred_risk    = learning_context.get("inferred_risk",  user_profile.get("risk_profile",    "moderado"))
        inferred_level   = learning_context.get("inferred_level", user_profile.get("knowledge_level", "iniciante"))
        recent_scores    = learning_context.get("recent_scores", [])
        mastered_topics  = learning_context.get("mastered_topics", [])
        alloc            = learning_context.get("portfolio_allocation", {})
        current_nw       = learning_context.get("current_net_worth", 0.0)
        goal_urgency     = learning_context.get("goal_urgency", {})
        recent_behavior  = learning_context.get("recent_behavior", {})

        # ── score / difficulty line ───────────────────────────────────────────
        if last_score is None:
            score_line      = "Pontuação: (primeira quest)"
            difficulty_hint = "É a primeira quest — use dificuldade introdutória e um objetivo simples e concreto."
        elif last_score >= 75:
            score_line      = f"Pontuação na última quest: {last_score}/100"
            difficulty_hint = "O usuário está se saindo bem — aumente a dificuldade e introduza um conceito novo."
        elif last_score < 50:
            score_line      = f"Pontuação na última quest: {last_score}/100"
            difficulty_hint = "O usuário está com dificuldade — mantenha acessível e reforce a fraqueza principal."
        else:
            score_line      = f"Pontuação na última quest: {last_score}/100"
            difficulty_hint = "Desempenho moderado — mantenha dificuldade similar, foque na fraqueza principal."

        # ── score trend ───────────────────────────────────────────────────────
        if len(recent_scores) >= 2:
            trend = recent_scores[-1] - recent_scores[0]
            if trend > 10:
                trend_line = f"Tendência de melhora nas últimas quests ({', '.join(map(str, recent_scores))})."
            elif trend < -10:
                trend_line = f"Tendência de queda nas últimas quests ({', '.join(map(str, recent_scores))}) — reforce conceitos básicos."
            else:
                trend_line = f"Desempenho estável ({', '.join(map(str, recent_scores))})."
        elif len(recent_scores) == 1:
            trend_line = f"Apenas uma quest concluída (score: {recent_scores[0]})."
        else:
            trend_line = "Nenhuma quest concluída ainda."

        # ── mastered topics line ──────────────────────────────────────────────
        if mastered_topics:
            mastered_line = f"Já dominados (NÃO repetir como tema principal): {', '.join(mastered_topics)}."
        else:
            mastered_line = "Nenhum tema dominado ainda — qualquer foco educativo é válido."

        # ── portfolio context ─────────────────────────────────────────────────
        cash_pct   = alloc.get("cash_pct",   0.0)
        fixed_pct  = alloc.get("fixed_pct",  0.0)
        stocks_pct = alloc.get("stocks_pct", 0.0)
        if current_nw > 0:
            portfolio_line = (
                f"Patrimônio atual: R$ {current_nw:,.2f} | "
                f"Caixa: {cash_pct}% | Renda Fixa: {fixed_pct}% | Renda Variável: {stocks_pct}%"
            )
        else:
            portfolio_line = "Portfólio ainda não iniciado."

        prompt = self._prompts.format(
            "quest", "generate_quest",
            quest_type_upper=quest_type.upper(),
            quest_type_rules=quest_type_rules,
            evento_events_section=evento_events_section,
            monthly_surplus=monthly_surplus,
            name=name,
            inferred_risk=inferred_risk,
            inferred_level=inferred_level,
            declared_risk=user_profile.get("risk_profile"),
            declared_level=user_profile.get("knowledge_level"),
            monthly_income=monthly_income,
            monthly_expenses=monthly_expenses,
            goal=goal,
            goal_amount=goal_amount,
            goal_deadline=goal_deadline,
            portfolio_line=portfolio_line,
            urgency_goal_amount=goal_urgency.get("goal_amount", goal_amount),
            urgency_completion_pct=goal_urgency.get("completion_pct", 0.0),
            urgency_current_nw=goal_urgency.get("current_net_worth", current_nw),
            urgency_months_remaining=goal_urgency.get("months_remaining", goal_deadline),
            urgency_required_saving=goal_urgency.get("required_monthly_saving", 0.0),
            urgency_on_track_label="Sim — ritmo de poupança é suficiente" if goal_urgency.get("on_track") else "Não — usuário precisa poupar mais para atingir a meta no prazo",
            behavior_cycles_analyzed=recent_behavior.get("cycles_analyzed", 0),
            behavior_trade_count=recent_behavior.get("trade_count", 0),
            behavior_cash_hoard_cycles=recent_behavior.get("cash_hoard_cycles", 0),
            behavior_avg_cash_pct=recent_behavior.get("avg_cash_pct", 0.0),
            behavior_dominant_class=recent_behavior.get("dominant_asset_class", "caixa"),
            score_line=score_line,
            trend_line=trend_line,
            completed_quests=completed_quests,
            last_quest_type=last_quest_type,
            main_weakness=main_weakness,
            mastered_line=mastered_line,
            difficulty_hint=difficulty_hint,
        )
        return self._bob.send_prompt(prompt)

from __future__ import annotations
import json
from .bob import Bob


class Engine:

    def __init__(self, bob: Bob):
        self._bob = bob

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
        )
        outcome_lines = "\n".join(
            f"  - {item.get('category', 'Unknown')}: R$ {item.get('amount', 0):.2f}"
            for item in outcomes
        )
        debt_lines = "\n".join(
            f"  - {item.get('creditor', 'Unknown')}: total R$ {item.get('amount', 0):.2f}"
            f", parcela R$ {item.get('monthly_payment', 0):.2f}/mês"
            for item in debts
        )

        total_income = sum(item.get("amount", 0) for item in incomes)
        total_outcome = sum(item.get("amount", 0) for item in outcomes)
        total_debt_payment = sum(item.get("monthly_payment", 0) for item in debts)
        net = total_income - total_outcome - total_debt_payment

        prompt = f"""Você é um assistente educacional de finanças pessoais dentro de um simulador gamificado. Neste ambiente,
cada quest simula a passagem de tempo correspondente a um mês, leve isso em consideração ao gerar a quest.
O usuário a seguir está iniciando uma sessão. Memorize este perfil — ele será a base para todas as suas avaliações, briefings e debriefings desta sessão.

=== PERFIL DO USUÁRIO ===
Nome: {name}

Entradas mensais (total: R$ {total_income:.2f}):
{income_lines or "  (nenhuma informada)"}

Saídas mensais fixas (total: R$ {total_outcome:.2f}):
{outcome_lines or "  (nenhuma informada)"}

Dívidas (parcela total: R$ {total_debt_payment:.2f}/mês):
{debt_lines or "  (nenhuma informada)"}

Saldo livre estimado: R$ {net:.2f}/mês

Com base neste perfil, calibre sua linguagem, nível de risco sugerido e expectativas de desempenho para este usuário.
Aguarde as instruções da próxima etapa (briefing da quest). APENAS ARMAZENE OS DADOS RECEBIDOS, NÃO GERE NENHUMA RESPOSTA SEM SER SOLICITADO."""
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

        prompt = f"""=== ESTADO DO SIMULADOR — CICLO {cycle} ===

INDICADORES DE MERCADO:
{market_block}

PORTFÓLIO DO USUÁRIO:
{portfolio_block}

INDICADORES FINANCEIROS:
{indicators_block}

MERCADO DE AÇÕES (preços atuais):
{stocks_block}

PRODUTOS DE RENDA FIXA DISPONÍVEIS:
{products_block}

---
Com base neste estado, você pode ser consultado como conselheiro enquanto o usuário toma suas decisões de investimento para este ciclo.
Não tome decisões pelo usuário — apenas oriente quando solicitado."""

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
            prompt = (
                "O usuário não realizou nenhuma operação neste ciclo. "
                "Considere isso na sua avaliação de desempenho."
            )
            return self._bob.send_prompt(prompt)

        # Infer cycle from first entry if not given explicitly
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

        prompt = f"""=== AÇÕES DO USUÁRIO — CICLO {display_cycle} ===

O usuário realizou {len(actions)} operação(ões) neste ciclo:

{actions_block}

---
Estas são todas as decisões tomadas pelo usuário neste ciclo.
Guarde-as para o debriefing — avalie a qualidade das escolhas em relação ao contexto de mercado e ao perfil do usuário."""

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

        # --- Cycle events ------------------------------------------------
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

        # --- Portfolio cycle earnings ------------------------------------
        summaries = cycle_result.get("portfolio_summaries", {})
        earnings_lines = []
        for summary in summaries.values():
            fixed_earnings = summary.get("fixed_earnings", 0.0)
            earnings_lines.append(
                f"  Rendimentos de renda fixa no ciclo: R$ {fixed_earnings:.2f}"
            )
        earnings_block = "\n".join(earnings_lines) or "  (sem rendimentos registrados)"

        prompt = f"""=== SOLICITAÇÃO DE DEBRIEFING — CICLO {cycle_num} ===

TIPO DE QUEST: {quest_type_label}
OBJETIVO DA QUEST: {quest_objective}
RESULTADO: {objective_status}

EVENTOS DO CICLO:
{events_block}

RENDIMENTOS DO CICLO:
{earnings_block}

---
Com base em tudo que foi compartilhado nesta sessão — perfil do usuário, estado do simulador, ações realizadas e resultado do ciclo acima — realize o debriefing completo.

Seu debriefing deve obrigatoriamente conter:

1. RESUMO DO DESEMPENHO
   Explique o que o usuário fez bem e o que fez mal, considerando o tipo de quest ({quest_type}).

2. ESTIMATIVA ÓTIMA
   Descreva a estratégia que teria maximizado o resultado neste ciclo dado o contexto de mercado. Seja específico (quais ativos, quanto alocar).

3. QUANTO FICOU NA MESA
   Calcule ou estime a diferença entre o resultado obtido e o resultado ótimo em R$.

4. PONTUAÇÃO  (formato obrigatório)
   Atribua uma pontuação de 0 a 100 considerando:
   - Cumprimento do objetivo da quest (peso maior)
   - Qualidade das decisões de alocação para o perfil do usuário
   - Gestão de risco e reserva de emergência
   Apresente como: PONTUAÇÃO: XX/100

5. ORIENTAÇÃO PARA O PRÓXIMO CICLO
   Uma instrução educativa curta (2–3 frases) baseada no principal erro ou oportunidade perdida."""

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

        prompt = f"""Gere conteúdo educativo de finanças seguindo as instruções abaixo e retorne SOMENTE o JSON solicitado.

=== GERAÇÃO DE CONTEÚDO EDUCATIVO ===

CONTEXTO DO USUÁRIO:
  Nome            : {name}
  Nível           : {knowledge_level}
  Perfil de risco : {risk_profile}
  Objetivo        : {goal}

DESEMPENHO NO SIMULADOR:
  Pontuação média : {avg_score:.1f}/100
  Quests concluídas: {completed_quests}
  Principal fraqueza: {main_weakness}
  Temas das últimas quests: {', '.join(last_topics) if last_topics else '(nenhuma)'}

BIBLIOTECA DE ESTUDO ATUAL:
  Conteúdos dominados : {mastered_count}
  Conteúdos pendentes : {unmastered}
  Temas já cobertos:
{topics_covered_block}
  Melhores scores de quiz por tema:
{best_scores_block}

INSTRUÇÃO DE SELEÇÃO DE TEMA:
{topic_instruction}

---
Você é um especialista em educação financeira. Sua tarefa é:

1. PESQUISAR o tema escolhido com profundidade técnica — inclua conceitos, mecanismos, fórmulas relevantes e exemplos reais do mercado brasileiro.

2. ADAPTAR esse conteúdo para o nível "{knowledge_level}" do usuário — use linguagem acessível, analogias práticas e exemplos conectados ao objetivo "{goal}" do usuário. NÃO omita a substância, apenas torne-a mais digestível.

3. CRIAR um quiz de 4 perguntas de múltipla escolha (4 opções cada) que teste a compreensão real do tema — não apenas memorização.

Retorne SOMENTE o JSON abaixo, sem texto adicional antes ou depois, sem markdown, sem blocos de código:

{{
  "topic": "<nome do tema escolhido>",
  "source_text": "<conteúdo técnico completo, em português, com ao menos 3 parágrafos>",
  "adapted_text": "<versão adaptada e simplificada, em português, com ao menos 3 parágrafos e exemplos práticos>",
  "quiz": [
    {{
      "question": "<pergunta>",
      "options": ["<A>", "<B>", "<C>", "<D>"],
      "correct_index": <0-3>,
      "explanation": "<explicação da resposta correta>"
    }}
  ]
}}"""

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
        avg_score     = simulator_performance.get("avg_score", 0.0)
        main_weakness = simulator_performance.get("main_weakness", "não identificada")
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

        prompt = f"""Avalie o domínio do conteúdo seguindo as instruções abaixo e retorne SOMENTE o JSON solicitado.

=== AVALIAÇÃO DE DOMÍNIO DO CONTEÚDO ===

TEMA AVALIADO: {topic}
NÍVEL DO USUÁRIO: {knowledge_level}

RESULTADOS DE QUIZ SOBRE ESTE TEMA:
{quiz_block}
  Melhor score: {best_score}/100
  Último score: {last_score}/100
  Total de tentativas: {attempts}

DESEMPENHO NO SIMULADOR (contexto geral):
  Pontuação média : {avg_score:.1f}/100
  Principal fraqueza identificada: {main_weakness}
  Quests relacionadas a este tema concluídas: {related_quests}

CRITÉRIOS DE DOMÍNIO SUGERIDOS (use como referência, não como regra rígida):
  - Quiz: score >= 75 em ao menos uma tentativa
  - Simulador: pontuação média >= 60 após quests relacionadas ao tema
  - Consistência: melhora progressiva nos scores de quiz

---
Com base nos dados acima, avalie se o usuário demonstrou domínio suficiente do tema "{topic}" para avançar para conteúdo mais complexo.

Retorne SOMENTE o JSON abaixo, sem texto adicional:

{{
  "mastered": <true ou false>,
  "reason": "<explicação em 1-2 frases do porquê dominado ou não>",
  "recommendation": "<o que o usuário deve estudar ou praticar a seguir>"
}}"""

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

        # Group actions by cycle value
        from collections import defaultdict
        actions_by_cycle: dict = defaultdict(list)
        for a in actions:
            actions_by_cycle[a.get("cycle", 0)].append(a)

        # Build the block with temporal labels per cycle group
        current_cycle = portfolio_snapshot.get("cycle", max(actions_by_cycle.keys(), default=0))
        sorted_cycles = sorted(actions_by_cycle.keys())

        cycle_blocks = []
        for cyc in sorted_cycles:
            # Label the cycle relative to the current one
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
            for h in inference_history[-5:]:   # últimas 5 inferências
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

        prompt = f"""Analise o desempenho da quest seguindo as instruções abaixo e retorne SOMENTE o JSON solicitado.

=== ANÁLISE DE DESEMPENHO DA QUEST ===

QUEST: {q_title}
TIPO: {q_type}
OBJETIVO: {q_objective}
CONDIÇÃO DE VITÓRIA: {q_victory}
CONDIÇÃO DE DERROTA: {q_defeat}
DURAÇÃO: {q_cycles} ciclo(s)

AÇÕES DO USUÁRIO (organizadas por mês):
ATENÇÃO — LEITURA OBRIGATÓRIA ANTES DE AVALIAR:
  • As ações estão agrupadas por mês (ciclo).
  • O grupo marcado com ★ MÊS ATUAL contém as NOVAS DECISÕES do usuário — são estas que devem ser avaliadas.
  • Os grupos "MÊS ANTERIOR" e "MÊS Nº (há X meses)" são HISTÓRICO para contexto comparativo.
    NÃO interprete ações históricas como se tivessem sido realizadas novamente agora.
    Use o histórico apenas para identificar padrões e evolução do comportamento ao longo do tempo.

{actions_block}

ESTADO FINAL DO PORTFÓLIO:
{portfolio_block}

PERFIL DECLARADO ATUAL:
  Perfil de risco     : {c_risk}
  Nível de conhecimento: {c_level}
  Objetivo            : {c_goal}
  Sobra mensal        : R$ {c_surplus:.2f}

HISTÓRICO DE INFERÊNCIAS ANTERIORES:
{history_block}

---
Avalie com base nas NOVAS DECISÕES do mês atual (★). Use o histórico para entender tendências.
Considere:
  - Como o usuário alocou os recursos no mês atual (diversificação, proporção renda fixa/variável)
  - Se respeitou a reserva de emergência
  - Se agiu de forma coerente com o perfil declarado ou demonstrou comportamento diferente
  - Evolução em relação às inferências anteriores e ao histórico de ações (se houver)
  - Em que grau o usuário cumpriu o objetivo da quest (condição de vitória vs derrota) com as ações DO MÊS ATUAL.
    Caso o usuário não cumpra o solicitado, a nota deve ser afetada drasticamente.
Retorne SOMENTE o JSON abaixo, sem texto adicional:

{{
  "score": <0-100, pontuação geral ponderando os três critérios abaixo>,
  "objective_score": <0-100, grau de cumprimento do OBJETIVO específico desta quest. 0-24 = não cumprido, 25-75 = parcial, 76-100 = cumprido>,
  "allocation_score": <0-100, qualidade da alocação do portfólio: diversificação, proporção renda fixa/variável, uso adequado do caixa>,
  "risk_score": <0-100, qualidade da gestão de risco: reserva de emergência, exposição adequada ao risco declarado, proteção do capital>,
  "main_weakness": "<fraqueza principal em 1-3 palavras, ex: diversificacao, gestao_de_risco, liquidez>",
  "inferred_risk": "<conservador|moderado|arrojado>",
  "inferred_level": "<iniciante|intermediario|avancado>",
  "reasoning": "<2-3 frases justificando a inferência com base no comportamento observado>",
  "summary": "<2-3 frases de feedback direto ao usuário sobre o que fez bem e o que pode melhorar>",
  "quest_tip": "<1 dica educativa curta e acionável para a próxima quest>",
  "narrative": "<debriefing completo em 5 seções: 1. RESUMO DO DESEMPENHO — o que o usuário fez bem e mal considerando o tipo de quest; 2. ESTIMATIVA ÓTIMA — a estratégia que teria maximizado o resultado, com ativos e % específicos; 3. QUANTO FICOU NA MESA — diferença estimada em R$ entre resultado obtido e resultado ótimo; 4. PONTUAÇÃO: XX/100 — pontuação exibindo objective_score, allocation_score e risk_score que você gerou neste JSON; 5. ORIENTAÇÃO PARA O PRÓXIMO CICLO — instrução educativa de 2-3 frases baseada no principal erro>"
}}"""

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

        prompt = f"""Gere uma quest de investimentos seguindo as instruções abaixo e retorne SOMENTE o JSON solicitado.

=== GERAÇÃO DE QUEST — TIPO: {quest_type.upper()} ===

REGRAS DO TIPO:
{quest_type_rules}

AÇÕES DISPONÍVEIS — RESTRIÇÃO ABSOLUTA:
O simulador permite APENAS as seguintes ações. A quest DEVE ser totalmente resolvível
usando somente estas ações. É PROIBIDO criar condições que dependam de qualquer outra ação.

  RENDA FIXA (comprar e resgatar posições):
    • Tesouro Selic        — pós-fixado, 100% SELIC, liquidez diária, sem carência
    • Tesouro Prefixado    — taxa fixa 11,5% a.a., carência 24 meses (pode resgatar antes)
    • Tesouro IPCA+        — IPCA + 5,5% a.a., carência 36 meses (pode resgatar antes)
    • CDB Liquidez Diária  — 100% CDI, liquidez diária, sem carência
    • CDB 90 dias          — 105% CDI, carência 3 meses (NÃO pode resgatar antes)
    • CDB 1 ano            — 110% CDI, carência 12 meses (NÃO pode resgatar antes)
    • LCI 6 meses          — 93% CDI, isento de IR, carência 6 meses (NÃO pode resgatar antes)
    • LCA 1 ano            — 95% CDI, isento de IR, carência 12 meses (NÃO pode resgatar antes)

  RENDA VARIÁVEL (comprar e vender cotas):
    • BRCO3 — Banco do Reinos S.A.   (setor: Financeiro, sensível à SELIC)
    • PTRX4 — PetroReinos S.A.       (setor: Energia, influenciada por commodities)
    • MGCO3 — MagiaComércio S.A.     (setor: Consumo, alta volatilidade)
    • GLDX3 — Guildas de Ouro S.A.   (setor: Mineração, hedge em crises)
    • TCNV5 — TecnoVentos S.A.       (setor: Tecnologia, muito volátil)

  CAIXA:
    • O depósito da sobra mensal (R$ {monthly_surplus:,.2f}) é automático — não é uma ação do usuário.
    • Saques NÃO são possíveis.

EXEMPLOS DO QUE É PROIBIDO GERAR:
  ✗ "Contrate um seguro", "Abra uma poupança", "Invista em FIIs", "Diversifique em 5 ativos"
    (FIIs não existem no simulador)
  ✗ Qualquer produto financeiro não listado acima
  ✗ Condições que dependam de eventos externos ao controle do usuário (ex: "espere a SELIC cair")
  ✗ Condições que exijam VENDER renda fixa em carência (ex: CDB 90 dias só pode ser resgatado após 3 meses)

PERFIL DO USUÁRIO:
  Nome                   : {name}
  Perfil de risco inferido (pelo agente, use este): {inferred_risk}
  Nível de conhecimento inferido (pelo agente, use este): {inferred_level}
  (Perfil declarado no onboarding — apenas referência: risco={user_profile.get("risk_profile")}, nível={user_profile.get("knowledge_level")})
  Renda mensal           : R$ {monthly_income:,.2f}
  Gastos fixos mensais   : R$ {monthly_expenses:,.2f}
  Sobra mensal para investir: R$ {monthly_surplus:,.2f}
  Objetivo financeiro    : {goal}
  Meta                   : R$ {goal_amount:,.2f} em {goal_deadline} meses

ESTADO DO PORTFÓLIO:
  {portfolio_line}

CONTEXTO DE META:
  Meta financeira      : {goal_urgency.get("goal_amount", goal_amount):,.2f} R$
  Progresso atual      : {goal_urgency.get("completion_pct", 0.0):.1f}%  (R$ {goal_urgency.get("current_net_worth", current_nw):,.2f} acumulados)
  Meses restantes      : {goal_urgency.get("months_remaining", goal_deadline)}
  Poupança necessária/mês: R$ {goal_urgency.get("required_monthly_saving", 0.0):,.2f}
  Na trilha            : {"Sim — ritmo de poupança é suficiente" if goal_urgency.get("on_track") else "Não — usuário precisa poupar mais para atingir a meta no prazo"}

COMPORTAMENTO RECENTE (últimos {recent_behavior.get("cycles_analyzed", 0)} meses — HISTÓRICO TEMPORAL):
ATENÇÃO: estes dados são um resumo do histórico de comportamento do usuário ao longo dos meses.
  NÃO interprete estes dados como se o usuário tivesse realizado essas ações agora — são padrões acumulados.
  Use o histórico apenas para personalizar o tema e a dificuldade da próxima quest.
  Operações totais no período : {recent_behavior.get("trade_count", 0)}
  Meses com entesouramento    : {recent_behavior.get("cash_hoard_cycles", 0)} (meses em que caixa > 50% do patrimônio)
  % média em caixa no período : {recent_behavior.get("avg_cash_pct", 0.0):.1f}%
  Classe de ativo dominante   : {recent_behavior.get("dominant_asset_class", "caixa")}

HISTÓRICO DE APRENDIZADO:
  {score_line}
  {trend_line}
  Quests concluídas      : {completed_quests}
  Última quest (tipo)    : {last_quest_type}
  Principal fraqueza identificada: {main_weakness}
  {mastered_line}

CALIBRAÇÃO DE DIFICULDADE:
  {difficulty_hint}

---
INSTRUÇÕES:
- Calibre a dificuldade e o foco educativo usando o perfil INFERIDO (não o declarado).
- Direcione o tema educativo da quest à fraqueza principal ({main_weakness}), a menos que ela já esteja nos tópicos dominados.
- Reflita o estado real do portfólio: se o usuário está muito em caixa, incentive aplicação; se está muito concentrado em um ativo, incentive diversificação.
- Defina metas numéricas realistas com base na sobra mensal de R$ {monthly_surplus:,.2f}.
- NÃO repita como tema principal nenhum dos tópicos já dominados.
- Use o CONTEXTO DE META para calibrar o valor objetivo da quest: se o usuário está atrasado (fora da trilha), aumente a urgência e o valor-alvo; se está adiantado, introduza mais complexidade.
- Use o COMPORTAMENTO RECENTE para criar uma narrativa personalizada com base em padrões históricos (ex: entesouramento, concentração, frequência de trades). IMPORTANTE: esses dados refletem comportamentos passados — não ações realizadas agora. Gere uma quest que incentive melhorias em relação a esses padrões.
- ANTES de gerar o JSON, verifique mentalmente: cada condição de vitória e derrota é realizável usando APENAS as ações listadas em "AÇÕES DISPONÍVEIS"? Se não for, reescreva até que seja.
Retorne SOMENTE o JSON abaixo, sem texto adicional, sem markdown, sem comentários:

{{
  "title": "<título narrativo curto e imersivo>",
  "context": "<2-3 frases de cenário com tom narrativo e referência à situação real do usuário>",
  "objective": "<uma frase clara e mensurável com valor em R$ ou % baseado no perfil>",
  "victory_condition": "<critério objetivo em R$ ou % — use a sobra mensal como referência>",
  "defeat_condition": "<o que configura falha — seja explícito e realista>",
  "initial_tip": "<1 dica educativa curta focada na fraqueza '{main_weakness}' do usuário>"
}}"""

        return self._bob.send_prompt(prompt)

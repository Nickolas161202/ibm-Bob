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

        prompt = f"""Você é um assistente educacional de finanças pessoais dentro de um simulador gamificado.
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
Aguarde as instruções da próxima etapa (briefing da quest)."""
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
        objective_achieved: bool,
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
        objective_achieved: whether the user met the quest objective
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

        objective_status = "✅ OBJETIVO CUMPRIDO" if objective_achieved else "❌ OBJETIVO NÃO CUMPRIDO"

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

    def generate_quest(
        self,
        quest_type: str,
        user_profile: dict,
        learning_context: dict,
    ) -> str:
        """
        Asks Bob to generate a quest for the upcoming cycle.

        Should be called after the previous cycle's debriefing, using the
        score and observations from that debriefing to seed difficulty and
        narrative tone.

        Parameters
        ----------
        quest_type       : "acumulação" | "sobrevivência" | "evento"
        user_profile     : dict with the user's financial snapshot, e.g.:
                             {
                               "name": str,
                               "monthly_income": float,
                               "monthly_expenses": float,
                               "monthly_surplus": float,
                               "risk_profile": str,       # "conservador" | "moderado" | "arrojado"
                               "knowledge_level": str,    # "iniciante" | "intermediário" | "avançado"
                               "goal": str,
                               "goal_amount": float,
                               "goal_deadline_months": int,
                             }
        learning_context : dict with the user's progression data, e.g.:
                             {
                               "last_score": int,          # 0–100 from previous debriefing
                               "completed_quests": int,
                               "main_weakness": str,       # e.g. "diversificação"
                               "last_quest_type": str,
                               "unlocked_event": bool,     # True if next quest should be "evento"
                             }

        Returns the raw text response from Bob (the full quest briefing).
        """
        quest_type_rules = {
            "acumulação":    "O objetivo é acumular o máximo de lucro minimizando riscos. "
                             "O usuário vence se superar uma meta de rendimento definida na quest.",
            "sobrevivência": "O objetivo é reduzir perdas ao máximo. "
                             "O usuário vence se mantiver o patrimônio acima de um limite definido na quest.",
            "evento":        "Uma situação especial ocorre este mês (ex: aumento de salário, perda de um bem, "
                             "oportunidade de investimento específico). O usuário deve reagir a este evento "
                             "com uma decisão financeira concreta. Após a quest, gere conteúdo educativo "
                             "sobre o tipo de investimento envolvido.",
        }.get(quest_type.lower(), quest_type)

        # --- User profile block ------------------------------------------
        name             = user_profile.get("name", "Usuário")
        monthly_income   = user_profile.get("monthly_income", 0.0)
        monthly_expenses = user_profile.get("monthly_expenses", 0.0)
        monthly_surplus  = user_profile.get("monthly_surplus", monthly_income - monthly_expenses)
        risk_profile     = user_profile.get("risk_profile", "moderado")
        knowledge_level  = user_profile.get("knowledge_level", "iniciante")
        goal             = user_profile.get("goal", "não definido")
        goal_amount      = user_profile.get("goal_amount", 0.0)
        goal_deadline    = user_profile.get("goal_deadline_months", 0)

        profile_block = f"""\
Usuário       : {name}
Renda mensal  : R$ {monthly_income:.2f}
Gastos fixos  : R$ {monthly_expenses:.2f}
Sobra mensal  : R$ {monthly_surplus:.2f}
Perfil        : {risk_profile}  |  Nível: {knowledge_level}
Meta          : {goal}  (R$ {goal_amount:.2f} em {goal_deadline} meses)"""

        # --- Learning context block --------------------------------------
        last_score       = learning_context.get("last_score")
        completed_quests = learning_context.get("completed_quests", 0)
        main_weakness    = learning_context.get("main_weakness", "não identificada")
        last_quest_type  = learning_context.get("last_quest_type", "nenhuma")
        unlocked_event   = learning_context.get("unlocked_event", False)

        score_line = f"Pontuação anterior : {last_score}/100" if last_score is not None else "Pontuação anterior : (primeira quest)"

        learning_block = f"""\
{score_line}
Quests concluídas  : {completed_quests}
Última quest       : {last_quest_type}
Principal fraqueza : {main_weakness}
Evento desbloqueado: {"sim" if unlocked_event else "não"}"""

        prompt = f"""=== GERAÇÃO DE QUEST — TIPO: {quest_type.upper()} ===

REGRAS DO TIPO DE QUEST:
{quest_type_rules}

PERFIL DO USUÁRIO:
{profile_block}

CONTEXTO DE APRENDIZADO:
{learning_block}

---
Gere a quest deste ciclo seguindo obrigatoriamente o formato abaixo.
Calibre a dificuldade com base na pontuação anterior (pontuação alta → mais desafiador; pontuação baixa → mais acessível).
Use a principal fraqueza do usuário para direcionar o foco educativo da quest.

FORMATO OBRIGATÓRIO DA QUEST:

TÍTULO: (título narrativo curto e imersivo)

CONTEXTO: (2–3 frases descrevendo o cenário do mês com tom narrativo — o que aconteceu na vida financeira do usuário)

OBJETIVO: (uma frase clara e mensurável — o usuário sabe exatamente o que precisa fazer para vencer)

CONDIÇÃO DE VITÓRIA: (critério objetivo, em R$ ou %, que será verificado ao final do ciclo)

CONDIÇÃO DE DERROTA: (o que configura falha — seja explícito)

DICA INICIAL: (uma orientação educativa curta, sem entregar a solução, focada na fraqueza principal do usuário)"""

        return self._bob.send_prompt(prompt)

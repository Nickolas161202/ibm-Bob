"""
main.py
-------
Ponto de entrada da aplicação — State Machine da interface gráfica.

Diagrama de estados (states_ibm.json):

  ┌─────────────┐  Dont have profile  ┌───────────────────┐
  │   Inicial   │────────────────────►│  Criação de Perfil│
  │             │  Already has profile│                   │
  │             │───────────────────┐ └────────┬──────────┘
  └─────────────┘                   │          │ on_submit
                                    │          ▼
                                    │ ┌────────────────────┐
                                    └►│        Hub         │
                                      └──┬──────┬──────┬───┘
                              Missões  │      │      │ Reconfigurar
                                         ▼      │      ▼
                              ┌──────────────┐  │  ┌──────────────────┐
                              │Quest Gerada  │  │  │  Criação Perfil  │
                              └──────┬───────┘  │  └──────────────────┘
                                     ▼          │ Estudos (a implementar)
                           ┌──────────────────────┐
                  ┌───────►│  Simulador Principal  │◄──────┐
                  │        └──┬───────────────┬───┘        │
                  │  back     │ Low Risk      │ High Risk  │ back
                  │           ▼               ▼            │
                  │  ┌──────────────┐  ┌──────────────┐   │
                  └──│  Renda Fixa  │  │ Renda Variável│──┘
                     └──────────────┘  └──────────────┘
                                               │ User Done?
                                               ▼
                                    ┌──────────────────────┐
                                    │   Debriefing Page    │
                                    └──────────┬───────────┘
                                               │
                                               ▼
                                    ┌──────────────────────┐
                                    │      End Month       │
                                    └──────────┬───────────┘
                                               │ (loop)
                                               ▼
                                             Hub
"""

from __future__ import annotations

import os
import sys
from enum import Enum, auto
from typing import Optional

import customtkinter as ctk

# ── path setup ───────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── simulator engine ──────────────────────────────────────────────────────────
from src.Simulator.engine import SimulatorEngine
from src.Simulator.portfolio import InvestorProfile
from src.Simulator.fixed_income import FixedIncomeType, PRODUCTS

# ── study library ─────────────────────────────────────────────────────────────
import json
import uuid
from src.Study.library import StudyLibrary, StudyContent, QuizQuestion

# ── interface pages ───────────────────────────────────────────────────────────
from src.Interfaces.initial import InitialPage
from src.Interfaces.createProfile import CreateProfilePage
from src.Interfaces.questGenerated import QuestGeneratedPage
from src.Interfaces.mainPage import MainPage
from src.Interfaces.lowRiskInvestments import LowRiskInvestmentsPage
from src.Interfaces.highRiskInvestments import HighRiskInvestmentsPage
from src.Interfaces.debriefing import DebriefingPage
from src.Interfaces.endOfMonth import EndOfMonthPage
from src.Interfaces.hub import HubPage
from src.Interfaces.studyPage import StudyPage


# ─────────────────────────────────────────────────────────────────────────────
# State enumeration — mirrors every node in states_ibm.json
# ─────────────────────────────────────────────────────────────────────────────

class AppState(Enum):
    INICIAL              = auto()   # i2zG1y6y6l51
    CREATE_PROFILE       = auto()   # u2zG367~7dvM
    HUB                  = auto()   # menu principal pós-onboarding
    STUDY                = auto()   # biblioteca de estudos
    QUEST_GENERATED      = auto()   # B2zGtmQY~6EB
    SIMULATOR_MAIN       = auto()   # K3zGYcP4SeMW
    LOW_RISK             = auto()   # d4zGHF4CtUvb
    HIGH_RISK            = auto()   # x4zG6X-rLHkF
    DEBRIEFING           = auto()   # p5zGgpEZZiCr
    END_MONTH            = auto()   # F5zGDV1C7XfM


# ─────────────────────────────────────────────────────────────────────────────
# Application — state machine + frame management
# ─────────────────────────────────────────────────────────────────────────────

class App(ctk.CTk):
    """
    Root window that owns the state machine.

    Only one CTkFrame (page) is visible at a time.
    Transitions are driven by callbacks passed into each page.
    """

    def __init__(self):
        super().__init__()
        self.title("Simulador de Investimentos — Reino das Finanças")
        self.geometry("680x560")
        self.resizable(False, False)

        # ── simulator state ───────────────────────────────────────────────────
        self._engine: Optional[SimulatorEngine] = None
        self._profile: Optional[InvestorProfile] = None
        self._last_cycle_result = None   # CycleResult from advance_cycle()

        # ── quest state ───────────────────────────────────────────────────────
        # Active quest data — reset each time a new quest is generated
        self._quest_title: str = ""
        self._quest_description: str = ""
        self._quest_objective: str = ""
        self._quest_type: str = "acumulação"   # "acumulação" | "sobrevivência" | "evento"
        # Net worth at the moment the quest starts, for completion check
        self._quest_start_net_worth: float = 0.0
        # Whether the salary was already deposited for the current simulator session
        self._salary_deposited: bool = False

        # ── study library (one instance per profile, loaded lazily) ───────────
        self._study_library: Optional[StudyLibrary] = None
        # tracks quest scores for mastery evaluation
        self._quest_scores: list[int] = []

        # ── current frame reference (for clean destroy) ───────────────────────
        self._current_frame: Optional[ctk.CTkFrame] = None

        # ── start ─────────────────────────────────────────────────────────────
        self._transition(AppState.INICIAL)

    # ─────────────────────────────────────────────────────────────────────────
    # Core transition method
    # ─────────────────────────────────────────────────────────────────────────

    def _transition(self, state: AppState):
        """Destroy the current page and instantiate the next one."""
        if self._current_frame is not None:
            self._current_frame.destroy()
            self._current_frame = None

        frame = self._build_state(state)
        frame.pack(fill="both", expand=True)
        self._current_frame = frame

    def _build_state(self, state: AppState) -> ctk.CTkFrame:
        """Factory — returns the CTkFrame for the given state."""

        # ── INICIAL ───────────────────────────────────────────────────────────
        if state == AppState.INICIAL:
            def on_next():
                if self._profile is not None:
                    # Already has a profile → go to hub
                    self._transition(AppState.HUB)
                else:
                    # No profile yet → create one
                    self._transition(AppState.CREATE_PROFILE)

            return InitialPage(
                master=self,
                on_next=on_next,
                fg_color="transparent",
            )

        # ── CREATE_PROFILE ────────────────────────────────────────────────────
        if state == AppState.CREATE_PROFILE:
            def on_submit(profile: InvestorProfile):
                self._profile = profile
                self._engine = SimulatorEngine()
                self._engine.create_portfolio(profile, initial_cash=profile.monthly_surplus)
                self._salary_deposited = True   # initial cash counts as first deposit
                self._transition(AppState.HUB)

            return CreateProfilePage(
                master=self,
                on_submit=on_submit,
                fg_color="transparent",
            )

        # ── HUB ───────────────────────────────────────────────────────────────
        if state == AppState.HUB:
            portfolio = self._current_portfolio()
            snap = self._engine.snapshot(portfolio) if self._engine and portfolio else {}

            return HubPage(
                master=self,
                player_name=self._profile.name if self._profile else "Aventureiro",
                cycle=snap.get("cycle", 0),
                net_worth=snap.get("net_worth", 0.0),
                on_missions=lambda: self._start_quest(),
                on_study=lambda: self._transition(AppState.STUDY),
                on_reconfigure=lambda: self._transition(AppState.CREATE_PROFILE),
                fg_color="transparent",
            )

        # ── STUDY ─────────────────────────────────────────────────────────────
        if state == AppState.STUDY:
            lib = self._ensure_study_library()

            def on_request_topic(topic: str):
                self._generate_study_content(requested_topic=topic)
                # Refresh the current StudyPage in place if it is still active
                if (
                    isinstance(self._current_frame, StudyPage)
                    and self._study_library is not None
                ):
                    self._current_frame.refresh_contents(
                        self._study_library.get_all()
                    )

            def on_quiz_completed(content_id: str, correct: int, total: int):
                cycle = (
                    self._engine.market.cycle if self._engine else 0
                )
                lib.record_quiz_result(content_id, correct, cycle)
                # ask the AI to evaluate mastery after each quiz
                self._evaluate_mastery(content_id)
                # Refresh list to reflect updated badges
                if isinstance(self._current_frame, StudyPage):
                    self._current_frame.refresh_contents(lib.get_all())

            return StudyPage(
                master=self,
                contents=lib.get_all(),
                on_back=lambda: self._transition(AppState.HUB),
                on_request_topic=on_request_topic,
                on_quiz_completed=on_quiz_completed,
                fg_color="transparent",
            )

        # ── QUEST_GENERATED ───────────────────────────────────────────────────
        if state == AppState.QUEST_GENERATED:
            def on_start():
                # Record net worth at quest start for completion tracking
                portfolio = self._current_portfolio()
                if self._engine and portfolio:
                    snap = self._engine.snapshot(portfolio)
                    self._quest_start_net_worth = snap.get("net_worth", 0.0)
                self._transition(AppState.SIMULATOR_MAIN)

            return QuestGeneratedPage(
                master=self,
                quest_title=self._quest_title,
                quest_description=self._quest_description,
                quest_objective=self._quest_objective,
                on_start=on_start,
                fg_color="transparent",
            )

        # ── SIMULATOR_MAIN ────────────────────────────────────────────────────
        if state == AppState.SIMULATOR_MAIN:
            # Deposit monthly salary once per simulator session (new cycle)
            if self._engine and self._profile and not self._salary_deposited:
                portfolio = self._current_portfolio()
                if portfolio:
                    self._engine.deposit(
                        portfolio,
                        self._profile.monthly_surplus,
                        note="Salário do mês",
                    )
                self._salary_deposited = True

            portfolio = self._current_portfolio()
            snap = self._engine.snapshot(portfolio) if self._engine and portfolio else {}

            return MainPage(
                master=self,
                player_name=self._profile.name if self._profile else "Aventureiro",
                cash=snap.get("cash", 0.0),
                net_worth=snap.get("net_worth", 0.0),
                cycle=snap.get("cycle", 1),
                on_low_risk=lambda: self._transition(AppState.LOW_RISK),
                on_high_risk=lambda: self._transition(AppState.HIGH_RISK),
                on_end_month=lambda: self._transition(AppState.DEBRIEFING),
                fg_color="transparent",
            )

        # ── LOW_RISK ──────────────────────────────────────────────────────────
        if state == AppState.LOW_RISK:
            portfolio = self._current_portfolio()
            snap = self._engine.snapshot(portfolio) if self._engine and portfolio else {}

            # Build product list from real engine data
            products = self._build_fixed_products()

            # Build open positions list with index
            open_positions = [
                {**pos_snap, "index": i, "label": pos_snap.get("product", "—")}
                for i, pos_snap in enumerate(snap.get("fixed_positions", []))
            ]

            def on_invest(product_key: str, amount: float):
                try:
                    ftype = FixedIncomeType(product_key)
                    self._engine.buy_fixed(portfolio, ftype, amount)
                    print(f"[LOW RISK] Investido R$ {amount:.2f} em {product_key}")
                except Exception as e:
                    print(f"[LOW RISK] Erro ao investir: {e}")
                self._transition(AppState.SIMULATOR_MAIN)

            def on_redeem(position_index: int):
                try:
                    redeemed = self._engine.redeem_fixed(portfolio, position_index)
                    print(f"[LOW RISK] Resgatado R$ {redeemed:.2f} (posição {position_index})")
                except Exception as e:
                    print(f"[LOW RISK] Erro ao resgatar: {e}")
                self._transition(AppState.SIMULATOR_MAIN)

            return LowRiskInvestmentsPage(
                master=self,
                products=products,
                open_positions=open_positions,
                cash=snap.get("cash", 0.0),
                on_invest=on_invest,
                on_redeem=on_redeem,
                on_back=lambda: self._transition(AppState.SIMULATOR_MAIN),
                fg_color="transparent",
            )

        # ── HIGH_RISK ─────────────────────────────────────────────────────────
        if state == AppState.HIGH_RISK:
            portfolio = self._current_portfolio()
            snap = self._engine.snapshot(portfolio) if self._engine and portfolio else {}

            # Build stock list from real engine market data
            stocks = [
                s_snap
                for s_snap in (
                    self._engine.stocks[t].snapshot()
                    for t in self._engine.stocks
                )
            ] if self._engine else []

            portfolio_positions = snap.get("stock_positions", [])

            def on_buy(ticker: str, amount: float):
                try:
                    self._engine.buy_stock(portfolio, ticker, amount)
                    print(f"[HIGH RISK] Comprado R$ {amount:.2f} de {ticker}")
                except Exception as e:
                    print(f"[HIGH RISK] Erro ao comprar: {e}")
                self._transition(AppState.SIMULATOR_MAIN)

            def on_sell(ticker: str, shares: float):
                try:
                    proceeds = self._engine.sell_stock(portfolio, ticker, shares)
                    print(f"[HIGH RISK] Vendido {shares} cotas de {ticker} → R$ {proceeds:.2f}")
                except Exception as e:
                    print(f"[HIGH RISK] Erro ao vender: {e}")
                self._transition(AppState.SIMULATOR_MAIN)

            return HighRiskInvestmentsPage(
                master=self,
                stocks=stocks,
                portfolio_positions=portfolio_positions,
                cash=snap.get("cash", 0.0),
                on_buy=on_buy,
                on_sell=on_sell,
                on_back=lambda: self._transition(AppState.SIMULATOR_MAIN),
                fg_color="transparent",
            )

        # ── DEBRIEFING ────────────────────────────────────────────────────────
        if state == AppState.DEBRIEFING:
            portfolio = self._current_portfolio()
            snap = self._engine.snapshot(portfolio) if self._engine and portfolio else {}
            alloc = snap.get("allocation", {})

            # Calculate net-worth change since last cycle
            nw = snap.get("net_worth", 0.0)
            history = portfolio.net_worth_history if portfolio else []
            prev_nw = history[-2] if len(history) >= 2 else history[0] if history else nw
            change = nw - prev_nw

            # Quest completion check
            quest_completed = self._check_quest_completed(snap)

            # AI debriefing feedback (best-effort)
            agent_feedback = self._request_ai_debriefing(
                snap=snap,
                quest_completed=quest_completed,
            )

            return DebriefingPage(
                master=self,
                player_name=self._profile.name if self._profile else "Aventureiro",
                net_worth=nw,
                net_worth_change=change,
                cash_pct=alloc.get("cash_pct", 0.0),
                fixed_pct=alloc.get("fixed_pct", 0.0),
                stocks_pct=alloc.get("stocks_pct", 0.0),
                cycles_played=snap.get("cycle", 1),
                agent_feedback=agent_feedback,
                quest_completed=quest_completed,
                on_continue=lambda: self._transition(AppState.END_MONTH),
                fg_color="transparent",
            )

        # ── END_MONTH ─────────────────────────────────────────────────────────
        if state == AppState.END_MONTH:
            result = None
            if self._engine:
                result = self._engine.advance_cycle()
                self._last_cycle_result = result
            # Reset salary flag for the new cycle
            self._salary_deposited = False

            market = self._engine.market.summary() if self._engine else {}

            return EndOfMonthPage(
                master=self,
                cycle=result.cycle if result else 1,
                market_events=result.market_events if result else [],
                stock_events=result.stock_events if result else [],
                fixed_earnings=sum(
                    v.get("fixed_earnings", 0.0)
                    for v in (result.portfolio_summaries.values() if result else [])
                ),
                selic_pct=market.get("selic_annual_pct", 0.0),
                inflation_pct=market.get("inflation_annual_pct", 0.0),
                on_next=lambda: self._transition(AppState.HUB),
                fg_color="transparent",
            )

        raise ValueError(f"Unknown state: {state}")

    # ─────────────────────────────────────────────────────────────────────────
    # Quest helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _start_quest(self):
        """Generate (or fall back to hardcoded) quest data, then transition."""
        self._generate_quest()
        self._transition(AppState.QUEST_GENERATED)

    def _generate_quest(self):
        """
        Calls the AI engine to generate a quest for the current cycle.
        Falls back gracefully to a default quest if the AI is unavailable.
        """
        import random

        quest_types = ["acumulação", "sobrevivência", "evento"]
        scores = self._quest_scores
        # If last score was low, favour simpler accumulation quests
        if scores and scores[-1] < 40:
            quest_type = "acumulação"
        else:
            quest_type = random.choice(quest_types[:2])  # event quests unlock later
        self._quest_type = quest_type

        user_profile = {}
        if self._profile:
            user_profile = {
                "name": self._profile.name,
                "monthly_income": self._profile.monthly_income,
                "monthly_expenses": self._profile.monthly_expenses,
                "monthly_surplus": self._profile.monthly_surplus,
                "risk_profile": self._profile.risk_profile,
                "knowledge_level": self._profile.knowledge_level,
                "goal": self._profile.goal,
                "goal_amount": self._profile.goal_amount,
                "goal_deadline_months": self._profile.goal_deadline_months,
            }

        learning_context = {
            "last_score": scores[-1] if scores else None,
            "completed_quests": len(scores),
            "main_weakness": self._simulator_performance()["main_weakness"],
            "last_quest_type": self._quest_type,
            "unlocked_event": len(scores) >= 5,
        }

        try:
            api_key = os.environ.get("BOBSHELL_API_KEY", "")
            from src.Ai.engine import Engine as AiEngine
            from src.Ai.bob import Bob
            bob = Bob(email="", password=api_key)
            bob.login()
            ai = AiEngine(bob)
            raw = ai.generate_quest(
                quest_type=quest_type,
                user_profile=user_profile,
                learning_context=learning_context,
            )
            # Parse structured response — extract TÍTULO, CONTEXTO, OBJETIVO
            lines = raw.splitlines()
            title = obj = desc_lines = ""
            capturing_context = False
            context_buf: list[str] = []
            for line in lines:
                if line.startswith("TÍTULO:"):
                    title = line.replace("TÍTULO:", "").strip()
                    capturing_context = False
                elif line.startswith("CONTEXTO:"):
                    capturing_context = True
                    rest = line.replace("CONTEXTO:", "").strip()
                    if rest:
                        context_buf.append(rest)
                elif line.startswith("OBJETIVO:"):
                    capturing_context = False
                    obj = line.replace("OBJETIVO:", "").strip()
                elif capturing_context and line.strip():
                    context_buf.append(line.strip())
            desc_lines = " ".join(context_buf)

            if title:
                self._quest_title = title
            if desc_lines:
                self._quest_description = desc_lines
            if obj:
                self._quest_objective = f"🎯  {obj}"

        except Exception as e:
            print(f"[QUEST] Falha ao gerar quest via IA: {e}")
            self._quest_title = "O Fundo de Emergência do Rei"
            self._quest_description = (
                "O reino enfrenta tempos incertos. O conselheiro real recomenda "
                "que todo cidadão mantenha uma reserva segura antes de aventurar-se "
                "nos mercados de capitais."
            )
            if self._profile:
                target = self._profile.monthly_expenses * 4
                self._quest_objective = (
                    f"🎯  Objetivo: acumule R$ {target:,.2f} em ativos líquidos."
                )
            else:
                self._quest_objective = "🎯  Objetivo: acumular uma reserva de emergência."

    def _check_quest_completed(self, snap: dict) -> bool:
        """Simple heuristic: for accumulation quests, check if net worth grew."""
        if self._quest_type == "acumulação":
            return snap.get("net_worth", 0.0) > self._quest_start_net_worth
        if self._quest_type == "sobrevivência":
            # Survival: net worth didn't drop below start
            return snap.get("net_worth", 0.0) >= self._quest_start_net_worth
        return True  # event quests always count as attempted

    def _request_ai_debriefing(self, snap: dict, quest_completed: bool) -> str:
        """
        Calls the AI engine for a debriefing narrative.
        Returns a fallback string if the AI is unavailable.
        """
        try:
            api_key = os.environ.get("BOBSHELL_API_KEY", "")
            from src.Ai.engine import Engine as AiEngine
            from src.Ai.bob import Bob
            bob = Bob(email="", password=api_key)
            bob.login()
            ai = AiEngine(bob)

            # Send simulator context first
            market_snap = self._engine.market_snapshot() if self._engine else {}
            full_ctx = {**snap, **market_snap}
            ai.send_simulator_context(full_ctx)

            # Send player actions
            portfolio = self._current_portfolio()
            actions = portfolio.transaction_log[-20:] if portfolio else []
            ai.send_player_actions(actions, cycle=snap.get("cycle"))

            # Request debriefing
            cycle_result_dict = {}
            if self._last_cycle_result:
                cycle_result_dict = {
                    "cycle": self._last_cycle_result.cycle,
                    "market_events": self._last_cycle_result.market_events,
                    "stock_events": self._last_cycle_result.stock_events,
                    "portfolio_summaries": self._last_cycle_result.portfolio_summaries,
                }
            raw = ai.send_debriefing_request(
                quest_type=self._quest_type,
                quest_objective=self._quest_objective,
                objective_achieved=quest_completed,
                cycle_result=cycle_result_dict,
            )
            # Extract the score for quest_scores tracking
            for line in raw.splitlines():
                if "PONTUAÇÃO:" in line.upper():
                    try:
                        score_str = line.upper().split("PONTUAÇÃO:")[-1].strip()
                        score = int(score_str.split("/")[0].strip())
                        self._quest_scores.append(score)
                    except (ValueError, IndexError):
                        pass
            return raw

        except Exception as e:
            print(f"[DEBRIEFING] Falha ao obter feedback via IA: {e}")
            alloc = snap.get("allocation", {})
            fixed_pct = alloc.get("fixed_pct", 0.0)
            stocks_pct = alloc.get("stocks_pct", 0.0)
            cash_pct = alloc.get("cash_pct", 0.0)

            if cash_pct > 60:
                return (
                    "Seu saldo em caixa está muito alto. "
                    "Considere diversificar: aplique parte em Renda Fixa para ao menos "
                    "proteger contra a inflação enquanto mantém sua reserva de emergência."
                )
            if fixed_pct == 0 and stocks_pct == 0:
                return (
                    "Nenhum investimento realizado este mês. "
                    "Mesmo uma pequena aplicação em Tesouro Selic já protege seu dinheiro "
                    "da inflação e constrói o hábito de investir."
                )
            if stocks_pct > 70:
                return (
                    "Alta concentração em renda variável. "
                    "Diversifique com renda fixa para reduzir o risco total do portfólio."
                )
            return (
                "Continue investindo com disciplina! "
                "Mantenha sua reserva de emergência antes de buscar maior retorno."
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _current_portfolio(self):
        """Returns the active Portfolio, or None if not yet created."""
        if self._engine is None or self._profile is None:
            return None
        return self._engine.portfolios.get(self._profile.user_id)

    def _build_fixed_products(self) -> list[dict]:
        """
        Builds the product list for LowRiskInvestmentsPage from the real
        PRODUCTS catalogue, formatted with current market rates.
        """
        market = self._engine.market if self._engine else None
        result = []
        for ftype, prod in PRODUCTS.items():
            if prod.indexer == "selic":
                rate_val = market.selic_annual if market else 0.0
                rate_display = f"100% SELIC  ({rate_val:.2f}% a.a.)"
            elif prod.indexer == "cdi_pct":
                cdi = market.cdi_annual if market else 0.0
                effective = cdi * prod.rate_param
                rate_display = (
                    f"{prod.rate_param*100:.0f}% CDI  "
                    f"(≈ {effective:.2f}% a.a.)"
                )
            elif prod.indexer == "prefixed":
                rate_display = f"{prod.rate_param:.1f}% a.a. (fixo)"
            elif prod.indexer == "ipca_plus":
                inf = market.inflation_annual if market else 0.0
                rate_display = (
                    f"IPCA + {prod.rate_param:.1f}%  "
                    f"(≈ {inf + prod.rate_param:.2f}% a.a.)"
                )
            else:
                rate_display = f"{prod.rate_param}"

            maturity = (
                "Liquidez diária" if prod.maturity_months == 0
                else f"{prod.maturity_months} meses"
            )

            result.append({
                "key": ftype.value,
                "label": prod.label,
                "rate_display": rate_display,
                "maturity": maturity,
                "min_investment": prod.min_investment,
                "ir_exempt": prod.ir_exempt,
                "description": prod.description,
            })
        return result

    def _ensure_study_library(self) -> StudyLibrary:
        """Returns (creating if needed) the StudyLibrary for the current profile."""
        if self._study_library is None:
            user_id = self._profile.user_id if self._profile else "anonymous"
            self._study_library = StudyLibrary(user_id=user_id, data_dir=".")
        return self._study_library

    def _simulator_performance(self) -> dict:
        """Builds the simulator_performance dict consumed by the AI engine."""
        scores = self._quest_scores
        avg = sum(scores) / len(scores) if scores else 0.0

        # Infer main weakness from portfolio allocation
        main_weakness = "diversificação"
        portfolio = self._current_portfolio()
        if self._engine and portfolio:
            snap = self._engine.snapshot(portfolio)
            alloc = snap.get("allocation", {})
            if alloc.get("cash_pct", 0) > 60:
                main_weakness = "aplicação do saldo em caixa"
            elif alloc.get("stocks_pct", 0) > 70:
                main_weakness = "concentração em renda variável"
            elif alloc.get("fixed_pct", 0) == 0 and alloc.get("stocks_pct", 0) == 0:
                main_weakness = "início do hábito de investir"

        return {
            "avg_score": avg,
            "completed_quests": len(scores),
            "main_weakness": main_weakness,
            "last_quest_topics": [],
        }

    def _generate_study_content(self, requested_topic: str | None = None):
        """
        Calls the AI engine to generate a new StudyContent and persists it.
        Falls back gracefully if the AI engine is not available.
        """
        from src.Ai.engine import Engine as AiEngine
        from src.Ai.bob import Bob

        lib = self._ensure_study_library()

        profile_dict = {}
        if self._profile:
            profile_dict = {
                "name": self._profile.name,
                "knowledge_level": self._profile.knowledge_level,
                "risk_profile": self._profile.risk_profile,
                "goal": self._profile.goal,
                "monthly_income": self._profile.monthly_income,
                "monthly_expenses": self._profile.monthly_expenses,
                "monthly_surplus": self._profile.monthly_surplus,
                "goal_amount": self._profile.goal_amount,
                "goal_deadline_months": self._profile.goal_deadline_months,
            }

        try:
            api_key = os.environ.get("BOBSHELL_API_KEY", "")
            bob = Bob(email="", password=api_key)
            bob.login()
            ai = AiEngine(bob)
            raw = ai.generate_study_content(
                user_profile=profile_dict,
                simulator_performance=self._simulator_performance(),
                library_summary=lib.mastery_summary(),
                requested_topic=requested_topic,
            )
            data = json.loads(raw)
            content = StudyContent(
                id=str(uuid.uuid4()),
                topic=data["topic"],
                source_text=data["source_text"],
                adapted_text=data["adapted_text"],
                quiz=[QuizQuestion(**q) for q in data.get("quiz", [])],
                sim_score_at_creation=self._simulator_performance()["avg_score"],
                created_cycle=self._engine.market.cycle if self._engine else 0,
                requested_by_user=requested_topic is not None,
            )
            lib.add(content)
        except Exception as e:
            print(f"[STUDY] Falha ao gerar conteúdo via IA: {e}")

    def _evaluate_mastery(self, content_id: str):
        """
        After a quiz, asks the AI whether the topic has been mastered.
        Updates the library if mastered=True is returned.
        """
        from src.Ai.engine import Engine as AiEngine
        from src.Ai.bob import Bob

        lib = self._ensure_study_library()
        content = lib.get_by_id(content_id)
        if content is None:
            return

        try:
            api_key = os.environ.get("BOBSHELL_API_KEY", "")
            bob = Bob(email="", password=api_key)
            bob.login()
            ai = AiEngine(bob)
            quiz_dicts = [
                {"cycle": r.cycle, "score": r.score,
                 "correct": r.correct, "total": r.total}
                for r in content.quiz_results
            ]
            raw = ai.evaluate_study_mastery(
                topic=content.topic,
                quiz_results=quiz_dicts,
                simulator_performance=self._simulator_performance(),
                knowledge_level=(
                    self._profile.knowledge_level
                    if self._profile else "iniciante"
                ),
            )
            data = json.loads(raw)
            if data.get("mastered"):
                lib.mark_mastered(content_id)
                print(f"[STUDY] Tema '{content.topic}' marcado como dominado.")
        except Exception as e:
            print(f"[STUDY] Falha ao avaliar domínio via IA: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    app = App()
    app.mainloop()

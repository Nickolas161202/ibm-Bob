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
                  ┌───────►│ Simulador Principal  │◄──────-┐
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

import json
import os
import sys
import uuid
from dataclasses import asdict
from enum import Enum, auto
from pathlib import Path
from typing import Callable, Optional

import customtkinter as ctk

# ── path setup ───────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── simulator engine ──────────────────────────────────────────────────────────
from src.Simulator.engine import SimulatorEngine
from src.Simulator.portfolio import InvestorProfile
from src.Simulator.fixed_income import FixedIncomeType, PRODUCTS

# ── study library ─────────────────────────────────────────────────────────────
from src.Study.library import StudyLibrary, StudyContent, QuizQuestion

# ── profile inference ─────────────────────────────────────────────────────────
from src.Simulator.portfolio import ProfileInferenceState, ProfileInferenceEntry

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
from src.Interfaces.profileConfirm import ProfileConfirmDialog


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
# Profile persistence
# ─────────────────────────────────────────────────────────────────────────────

_PROFILES_DIR = Path(__file__).parent / "data" / "profiles"


def _save_profile(profile: InvestorProfile) -> Path:
    """Serialise *profile* to ``data/profiles/<user_id>.json`` and return the path."""
    _PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    path = _PROFILES_DIR / f"{profile.user_id}.json"
    path.write_text(json.dumps(asdict(profile), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _load_latest_profile() -> Optional[InvestorProfile]:
    """Return the most recently saved InvestorProfile, or None if none exist."""
    if not _PROFILES_DIR.exists():
        return None
    files = sorted(_PROFILES_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return None
    data = json.loads(files[0].read_text(encoding="utf-8"))
    return InvestorProfile(**data)


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
        self._profile: Optional[InvestorProfile] = _load_latest_profile()
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

        if self._profile is not None:
            self._engine = SimulatorEngine()
            self._engine.create_portfolio(self._profile, initial_cash=self._profile.monthly_surplus)

        # ── profile inference state ───────────────────────────────────────────
        self._inference_state: ProfileInferenceState = ProfileInferenceState()
        # active quest dict (title, type, objective, …) — populated by QUEST_GENERATED
        self._active_quest: dict = {}
        # snapshot of portfolio taken at the START of a quest (baseline for evaluation)
        self._quest_start_snapshot: dict = {}
        # transaction log slice taken at quest start (to send only quest actions)
        self._quest_start_log_len: int = 0

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
                _save_profile(profile)
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
            # Generate the quest via AI (falls back to hardcoded on failure)
            quest_data = self._generate_quest()

            def on_start():
                # Record the portfolio baseline so we can evaluate later
                portfolio = self._current_portfolio()
                if self._engine and portfolio:
                    self._quest_start_snapshot = self._engine.snapshot(portfolio)
                    self._quest_start_log_len  = len(portfolio.transaction_log)
                self._transition(AppState.SIMULATOR_MAIN)

            return QuestGeneratedPage(
                master=self,
                quest_title=quest_data.get("title", "Nova Missão"),
                quest_description=(
                    quest_data.get("context", "")
                    + "\n\n💡  " + quest_data.get("initial_tip", "")
                ).strip(),
                quest_objective="🎯  " + quest_data.get("objective", ""),
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
                p = self._current_portfolio()
                if self._engine is not None and p is not None:
                    try:
                        ftype = FixedIncomeType(product_key)
                        self._engine.buy_fixed(p, ftype, amount)
                        print(f"[LOW RISK] Investido R$ {amount:.2f} em {product_key}")
                    except Exception as e:
                        print(f"[LOW RISK] Erro ao investir: {e}")
                self._transition(AppState.SIMULATOR_MAIN)

            def on_redeem(position_index: int):
                p = self._current_portfolio()
                if self._engine is not None and p is not None:
                    try:
                        redeemed = self._engine.redeem_fixed(p, position_index)
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
                p = self._current_portfolio()
                if self._engine is not None and p is not None:
                    try:
                        self._engine.buy_stock(p, ticker, amount)
                        print(f"[HIGH RISK] Comprado R$ {amount:.2f} de {ticker}")
                    except Exception as e:
                        print(f"[HIGH RISK] Erro ao comprar: {e}")
                self._transition(AppState.SIMULATOR_MAIN)

            def on_sell(ticker: str, shares: float):
                p = self._current_portfolio()
                if self._engine is not None and p is not None:
                    try:
                        proceeds = self._engine.sell_stock(p, ticker, shares)
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

            # ── Run post-quest AI evaluation (async-style: best-effort) ───────
            ai_result = self._evaluate_quest(portfolio, snap)
            feedback  = ai_result.get(
                "summary",
                "Continue investindo com disciplina! "
                "Mantenha sua reserva de emergência antes de buscar maior retorno.",
            )
            quest_completed = self._active_quest.get("objective_achieved", False)

            def on_continue():
                # Show profile update confirmation if needed, then advance
                self._maybe_confirm_profile_update(
                    ai_result=ai_result,
                    on_done=lambda: self._transition(AppState.END_MONTH),
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
                agent_feedback=feedback,
                quest_completed=quest_completed,
                on_continue=on_continue,
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

    # ─────────────────────────────────────────────────────────────────────────
    # Quest generation & post-quest evaluation
    # ─────────────────────────────────────────────────────────────────────────

    def _generate_quest(self) -> dict:
        """
        Calls the AI engine to generate the next quest based on the inferred
        profile. Returns a quest dict. Falls back to a safe hardcoded quest
        if the AI call fails.
        """
        from src.Ai.engine import Engine as AiEngine
        from src.Ai.bob import Bob

        fallback = {
            "title": "O Fundo de Emergência do Rei",
            "context": (
                "O reino enfrenta tempos incertos. O conselheiro real recomenda "
                "que todo cidadão mantenha uma reserva segura antes de aventurar-se "
                "nos mercados de capitais."
            ),
            "objective": (
                f"Acumule R$ {(self._profile.monthly_expenses * 4):,.2f} "
                "em ativos líquidos."
                if self._profile else "Acumule uma reserva de emergência."
            ),
            "victory_condition": "Reserva de emergência ≥ 4 meses de despesas em ativos líquidos.",
            "defeat_condition":  "Não atingir a meta no prazo do ciclo.",
            "initial_tip": "Tesouro Selic e CDB de liquidez diária são ótimas opções para reserva.",
            "type": "acumulação",
        }

        if not self._profile:
            self._active_quest = fallback
            return fallback

        inf  = self._inference_state
        profile_dict = {
            "name":                  self._profile.name,
            "monthly_income":        self._profile.monthly_income,
            "monthly_expenses":      self._profile.monthly_expenses,
            "monthly_surplus":       self._profile.monthly_surplus,
            "risk_profile":          self._profile.risk_profile,
            "knowledge_level":       self._profile.knowledge_level,
            "goal":                  self._profile.goal,
            "goal_amount":           self._profile.goal_amount,
            "goal_deadline_months":  self._profile.goal_deadline_months,
        }
        learning_ctx = {
            "last_score":       inf.last_score,
            "completed_quests": inf.completed_quests,
            "main_weakness":    inf.main_weakness,
            "last_quest_type":  self._active_quest.get("type", "nenhuma"),
            "inferred_risk":    self._profile.risk_profile,
            "inferred_level":   self._profile.knowledge_level,
        }

        # alternate quest types: acumulação → sobrevivência → acumulação ...
        q_type = (
            "sobrevivência"
            if inf.completed_quests % 3 == 2
            else "acumulação"
        )

        try:
            api_key = os.environ.get("BOBSHELL_API_KEY", "")
            bob = Bob(email="", password=api_key)
            bob.login()
            ai  = AiEngine(bob)
            raw = ai.generate_quest(
                quest_type=q_type,
                user_profile=profile_dict,
                learning_context=learning_ctx,
            )
            data = json.loads(raw)
            data.setdefault("type", q_type)
            self._active_quest = data
            return data
        except Exception as e:
            print(f"[QUEST] Falha ao gerar quest via IA: {e}")
            self._active_quest = fallback
            return fallback

    def _evaluate_quest(self, portfolio, snap: dict) -> dict:
        """
        Sends quest actions + final snapshot to the AI for evaluation.
        Records the resulting ProfileInferenceEntry.
        Returns the parsed AI result dict (empty dict on failure).
        """
        from src.Ai.engine import Engine as AiEngine
        from src.Ai.bob import Bob

        if not self._profile or not portfolio:
            return {}

        # Only actions taken DURING this quest
        actions = portfolio.transaction_log[self._quest_start_log_len:]

        current_profile = {
            "risk_profile":    self._profile.risk_profile,
            "knowledge_level": self._profile.knowledge_level,
            "goal":            self._profile.goal,
            "monthly_surplus": self._profile.monthly_surplus,
        }
        history_dicts = [
            {
                "cycle":          e.cycle,
                "score":          e.score,
                "main_weakness":  e.main_weakness,
                "inferred_risk":  e.inferred_risk,
                "inferred_level": e.inferred_level,
                "applied":        e.applied,
            }
            for e in self._inference_state.history
        ]

        try:
            api_key = os.environ.get("BOBSHELL_API_KEY", "")
            bob = Bob(email="", password=api_key)
            bob.login()
            ai  = AiEngine(bob)
            raw = ai.analyze_quest_performance(
                quest=self._active_quest,
                actions=actions,
                portfolio_snapshot=snap,
                current_profile=current_profile,
                inference_history=history_dicts,
            )
            data = json.loads(raw)

            # normalise accent-free values from the AI
            _risk_norm  = {"conservador": "conservador", "moderado": "moderado", "arrojado": "arrojado"}
            _level_norm = {"iniciante": "iniciante", "intermediario": "intermediário",
                           "intermediário": "intermediário", "avancado": "avançado", "avançado": "avançado"}
            data["inferred_risk"]  = _risk_norm.get(data.get("inferred_risk", ""), self._profile.risk_profile)
            data["inferred_level"] = _level_norm.get(data.get("inferred_level", ""), self._profile.knowledge_level)

            # Record in inference history (not yet applied — pending confirmation decision)
            score = min(max(int(data.get("score", 0)), 0), 100)
            entry = ProfileInferenceEntry(
                cycle=self._engine.market.cycle if self._engine else 0,
                score=score,
                main_weakness=data.get("main_weakness", "não identificada"),
                inferred_risk=data["inferred_risk"],
                inferred_level=data["inferred_level"],
                reasoning=data.get("reasoning", ""),
                applied=False,
            )
            self._inference_state.record(entry)
            self._quest_scores.append(score)
            return data
        except Exception as e:
            print(f"[QUEST] Falha ao avaliar quest via IA: {e}")
            return {}

    def _maybe_confirm_profile_update(self, ai_result: dict, on_done: Callable):
        """
        Decides whether to silently apply the inferred profile update or
        show the confirmation dialog first. Calls on_done() when resolved.
        """
        if not ai_result or not self._profile:
            on_done()
            return

        new_risk  = ai_result.get("inferred_risk",  self._profile.risk_profile)
        new_level = ai_result.get("inferred_level", self._profile.knowledge_level)

        no_change = (
            new_risk  == self._profile.risk_profile
            and new_level == self._profile.knowledge_level
        )
        if no_change:
            on_done()
            return

        needs_confirm = self._inference_state.needs_confirmation(
            new_risk=new_risk,
            new_level=new_level,
            current_risk=self._profile.risk_profile,
            current_level=self._profile.knowledge_level,
        )

        def apply_update():
            assert self._profile is not None
            self._profile.risk_profile    = new_risk
            self._profile.knowledge_level = new_level
            # mark last entry as applied
            if self._inference_state.history:
                self._inference_state.history[-1].applied          = True
                self._inference_state.history[-1].confirmed_by_user = needs_confirm
            self._inference_state.mark_confirmed() if needs_confirm else self._inference_state.mark_silent_update()
            on_done()

        def reject_update():
            self._inference_state.mark_confirmed()   # reset counter either way
            on_done()

        if needs_confirm:
            dlg = ProfileConfirmDialog(
                master=self,
                current_risk=self._profile.risk_profile,
                current_level=self._profile.knowledge_level,
                inferred_risk=new_risk,
                inferred_level=new_level,
                reasoning=ai_result.get("reasoning", ""),
                on_confirm=apply_update,
                on_reject=reject_update,
            )
            dlg.grab_set()
        else:
            apply_update()


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    app = App()
    app.mainloop()

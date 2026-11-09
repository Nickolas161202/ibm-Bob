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
import random
import sys
import uuid
import threading
from dataclasses import asdict
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Optional

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
from src.Interfaces.editIncome import EditIncomePage
from src.Interfaces.profileConfirm import ProfileConfirmDialog
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")
from src.Interfaces.loading import LoadingPage


# ─────────────────────────────────────────────────────────────────────────────
# State enumeration — mirrors every node in states_ibm.json
# ─────────────────────────────────────────────────────────────────────────────

class AppState(Enum):
    INICIAL              = auto()   # i2zG1y6y6l51
    CREATE_PROFILE       = auto()   # u2zG367~7dvM
    HUB                  = auto()   # menu principal pós-onboarding
    EDIT_PROFILE         = auto()   # edição de nome/renda/gastos
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
_PROFILE_FILE  = _PROFILES_DIR / "profile.json"
_PORTFOLIO_FILE = _PROFILES_DIR / "portfolio.json"


def _save_profile(profile: InvestorProfile) -> Path:
    """Serialise *profile* to ``data/profiles/profile.json``, overwriting any previous one."""
    _PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    # Remove any old per-user-id files left from a previous layout
    for old in _PROFILES_DIR.glob("*.json"):
        if old not in (_PROFILE_FILE, _PORTFOLIO_FILE):
            old.unlink(missing_ok=True)
    _PROFILE_FILE.write_text(json.dumps(asdict(profile), indent=2, ensure_ascii=False), encoding="utf-8")
    return _PROFILE_FILE


def _load_latest_profile() -> Optional[InvestorProfile]:
    """Return the single saved InvestorProfile, or None if it does not exist."""
    if not _PROFILE_FILE.exists():
        return None
    data = json.loads(_PROFILE_FILE.read_text(encoding="utf-8"))
    return InvestorProfile(**data)


# ─────────────────────────────────────────────────────────────────────────────
# Portfolio persistence
# ─────────────────────────────────────────────────────────────────────────────

def _save_portfolio(engine: "SimulatorEngine", profile: InvestorProfile) -> None:
    """
    Serialise the portfolio's mutable state to ``data/profiles/portfolio.json``.

    Saves:
      - cash
      - fixed_positions  (enough to reconstruct each FixedIncomePosition)
      - stock_positions   (enough to reconstruct each StockPosition)
      - net_worth_history, cash_history
      - transaction_log
      - market cycle + SELIC (so earnings stay consistent on reload)
    """
    from src.Simulator.fixed_income import FixedIncomeType
    portfolio = engine.portfolios.get(profile.user_id)
    if portfolio is None:
        return

    fixed = []
    for pos in portfolio.fixed_positions:
        fixed.append({
            "product_type":       pos.product.product_type.value,
            "principal":          round(pos.principal, 6),
            "purchase_cycle":     pos.purchase_cycle,
            "locked_rate_annual": pos.locked_rate_annual,
            "gross_earnings":     round(pos.gross_earnings, 6),
            "cycles_held":        pos.cycles_held,
        })

    stocks = {}
    for ticker, pos in portfolio.stock_positions.items():
        stocks[ticker] = {
            "shares":              round(pos.shares, 6),
            "avg_purchase_price":  round(pos.avg_purchase_price, 6),
            "total_invested":      round(pos.total_invested, 6),
        }

    data = {
        "cash":               round(portfolio.cash, 6),
        "fixed_positions":    fixed,
        "stock_positions":    stocks,
        "net_worth_history":  portfolio.net_worth_history,
        "cash_history":       portfolio.cash_history,
        "transaction_log":    portfolio.transaction_log,
        "market_cycle":       engine.market.cycle,
        "market_selic":       engine.market.selic_annual,
        "deposit_done_cycle": -1,   # reset; App will repopulate
    }

    _PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    _PORTFOLIO_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _load_portfolio(engine: "SimulatorEngine", profile: InvestorProfile) -> int:
    """
    Restore the portfolio from ``data/profiles/portfolio.json`` into *engine*.
    Returns the saved ``deposit_done_cycle`` value (default -1).

    Must be called AFTER engine.create_portfolio() so the Portfolio object
    already exists in engine.portfolios.
    """
    if not _PORTFOLIO_FILE.exists():
        return -1

    from src.Simulator.fixed_income import FixedIncomeType, PRODUCTS, FixedIncomePosition
    from src.Simulator.variable_income import StockPosition

    data = json.loads(_PORTFOLIO_FILE.read_text(encoding="utf-8"))
    portfolio = engine.portfolios.get(profile.user_id)
    if portfolio is None:
        return -1

    # Restore market state so rates are consistent
    engine.market.cycle        = data.get("market_cycle", 0)
    engine.market.selic_annual = data.get("market_selic", engine.market.selic_annual)

    # Restore cash
    portfolio.cash = data.get("cash", 0.0)

    # Restore fixed income positions
    portfolio.fixed_positions.clear()
    for fp in data.get("fixed_positions", []):
        ft = FixedIncomeType(fp["product_type"])
        product = PRODUCTS[ft]
        pos = FixedIncomePosition(
            product=product,
            principal=fp["principal"],
            purchase_cycle=fp["purchase_cycle"],
            locked_rate_annual=fp.get("locked_rate_annual"),
        )
        pos.gross_earnings = fp.get("gross_earnings", 0.0)
        pos.cycles_held    = fp.get("cycles_held", 0)
        portfolio.fixed_positions.append(pos)

    # Restore stock positions
    portfolio.stock_positions.clear()
    for ticker, sp in data.get("stock_positions", {}).items():
        portfolio.stock_positions[ticker] = StockPosition(
            ticker=ticker,
            shares=sp["shares"],
            avg_purchase_price=sp["avg_purchase_price"],
            total_invested=sp["total_invested"],
        )

    # Restore history + log
    portfolio.net_worth_history = data.get("net_worth_history", [])
    portfolio.cash_history      = data.get("cash_history", [])
    portfolio.transaction_log   = data.get("transaction_log", [])

    return data.get("deposit_done_cycle", -1)


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
        self.title("Simulador de Investimentos — Finvest")
        self.geometry("680x620")
        self.minsize(520, 480)
        self.resizable(True, True)

        # ── simulator state ───────────────────────────────────────────────────
        self._engine: Optional[SimulatorEngine] = None
        self._profile: Optional[InvestorProfile] = _load_latest_profile()
        self._last_cycle_result = None   # CycleResult from advance_cycle()
        # tracks whether the monthly deposit was already done for the current cycle
        self._deposit_done_for_cycle: int = -1

        # ── study library (one instance per profile, loaded lazily) ───────────
        self._study_library: Optional[StudyLibrary] = None
        # tracks quest scores for mastery evaluation
        self._quest_scores: list[int] = []

        if self._profile is not None:
            self._engine = SimulatorEngine()
            self._engine.create_portfolio(self._profile, initial_cash=self._profile.monthly_surplus)
            # Restore saved portfolio state (overwrites the initial_cash if a save exists)
            self._deposit_done_for_cycle = _load_portfolio(self._engine, self._profile)

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
                _save_portfolio(self._engine, profile)
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
                on_reconfigure=lambda: self._transition(AppState.EDIT_PROFILE),
                fg_color="transparent",
            )

        # ── EDIT_PROFILE ──────────────────────────────────────────────────────
        if state == AppState.EDIT_PROFILE:
            assert self._profile is not None  # only reachable from HUB which requires a profile
            _profile = self._profile

            def on_edit_save(name: str, income: float, expenses: float, goal: str, goal_amount: float, goal_deadline: int):
                _profile.name = name
                _profile.monthly_income = income
                _profile.monthly_expenses = expenses
                _profile.goal = goal
                _profile.goal_amount = goal_amount
                _profile.goal_deadline_months = goal_deadline
                _save_profile(_profile)
                self._transition(AppState.HUB)

            return EditIncomePage(
                master=self,
                profile=_profile,
                on_save=on_edit_save,
                on_cancel=lambda: self._transition(AppState.HUB),
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
            def _show_quest(quest_data: dict):
                def on_start():
                    portfolio = self._current_portfolio()
                    if self._engine and portfolio:
                        self._quest_start_snapshot = self._engine.snapshot(portfolio)
                        self._quest_start_log_len  = len(portfolio.transaction_log)
                    self._transition(AppState.SIMULATOR_MAIN)

                self._replace_loading(QuestGeneratedPage(
                    master=self,
                    quest_title=quest_data.get("title", "Nova Missão"),
                    quest_description=(
                        quest_data.get("context", "")
                        + "\n\n💡  " + quest_data.get("initial_tip", "")
                    ).strip(),
                    quest_objective="🎯  " + quest_data.get("objective", ""),
                    on_start=on_start,
                    fg_color="transparent",
                ))

            self._run_in_background(
                task=self._generate_quest,
                on_done=_show_quest,
                message="Seu objetivo está sendo gerado.",
            )
            return LoadingPage(
                master=self,
                message="Seu objetivo está sendo gerado.",
                sub_message="Isso pode levar alguns segundos.",
                fg_color="transparent",
            )

        # ── SIMULATOR_MAIN ────────────────────────────────────────────────────
        if state == AppState.SIMULATOR_MAIN:
            portfolio = self._current_portfolio()

            # Deposit monthly surplus once per market cycle
            if (
                self._engine
                and portfolio
                and self._profile
                and self._engine.market.cycle != self._deposit_done_for_cycle
            ):
                surplus = self._profile.monthly_surplus
                if surplus > 0:
                    self._engine.deposit(portfolio, surplus, note="Renda mensal")
                self._deposit_done_for_cycle = self._engine.market.cycle

            snap = self._engine.snapshot(portfolio) if self._engine and portfolio else {}

            return MainPage(
                master=self,
                player_name=self._profile.name if self._profile else "Aventureiro",
                cash=snap.get("cash", 0.0),
                net_worth=snap.get("net_worth", 0.0),
                cycle=snap.get("cycle", 1),
                fixed_positions=snap.get("fixed_positions", []),
                stock_positions=snap.get("stock_positions", []),
                active_quest=self._active_quest or None,
                on_low_risk=lambda: self._transition(AppState.LOW_RISK),
                on_high_risk=lambda: self._transition(AppState.HIGH_RISK),
                on_end_month=lambda: self._transition(AppState.DEBRIEFING),
                fg_color="transparent",
            )

        # ── LOW_RISK ──────────────────────────────────────────────────────────
        if state == AppState.LOW_RISK:
            portfolio = self._current_portfolio()
            snap = self._engine.snapshot(portfolio) if self._engine and portfolio else {}

            # Build product list using the engine's PRODUCTS catalogue + live rates
            products_for_ui = self._build_fixed_products() or None

            # Build open positions from the portfolio snapshot
            open_positions = [
                {**pos, "index": i, "label": pos.get("label", pos.get("product", ""))}
                for i, pos in enumerate(snap.get("fixed_positions", []))
            ]

            def on_invest(label: str, amount: float):
                p = self._current_portfolio()
                if not self._engine or not p:
                    self._transition(AppState.SIMULATOR_MAIN)
                    return
                from src.Simulator.fixed_income import FixedIncomeType as _FIT
                _label_to_type: dict[str, _FIT] = {ft.value: ft for ft in _FIT}
                ft = _label_to_type.get(label)
                if ft is None:
                    print(f"[LOW RISK] Produto desconhecido: {label}")
                    self._transition(AppState.SIMULATOR_MAIN)
                    return
                try:
                    self._engine.buy_fixed(p, ft, amount)
                    if self._profile: _save_portfolio(self._engine, self._profile)
                except ValueError as exc:
                    print(f"[LOW RISK] Erro ao investir: {exc}")
                self._transition(AppState.SIMULATOR_MAIN)

            def on_redeem(position_index: int):
                p = self._current_portfolio()
                if not self._engine or not p:
                    self._transition(AppState.SIMULATOR_MAIN)
                    return
                try:
                    self._engine.redeem_fixed(p, position_index)
                    if self._profile: _save_portfolio(self._engine, self._profile)
                except ValueError as exc:
                    print(f"[LOW RISK] Erro ao resgatar: {exc}")
                self._transition(AppState.SIMULATOR_MAIN)

            return LowRiskInvestmentsPage(
                master=self,
                products=products_for_ui,
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
                        if self._profile: _save_portfolio(self._engine, self._profile)
                    except Exception as e:
                        print(f"[HIGH RISK] Erro ao comprar: {e}")
                self._transition(AppState.SIMULATOR_MAIN)

            def on_sell(ticker: str, shares: float):
                p = self._current_portfolio()
                if self._engine is not None and p is not None:
                    try:
                        proceeds = self._engine.sell_stock(p, ticker, shares)
                        print(f"[HIGH RISK] Vendido {shares} cotas de {ticker} → R$ {proceeds:.2f}")
                        if self._profile: _save_portfolio(self._engine, self._profile)
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

            def _show_debriefing(ai_result: dict):
                # Prefer the rich 5-section narrative; fall back to summary
                feedback = ai_result.get("narrative") or ai_result.get(
                    "summary",
                    "Continue investindo com disciplina! "
                    "Mantenha sua reserva de emergência antes de buscar maior retorno.",
                )

                # ── All scores come exclusively from the AI result ─────────────
                # score       → overall badge (🏆 / ⚡ / 💀)
                # objective_score, allocation_score, risk_score → sub-score pills
                # Using a single source of truth avoids contradictory values.
                quest_completed  = ai_result.get("score", 50)
                quest_tip        = ai_result.get("quest_tip", "")
                objective_score  = ai_result.get("objective_score")
                allocation_score = ai_result.get("allocation_score")
                risk_score       = ai_result.get("risk_score")

                # Goal progress fields
                goal_p_snap = snap.get("goal_progress", {})
                goal_name = self._profile.goal if self._profile else ""
                goal_completion_pct = goal_p_snap.get("completion_pct", 0.0)
                goal_amount = goal_p_snap.get("goal_amount", 0.0)
                goal_remaining_r = max(0.0, goal_amount - nw)

                def on_continue():
                    self._maybe_confirm_profile_update(
                        ai_result=ai_result,
                        on_done=lambda: self._transition(AppState.END_MONTH),
                    )

                self._replace_loading(DebriefingPage(
                    master=self,
                    player_name=self._profile.name if self._profile else "Aventureiro",
                    net_worth=nw,
                    net_worth_change=change,
                    cash_pct=alloc.get("cash_pct", 0.0),
                    fixed_pct=alloc.get("fixed_pct", 0.0),
                    stocks_pct=alloc.get("stocks_pct", 0.0),
                    cycles_played=snap.get("cycle", 1),
                    agent_feedback=feedback,
                    quest_score=quest_completed,
                    on_continue=on_continue,
                    goal_name=goal_name,
                    goal_completion_pct=goal_completion_pct,
                    goal_remaining_r=goal_remaining_r,
                    objective_score=objective_score,
                    allocation_score=allocation_score,
                    risk_score=risk_score,
                    quest_tip=quest_tip,
                    fg_color="transparent",
                ))

            self._run_in_background(
                task=lambda: self._evaluate_quest(portfolio, snap),
                on_done=_show_debriefing,
                message="O Conselheiro Real está avaliando seu desempenho…",
            )
            return LoadingPage(
                master=self,
                message="O Conselheiro Real está avaliando seu desempenho…",
                sub_message="Aguarde enquanto seu relatório é preparado.",
                fg_color="transparent",
            )

        # ── END_MONTH ─────────────────────────────────────────────────────────
        if state == AppState.END_MONTH:
            result = None
            if self._engine:
                result = self._engine.advance_cycle()
                self._last_cycle_result = result
                if self._profile: _save_portfolio(self._engine, self._profile)
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
        """Transition to the quest screen; generation runs in the background."""
        self._transition(AppState.QUEST_GENERATED)

    def _request_ai_debriefing(self, snap: dict, quest_completed: bool) -> str:
        """
        Calls the AI engine for a debriefing narrative.
        Returns a fallback string if the AI is unavailable.
        """
        # TODO: re-enable AI calls when testing is done
        # try:
        #     api_key = os.environ.get("BOBSHELL_API_KEY", "")
        #     from src.Ai.engine import Engine as AiEngine
        #     from src.Ai.bob import Bob
        #     bob = Bob(email="", password=api_key)
        #     bob.login()
        #     ai = AiEngine(bob)
        #     market_snap = self._engine.market_snapshot() if self._engine else {}
        #     full_ctx = {**snap, **market_snap}
        #     ai.send_simulator_context(full_ctx)
        #     portfolio = self._current_portfolio()
        #     actions = portfolio.transaction_log[-20:] if portfolio else []
        #     ai.send_player_actions(actions, cycle=snap.get("cycle"))
        #     cycle_result_dict = {}
        #     if self._last_cycle_result:
        #         cycle_result_dict = {
        #             "cycle": self._last_cycle_result.cycle,
        #             "market_events": self._last_cycle_result.market_events,
        #             "stock_events": self._last_cycle_result.stock_events,
        #             "portfolio_summaries": self._last_cycle_result.portfolio_summaries,
        #         }
        #     raw = ai.send_debriefing_request(
        #         quest_type=self._active_quest.get("type", "acumulação"),
        #         quest_objective=self._active_quest.get("objective", ""),
        #         objective_achieved=quest_completed,
        #         cycle_result=cycle_result_dict,
        #     )
        #     for line in raw.splitlines():
        #         if "PONTUAÇÃO:" in line.upper():
        #             try:
        #                 score_str = line.upper().split("PONTUAÇÃO:")[-1].strip()
        #                 score = int(score_str.split("/")[0].strip())
        #                 self._quest_scores.append(score)
        #             except (ValueError, IndexError):
        #                 pass
        #     return raw
        # except Exception as e:
        #     print(f"[DEBRIEFING] Falha ao obter feedback via IA: {e}")

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

    def _run_in_background(
        self,
        task: Callable[[], Any],
        on_done: Callable[[Any], None],
        message: str = "Processando…",
    ) -> None:
        """
        Executa *task* em uma thread separada para não bloquear a UI.
        Quando a tarefa termina, agenda a chamada de *on_done(result)*
        de volta no thread principal do Tkinter via `after()`.

        Args:
            task:     Função sem argumentos que retorna o resultado.
            on_done:  Callback chamado no thread principal com o resultado.
            message:  Texto de contexto (usado apenas para rastreabilidade).
        """
        def _worker():
            try:
                result = task()
            except Exception as exc:
                print(f"[BG] Erro em tarefa de background ({message}): {exc}")
                result = {}
            # Agenda a continuação no thread principal do Tkinter
            self.after(0, lambda: on_done(result))

        # Defer thread start by one event-loop tick so the loading page is
        # fully packed and painted before the worker (which may finish almost
        # instantly for sync stubs) schedules on_done back on the main thread.
        self.after(50, lambda: threading.Thread(target=_worker, daemon=True).start())

    def _replace_loading(self, new_frame: ctk.CTkFrame) -> None:
        """
        Substitui a tela de loading atual pelo *new_frame* fornecido.
        Deve ser chamado apenas no thread principal do Tkinter (via after()).
        """
        if self._current_frame is not None:
            # Stop the indeterminate progress-bar animation before destroying
            # the frame so its pending after() callbacks don't keep firing
            # against a dead widget and corrupt the Tkinter event queue.
            if isinstance(self._current_frame, LoadingPage):
                self._current_frame.stop()
            self._current_frame.destroy()
            self._current_frame = None
        new_frame.pack(fill="both", expand=True)
        self._current_frame = new_frame

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
        # TODO: re-enable AI calls when testing is done
        # from src.Ai.engine import Engine as AiEngine
        # from src.Ai.bob import Bob
        # lib = self._ensure_study_library()
        # profile_dict = { ... }
        # try:
        #     api_key = os.environ.get("BOB_API_KEY", "")
        #     bob = Bob(email="", password=api_key)
        #     bob.login()
        #     ai = AiEngine(bob)
        #     raw = ai.generate_study_content(...)
        #     data = json.loads(raw)
        #     lib.add(StudyContent(...))
        # except Exception as e:
        #     print(f"[STUDY] Falha ao gerar conteúdo via IA: {e}")

        lib = self._ensure_study_library()
        topic = requested_topic or "Reserva de Emergência"
        content = StudyContent(
            id=str(uuid.uuid4()),
            topic=topic,
            source_text=(
                "A reserva de emergência é um valor guardado para cobrir imprevistos, "
                "equivalente a 3–6 meses de despesas mensais."
            ),
            adapted_text=(
                f"Pense na reserva de emergência como seu escudo financeiro! "
                f"Guarde de 3 a 6 meses dos seus gastos em um lugar seguro e de fácil acesso, "
                f"como o Tesouro Selic ou um CDB de liquidez diária."
            ),
            quiz=[
                QuizQuestion(
                    question="Qual é o tamanho ideal de uma reserva de emergência?",
                    options=[
                        "1 mês de despesas",
                        "3 a 6 meses de despesas",
                        "1 ano de renda",
                        "Não é necessário ter reserva",
                    ],
                    correct_index=1,
                    explanation="A reserva de emergência deve cobrir de 3 a 6 meses de despesas.",
                )
            ],
            sim_score_at_creation=self._simulator_performance()["avg_score"],
            created_cycle=self._engine.market.cycle if self._engine else 0,
            requested_by_user=requested_topic is not None,
        )
        lib.add(content)

    def _evaluate_mastery(self, content_id: str):
        """
        After a quiz, asks the AI whether the topic has been mastered.
        Updates the library if mastered=True is returned.
        """
        # TODO: re-enable AI calls when testing is done
        # from src.Ai.engine import Engine as AiEngine
        # from src.Ai.bob import Bob
        # lib = self._ensure_study_library()
        # content = lib.get_by_id(content_id)
        # if content is None: return
        # try:
        #     api_key = os.environ.get("BOB_API_KEY", "")
        #     ...
        #     data = json.loads(raw)
        #     if data.get("mastered"): lib.mark_mastered(content_id)
        # except Exception as e:
        #     print(f"[STUDY] Falha ao avaliar domínio via IA: {e}")

        lib = self._ensure_study_library()
        content = lib.get_by_id(content_id)
        if content is None:
            return
        # Static rule: mastered if last quiz score >= 75
        if content.quiz_results and content.quiz_results[-1].score >= 75:
            lib.mark_mastered(content_id)
            print(f"[STUDY] Tema '{content.topic}' marcado como dominado (stub).")

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
        # Use the latest AI-inferred risk/level from history; fall back to
        # the declared profile values only when no inference exists yet.
        last_inference = inf.history[-1] if inf.history else None
        inferred_risk  = last_inference.inferred_risk  if last_inference else self._profile.risk_profile
        inferred_level = last_inference.inferred_level if last_inference else self._profile.knowledge_level

        # Collect recent quest scores for trend analysis
        recent_scores = [e.score for e in inf.history[-5:]] if inf.history else []

        # Mastered topics from the study library (so Bob avoids repeating them)
        lib = self._study_library
        mastered_topics = (
            [c.topic for c in lib.get_all() if c.mastered] if lib else []
        )

        # Current portfolio allocation (so Bob can tailor the quest theme)
        portfolio = self._current_portfolio()
        if portfolio and self._engine:
            snap = self._engine.snapshot(portfolio)
            alloc = snap.get("allocation", {})
            current_net_worth = snap.get("net_worth", 0.0)
        else:
            snap = {}
            alloc = {}
            current_net_worth = 0.0

        # ── Sub-Task 1: goal_urgency ──────────────────────────────────────────
        goal_p = snap.get("goal_progress", {})
        goal_amount = self._profile.goal_amount
        goal_deadline = self._profile.goal_deadline_months
        completed_months = snap.get("cycle", 0)
        months_remaining = max(0, goal_deadline - completed_months)
        completion_pct = goal_p.get("completion_pct", 0.0)
        remaining_r = max(0.0, goal_amount - current_net_worth)
        required_monthly = (remaining_r / months_remaining) if months_remaining > 0 else remaining_r
        on_track = (required_monthly <= self._profile.monthly_surplus) if months_remaining > 0 else completion_pct >= 100.0
        goal_urgency = {
            "on_track":               on_track,
            "months_remaining":       months_remaining,
            "required_monthly_saving": round(required_monthly, 2),
            "current_net_worth":      current_net_worth,
            "goal_amount":            goal_amount,
            "completion_pct":         completion_pct,
        }

        # ── Sub-Task 1: recent_behavior ───────────────────────────────────────
        market_cycle = snap.get("cycle", 0)
        cutoff_cycle = max(0, market_cycle - 2)
        recent_actions = [
            e for e in (portfolio.transaction_log if portfolio else [])
            if e.get("cycle", 0) >= cutoff_cycle
        ]
        trade_actions = {"buy_fixed", "redeem_fixed", "buy_stock", "sell_stock"}
        trade_count = sum(1 for e in recent_actions if e.get("action") in trade_actions)
        cash_history_slice = (portfolio.cash_history[-3:] if portfolio and portfolio.cash_history else [])
        total_nw_slices = [portfolio.net_worth_history[i] for i in range(
            max(0, len(portfolio.net_worth_history) - 3), len(portfolio.net_worth_history)
        )] if portfolio else []
        avg_cash_pct = 0.0
        if cash_history_slice and total_nw_slices:
            pairs = zip(cash_history_slice, total_nw_slices)
            cash_pcts = [c / nw * 100 if nw > 0 else 100.0 for c, nw in pairs]
            avg_cash_pct = round(sum(cash_pcts) / len(cash_pcts), 1)
        cash_hoard_cycles = sum(
            1 for c, nw in zip(cash_history_slice, total_nw_slices)
            if nw > 0 and (c / nw) > 0.5
        )
        # Determine dominant asset class from recent buys
        class_counts: dict = {}
        for e in recent_actions:
            action = e.get("action", "")
            if action in ("buy_fixed", "redeem_fixed"):
                class_counts["renda_fixa"] = class_counts.get("renda_fixa", 0) + 1
            elif action in ("buy_stock", "sell_stock"):
                class_counts["renda_variavel"] = class_counts.get("renda_variavel", 0) + 1
        dominant_asset_class = max(class_counts, key=lambda k: class_counts[k]) if class_counts else "caixa"
        recent_behavior = {
            "cycles_analyzed":    min(3, market_cycle + 1),
            "trade_count":        trade_count,
            "cash_hoard_cycles":  cash_hoard_cycles,
            "avg_cash_pct":       avg_cash_pct,
            "dominant_asset_class": dominant_asset_class,
        }

        learning_ctx = {
            "last_score":           inf.last_score,
            "completed_quests":     inf.completed_quests,
            "main_weakness":        inf.main_weakness,
            "last_quest_type":      self._active_quest.get("type", "nenhuma"),
            "inferred_risk":        inferred_risk,
            "inferred_level":       inferred_level,
            "recent_scores":        recent_scores,
            "mastered_topics":      mastered_topics,
            "portfolio_allocation": alloc,
            "current_net_worth":    current_net_worth,
            "goal_urgency":         goal_urgency,
            "recent_behavior":      recent_behavior,
        }

        # Quest type chosen randomly among the three types
        q_type = random.choice(["acumulação", "sobrevivência", "evento"])

        try:
            api_key = os.environ.get("BOB_API_KEY", "")
            bob = Bob(email="", password=api_key)
            bob.login()
            ai = AiEngine(bob)
            ai.initialize_session(
                name=self._profile.name,
                incomes=[{"source": "Renda mensal", "amount": self._profile.monthly_income}],
                outcomes=[{"category": "Gastos fixos", "amount": self._profile.monthly_expenses}],
                debts=[],
            )
            if portfolio and self._engine:
                # Merge the full portfolio snapshot (cash, net_worth, positions,
                # allocation, emergency_fund, goal_progress) with the market
                # snapshot (selic, inflation, available stocks and fixed products)
                # so the agent sees the real cash on hand when crafting the quest.
                full_ctx = {**snap, **self._engine.market_snapshot()}
                ai.send_simulator_context(full_ctx)
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

        # ── Sub-Task 2: AI quest evaluation ──────────────────────────────────
        # Use last-3-cycles window, same as the behavioural summary
        current_cycle = snap.get("cycle", 0)
        cutoff = max(0, current_cycle - 2)
        actions = [
            e for e in portfolio.transaction_log
            if e.get("cycle", 0) >= cutoff
        ]

        try:
            api_key = os.environ.get("BOB_API_KEY", "")
            bob = Bob(email="", password=api_key)
            bob.login()
            ai = AiEngine(bob)
            raw = ai.analyze_quest_performance(
                quest=self._active_quest,
                actions=actions,
                portfolio_snapshot=snap,
                current_profile=current_profile,
                inference_history=history_dicts,
            )
            data = json.loads(raw)

            # Normalise all numeric scores to int 0–100 (single source of truth)
            score      = min(max(int(data.get("score",            50)), 0), 100)
            obj_score  = min(max(int(data.get("objective_score",  50)), 0), 100)
            alloc_score = min(max(int(data.get("allocation_score", 50)), 0), 100)
            risk_score_ = min(max(int(data.get("risk_score",       50)), 0), 100)
            data["score"]            = score
            data["objective_score"]  = obj_score
            data["allocation_score"] = alloc_score
            data["risk_score"]       = risk_score_

            # Validate enum fields; fall back to current profile on invalid values
            _valid_risk  = {"conservador", "moderado", "arrojado"}
            _valid_level = {"iniciante", "intermediário", "avançado"}
            if data.get("inferred_risk") not in _valid_risk:
                data["inferred_risk"] = self._profile.risk_profile
            if data.get("inferred_level") not in _valid_level:
                data["inferred_level"] = self._profile.knowledge_level

            # Fill any missing keys with safe defaults
            data.setdefault("summary", (
                "Continue investindo com disciplina! "
                "Mantenha sua reserva de emergência antes de buscar maior retorno."
            ))
            data.setdefault("main_weakness", "diversificação")
            data.setdefault("reasoning", "")
            data.setdefault("quest_tip", "Experimente diversificar entre renda fixa e variável.")
            data.setdefault("narrative", "")

            # Record inference entry
            entry = ProfileInferenceEntry(
                cycle=current_cycle,
                score=score,
                main_weakness=data["main_weakness"],
                inferred_risk=data["inferred_risk"],
                inferred_level=data["inferred_level"],
                reasoning=data["reasoning"],
            )
            self._inference_state.record(entry)
            self._quest_scores.append(score)
            return data

        except Exception as e:
            print(f"[QUEST] Falha ao avaliar quest via IA: {e}")

        # Static stub fallback — keep all score fields consistent
        score = 50
        self._quest_scores.append(score)
        return {
            "score":            score,
            "objective_score":  50,
            "allocation_score": 50,
            "risk_score":       50,
            "summary": (
                "Continue investindo com disciplina! "
                "Mantenha sua reserva de emergência antes de buscar maior retorno."
            ),
            "main_weakness":   "diversificação",
            "inferred_risk":   self._profile.risk_profile,
            "inferred_level":  self._profile.knowledge_level,
            "reasoning":       "Avaliação automática (modo de teste — IA desativada).",
            "quest_tip":       "Experimente diversificar entre renda fixa e variável.",
        }

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

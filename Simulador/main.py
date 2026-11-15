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

from src.Simulator.auth import hash_password, verify_password

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
from src.Interfaces.loginPage import LoginPage as LoginPageUI
from src.Interfaces.setPasswordDialog import SetPasswordDialog
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")
from src.Interfaces.loading import LoadingPage


# ─────────────────────────────────────────────────────────────────────────────
# State enumeration — mirrors every node in states_ibm.json
# ─────────────────────────────────────────────────────────────────────────────

class AppState(Enum):
    INICIAL              = auto()   # i2zG1y6y6l51
    LOGIN                = auto()   # tela de seleção/login de perfil
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
# Profile persistence  (multi-profile layout)
#
# Layout on disk:
#   data/profiles/
#     <user_id>/
#       profile.json    ← InvestorProfile (includes password_hash)
#       portfolio.json  ← Portfolio state
#
# Legacy single-profile files (profile.json / portfolio.json at root of
# data/profiles/) are migrated automatically on first load.
# ─────────────────────────────────────────────────────────────────────────────

_PROFILES_DIR        = Path(__file__).parent / "data" / "profiles"
_LEGACY_PROFILE_FILE = _PROFILES_DIR / "profile.json"
_LEGACY_PORTFOLIO_FILE = _PROFILES_DIR / "portfolio.json"


def _profile_dir(user_id: str) -> Path:
    return _PROFILES_DIR / user_id


def _profile_file(user_id: str) -> Path:
    return _profile_dir(user_id) / "profile.json"


def _portfolio_file(user_id: str) -> Path:
    return _profile_dir(user_id) / "portfolio.json"


def _migrate_legacy_profile() -> None:
    """
    Move the old single-profile files into the new per-user-id folder layout,
    so existing saves are not lost on first upgrade.
    """
    if not _LEGACY_PROFILE_FILE.exists():
        return
    try:
        data = json.loads(_LEGACY_PROFILE_FILE.read_text(encoding="utf-8"))
        uid = data.get("user_id")
        if not uid:
            return
        dest_dir = _profile_dir(uid)
        dest_dir.mkdir(parents=True, exist_ok=True)
        # Only migrate if the new location doesn't already exist
        if not _profile_file(uid).exists():
            # Ensure password_hash field present (old saves won't have it)
            data.setdefault("password_hash", "")
            _profile_file(uid).write_text(
                json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        if _LEGACY_PORTFOLIO_FILE.exists() and not _portfolio_file(uid).exists():
            import shutil
            shutil.copy2(_LEGACY_PORTFOLIO_FILE, _portfolio_file(uid))
        # Remove legacy files after successful migration
        _LEGACY_PROFILE_FILE.unlink(missing_ok=True)
        _LEGACY_PORTFOLIO_FILE.unlink(missing_ok=True)
    except Exception as exc:
        print(f"[migrate] Aviso: falha ao migrar perfil legado: {exc}")


def _save_profile(profile: InvestorProfile) -> Path:
    """Serialise *profile* to its per-user-id folder."""
    dest = _profile_dir(profile.user_id)
    dest.mkdir(parents=True, exist_ok=True)
    _profile_file(profile.user_id).write_text(
        json.dumps(asdict(profile), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return _profile_file(profile.user_id)


def _load_all_profiles() -> list[InvestorProfile]:
    """Return all saved InvestorProfiles sorted by name."""
    _migrate_legacy_profile()
    profiles = []
    if not _PROFILES_DIR.exists():
        return profiles
    for uid_dir in _PROFILES_DIR.iterdir():
        if not uid_dir.is_dir():
            continue
        pf = uid_dir / "profile.json"
        if not pf.exists():
            continue
        try:
            data = json.loads(pf.read_text(encoding="utf-8"))
            data.setdefault("password_hash", "")
            profiles.append(InvestorProfile(**data))
        except Exception as exc:
            print(f"[load] Aviso: falha ao carregar perfil em {uid_dir}: {exc}")
    profiles.sort(key=lambda p: p.name.lower())
    return profiles


def _load_profile(user_id: str) -> Optional[InvestorProfile]:
    """Load a single profile by user_id."""
    pf = _profile_file(user_id)
    if not pf.exists():
        return None
    data = json.loads(pf.read_text(encoding="utf-8"))
    data.setdefault("password_hash", "")
    return InvestorProfile(**data)


# ─────────────────────────────────────────────────────────────────────────────
# Portfolio persistence
# ─────────────────────────────────────────────────────────────────────────────

def _save_portfolio(
    engine: "SimulatorEngine",
    profile: InvestorProfile,
    deposit_done_cycle: int = -1,
) -> None:
    """
    Serialise the portfolio's mutable state to its per-user-id folder.

    Saves:
      - cash
      - fixed_positions  (enough to reconstruct each FixedIncomePosition)
      - stock_positions   (enough to reconstruct each StockPosition)
      - net_worth_history, cash_history
      - transaction_log
      - market cycle + SELIC (so earnings stay consistent on reload)
      - deposit_done_cycle: the cycle for which the monthly deposit was already
        made, so a reload mid-cycle does not trigger a second deposit.
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
            "is_emergency_fund":  pos.is_emergency_fund,
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
        "deposit_done_cycle": deposit_done_cycle,
    }

    dest_dir = _profile_dir(profile.user_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    _portfolio_file(profile.user_id).write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _load_portfolio(engine: "SimulatorEngine", profile: InvestorProfile) -> int:
    """
    Restore the portfolio from its per-user-id folder into *engine*.
    Returns the saved ``deposit_done_cycle`` value (default -1).

    Must be called AFTER engine.create_portfolio() so the Portfolio object
    already exists in engine.portfolios.
    """
    pf = _portfolio_file(profile.user_id)
    if not pf.exists():
        return -1

    from src.Simulator.fixed_income import FixedIncomeType, PRODUCTS, FixedIncomePosition
    from src.Simulator.variable_income import StockPosition

    data = json.loads(pf.read_text(encoding="utf-8"))
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
            is_emergency_fund=fp.get("is_emergency_fund", False),
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
        self._profile: Optional[InvestorProfile] = None
        self._last_cycle_result = None   # CycleResult from advance_cycle()
        # tracks whether the monthly deposit was already done for the current cycle
        self._deposit_done_for_cycle: int = -1

        # ── study library (one instance per profile, loaded lazily) ───────────
        self._study_library: Optional[StudyLibrary] = None
        # tracks quest scores for mastery evaluation
        self._quest_scores: list[int] = []

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

        # ── start — always go to login screen ────────────────────────────────
        self._transition(AppState.LOGIN)

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

        # ── LOGIN ─────────────────────────────────────────────────────────────
        if state in (AppState.LOGIN, AppState.INICIAL):
            profiles_data = [
                {
                    "user_id":      p.user_id,
                    "name":         p.name,
                    "goal":         p.goal,
                    "has_password": bool(p.password_hash),
                }
                for p in _load_all_profiles()
            ]

            def on_select(user_id: str, password: str):
                loaded = _load_profile(user_id)
                if loaded is None:
                    return
                # Senha incorreta?
                if loaded.password_hash and not verify_password(password, loaded.password_hash):
                    # Exibe a mensagem de erro na tela existente, sem recriar
                    if isinstance(self._current_frame, LoginPageUI):
                        self._current_frame.show_error("❌  Senha incorreta. Tente novamente.")
                    return
                # Login bem-sucedido
                self._profile = loaded
                self._engine = SimulatorEngine()
                self._engine.create_portfolio(loaded, initial_cash=loaded.monthly_surplus)
                self._deposit_done_for_cycle = _load_portfolio(self._engine, loaded)
                self._study_library = None
                self._quest_scores = []
                self._inference_state = ProfileInferenceState()
                self._active_quest = {}
                self._quest_start_snapshot = {}
                self._quest_start_log_len = 0
                self._transition(AppState.HUB)

            return LoginPageUI(
                master=self,
                profiles=profiles_data,
                on_select=on_select,
                on_create_new=lambda: self._transition(AppState.CREATE_PROFILE),
                fg_color="transparent",
            )

        # ── CREATE_PROFILE ────────────────────────────────────────────────────
        if state == AppState.CREATE_PROFILE:
            def on_submit(profile: InvestorProfile):
                # Abre o diálogo de senha antes de salvar
                def on_password(password: str):
                    if password:
                        profile.password_hash = hash_password(password)
                    self._profile = profile
                    self._engine = SimulatorEngine()
                    self._engine.create_portfolio(profile, initial_cash=profile.monthly_surplus)
                    self._salary_deposited = True   # initial cash counts as first deposit
                    _save_profile(profile)
                    _save_portfolio(self._engine, profile, self._deposit_done_for_cycle)
                    self._transition(AppState.HUB)

                SetPasswordDialog(
                    master=self,
                    profile_name=profile.name,
                    on_confirm=on_password,
                )

            return CreateProfilePage(
                master=self,
                on_submit=on_submit,
                fg_color="transparent",
            )

        # ── HUB ───────────────────────────────────────────────────────────────
        if state == AppState.HUB:
            portfolio = self._current_portfolio()
            snap = self._engine.snapshot(portfolio) if self._engine and portfolio else {}

            def on_switch_profile():
                self._profile = None
                self._engine = None
                self._study_library = None
                self._quest_scores = []
                self._inference_state = ProfileInferenceState()
                self._active_quest = {}
                self._quest_start_snapshot = {}
                self._quest_start_log_len = 0
                self._deposit_done_for_cycle = -1
                self._transition(AppState.LOGIN)

            return HubPage(
                master=self,
                player_name=self._profile.name if self._profile else "Aventureiro",
                cycle=snap.get("cycle", 0),
                net_worth=snap.get("net_worth", 0.0),
                on_missions=lambda: self._start_quest(),
                on_study=lambda: self._transition(AppState.STUDY),
                on_reconfigure=lambda: self._transition(AppState.EDIT_PROFILE),
                on_switch_profile=on_switch_profile,
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

            # Seed the library with the first catalogue entry on first visit so
            # the user always has at least one piece of content with a quiz.
            if not lib.get_all():
                self._generate_study_content()

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

                    # ── Apply simulator events for "evento" quests ────────────
                    applied: list[dict] = []
                    if (
                        quest_data.get("type") == "evento"
                        and self._engine
                        and portfolio
                    ):
                        for ev in quest_data.get("simulator_events", []):
                            try:
                                ev_type = ev.get("type", "")
                                amount  = float(ev.get("amount", 0))
                                desc    = ev.get("description", "Evento")
                                if ev_type not in ("income_bonus", "expense_shock"):
                                    continue
                                if amount <= 0:
                                    continue
                                self._engine.apply_event(portfolio, ev_type, amount, desc)
                                applied.append({"type": ev_type, "amount": amount, "description": desc})
                            except Exception as exc:
                                print(f"[EVENTO] Falha ao aplicar evento {ev}: {exc}")
                        if applied:
                            self._active_quest["applied_events"] = applied
                            if self._profile:
                                _save_portfolio(self._engine, self._profile, self._deposit_done_for_cycle)

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
                    cycles_total=int(quest_data.get("cycles_total", 1)),
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

            def on_invest(label: str, amount: float, emergency_fund: bool = False):
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
                    self._engine.buy_fixed(p, ft, amount, emergency_fund=emergency_fund)
                    if self._profile: _save_portfolio(self._engine, self._profile, self._deposit_done_for_cycle)
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
                    if self._profile: _save_portfolio(self._engine, self._profile, self._deposit_done_for_cycle)
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

            # Build stock list from real engine market data.
            # Strip internal-only fields (trend, cycles_in_trend) before
            # passing to the UI — players should not see the engine's hidden state.
            _HIDDEN = {"trend", "cycles_in_trend"}
            stocks = [
                {k: v for k, v in self._engine.stocks[t].snapshot().items() if k not in _HIDDEN}
                for t in self._engine.stocks
            ] if self._engine else []

            portfolio_positions = snap.get("stock_positions", [])

            def on_buy(ticker: str, amount: float):
                p = self._current_portfolio()
                if self._engine is not None and p is not None:
                    try:
                        self._engine.buy_stock(p, ticker, amount)
                        print(f"[HIGH RISK] Comprado R$ {amount:.2f} de {ticker}")
                        if self._profile: _save_portfolio(self._engine, self._profile, self._deposit_done_for_cycle)
                    except Exception as e:
                        print(f"[HIGH RISK] Erro ao comprar: {e}")
                self._transition(AppState.SIMULATOR_MAIN)

            def on_sell(ticker: str, shares: float):
                p = self._current_portfolio()
                if self._engine is not None and p is not None:
                    try:
                        proceeds = self._engine.sell_stock(p, ticker, shares)
                        print(f"[HIGH RISK] Vendido {shares} cotas de {ticker} → R$ {proceeds:.2f}")
                        if self._profile: _save_portfolio(self._engine, self._profile, self._deposit_done_for_cycle)
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

                # All scores come exclusively from the AI result
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

                # ── Multi-cycle quest: determine if there are more cycles left ──
                current_cycle = snap.get("cycle", 0)
                start_cycle   = (self._quest_start_snapshot or {}).get("cycle", current_cycle)
                cycles_played = max(1, current_cycle - start_cycle + 1)
                cycles_total  = int(self._active_quest.get("cycles_total", 1))
                quest_continues = cycles_played < cycles_total

                def on_continue():
                    # For the final cycle (or single-cycle quests), confirm profile
                    # update then advance to END_MONTH normally.
                    # For intermediate cycles, skip profile update and just advance.
                    if quest_continues:
                        self._transition(AppState.END_MONTH)
                    else:
                        self._maybe_confirm_profile_update(
                            ai_result=ai_result,
                            on_done=lambda: self._transition(AppState.END_MONTH),
                        )

                # ── Badge label: show cycle progress for multi-cycle quests ─────
                if cycles_total > 1:
                    cycle_label = f"Ciclo {cycles_played} de {cycles_total}"
                else:
                    cycle_label = None

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
                    quest_continues=quest_continues,
                    quest_cycle_label=cycle_label,
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
                if self._profile: _save_portfolio(self._engine, self._profile, self._deposit_done_for_cycle)
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

    def _is_quest_multi_cycle_active(self) -> bool:
        """
        Returns True when there is an ongoing multi-cycle quest that still has
        remaining cycles to play (i.e. the user should continue it rather than
        generating a new one).
        """
        if not self._active_quest:
            return False
        cycles_total = int(self._active_quest.get("cycles_total", 1))
        if cycles_total <= 1:
            return False
        # Compare current simulator cycle against the cycle when the quest started
        current_cycle = self._engine.market.cycle if self._engine else 0
        start_cycle   = self._quest_start_snapshot.get("cycle", current_cycle)
        cycles_played = max(1, current_cycle - start_cycle + 1)
        return cycles_played < cycles_total

    def _start_quest(self):
        """
        Transition to the quest screen.
        If a multi-cycle quest is still running, go straight to SIMULATOR_MAIN
        (skipping generation) so the user continues the same quest.
        """
        if self._is_quest_multi_cycle_active():
            self._transition(AppState.SIMULATOR_MAIN)
        else:
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

    # ------------------------------------------------------------------
    # Catálogo estático de materiais de estudo
    # Baseado em evidências da literatura de finanças pessoais e
    # investimentos (referências: Scite.ai — Thaler & Sunstein 2008,
    # Benartzi & Thaler 2001, Malkiel 2019, Bogle 2007, Lusardi & Mitchell
    # 2014, Sharpe 1964, Markowitz 1952, entre outros).
    # ------------------------------------------------------------------
    _STUDY_CATALOGUE: list[dict] = [
        {
            "topic": "Reserva de Emergência",
            "source_text": (
                "A reserva de emergência é um colchão de liquidez recomendado para cobrir "
                "despesas inesperadas sem recorrer a dívidas caras. A literatura de finanças "
                "comportamentais (Thaler & Sunstein, 2008) mostra que a ausência de reserva "
                "é um dos principais gatilhos de estresse financeiro e de decisões sub-ótimas "
                "sob pressão. Estudos recomendam entre 3 e 6 meses de despesas mensais fixas, "
                "alocados em ativos de alta liquidez e baixo risco (ex: Tesouro Selic, CDB de "
                "liquidez diária ou fundo DI com taxa zero)."
            ),
            "adapted_text": (
                "Pense na reserva de emergência como seu escudo financeiro!\n\n"
                "Guarde de 3 a 6 meses dos seus gastos mensais em um lugar seguro e de fácil "
                "acesso — Tesouro Selic ou CDB com liquidez diária são ótimas opções.\n\n"
                "Sem ela, qualquer imprevisto (carro quebrado, demissão, problema de saúde) "
                "pode te forçar a usar cartão de crédito ou empréstimo com juros altíssimos. "
                "Monte a reserva antes de pensar em qualquer outro investimento."
            ),
            "quiz": [
                QuizQuestion(
                    question="Qual é o tamanho ideal de uma reserva de emergência?",
                    options=[
                        "1 mês de despesas",
                        "3 a 6 meses de despesas",
                        "1 ano de renda bruta",
                        "Não é necessário ter reserva",
                    ],
                    correct_index=1,
                    explanation=(
                        "3 a 6 meses de despesas mensais é o intervalo recomendado pela maior "
                        "parte da literatura de finanças pessoais. Autônomos e quem tem renda "
                        "variável devem mirar nos 6 meses."
                    ),
                ),
                QuizQuestion(
                    question="Qual é o melhor lugar para guardar a reserva de emergência?",
                    options=[
                        "Poupança com liquidez em 30 dias",
                        "Ações de empresas sólidas",
                        "Tesouro Selic ou CDB com liquidez diária",
                        "Fundo imobiliário (FII)",
                    ],
                    correct_index=2,
                    explanation=(
                        "A reserva precisa estar em ativos com liquidez imediata e sem risco de "
                        "perda. Tesouro Selic e CDB de liquidez diária atendem a esses critérios "
                        "e ainda rendem mais do que a poupança tradicional."
                    ),
                ),
            ],
        },
        {
            "topic": "Juros Compostos",
            "source_text": (
                "Os juros compostos (Albert Einstein teria chamado de 'oitava maravilha do mundo') "
                "são calculados sobre o montante acumulado, não apenas sobre o principal. "
                "Matematicamente: M = P × (1 + i)^n. A pesquisa de Lusardi & Mitchell (2014, "
                "Journal of Economic Literature) demonstra que a compreensão de juros compostos "
                "é o indicador de literacia financeira mais fortemente correlacionado com "
                "acumulação de riqueza ao longo da vida. Começar cedo amplifica drasticamente "
                "o efeito — duplicar o prazo de investimento multiplica o resultado final de "
                "forma exponencial, não linear."
            ),
            "adapted_text": (
                "Juros compostos são os juros que rendem sobre juros — e é por isso que tempo "
                "é o seu maior aliado nos investimentos!\n\n"
                "Exemplo prático: R$ 1.000 a 1% ao mês:\n"
                "• Após 12 meses → R$ 1.127\n"
                "• Após 24 meses → R$ 1.270\n"
                "• Após 60 meses → R$ 1.817\n\n"
                "Quanto mais cedo você começa, menos precisa investir para chegar ao mesmo "
                "resultado. Estudos mostram que quem começa a investir aos 25 anos chega à "
                "aposentadoria com até 3× mais dinheiro do que quem começa aos 35, investindo "
                "o mesmo valor mensal."
            ),
            "quiz": [
                QuizQuestion(
                    question="O que diferencia juros compostos de juros simples?",
                    options=[
                        "Juros compostos têm taxa maior",
                        "Juros compostos incidem sobre o montante acumulado (principal + juros anteriores)",
                        "Juros compostos só existem em investimentos de longo prazo",
                        "Juros simples rendem mais no longo prazo",
                    ],
                    correct_index=1,
                    explanation=(
                        "Nos juros compostos, a cada período os juros são calculados sobre o "
                        "total acumulado (principal + juros anteriores), gerando crescimento "
                        "exponencial. Nos juros simples, a base é sempre o principal original."
                    ),
                ),
                QuizQuestion(
                    question=(
                        "Por que começar a investir cedo faz tanta diferença nos juros compostos?"
                    ),
                    options=[
                        "Porque as taxas de juros são maiores para jovens",
                        "Porque o imposto de renda é menor para quem investe há mais tempo",
                        "Porque o tempo amplia o efeito exponencial dos rendimentos reinvestidos",
                        "Porque os bancos oferecem produtos exclusivos para investidores jovens",
                    ],
                    correct_index=2,
                    explanation=(
                        "Quanto maior o prazo (n), mais ciclos de reinvestimento ocorrem, "
                        "ampliando o crescimento exponencialmente. Uma diferença de 10 anos "
                        "no início pode mais do que dobrar o patrimônio final."
                    ),
                ),
            ],
        },
        {
            "topic": "Diversificação de Carteira",
            "source_text": (
                "A Teoria Moderna do Portfólio (Markowitz, 1952, Journal of Finance) demonstrou "
                "matematicamente que combinar ativos com correlações baixas ou negativas reduz o "
                "risco total da carteira sem necessariamente sacrificar o retorno esperado. "
                "O risco específico (não-sistemático) pode ser virtualmente eliminado com ~15–20 "
                "ativos descorrelacionados. Estudos posteriores (Statman, 1987) sugerem que a "
                "diversificação completa requer entre 30 e 40 ações. Fundos de índice (ETFs) "
                "permitem diversificação ampla com custos muito baixos."
            ),
            "adapted_text": (
                "Não coloque todos os ovos na mesma cesta — esse ditado popular resume "
                "perfeitamente a diversificação!\n\n"
                "Ao distribuir seus investimentos entre diferentes tipos de ativos (renda fixa, "
                "ações, FIIs, câmbio), você reduz o risco: se um ativo cai, os outros podem "
                "compensar.\n\n"
                "Dica prática: ETFs de índice (ex: BOVA11 no Brasil) já incluem dezenas de "
                "ações de uma vez, com taxas baixas, e são ótimos para diversificar sem "
                "precisar escolher empresa por empresa."
            ),
            "quiz": [
                QuizQuestion(
                    question="O que a diversificação de carteira permite reduzir?",
                    options=[
                        "O risco sistemático (de mercado)",
                        "O risco específico (não-sistemático) dos ativos individuais",
                        "A tributação sobre ganhos de capital",
                        "A volatilidade do câmbio",
                    ],
                    correct_index=1,
                    explanation=(
                        "A diversificação elimina o risco específico de cada ativo (risco "
                        "não-sistemático). O risco de mercado (sistemático), como crises "
                        "econômicas globais, afeta todos os ativos e não pode ser diversificado."
                    ),
                ),
                QuizQuestion(
                    question=(
                        "Qual ferramenta permite diversificar em dezenas de ações com um único "
                        "investimento e baixas taxas?"
                    ),
                    options=[
                        "CDB prefixado",
                        "ETF de índice (ex: BOVA11)",
                        "Tesouro IPCA+",
                        "Fundo de previdência com taxa de carregamento",
                    ],
                    correct_index=1,
                    explanation=(
                        "ETFs (Exchange-Traded Funds) replicam índices de ações e permitem "
                        "exposição a dezenas ou centenas de empresas com uma única compra, "
                        "taxas de administração muito baixas e liquidez diária."
                    ),
                ),
            ],
        },
        {
            "topic": "Tesouro Direto",
            "source_text": (
                "O Tesouro Direto é um programa do Tesouro Nacional que permite a pessoas físicas "
                "investir em títulos públicos federais pela internet desde 2002. Os principais "
                "títulos são: Tesouro Selic (pós-fixado, acompanha a taxa básica de juros), "
                "Tesouro Prefixado (taxa travada na compra) e Tesouro IPCA+ (proteção contra "
                "inflação + taxa real). A literatura de finanças pessoais (Malkiel, 2019) destaca "
                "títulos públicos como a base da alocação conservadora por seu risco soberano "
                "(menor risco de crédito disponível no mercado doméstico) e liquidez diária "
                "no caso do Tesouro Selic."
            ),
            "adapted_text": (
                "O Tesouro Direto é uma das formas mais seguras de investir no Brasil, pois você "
                "está emprestando dinheiro para o governo federal.\n\n"
                "Tipos principais:\n"
                "• Tesouro Selic → rende conforme a taxa Selic (ótimo para reserva de emergência)\n"
                "• Tesouro Prefixado → você sabe exatamente quanto vai receber no vencimento\n"
                "• Tesouro IPCA+ → protege seu dinheiro da inflação e ainda paga um juro real\n\n"
                "Aplique a partir de R$ 30 e pague apenas 0,20% ao ano de taxa de custódia "
                "(e zero taxa de corretagem nas principais corretoras)."
            ),
            "quiz": [
                QuizQuestion(
                    question="Qual título do Tesouro Direto é mais indicado para a reserva de emergência?",
                    options=[
                        "Tesouro Prefixado de longo prazo",
                        "Tesouro IPCA+ com vencimento em 2045",
                        "Tesouro Selic",
                        "Tesouro Renda+",
                    ],
                    correct_index=2,
                    explanation=(
                        "O Tesouro Selic tem liquidez diária e valor de mercado praticamente "
                        "sem oscilação, tornando-o ideal para a reserva de emergência. Os demais "
                        "podem ter marcação a mercado e perdas se resgatados antes do vencimento."
                    ),
                ),
                QuizQuestion(
                    question="O que o Tesouro IPCA+ garante ao investidor?",
                    options=[
                        "Rentabilidade igual à taxa Selic",
                        "Proteção contra a inflação mais uma taxa de juro real fixa",
                        "Isenção de imposto de renda",
                        "Liquidez diária sem perda de rentabilidade",
                    ],
                    correct_index=1,
                    explanation=(
                        "O Tesouro IPCA+ rende IPCA + taxa prefixada (ex: IPCA + 6% a.a.), "
                        "preservando o poder de compra do investidor mesmo em cenários de "
                        "inflação elevada."
                    ),
                ),
            ],
        },
        {
            "topic": "Renda Variável e Ações",
            "source_text": (
                "Ações representam frações do capital social de uma empresa. O retorno histórico "
                "de longo prazo das ações supera o de renda fixa na maioria dos mercados (Siegel, "
                "'Stocks for the Long Run', 2014). Contudo, a volatilidade de curto prazo é alta "
                "— crises podem gerar quedas de 30–50% em meses. A pesquisa comportamental "
                "(Benartzi & Thaler, 2001, American Economic Review) mostrou que investidores "
                "individuais tendem a vender no pior momento (aversão a perdas) e comprar nos "
                "picos (excesso de confiança), destruindo retorno. Estratégias sistemáticas "
                "(aportes regulares, rebalanceamento periódico) mitigam esses vieses."
            ),
            "adapted_text": (
                "Investir em ações significa se tornar sócio de uma empresa — se ela crescer, "
                "você lucra; se ela tiver problemas, o valor da ação cai.\n\n"
                "Pontos-chave:\n"
                "• Ações têm o maior potencial de retorno no longo prazo, mas também maior risco\n"
                "• Nunca invista em ações dinheiro que você pode precisar em menos de 3–5 anos\n"
                "• Aporte regularmente (mesmo pouco) em vez de tentar 'acertar o momento certo'\n"
                "• Diversifique: nunca coloque mais de 10% em uma única empresa\n\n"
                "Estudos mostram que a maioria dos investidores amadores perde para o índice "
                "porque reage à emoção, não à lógica. ETFs de índice são uma alternativa "
                "inteligente para quem está começando."
            ),
            "quiz": [
                QuizQuestion(
                    question=(
                        "Qual é o maior erro comportamental que investidores individuais cometem "
                        "ao investir em ações, segundo a pesquisa de Benartzi & Thaler (2001)?"
                    ),
                    options=[
                        "Diversificar demais a carteira",
                        "Vender nos momentos de queda e comprar nos momentos de alta (aversão a perdas)",
                        "Manter as ações por tempo demais",
                        "Reinvestir os dividendos",
                    ],
                    correct_index=1,
                    explanation=(
                        "A aversão a perdas leva investidores a vender em pânico nas quedas "
                        "(realizando o prejuízo) e a comprar exuberantes nas altas (pagando caro). "
                        "Aportes sistemáticos e regulares são a melhor defesa contra esses vieses."
                    ),
                ),
                QuizQuestion(
                    question="Por que ações são mais indicadas para o longo prazo?",
                    options=[
                        "Porque pagam juros mensais garantidos",
                        "Porque são isentas de imposto de renda",
                        "Porque a volatilidade de curto prazo se dilui ao longo do tempo e os retornos históricos superam a renda fixa",
                        "Porque o governo garante o capital investido",
                    ],
                    correct_index=2,
                    explanation=(
                        "No curto prazo, as ações podem cair muito. No longo prazo, os retornos "
                        "históricos de mercados acionários superam consistentemente os de renda "
                        "fixa, e a volatilidade se dilui com o tempo."
                    ),
                ),
            ],
        },
        {
            "topic": "Fundos Imobiliários (FIIs)",
            "source_text": (
                "Fundos de Investimento Imobiliário (FIIs) são veículos coletivos que investem "
                "em imóveis (shoppings, galpões logísticos, escritórios, hospitais) ou em títulos "
                "imobiliários (CRIs, LCIs). Negociados em bolsa, oferecem liquidez que imóveis "
                "físicos não têm. Os rendimentos distribuídos mensalmente (mínimo 95% do lucro "
                "caixa) são isentos de IR para pessoa física, contanto que o fundo tenha mais "
                "de 50 cotistas e as cotas sejam negociadas em bolsa (Lei nº 11.033/2004). "
                "O risco inclui vacância, inadimplência e variação do mercado imobiliário."
            ),
            "adapted_text": (
                "FIIs permitem que você invista no mercado imobiliário com pouco dinheiro "
                "(a partir de ~R$ 10 por cota) e receba aluguéis mensais diretamente na sua "
                "conta!\n\n"
                "Vantagens:\n"
                "• Renda mensal isenta de imposto de renda para pessoa física\n"
                "• Liquidez: você pode vender as cotas na bolsa a qualquer momento\n"
                "• Diversificação: um único FII já pode incluir dezenas de imóveis\n\n"
                "Fique atento à taxa de vacância (imóveis desocupados) e ao tipo de fundo: "
                "FIIs de tijolo (imóveis físicos) ou de papel (títulos imobiliários como CRI)."
            ),
            "quiz": [
                QuizQuestion(
                    question="Qual é a vantagem tributária dos rendimentos distribuídos por FIIs para pessoa física?",
                    options=[
                        "Alíquota reduzida de 10%",
                        "Isenção total de imposto de renda sobre os rendimentos distribuídos",
                        "Dedução no imposto de renda anual",
                        "Alíquota de 15% com desconto na fonte",
                    ],
                    correct_index=1,
                    explanation=(
                        "Os rendimentos mensais distribuídos por FIIs listados em bolsa com mais "
                        "de 50 cotistas são isentos de IR para pessoa física, tornando-os "
                        "atraentes para quem busca renda passiva."
                    ),
                ),
                QuizQuestion(
                    question="O que é taxa de vacância em um FII de tijolo?",
                    options=[
                        "A taxa de administração cobrada pelo gestor",
                        "O percentual de imóveis desocupados (sem inquilino) no portfólio do fundo",
                        "A rentabilidade esperada do fundo",
                        "O desconto em relação ao valor patrimonial",
                    ],
                    correct_index=1,
                    explanation=(
                        "Vacância indica o percentual de área locável desocupada. Quanto maior "
                        "a vacância, menor a receita de aluguéis e, consequentemente, menor o "
                        "rendimento distribuído aos cotistas."
                    ),
                ),
            ],
        },
        {
            "topic": "Vieses Comportamentais nos Investimentos",
            "source_text": (
                "A Economia Comportamental (Kahneman & Tversky, 1979, Econometrica; Thaler, "
                "Nobel 2017) identificou padrões sistemáticos de irracionalidade em decisões "
                "financeiras. Os principais vieses documentados são: aversão a perdas (perdas "
                "doem ~2× mais do que ganhos equivalentes alegram), excesso de confiança "
                "(superestimação da própria capacidade de selecionar ativos), viés de ancoragem "
                "(dependência excessiva do preço de compra), comportamento de manada (seguir a "
                "multidão) e desconto hiperbólico (preferência por recompensas imediatas "
                "sobre benefícios futuros maiores)."
            ),
            "adapted_text": (
                "Nosso cérebro não foi feito para investir — ele reage às emoções do momento, "
                "não à lógica de longo prazo. Conhecer seus vieses é o primeiro passo para "
                "superá-los!\n\n"
                "Principais armadilhas mentais:\n"
                "• Aversão a perdas: você sofre mais com uma perda de R$ 100 do que se alegra "
                "com um ganho de R$ 100 → evita vender prejuízo e realiza o ganho cedo demais\n"
                "• Excesso de confiança: acha que sabe mais do que o mercado → opera demais e paga taxas desnecessárias\n"
                "• Comportamento de manada: compra quando todo mundo compra (pico) e vende quando todo mundo vende (fundo)\n\n"
                "Solução: automatize seus aportes, defina uma estratégia e não a altere por emoção."
            ),
            "quiz": [
                QuizQuestion(
                    question=(
                        "De acordo com Kahneman & Tversky, quanto as perdas pesam emocionalmente "
                        "em comparação a ganhos de mesmo valor?"
                    ),
                    options=[
                        "Igual — ganhos e perdas têm o mesmo peso emocional",
                        "Perdas pesam cerca de 2× mais do que ganhos equivalentes",
                        "Ganhos pesam mais porque são motivadores",
                        "Depende do perfil de risco do investidor",
                    ],
                    correct_index=1,
                    explanation=(
                        "A Teoria do Prospecto (Kahneman & Tversky, 1979) demonstrou que a dor "
                        "de uma perda é psicologicamente cerca de 2× maior do que o prazer de "
                        "um ganho equivalente — o que explica decisões irracionais como manter "
                        "posições perdedoras indefinidamente."
                    ),
                ),
                QuizQuestion(
                    question="Qual estratégia ajuda a combater o viés do comportamento de manada?",
                    options=[
                        "Acompanhar notícias financeiras diariamente para decidir quando comprar",
                        "Investir apenas em momentos de alta do mercado",
                        "Automatizar aportes periódicos com valor fixo, independentemente do mercado",
                        "Concentrar o capital em poucos ativos de alta convicção",
                    ],
                    correct_index=2,
                    explanation=(
                        "Aportes automáticos e regulares (Dollar-Cost Averaging) eliminam a "
                        "tentação de 'acertar o momento certo' e reduzem o impacto emocional "
                        "das flutuações de mercado, resultando em preço médio mais vantajoso."
                    ),
                ),
            ],
        },
        {
            "topic": "Planejamento de Aposentadoria",
            "source_text": (
                "Pesquisas de Lusardi & Mitchell (2011, American Economic Review) demonstram que "
                "a literacia financeira está fortemente correlacionada com o planejamento de "
                "aposentadoria e a acumulação de riqueza. No Brasil, a Previdência Social (INSS) "
                "tem teto de benefício limitado (R$ 7.786,02 em 2024), tornando a previdência "
                "complementar essencial para quem almeja manter o padrão de vida. Opções: PGBL "
                "(dedução no IR, tributação na saída sobre o total) e VGBL (sem dedução, "
                "tributação só sobre rendimentos). A tabela regressiva do IR favorece resgates "
                "após 10 anos (alíquota mínima de 10%)."
            ),
            "adapted_text": (
                "Quanto mais cedo você começar a poupar para a aposentadoria, menos precisará "
                "guardar por mês — os juros compostos farão o trabalho pesado!\n\n"
                "Pontos essenciais:\n"
                "• O teto do INSS é ~R$ 7.786 — se você ganha mais, precisará complementar\n"
                "• PGBL: indicado para quem declara IR completo (deduz até 12% da renda bruta)\n"
                "• VGBL: indicado para quem declara IR simplificado ou já maximizou o PGBL\n"
                "• Escolha sempre a tabela regressiva (10% após 10 anos) se o objetivo for longo prazo\n\n"
                "Regra prática: invista pelo menos 15% da sua renda mensal para a aposentadoria."
            ),
            "quiz": [
                QuizQuestion(
                    question="Qual produto de previdência privada permite deduzir até 12% da renda bruta no IR?",
                    options=[
                        "VGBL",
                        "PGBL",
                        "CDB de longo prazo",
                        "Tesouro IPCA+",
                    ],
                    correct_index=1,
                    explanation=(
                        "O PGBL (Plano Gerador de Benefício Livre) permite deduzir contribuições "
                        "de até 12% da renda bruta tributável na declaração completa do IR. "
                        "Na saída, o IR incide sobre o valor total resgatado (principal + rendimentos)."
                    ),
                ),
                QuizQuestion(
                    question=(
                        "Na tabela regressiva de IR para previdência privada, qual é a alíquota "
                        "mínima e após quanto tempo ela é atingida?"
                    ),
                    options=[
                        "5% após 5 anos",
                        "10% após 10 anos",
                        "15% após 7 anos",
                        "Zero após 20 anos",
                    ],
                    correct_index=1,
                    explanation=(
                        "Na tabela regressiva, a alíquota começa em 35% (até 2 anos) e cai "
                        "progressivamente até 10% para recursos com mais de 10 anos, tornando "
                        "a previdência privada muito eficiente tributariamente no longo prazo."
                    ),
                ),
            ],
        },
        {
            "topic": "Controle de Dívidas e Taxa de Juros",
            "source_text": (
                "O custo do crédito no Brasil é um dos mais altos do mundo. Em 2024, o rotativo "
                "do cartão de crédito ultrapassou 400% a.a. e o cheque especial frequentemente "
                "supera 100% a.a. A pesquisa comportamental (Stango & Zinman, 2009, Journal of "
                "Finance) demonstra que consumidores subestimam sistematicamente o custo real "
                "do crédito parcelado. A estratégia 'avalanche' (priorizar a dívida de maior "
                "juros) é matematicamente ótima; a estratégia 'bola de neve' (priorizar a menor "
                "dívida) tem evidências comportamentais de maior adesão."
            ),
            "adapted_text": (
                "Dívida cara destrói seu patrimônio muito mais rápido do que qualquer "
                "investimento pode construí-lo. Eliminar dívidas de alto custo é o investimento "
                "com maior retorno garantido que você pode fazer!\n\n"
                "Regra de ouro: se a dívida tem juros maiores do que o rendimento do seu "
                "investimento, pague a dívida primeiro.\n\n"
                "Duas estratégias para sair das dívidas:\n"
                "• Avalanche: pague primeiro a dívida com maior taxa de juros (economiza mais dinheiro)\n"
                "• Bola de neve: pague primeiro a menor dívida (gera motivação para continuar)\n\n"
                "Nunca use o rotativo do cartão de crédito — pague sempre o valor total da fatura."
            ),
            "quiz": [
                QuizQuestion(
                    question=(
                        "Na estratégia 'avalanche' de pagamento de dívidas, qual dívida deve "
                        "ser priorizada?"
                    ),
                    options=[
                        "A dívida com o maior saldo devedor",
                        "A dívida com a maior taxa de juros",
                        "A dívida com o menor prazo restante",
                        "A dívida mais antiga",
                    ],
                    correct_index=1,
                    explanation=(
                        "A estratégia avalanche prioriza a dívida com maior taxa de juros, "
                        "minimizando o custo total pago. É matematicamente superior à bola "
                        "de neve, embora ambas sejam válidas dependendo do perfil do devedor."
                    ),
                ),
                QuizQuestion(
                    question="Por que nunca se deve usar o rotativo do cartão de crédito?",
                    options=[
                        "Porque gera pontos negativos no score de crédito",
                        "Porque os juros do rotativo ultrapassam 400% ao ano no Brasil",
                        "Porque o banco pode cancelar o cartão",
                        "Porque reduz o limite de crédito disponível",
                    ],
                    correct_index=1,
                    explanation=(
                        "O rotativo do cartão de crédito é a modalidade de crédito mais cara "
                        "do Brasil, com taxas que podem superar 400% ao ano. Uma dívida de "
                        "R$ 1.000 no rotativo pode se transformar em mais de R$ 5.000 em 12 meses."
                    ),
                ),
            ],
        },
        {
            "topic": "ETFs e Fundos de Índice",
            "source_text": (
                "John Bogle (fundador da Vanguard, 1975) popularizou os fundos de índice como "
                "alternativa superior à gestão ativa para o investidor individual. Dados "
                "extensivos do SPIVA (S&P Indices vs. Active) mostram que mais de 90% dos "
                "fundos ativos não superam o índice de referência em horizontes de 15+ anos, "
                "principalmente devido aos custos de gestão. ETFs (Exchange-Traded Funds) "
                "combinam a diversificação de fundos de índice com liquidez intraday de ações, "
                "taxas de administração muito baixas (0,05%–0,30% a.a. no Brasil) e "
                "transparência de carteira."
            ),
            "adapted_text": (
                "ETFs são fundos que replicam índices (como o Ibovespa ou o S&P 500) e são "
                "negociados na bolsa como ações. São um dos produtos favoritos de investidores "
                "inteligentes ao redor do mundo!\n\n"
                "Por que ETFs são poderosos:\n"
                "• Diversificação instantânea: um único ETF pode incluir 50, 100 ou 500 empresas\n"
                "• Custo baixíssimo: taxas de 0,05% a 0,30% ao ano, muito menos que fundos ativos\n"
                "• Transparência: você sabe exatamente em quais empresas está investindo\n\n"
                "Estudos mostram que mais de 90% dos fundos de gestão ativa não batem o índice "
                "no longo prazo. Muitas vezes, o simples é o melhor."
            ),
            "quiz": [
                QuizQuestion(
                    question="O que diferencia um ETF de um fundo de investimento tradicional?",
                    options=[
                        "ETFs só investem em renda fixa",
                        "ETFs são negociados em bolsa como ações, têm liquidez intraday e geralmente taxas menores",
                        "ETFs garantem rentabilidade superior à renda fixa",
                        "ETFs são exclusivos para investidores qualificados",
                    ],
                    correct_index=1,
                    explanation=(
                        "ETFs são negociados na bolsa durante o horário de pregão (liquidez "
                        "intraday), têm taxas de administração muito baixas e carteira "
                        "transparente. Fundos tradicionais têm cotas com liquidez em D+1 ou mais."
                    ),
                ),
                QuizQuestion(
                    question=(
                        "Segundo dados do SPIVA, qual percentual de fundos de gestão ativa "
                        "supera o índice de referência em horizontes acima de 15 anos?"
                    ),
                    options=[
                        "Cerca de 50% — metade bate o índice",
                        "Cerca de 70%",
                        "Menos de 10%",
                        "Aproximadamente 30%",
                    ],
                    correct_index=2,
                    explanation=(
                        "Dados históricos do SPIVA mostram consistentemente que menos de 10% "
                        "dos fundos ativos superam seu índice de referência em períodos longos "
                        "(15+ anos), principalmente devido aos custos de gestão e corretagem."
                    ),
                ),
            ],
        },
    ]

    def _generate_study_content(self, requested_topic: str | None = None):
        """
        Selects a StudyContent from the curated catalogue and persists it.
        If the user requests a specific topic, the best matching entry is used;
        otherwise the next uncovered topic in the catalogue is chosen.
        Topics already covered in the library are skipped to avoid duplicates.
        Falls back to the AI engine (when re-enabled) for topics not in the catalogue.
        """
        # TODO: re-enable AI calls when testing is done
        # from src.Ai.engine import Engine as AiEngine
        # from src.Ai.bob import Bob
        # ...

        lib = self._ensure_study_library()
        covered = set(lib.covered_topics())
        cycle   = self._engine.market.cycle if self._engine else 0
        avg     = self._simulator_performance()["avg_score"]

        # --- pick catalogue entry -------------------------------------------
        entry: dict | None = None

        if requested_topic:
            # exact match first, then case-insensitive substring
            norm = requested_topic.strip().lower()
            for e in self._STUDY_CATALOGUE:
                if e["topic"].lower() == norm:
                    entry = e
                    break
            if entry is None:
                for e in self._STUDY_CATALOGUE:
                    if norm in e["topic"].lower() or e["topic"].lower() in norm:
                        entry = e
                        break

        if entry is None:
            # pick the first catalogue topic not yet covered
            for e in self._STUDY_CATALOGUE:
                if e["topic"] not in covered:
                    entry = e
                    break

        if entry is None:
            # all catalogue topics covered — cycle from the beginning
            entry = self._STUDY_CATALOGUE[
                len(covered) % len(self._STUDY_CATALOGUE)
            ]

        # --- build StudyContent ---------------------------------------------
        content = StudyContent(
            id=str(uuid.uuid4()),
            topic=entry["topic"],
            source_text=entry["source_text"],
            adapted_text=entry["adapted_text"],
            quiz=entry["quiz"],
            sim_score_at_creation=avg,
            created_cycle=cycle,
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
            "cycles_total": 1,
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

        # ── Recent study topics (last 5 items studied, most recent first) ─────
        lib = self._study_library
        recent_study_topics: list[dict] = []
        if lib:
            all_contents = lib.get_all()
            # Sort by created_cycle descending
            sorted_contents = sorted(all_contents, key=lambda c: c.created_cycle, reverse=True)
            recent_study_topics = [
                {
                    "topic":   c.topic,
                    "mastered": c.mastered,
                    "cycle":   c.created_cycle,
                }
                for c in sorted_contents[:5]
            ]

        # ── cycles_total_hint: based on inferred level ────────────────────────
        _level_cycles: dict[str, list[int]] = {
            "iniciante":     [1],
            "intermediário": [1, 1, 2],   # mostly 1, occasionally 2
            "avançado":      [2, 2, 3],   # mostly 2-3
        }
        _choices = _level_cycles.get(inferred_level, [1])
        cycles_total_hint = random.choice(_choices)

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
            "recent_study_topics":  recent_study_topics,
            "cycles_total_hint":    cycles_total_hint,
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
            # Clamp cycles_total to [1, 3] and store the quest start cycle
            data["cycles_total"] = max(1, min(3, int(data.get("cycles_total", 1))))
            data["quest_cycle_start"] = snap.get("cycle", 0)
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

        # ── Actions scoped to this quest only (quest-start index) ────────────
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

        # ── cycles_played derived from quest-start snapshot ───────────────────
        current_cycle = snap.get("cycle", 0)
        start_cycle   = (self._quest_start_snapshot or {}).get("cycle", current_cycle)
        cycles_played = max(1, current_cycle - start_cycle + 1)

        # Stamp cycles_played onto the quest dict so the prompt sees it
        quest_for_eval = {**self._active_quest, "cycles_played": cycles_played}

        # ── Recent study topics for the AI ────────────────────────────────────
        lib = self._study_library
        recent_study_topics: list[dict] = []
        if lib:
            sorted_contents = sorted(lib.get_all(), key=lambda c: c.created_cycle, reverse=True)
            recent_study_topics = [
                {"topic": c.topic, "mastered": c.mastered, "cycle": c.created_cycle}
                for c in sorted_contents[:5]
            ]

        try:
            api_key = os.environ.get("BOB_API_KEY", "")
            bob = Bob(email="", password=api_key)
            bob.login()
            ai = AiEngine(bob)

            # Prime Bob with the player's financial profile
            ai.initialize_session(
                name=self._profile.name,
                incomes=[{"source": "Renda mensal", "amount": self._profile.monthly_income}],
                outcomes=[{"category": "Gastos fixos", "amount": self._profile.monthly_expenses}],
                debts=[],
            )

            # Send the market + portfolio context at quest start
            if self._quest_start_snapshot and self._engine:
                start_ctx = {**self._quest_start_snapshot, **self._engine.market_snapshot()}
                ai.send_simulator_context(start_ctx)

            # Remind Bob of the quest it generated
            ai.send_quest_context(quest_for_eval, cycles_played=cycles_played)

            raw = ai.analyze_quest_performance(
                quest=quest_for_eval,
                actions=actions,
                portfolio_snapshot=snap,
                current_profile=current_profile,
                inference_history=history_dicts,
                recent_study_topics=recent_study_topics,
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

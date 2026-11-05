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
from src.Simulator.fixed_income import FixedIncomeType

# ── study library ─────────────────────────────────────────────────────────────
import json
import uuid
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
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")


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
        self.title("Simulador de Investimentos — Finvest")
        self.geometry("680x560")
        self.resizable(False, False)

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
                on_missions=lambda: self._transition(AppState.QUEST_GENERATED),
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
                on_low_risk=lambda: self._transition(AppState.LOW_RISK),
                on_high_risk=lambda: self._transition(AppState.HIGH_RISK),
                on_end_month=lambda: self._transition(AppState.DEBRIEFING),
                fg_color="transparent",
            )

        # ── LOW_RISK ──────────────────────────────────────────────────────────
        if state == AppState.LOW_RISK:
            # Build product list from engine for real data
            _label_to_type: dict[str, FixedIncomeType] = {
                ft.value: ft for ft in FixedIncomeType
            }

            market_snap = self._engine.market_snapshot() if self._engine else {}
            raw_products = market_snap.get("fixed_products", {})
            products_for_ui = [
                {
                    "label": p["label"],
                    "indexer": p.get("indexer", ""),
                    "rate": p.get("description", ""),
                    "maturity": (
                        "Liquidez diária"
                        if p.get("maturity_months", 0) == 0
                        else f"{p['maturity_months']} meses"
                    ),
                    "min": f"R$ {p.get('min_investment', 0):,.2f}",
                    "ir_exempt": p.get("ir_exempt", False),
                }
                for p in raw_products.values()
            ] or None  # falls back to placeholders in the page

            def on_invest(label: str, amount: float):
                portfolio = self._current_portfolio()
                if not self._engine or not portfolio:
                    self._transition(AppState.SIMULATOR_MAIN)
                    return
                ft = _label_to_type.get(label)
                if ft is None:
                    print(f"[LOW RISK] Produto desconhecido: {label}")
                    self._transition(AppState.SIMULATOR_MAIN)
                    return
                try:
                    self._engine.buy_fixed(portfolio, ft, amount)
                except ValueError as exc:
                    print(f"[LOW RISK] Erro ao investir: {exc}")
                self._transition(AppState.SIMULATOR_MAIN)

            return LowRiskInvestmentsPage(
                master=self,
                products=products_for_ui,
                on_invest=on_invest,
                on_back=lambda: self._transition(AppState.SIMULATOR_MAIN),
                fg_color="transparent",
            )

        # ── HIGH_RISK ─────────────────────────────────────────────────────────
        if state == AppState.HIGH_RISK:
            # Build stock list from live engine state
            market_snap = self._engine.market_snapshot() if self._engine else {}
            stocks_for_ui = [
                {
                    "ticker": s["ticker"],
                    "name": s.get("name", s["ticker"]),
                    "price": s["price"],
                    "trend": s.get("trend", "estável"),
                }
                for s in market_snap.get("stocks", {}).values()
            ] or None  # falls back to placeholders in the page

            def on_buy(ticker: str, amount: float):
                portfolio = self._current_portfolio()
                if not self._engine or not portfolio:
                    self._transition(AppState.SIMULATOR_MAIN)
                    return
                try:
                    self._engine.buy_stock(portfolio, ticker, amount)
                except ValueError as exc:
                    print(f"[HIGH RISK] Erro ao comprar {ticker}: {exc}")
                self._transition(AppState.SIMULATOR_MAIN)

            def on_sell(ticker: str, shares: float):
                portfolio = self._current_portfolio()
                if not self._engine or not portfolio:
                    self._transition(AppState.SIMULATOR_MAIN)
                    return
                try:
                    self._engine.sell_stock(portfolio, ticker, shares)
                except ValueError as exc:
                    print(f"[HIGH RISK] Erro ao vender {ticker}: {exc}")
                self._transition(AppState.SIMULATOR_MAIN)

            return HighRiskInvestmentsPage(
                master=self,
                stocks=stocks_for_ui,
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

            # Evaluate acumulação quest objective before requesting AI debriefing
            if self._active_quest.get("type", "acumulação") == "acumulação":
                ef = snap.get("emergency_fund", {})
                goal_p = snap.get("goal_progress", {})
                # Victory: emergency fund adequate OR net-worth gained vs quest start
                start_nw = self._quest_start_snapshot.get("net_worth", 0.0)
                current_nw = snap.get("net_worth", 0.0)
                self._active_quest["objective_achieved"] = (
                    ef.get("adequate", False) or current_nw > start_nw
                )

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
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _current_portfolio(self):
        """Returns the active Portfolio, or None if not yet created."""
        if self._engine is None or self._profile is None:
            return None
        return self._engine.portfolios.get(self._profile.user_id)

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
        return {
            "avg_score": avg,
            "completed_quests": len(scores),
            "main_weakness": "diversificação",   # placeholder — será extraído do debriefing futuramente
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
            api_key = os.environ.get("BOB_API_KEY", "")
            bob = Bob(email="", password=api_key)
            bob.login()
            print("Oi")

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
            api_key = os.environ.get("BOB_API_KEY", "")
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
            alloc = {}
            current_net_worth = 0.0

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
        }

        # Quest-type rotation: acumulação → acumulação → sobrevivência → evento (every 4)
        _cycle_to_type = {0: "acumulação", 1: "acumulação", 2: "sobrevivência", 3: "evento"}
        q_type = _cycle_to_type[inf.completed_quests % 4]

        try:
            api_key = os.environ.get("BOB_API_KEY", "")
            bob = Bob(email="", password=api_key)
            bob.login()
            ai  = AiEngine(bob)

            # Give Bob the user's financial profile before quest generation
            ai.initialize_session(
                name=self._profile.name,
                incomes=[{"source": "Renda mensal", "amount": self._profile.monthly_income}],
                outcomes=[{"category": "Gastos fixos", "amount": self._profile.monthly_expenses}],
                debts=[],
            )

            # Give Bob the current simulator/market state
            if portfolio and self._engine:
                market_snap = self._engine.market_snapshot()
                merged_ctx = {**profile_dict, **market_snap}
                ai.send_simulator_context(merged_ctx)

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
            api_key = os.environ.get("BOB_API_KEY", "")
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

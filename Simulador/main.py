"""
main.py
-------
Ponto de entrada da aplicação — State Machine da interface gráfica.

Diagrama de estados (states_ibm.json):

  ┌─────────────┐  Dont have profile  ┌───────────────────┐
  │   Inicial   │────────────────────►│  Criação de Perfil│
  │             │  Already has profile│                   │
  │             │────────────────────►│  Geração da Quest ◄┘
  └─────────────┘                     └────────┬──────────┘
                                               │
                                               ▼
                                    ┌──────────────────────┐
                           ┌───────►│  InitialPage Simulator│◄──────┐
                           │        └──┬───────────────┬───┘        │
                           │  back     │ User Goes To  │ User goes  │ back
                           │           ▼               ▼            │
                           │  ┌──────────────┐  ┌──────────────┐   │
                           └──│  Low Risk    │  │  High Risk   │───┘
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
                                           Inicial
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

# ── interface pages ───────────────────────────────────────────────────────────
from src.Interfaces.initial import InitialPage
from src.Interfaces.createProfile import CreateProfilePage
from src.Interfaces.questGenerated import QuestGeneratedPage
from src.Interfaces.mainPage import MainPage
from src.Interfaces.lowRiskInvestments import LowRiskInvestmentsPage
from src.Interfaces.highRiskInvestments import HighRiskInvestmentsPage
from src.Interfaces.debriefing import DebriefingPage
from src.Interfaces.endOfMonth import EndOfMonthPage


# ─────────────────────────────────────────────────────────────────────────────
# State enumeration — mirrors every node in states_ibm.json
# ─────────────────────────────────────────────────────────────────────────────

class AppState(Enum):
    INICIAL              = auto()   # i2zG1y6y6l51
    CREATE_PROFILE       = auto()   # u2zG367~7dvM
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
                    # Already has a profile → skip creation, go to quest
                    self._transition(AppState.QUEST_GENERATED)
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
                self._transition(AppState.QUEST_GENERATED)

            return CreateProfilePage(
                master=self,
                on_submit=on_submit,
                fg_color="transparent",
            )

        # ── QUEST_GENERATED ───────────────────────────────────────────────────
        if state == AppState.QUEST_GENERATED:
            def on_start():
                self._transition(AppState.SIMULATOR_MAIN)

            return QuestGeneratedPage(
                master=self,
                quest_title="O Fundo de Emergência do Rei",
                quest_description=(
                    "O reino enfrenta tempos incertos. O conselheiro real recomenda "
                    "que todo cidadão mantenha uma reserva segura antes de aventurar-se "
                    "nos mercados de capitais."
                ),
                quest_objective=(
                    f"🎯  Objetivo: acumule R$ "
                    f"{(self._profile.monthly_expenses * 4):,.2f} em ativos líquidos."
                    if self._profile else "🎯  Objetivo: acumular uma reserva de emergência."
                ),
                on_start=on_start,
                fg_color="transparent",
            )

        # ── SIMULATOR_MAIN ────────────────────────────────────────────────────
        if state == AppState.SIMULATOR_MAIN:
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
            def on_invest(label: str, amount: float):
                # Placeholder — will wire to engine.buy_fixed() in next iteration
                print(f"[LOW RISK] Investir R$ {amount:.2f} em {label}")
                self._transition(AppState.SIMULATOR_MAIN)

            return LowRiskInvestmentsPage(
                master=self,
                on_invest=on_invest,
                on_back=lambda: self._transition(AppState.SIMULATOR_MAIN),
                fg_color="transparent",
            )

        # ── HIGH_RISK ─────────────────────────────────────────────────────────
        if state == AppState.HIGH_RISK:
            def on_buy(ticker: str, amount: float):
                print(f"[HIGH RISK] Comprar R$ {amount:.2f} de {ticker}")
                self._transition(AppState.SIMULATOR_MAIN)

            def on_sell(ticker: str, shares: float):
                print(f"[HIGH RISK] Vender {shares} cotas de {ticker}")
                self._transition(AppState.SIMULATOR_MAIN)

            return HighRiskInvestmentsPage(
                master=self,
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

            return DebriefingPage(
                master=self,
                player_name=self._profile.name if self._profile else "Aventureiro",
                net_worth=nw,
                net_worth_change=change,
                cash_pct=alloc.get("cash_pct", 0.0),
                fixed_pct=alloc.get("fixed_pct", 0.0),
                stocks_pct=alloc.get("stocks_pct", 0.0),
                cycles_played=snap.get("cycle", 1),
                agent_feedback=(
                    "Continue investindo com disciplina! "
                    "Mantenha sua reserva de emergência antes de buscar maior retorno."
                ),
                quest_completed=False,
                on_continue=lambda: self._transition(AppState.END_MONTH),
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
                on_next=lambda: self._transition(AppState.INICIAL),
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


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    app = App()
    app.mainloop()

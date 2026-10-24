"""
engine.py
---------
Motor central do simulador — orquestra ciclos, mercado, portfólios e quests.

Uma instância de SimulatorEngine representa uma sessão de simulação completa.
Pode ser usada tanto pelo agente de IA quanto pela interface do usuário.

Responsabilidades:
  - Gerenciar o estado global do mercado (MarketState)
  - Instanciar e atualizar todos os StockMarketState
  - Avançar ciclos e aplicar rendimentos a todos os portfólios registrados
  - Fornecer snapshots completos do estado para o agente/quests
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

from .market import MarketState
from .variable_income import StockMarketState, STOCKS
from .portfolio import Portfolio, InvestorProfile
from .fixed_income import FixedIncomeType, PRODUCTS


@dataclass
class CycleResult:
    """Resultado de um avanço de ciclo — eventos narrativos + métricas."""
    cycle: int
    market_events: list[str]
    stock_events: list[str]
    portfolio_summaries: dict[str, dict]  # user_id → snapshot parcial


class SimulatorEngine:
    """
    Engine central do simulador de investimentos.

    Uso básico:
        engine = SimulatorEngine()
        profile = InvestorProfile(...)
        portfolio = engine.create_portfolio(profile, initial_cash=5000)
        engine.advance_cycle()
        engine.buy_fixed(portfolio, FixedIncomeType.TESOURO_SELIC, 2000)
        snapshot = engine.snapshot(portfolio)
    """

    def __init__(self, seed: Optional[int] = None):
        import random
        if seed is not None:
            random.seed(seed)

        self.market = MarketState()
        # Instanciar todos os stocks definidos
        self.stocks: dict[str, StockMarketState] = {
            ticker: StockMarketState(definition=definition)
            for ticker, definition in STOCKS.items()
        }
        self.portfolios: dict[str, Portfolio] = {}

    # -----------------------------------------------------------------------
    # Criação de portfólio
    # -----------------------------------------------------------------------

    def create_portfolio(
        self,
        profile: InvestorProfile,
        initial_cash: float = 0.0,
    ) -> Portfolio:
        portfolio = Portfolio(profile=profile, cash=initial_cash)
        self.portfolios[profile.user_id] = portfolio
        return portfolio

    # -----------------------------------------------------------------------
    # Avanço de ciclo
    # -----------------------------------------------------------------------

    def advance_cycle(self) -> CycleResult:
        """
        Avança 1 ciclo (= 1 mês simulado) para todo o mercado:
          1. Avança o mercado (possível revisão da SELIC)
          2. Avança o preço de cada ação
          3. Aplica rendimentos de renda fixa a todos os portfólios
        """
        market_events = self.market.advance()
        stock_events: list[str] = []

        for stock_state in self.stocks.values():
            events = stock_state.advance(self.market)
            stock_events.extend(events)

        portfolio_summaries: dict[str, dict] = {}
        for user_id, portfolio in self.portfolios.items():
            result = portfolio.apply_cycle(self.market)
            portfolio_summaries[user_id] = result

        return CycleResult(
            cycle=self.market.cycle,
            market_events=market_events,
            stock_events=stock_events,
            portfolio_summaries=portfolio_summaries,
        )

    def advance_cycles(self, n: int) -> list[CycleResult]:
        """Avança múltiplos ciclos de uma vez. Retorna todos os resultados."""
        return [self.advance_cycle() for _ in range(n)]

    # -----------------------------------------------------------------------
    # Operações de portfólio (wrappers convenientes)
    # -----------------------------------------------------------------------

    def buy_fixed(
        self,
        portfolio: Portfolio,
        product_type: FixedIncomeType,
        amount: float,
    ):
        return portfolio.buy_fixed_income(product_type, amount, self.market.cycle)

    def redeem_fixed(self, portfolio: Portfolio, position_index: int):
        return portfolio.redeem_fixed_income(position_index, self.market.cycle)

    def buy_stock(self, portfolio: Portfolio, ticker: str, amount: float):
        return portfolio.buy_stock(ticker, amount, self.stocks, self.market.cycle)

    def sell_stock(self, portfolio: Portfolio, ticker: str, shares: float):
        return portfolio.sell_stock(ticker, shares, self.stocks, self.market.cycle)

    def deposit(self, portfolio: Portfolio, amount: float, note: str = "Depósito mensal"):
        return portfolio.deposit(amount, self.market.cycle, note)

    # -----------------------------------------------------------------------
    # Snapshots
    # -----------------------------------------------------------------------

    def snapshot(self, portfolio: Portfolio) -> dict:
        """Snapshot completo de um portfólio — usado pelo agente e pelas quests."""
        return portfolio.full_snapshot(self.market, self.stocks)

    def market_snapshot(self) -> dict:
        """Estado atual do mercado — todos os preços e trends."""
        return {
            "market": self.market.summary(),
            "stocks": {
                ticker: s.snapshot()
                for ticker, s in self.stocks.items()
            },
            "fixed_products": {
                pt.value: {
                    "label": p.label,
                    "indexer": p.indexer,
                    "rate_param": p.rate_param,
                    "maturity_months": p.maturity_months,
                    "min_investment": p.min_investment,
                    "ir_exempt": p.ir_exempt,
                    "liquid": p.liquid_before_maturity,
                    "description": p.description,
                }
                for pt, p in PRODUCTS.items()
            },
        }

    def narrative_cycle_summary(self, result: CycleResult) -> str:
        """
        Gera texto narrativo de um ciclo — para uso na interface RPG.
        """
        lines = [f"\n{'='*60}"]
        lines.append(f"  📅 Ciclo {result.cycle} — Mês {result.cycle} do Reino")
        lines.append(f"{'='*60}")

        if result.market_events:
            lines.append("\n🏛️  EVENTOS DO REINO:")
            for e in result.market_events:
                lines.append(f"   {e}")

        if result.stock_events:
            lines.append("\n📊 MERCADO DE AÇÕES:")
            for e in result.stock_events:
                lines.append(f"   {e}")

        market = self.market.summary()
        lines.append(
            f"\n💹 INDICADORES: SELIC {market['selic_annual_pct']:.2f}% a.a. | "
            f"Inflação ~{market['inflation_annual_pct']:.1f}% a.a."
        )
        lines.append("")
        return "\n".join(lines)

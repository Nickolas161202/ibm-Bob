"""
portfolio.py
------------
Portfólio do usuário — agrega renda fixa e variável, calcula métricas
financeiras e expõe o estado para o agente de IA e para as quests.

Métricas calculadas:
  - Patrimônio total (líquido)
  - Alocação por classe (renda fixa / variável / caixa)
  - Retorno total e retorno mensal médio
  - Indicadores para o agente: reserva de emergência adequada?, diversificação
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import uuid

from .market import MarketState
from .fixed_income import (
    FixedIncomePosition,
    FixedIncomeProduct,
    PRODUCTS,
    FixedIncomeType,
)
from .variable_income import StockPosition, StockMarketState, STOCKS


# ---------------------------------------------------------------------------
# Perfil do investidor — alimentado pelo agente de onboarding
# ---------------------------------------------------------------------------

@dataclass
class InvestorProfile:
    user_id: str
    name: str
    monthly_income: float        # R$ renda mensal
    monthly_expenses: float      # R$ gastos fixos mensais
    risk_profile: str            # "conservador" | "moderado" | "arrojado"
    knowledge_level: str         # "iniciante" | "intermediário" | "avançado"
    goal: str                    # descrição textual do objetivo
    goal_amount: float           # R$ meta financeira
    goal_deadline_months: int    # prazo em meses para atingir o objetivo

    @property
    def monthly_surplus(self) -> float:
        """Sobra mensal disponível para investimento."""
        return max(0.0, self.monthly_income - self.monthly_expenses)

    @property
    def recommended_emergency_fund(self) -> float:
        """3–6 meses de despesas fixas conforme perfil."""
        months = {"conservador": 6, "moderado": 4, "arrojado": 3}.get(
            self.risk_profile, 4
        )
        return self.monthly_expenses * months


# ---------------------------------------------------------------------------
# Portfólio principal
# ---------------------------------------------------------------------------

@dataclass
class Portfolio:
    profile: InvestorProfile
    cash: float = 0.0           # saldo disponível em caixa (R$)

    # posições abertas
    fixed_positions: list[FixedIncomePosition] = field(default_factory=list)
    stock_positions: dict[str, StockPosition] = field(default_factory=dict)

    # histórico de patrimônio por ciclo
    net_worth_history: list[float] = field(default_factory=list)
    cash_history: list[float] = field(default_factory=list)

    # transações
    transaction_log: list[dict] = field(default_factory=list)

    # -----------------------------------------------------------------------
    # Ações básicas de caixa
    # -----------------------------------------------------------------------

    def deposit(self, amount: float, cycle: int, note: str = "Depósito"):
        if amount <= 0:
            raise ValueError("Valor de depósito deve ser positivo.")
        self.cash += amount
        self._log(cycle, "deposit", amount, note=note)

    def withdraw(self, amount: float, cycle: int, note: str = "Saque"):
        if amount > self.cash:
            raise ValueError(f"Saldo insuficiente. Disponível: R$ {self.cash:.2f}")
        self.cash -= amount
        self._log(cycle, "withdraw", amount, note=note)

    # -----------------------------------------------------------------------
    # Renda Fixa
    # -----------------------------------------------------------------------

    def buy_fixed_income(
        self,
        product_type: FixedIncomeType,
        amount: float,
        cycle: int,
    ) -> FixedIncomePosition:
        product = PRODUCTS[product_type]
        if amount < product.min_investment:
            raise ValueError(
                f"Valor mínimo para {product.label}: R$ {product.min_investment:.2f}"
            )
        if amount > self.cash:
            raise ValueError(f"Saldo insuficiente. Disponível: R$ {self.cash:.2f}")

        self.cash -= amount
        pos = FixedIncomePosition(
            product=product,
            principal=amount,
            purchase_cycle=cycle,
            locked_rate_annual=product.rate_param if product.indexer == "prefixed" else None,
        )
        self.fixed_positions.append(pos)
        self._log(cycle, "buy_fixed", amount, ticker=product.label)
        return pos

    def redeem_fixed_income(
        self,
        position_index: int,
        cycle: int,
    ) -> float:
        if position_index >= len(self.fixed_positions):
            raise IndexError("Índice de posição inválido.")
        pos = self.fixed_positions[position_index]
        if not pos.can_redeem(cycle):
            raise ValueError(
                f"{pos.product.label} ainda não pode ser resgatado "
                f"(carência: {pos.product.maturity_months} meses)."
            )
        net_value = pos.redemption_value(cycle)
        self.cash += net_value
        self._log(cycle, "redeem_fixed", net_value, ticker=pos.product.label)
        self.fixed_positions.pop(position_index)
        return net_value

    # -----------------------------------------------------------------------
    # Renda Variável
    # -----------------------------------------------------------------------

    def buy_stock(
        self,
        ticker: str,
        amount: float,
        market_states: dict[str, StockMarketState],
        cycle: int,
    ) -> StockPosition:
        if ticker not in market_states:
            raise ValueError(f"Ticker '{ticker}' não encontrado no mercado.")
        if amount > self.cash:
            raise ValueError(f"Saldo insuficiente. Disponível: R$ {self.cash:.2f}")
        if amount <= 0:
            raise ValueError("Valor de compra deve ser positivo.")

        price = market_states[ticker].price
        shares = amount / price
        self.cash -= amount

        if ticker in self.stock_positions:
            self.stock_positions[ticker].add_shares(shares, price)
        else:
            self.stock_positions[ticker] = StockPosition(
                ticker=ticker,
                shares=shares,
                avg_purchase_price=price,
                total_invested=amount,
            )

        self._log(cycle, "buy_stock", amount, ticker=ticker, shares=shares, price=price)
        return self.stock_positions[ticker]

    def sell_stock(
        self,
        ticker: str,
        shares: float,
        market_states: dict[str, StockMarketState],
        cycle: int,
    ) -> float:
        if ticker not in self.stock_positions:
            raise ValueError(f"Você não possui ações de '{ticker}'.")
        pos = self.stock_positions[ticker]
        current_price = market_states[ticker].price
        proceeds = shares * current_price

        pos.sell_shares(shares)
        if pos.shares == 0:
            del self.stock_positions[ticker]

        self.cash += proceeds
        self._log(cycle, "sell_stock", proceeds, ticker=ticker, shares=shares, price=current_price)
        return proceeds

    # -----------------------------------------------------------------------
    # Avanço de ciclo — aplica rendimentos
    # -----------------------------------------------------------------------

    def apply_cycle(self, market: MarketState) -> dict:
        """
        Aplica 1 ciclo de rendimento a todas as posições de renda fixa.
        Retorna resumo dos rendimentos do ciclo.
        """
        fixed_earnings = 0.0
        for pos in self.fixed_positions:
            earning = pos.apply_cycle(market)
            fixed_earnings += earning

        net = self.net_worth(market_states={})  # sem ações para calcular
        self.net_worth_history.append(net)
        self.cash_history.append(self.cash)

        return {
            "cycle": market.cycle,
            "fixed_earnings": round(fixed_earnings, 2),
        }

    # -----------------------------------------------------------------------
    # Métricas e snapshots
    # -----------------------------------------------------------------------

    def fixed_income_total(self, cycle: int) -> float:
        return sum(pos.redemption_value(cycle) for pos in self.fixed_positions)

    def stock_total(self, market_states: dict[str, StockMarketState]) -> float:
        total = 0.0
        for ticker, pos in self.stock_positions.items():
            if ticker in market_states:
                total += pos.current_value(market_states[ticker].price)
        return total

    def net_worth(self, market_states: dict[str, StockMarketState], cycle: int = 0) -> float:
        return round(
            self.cash
            + self.fixed_income_total(cycle)
            + self.stock_total(market_states),
            2,
        )

    def allocation(
        self,
        market_states: dict[str, StockMarketState],
        cycle: int = 0,
    ) -> dict:
        total = self.net_worth(market_states, cycle)
        if total == 0:
            return {"cash_pct": 0, "fixed_pct": 0, "stocks_pct": 0}
        fixed = self.fixed_income_total(cycle)
        stocks = self.stock_total(market_states)
        return {
            "cash_pct": round(self.cash / total * 100, 1),
            "fixed_pct": round(fixed / total * 100, 1),
            "stocks_pct": round(stocks / total * 100, 1),
        }

    def emergency_fund_status(self, cycle: int) -> dict:
        """Verifica se o usuário tem reserva de emergência adequada."""
        # Considera apenas ativos líquidos (caixa + Tesouro Selic + CDB Diário)
        liquid = self.cash
        for pos in self.fixed_positions:
            if pos.product.liquid_before_maturity:
                liquid += pos.redemption_value(cycle)

        target = self.profile.recommended_emergency_fund
        pct = min(round(liquid / target * 100, 1), 100.0) if target > 0 else 100.0
        return {
            "liquid_assets": round(liquid, 2),
            "target": round(target, 2),
            "completion_pct": pct,
            "adequate": pct >= 100.0,
        }

    def goal_progress(self, market_states: dict[str, StockMarketState], cycle: int) -> dict:
        nw = self.net_worth(market_states, cycle)
        target = self.profile.goal_amount
        pct = min(round(nw / target * 100, 1), 100.0) if target > 0 else 100.0
        return {
            "current_net_worth": nw,
            "goal_amount": target,
            "goal": self.profile.goal,
            "completion_pct": pct,
            "achieved": pct >= 100.0,
        }

    def full_snapshot(
        self,
        market: MarketState,
        market_states: dict[str, StockMarketState],
    ) -> dict:
        cycle = market.cycle
        return {
            "cycle": cycle,
            "cash": round(self.cash, 2),
            "net_worth": self.net_worth(market_states, cycle),
            "allocation": self.allocation(market_states, cycle),
            "fixed_positions": [p.snapshot(cycle) for p in self.fixed_positions],
            "stock_positions": [
                p.snapshot(market_states[t].price)
                for t, p in self.stock_positions.items()
                if t in market_states
            ],
            "emergency_fund": self.emergency_fund_status(cycle),
            "goal_progress": self.goal_progress(market_states, cycle),
            "market": market.summary(),
        }

    # -----------------------------------------------------------------------
    # Log interno
    # -----------------------------------------------------------------------

    def _log(self, cycle: int, action: str, amount: float, **kwargs):
        entry = {"cycle": cycle, "action": action, "amount": round(amount, 2)}
        entry.update(kwargs)
        self.transaction_log.append(entry)

"""
variable_income.py
------------------
Sistema de renda variável com Trends (inspirado no Cookie Clicker).

Mecânica de preço por ciclo:
  1. Aplica o valor base da Trend (pequeno, direcional)
  2. Aplica ruído aleatório (pode ser muito maior que a Trend)
  => As flutuações parecem caóticas, mas convergem para a direção da Trend.

Após um número configurável de ciclos, cada ação pode mudar de Trend.
A probabilidade de mudança depende do perfil da ação (volátil muda mais).

Trends disponíveis:
  - RISING  : valor base positivo (tendência de alta)
  - FALLING : valor base negativo (tendência de baixa)
  - STABLE  : valor base próximo de zero
  - CHAOTIC : valor base baixo, mas ruído muito alto
"""

from __future__ import annotations
import random
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .market import MarketState


# ---------------------------------------------------------------------------
# Trends
# ---------------------------------------------------------------------------

class Trend(str, Enum):
    RISING  = "📈 Alta"
    FALLING = "📉 Baixa"
    STABLE  = "➡️  Estável"
    CHAOTIC = "🌀 Caótico"


# Parâmetros de cada Trend: (base_pct, noise_std_pct)
# base_pct   → variação base por ciclo como % do preço atual
# noise_std_pct → desvio padrão do ruído aleatório como % do preço
TREND_PARAMS: dict[Trend, tuple[float, float]] = {
    Trend.RISING:  ( 0.025,  0.040),   # +2.5% base, ±4% ruído
    Trend.FALLING: (-0.025,  0.040),   # -2.5% base, ±4% ruído
    Trend.STABLE:  ( 0.002,  0.020),   # +0.2% base, ±2% ruído
    Trend.CHAOTIC: ( 0.000,  0.120),   # 0% base,   ±12% ruído
}

# Probabilidade de cada nova Trend ser escolhida (pesos relativos)
TREND_WEIGHTS = {
    Trend.RISING:  0.30,
    Trend.FALLING: 0.30,
    Trend.STABLE:  0.30,
    Trend.CHAOTIC: 0.10,
}


def random_trend(exclude: Optional[Trend] = None) -> Trend:
    trends = [t for t in Trend if t != exclude]
    weights = [TREND_WEIGHTS[t] for t in trends]
    return random.choices(trends, weights=weights, k=1)[0]


# ---------------------------------------------------------------------------
# Definição estática das ações disponíveis
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StockDefinition:
    ticker: str
    name: str
    sector: str
    initial_price: float
    # Ciclos até a próxima possível mudança de Trend
    trend_change_min_cycles: int = 3
    trend_change_max_cycles: int = 8
    # Probabilidade de mudar de Trend quando o momento chega
    trend_change_probability: float = 0.60
    # Correlação com mercado: quanto a SELIC afeta essa ação (0–1)
    market_sensitivity: float = 0.3
    description: str = ""


STOCKS: dict[str, StockDefinition] = {
    "BRCO3": StockDefinition(
        ticker="BRCO3",
        name="Banco do Reinos S.A.",
        sector="Financeiro",
        initial_price=28.50,
        trend_change_min_cycles=4,
        trend_change_max_cycles=10,
        trend_change_probability=0.55,
        market_sensitivity=0.5,
        description="Grande banco estatal. Sensível a variações da SELIC.",
    ),
    "PTRX4": StockDefinition(
        ticker="PTRX4",
        name="PetroReinos S.A.",
        sector="Energia",
        initial_price=35.00,
        trend_change_min_cycles=3,
        trend_change_max_cycles=7,
        trend_change_probability=0.65,
        market_sensitivity=0.2,
        description="Empresa de energia. Influenciada por commodities simuladas.",
    ),
    "MGCO3": StockDefinition(
        ticker="MGCO3",
        name="MagiaComércio S.A.",
        sector="Consumo",
        initial_price=18.00,
        trend_change_min_cycles=2,
        trend_change_max_cycles=6,
        trend_change_probability=0.70,
        market_sensitivity=0.3,
        description="Varejo do reino. Alta volatilidade, alto potencial.",
    ),
    "GLDX3": StockDefinition(
        ticker="GLDX3",
        name="Guildas de Ouro S.A.",
        sector="Mineração",
        initial_price=55.00,
        trend_change_min_cycles=5,
        trend_change_max_cycles=12,
        trend_change_probability=0.45,
        market_sensitivity=0.1,
        description="Empresa de mineração. Tende a ser hedge em crises.",
    ),
    "TCNV5": StockDefinition(
        ticker="TCNV5",
        name="TecnoVentos S.A.",
        sector="Tecnologia",
        initial_price=12.00,
        trend_change_min_cycles=2,
        trend_change_max_cycles=5,
        trend_change_probability=0.80,
        market_sensitivity=0.4,
        description="Startup de tecnologia. Muito volátil, mas com grande upside.",
    ),
}


# ---------------------------------------------------------------------------
# Estado dinâmico de uma ação no mercado
# ---------------------------------------------------------------------------

@dataclass
class StockMarketState:
    """Estado atual de uma ação no mercado (preço, trend, histórico)."""
    definition: StockDefinition
    price: float = field(init=False)
    trend: Trend = field(init=False)
    cycles_in_trend: int = field(default=0, init=False)
    next_trend_check: int = field(init=False)
    price_history: list[float] = field(default_factory=list, init=False)
    trend_history: list[Trend] = field(default_factory=list, init=False)
    events: list[str] = field(default_factory=list, init=False)

    def __post_init__(self):
        self.price = self.definition.initial_price
        self.trend = random_trend()
        self.next_trend_check = random.randint(
            self.definition.trend_change_min_cycles,
            self.definition.trend_change_max_cycles,
        )

    def _compute_new_price(self, market: MarketState) -> float:
        """
        Calcula novo preço aplicando:
        1. Valor base da Trend
        2. Ruído aleatório gaussiano
        3. Influência da SELIC sobre o setor
        """
        base_pct, noise_std = TREND_PARAMS[self.trend]

        # Influência da SELIC: taxa alta pressiona ações para baixo
        selic_delta = (market.selic_annual - 10.75) / 100  # desvio da referência
        selic_effect = -selic_delta * self.definition.market_sensitivity * 0.5

        # Ruído gaussiano
        noise = random.gauss(0, noise_std)

        total_change_pct = base_pct + noise + selic_effect
        new_price = self.price * (1 + total_change_pct)

        # Preço mínimo: 10% do inicial (evita ir a zero)
        floor = self.definition.initial_price * 0.10
        return max(floor, round(new_price, 2))

    def advance(self, market: MarketState) -> list[str]:
        """
        Avança 1 ciclo. Atualiza preço e verifica mudança de Trend.
        Retorna lista de eventos narrativos ocorridos.
        """
        cycle_events: list[str] = []

        # Atualizar preço
        new_price = self._compute_new_price(market)
        self.price_history.append(self.price)
        self.price = new_price
        self.cycles_in_trend += 1

        # Verificar mudança de Trend
        if self.cycles_in_trend >= self.next_trend_check:
            if random.random() < self.definition.trend_change_probability:
                old_trend = self.trend
                self.trend = random_trend(exclude=self.trend)
                self.trend_history.append(old_trend)
                self.cycles_in_trend = 0
                self.next_trend_check = random.randint(
                    self.definition.trend_change_min_cycles,
                    self.definition.trend_change_max_cycles,
                )
                msg = (
                    f"[{self.definition.ticker}] Trend mudou: "
                    f"{old_trend.value} → {self.trend.value}"
                )
                cycle_events.append(msg)
                self.events.append(msg)

        return cycle_events

    @property
    def change_pct_last_cycle(self) -> float:
        """Variação percentual em relação ao ciclo anterior."""
        if not self.price_history:
            return 0.0
        prev = self.price_history[-1]
        if prev == 0:
            return 0.0
        return round((self.price - prev) / prev * 100, 2)

    def snapshot(self) -> dict:
        return {
            "ticker": self.definition.ticker,
            "name": self.definition.name,
            "sector": self.definition.sector,
            "price": round(self.price, 2),
            "change_pct": self.change_pct_last_cycle,
            "trend": self.trend.value,
            "cycles_in_trend": self.cycles_in_trend,
        }


# ---------------------------------------------------------------------------
# Posição individual de um usuário em uma ação
# ---------------------------------------------------------------------------

@dataclass
class StockPosition:
    ticker: str
    shares: float              # quantidade de ações (pode ser fracionada)
    avg_purchase_price: float  # preço médio de compra
    total_invested: float      # total em R$ investido

    def current_value(self, current_price: float) -> float:
        return round(self.shares * current_price, 2)

    def unrealized_pnl(self, current_price: float) -> float:
        return round(self.current_value(current_price) - self.total_invested, 2)

    def unrealized_pnl_pct(self, current_price: float) -> float:
        if self.total_invested == 0:
            return 0.0
        return round(self.unrealized_pnl(current_price) / self.total_invested * 100, 2)

    def add_shares(self, shares: float, price: float):
        """Compra adicional com atualização de preço médio."""
        new_total = self.total_invested + shares * price
        self.shares += shares
        self.total_invested = new_total
        self.avg_purchase_price = new_total / self.shares if self.shares > 0 else 0

    def sell_shares(self, shares: float) -> float:
        """Remove ações e retorna a parcela do investimento resgatada."""
        if shares > self.shares:
            raise ValueError(
                f"Tentativa de vender {shares} ações, mas possui apenas {self.shares}."
            )
        proportion = shares / self.shares
        cost_basis = self.total_invested * proportion
        self.shares -= shares
        self.total_invested -= cost_basis
        if self.shares == 0:
            self.avg_purchase_price = 0
            self.total_invested = 0
        return cost_basis

    def snapshot(self, current_price: float) -> dict:
        return {
            "ticker": self.ticker,
            "shares": round(self.shares, 4),
            "avg_purchase_price": round(self.avg_purchase_price, 2),
            "current_price": round(current_price, 2),
            "current_value": self.current_value(current_price),
            "unrealized_pnl": self.unrealized_pnl(current_price),
            "unrealized_pnl_pct": self.unrealized_pnl_pct(current_price),
        }

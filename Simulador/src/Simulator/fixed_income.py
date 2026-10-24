"""
fixed_income.py
---------------
Produtos de renda fixa disponíveis no simulador.

Todos os produtos têm:
  - Taxa de rendimento vinculada à SELIC/CDI (% do CDI ou taxa prefixada)
  - Prazo de vencimento em ciclos (meses simulados)
  - Liquidez: se pode ser resgatado antes do vencimento
  - Imposto de Renda regressivo (tabela simplificada)
  - Valor mínimo de aplicação

Produtos disponíveis:
  1. Tesouro Selic         — pós-fixado 100% SELIC, liquidez diária
  2. Tesouro Prefixado     — taxa fixa definida no momento da compra
  3. Tesouro IPCA+         — IPCA + spread fixo
  4. CDB Liquidez Diária   — pós-fixado ~100% CDI, liquidez diária
  5. CDB 90 dias           — pós-fixado ~105% CDI, carência 3 meses
  6. CDB 1 ano             — pós-fixado ~110% CDI, carência 12 meses
  7. LCI 6 meses           — 93% CDI, isento de IR, carência 6 meses
  8. LCA 1 ano             — 95% CDI, isento de IR, carência 12 meses
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import math

from .market import MarketState


# ---------------------------------------------------------------------------
# Tabela de IR regressiva (simplificada)
# ---------------------------------------------------------------------------

IR_TABLE = [
    (6,  0.225),   # até 6 meses:   22,5%
    (12, 0.200),   # 6–12 meses:    20%
    (24, 0.175),   # 12–24 meses:   17,5%
    (999, 0.150),  # acima de 24m:  15%
]

def ir_rate(months_held: int) -> float:
    for threshold, rate in IR_TABLE:
        if months_held <= threshold:
            return rate
    return 0.15


# ---------------------------------------------------------------------------
# Enum de tipos
# ---------------------------------------------------------------------------

class FixedIncomeType(str, Enum):
    TESOURO_SELIC       = "Tesouro Selic"
    TESOURO_PREFIXADO   = "Tesouro Prefixado"
    TESOURO_IPCA_PLUS   = "Tesouro IPCA+"
    CDB_DAILY           = "CDB Liquidez Diária"
    CDB_90              = "CDB 90 dias"
    CDB_1Y              = "CDB 1 ano"
    LCI_6M              = "LCI 6 meses"
    LCA_1Y              = "LCA 1 ano"


# ---------------------------------------------------------------------------
# Definição estática dos produtos
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FixedIncomeProduct:
    product_type: FixedIncomeType
    label: str
    min_investment: float         # R$
    maturity_months: int          # 0 = sem vencimento fixo
    liquid_before_maturity: bool  # pode resgatar antes?
    ir_exempt: bool               # isento de IR (LCI/LCA)?
    # Indexador: "selic", "cdi_pct" (% do CDI), "prefixed", "ipca_plus"
    indexer: str
    rate_param: float             # depende do indexador:
                                  #   cdi_pct  → 1.05 significa 105% do CDI
                                  #   prefixed → taxa anual fixa (ex: 12.5)
                                  #   ipca_plus → spread a.a. (ex: 5.5)
                                  #   selic    → ignorado (usa 100% SELIC)
    risk_label: str               = "Muito Baixo"
    description: str              = ""


PRODUCTS: dict[FixedIncomeType, FixedIncomeProduct] = {
    FixedIncomeType.TESOURO_SELIC: FixedIncomeProduct(
        product_type=FixedIncomeType.TESOURO_SELIC,
        label="Tesouro Selic",
        min_investment=100.0,
        maturity_months=0,
        liquid_before_maturity=True,
        ir_exempt=False,
        indexer="selic",
        rate_param=1.0,
        risk_label="Muito Baixo",
        description="Rendimento atrelado à taxa SELIC. Ideal para reserva de emergência.",
    ),
    FixedIncomeType.TESOURO_PREFIXADO: FixedIncomeProduct(
        product_type=FixedIncomeType.TESOURO_PREFIXADO,
        label="Tesouro Prefixado",
        min_investment=100.0,
        maturity_months=24,
        liquid_before_maturity=True,
        ir_exempt=False,
        indexer="prefixed",
        rate_param=11.5,
        risk_label="Baixo",
        description="Taxa anual fixa de 11.5%. Bom quando a SELIC tende a cair.",
    ),
    FixedIncomeType.TESOURO_IPCA_PLUS: FixedIncomeProduct(
        product_type=FixedIncomeType.TESOURO_IPCA_PLUS,
        label="Tesouro IPCA+",
        min_investment=100.0,
        maturity_months=36,
        liquid_before_maturity=True,
        ir_exempt=False,
        indexer="ipca_plus",
        rate_param=5.5,
        risk_label="Baixo",
        description="Protege contra a inflação: rende IPCA + 5.5% a.a.",
    ),
    FixedIncomeType.CDB_DAILY: FixedIncomeProduct(
        product_type=FixedIncomeType.CDB_DAILY,
        label="CDB Liquidez Diária",
        min_investment=500.0,
        maturity_months=0,
        liquid_before_maturity=True,
        ir_exempt=False,
        indexer="cdi_pct",
        rate_param=1.00,
        risk_label="Muito Baixo",
        description="100% do CDI com liquidez imediata. Alternativa ao Tesouro Selic.",
    ),
    FixedIncomeType.CDB_90: FixedIncomeProduct(
        product_type=FixedIncomeType.CDB_90,
        label="CDB 90 dias",
        min_investment=1000.0,
        maturity_months=3,
        liquid_before_maturity=False,
        ir_exempt=False,
        indexer="cdi_pct",
        rate_param=1.05,
        risk_label="Baixo",
        description="105% do CDI com carência de 3 meses. Requer disciplina.",
    ),
    FixedIncomeType.CDB_1Y: FixedIncomeProduct(
        product_type=FixedIncomeType.CDB_1Y,
        label="CDB 1 ano",
        min_investment=1000.0,
        maturity_months=12,
        liquid_before_maturity=False,
        ir_exempt=False,
        indexer="cdi_pct",
        rate_param=1.10,
        risk_label="Baixo",
        description="110% do CDI com carência de 12 meses. Maior retorno, menor flexibilidade.",
    ),
    FixedIncomeType.LCI_6M: FixedIncomeProduct(
        product_type=FixedIncomeType.LCI_6M,
        label="LCI 6 meses",
        min_investment=5000.0,
        maturity_months=6,
        liquid_before_maturity=False,
        ir_exempt=True,
        indexer="cdi_pct",
        rate_param=0.93,
        risk_label="Muito Baixo",
        description="93% do CDI, ISENTO de IR. Rentabilidade líquida supera CDB de 100% CDI.",
    ),
    FixedIncomeType.LCA_1Y: FixedIncomeProduct(
        product_type=FixedIncomeType.LCA_1Y,
        label="LCA 1 ano",
        min_investment=5000.0,
        maturity_months=12,
        liquid_before_maturity=False,
        ir_exempt=True,
        indexer="cdi_pct",
        rate_param=0.95,
        risk_label="Muito Baixo",
        description="95% do CDI, ISENTO de IR. Excelente para prazos de 12 meses.",
    ),
}


# ---------------------------------------------------------------------------
# Posição individual de renda fixa (instância de investimento)
# ---------------------------------------------------------------------------

@dataclass
class FixedIncomePosition:
    product: FixedIncomeProduct
    principal: float          # valor aplicado (R$)
    purchase_cycle: int       # ciclo em que foi comprado
    # Taxa prefixada registrada no momento da compra (para prefixed/ipca_plus)
    locked_rate_annual: Optional[float] = None

    # acumulado de rendimento bruto
    gross_earnings: float = field(default=0.0, init=False)
    cycles_held: int = field(default=0, init=False)

    def is_mature(self, current_cycle: int) -> bool:
        if self.product.maturity_months == 0:
            return False
        return (current_cycle - self.purchase_cycle) >= self.product.maturity_months

    def can_redeem(self, current_cycle: int) -> bool:
        return (
            self.product.liquid_before_maturity
            or self.is_mature(current_cycle)
        )

    def monthly_gross_rate(self, market: MarketState) -> float:
        """Taxa bruta mensal para o ciclo atual."""
        ix = self.product.indexer
        if ix == "selic":
            return market.selic_monthly
        elif ix == "cdi_pct":
            return market.cdi_monthly * self.product.rate_param
        elif ix == "prefixed":
            rate = self.locked_rate_annual or self.product.rate_param
            return (1 + rate / 100) ** (1 / 12) - 1
        elif ix == "ipca_plus":
            spread = self.product.rate_param
            annual = market.inflation_annual + spread
            return (1 + annual / 100) ** (1 / 12) - 1
        return 0.0

    def apply_cycle(self, market: MarketState) -> float:
        """Aplica 1 ciclo de rendimento. Retorna rendimento bruto do ciclo."""
        rate = self.monthly_gross_rate(market)
        earning = self.principal * rate
        self.principal += earning
        self.gross_earnings += earning
        self.cycles_held += 1
        return earning

    def redemption_value(self, current_cycle: int) -> float:
        """Valor líquido de resgate (após IR se aplicável)."""
        months = current_cycle - self.purchase_cycle
        if self.product.ir_exempt or self.gross_earnings <= 0:
            return self.principal
        rate = ir_rate(months)
        tax = self.gross_earnings * rate
        return self.principal - tax

    def snapshot(self, current_cycle: int) -> dict:
        months = current_cycle - self.purchase_cycle
        net = self.redemption_value(current_cycle)
        return {
            "product": self.product.label,
            "principal_with_earnings": round(self.principal, 2),
            "gross_earnings": round(self.gross_earnings, 2),
            "net_redemption_value": round(net, 2),
            "months_held": months,
            "ir_exempt": self.product.ir_exempt,
            "can_redeem": self.can_redeem(current_cycle),
            "is_mature": self.is_mature(current_cycle),
        }

"""
market.py
---------
Estado global compartilhado do mercado.
A taxa SELIC é a âncora do mercado: afeta rendimentos de renda fixa
e serve como referência para o risco de renda variável.
"""

from __future__ import annotations
import random
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Configurações de mercado
# ---------------------------------------------------------------------------

SELIC_INITIAL = 10.75          # % a.a. — valor inicial (referência real)
SELIC_MIN = 2.0
SELIC_MAX = 14.75
SELIC_CHANGE_PROBABILITY = 0.15  # chance de mudar a cada ciclo mensal
SELIC_CHANGE_STEP = 0.25         # mudança por passo (p.p.)
SELIC_MAX_STEPS = 2              # máximo de passos por revisão


@dataclass
class MarketState:
    """
    Estado global do mercado, compartilhado entre todos os usuários/sessões.
    Cada ciclo representa 1 mês simulado.
    """
    cycle: int = 0                        # ciclo atual (meses simulados)
    selic_annual: float = SELIC_INITIAL   # Taxa SELIC % a.a.
    selic_history: list[float] = field(default_factory=list)
    events: list[str] = field(default_factory=list)  # log de eventos narrativos

    # -----------------------------------------------------------------------
    # Propriedades derivadas
    # -----------------------------------------------------------------------

    @property
    def selic_monthly(self) -> float:
        """Taxa SELIC mensal equivalente (capitalização composta)."""
        return (1 + self.selic_annual / 100) ** (1 / 12) - 1

    @property
    def cdi_annual(self) -> float:
        """CDI ≈ SELIC - 0.10 p.p. (convenção de mercado simplificada)."""
        return max(0.0, self.selic_annual - 0.10)

    @property
    def cdi_monthly(self) -> float:
        return (1 + self.cdi_annual / 100) ** (1 / 12) - 1

    @property
    def inflation_annual(self) -> float:
        """Inflação simulada — correlacionada inversamente com SELIC."""
        base = 4.5
        delta = (SELIC_INITIAL - self.selic_annual) * 0.3
        return round(max(1.0, base + delta + random.gauss(0, 0.3)), 2)

    @property
    def inflation_monthly(self) -> float:
        return (1 + self.inflation_annual / 100) ** (1 / 12) - 1

    # -----------------------------------------------------------------------
    # Avanço de ciclo
    # -----------------------------------------------------------------------

    def advance(self, narrative_context: str = "") -> list[str]:
        """
        Avança 1 ciclo (1 mês simulado).
        Retorna lista de eventos ocorridos neste ciclo.
        """
        self.cycle += 1
        self.selic_history.append(self.selic_annual)
        cycle_events: list[str] = []

        # Possível revisão da SELIC
        if random.random() < SELIC_CHANGE_PROBABILITY:
            steps = random.randint(1, SELIC_MAX_STEPS)
            direction = random.choice([-1, 1])
            change = steps * SELIC_CHANGE_STEP * direction
            old_selic = self.selic_annual
            self.selic_annual = round(
                max(SELIC_MIN, min(SELIC_MAX, self.selic_annual + change)), 2
            )
            if self.selic_annual != old_selic:
                direction_text = "subiu" if change > 0 else "caiu"
                msg = (
                    f"[Ciclo {self.cycle}] O Banco Central {direction_text} a SELIC "
                    f"de {old_selic:.2f}% para {self.selic_annual:.2f}% a.a."
                )
                cycle_events.append(msg)

        self.events.extend(cycle_events)
        return cycle_events

    def summary(self) -> dict:
        return {
            "cycle": self.cycle,
            "selic_annual_pct": self.selic_annual,
            "selic_monthly_pct": round(self.selic_monthly * 100, 4),
            "cdi_annual_pct": self.cdi_annual,
            "inflation_annual_pct": self.inflation_annual,
        }


# Instância singleton — importada pelos outros módulos
market = MarketState()

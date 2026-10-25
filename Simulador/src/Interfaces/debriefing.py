"""
debriefing.py
-------------
Tela de debriefing — resumo detalhado do desempenho do jogador
ao final de uma quest ou da simulação.

Exibe: patrimônio atual, variação no período, alocação de portfólio
e uma mensagem de feedback do agente.
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk


class DebriefingPage(ctk.CTkFrame):
    """Tela de debriefing / relatório de desempenho."""

    def __init__(
        self,
        master,
        player_name: str = "Aventureiro",
        net_worth: float = 0.0,
        net_worth_change: float = 0.0,
        cash_pct: float = 0.0,
        fixed_pct: float = 0.0,
        stocks_pct: float = 0.0,
        cycles_played: int = 1,
        agent_feedback: str = "Bom trabalho! Continue investindo com disciplina.",
        quest_completed: bool = False,
        on_continue: Callable | None = None,
        **kwargs,
    ):
        """
        Args:
            master:           Widget pai.
            player_name:      Nome do jogador.
            net_worth:        Patrimônio total atual (R$).
            net_worth_change: Variação absoluta no período (R$, pode ser negativa).
            cash_pct:         % do portfólio em caixa.
            fixed_pct:        % em renda fixa.
            stocks_pct:       % em renda variável.
            cycles_played:    Número de ciclos/meses jogados.
            agent_feedback:   Mensagem textual do agente de IA.
            quest_completed:  Se a quest do período foi concluída.
            on_continue:      Callback ao clicar em "Continuar".
        """
        super().__init__(master, **kwargs)
        self._player_name = player_name
        self._net_worth = net_worth
        self._net_worth_change = net_worth_change
        self._cash_pct = cash_pct
        self._fixed_pct = fixed_pct
        self._stocks_pct = stocks_pct
        self._cycles_played = cycles_played
        self._agent_feedback = agent_feedback
        self._quest_completed = quest_completed
        self._on_continue = on_continue or (lambda: None)
        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)

        # ── Título ────────────────────────────────────────────────────────────
        quest_badge = "  🏆 Quest Concluída!" if self._quest_completed else ""
        ctk.CTkLabel(
            self,
            text=f"Relatório de Desempenho{quest_badge}",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).grid(row=0, column=0, padx=40, pady=(44, 4))

        ctk.CTkLabel(
            self,
            text=f"{self._player_name}  ·  {self._cycles_played} mês(es) jogado(s)",
            font=ctk.CTkFont(size=13),
            text_color="gray",
        ).grid(row=1, column=0, padx=40, pady=(0, 24))

        # ── Cards de métricas ─────────────────────────────────────────────────
        metrics = ctk.CTkFrame(self, fg_color="transparent")
        metrics.grid(row=2, column=0, padx=40, pady=0, sticky="ew")
        metrics.grid_columnconfigure((0, 1), weight=1)

        # Patrimônio
        self._metric_card(
            metrics, col=0,
            title="💰  Patrimônio Total",
            value=f"R$ {self._net_worth:,.2f}",
        )

        # Variação
        sign = "+" if self._net_worth_change >= 0 else ""
        change_color = "#4caf50" if self._net_worth_change >= 0 else "#e05c5c"
        self._metric_card(
            metrics, col=1,
            title="📈  Variação no Período",
            value=f"{sign}R$ {self._net_worth_change:,.2f}",
            value_color=change_color,
        )

        # ── Alocação ──────────────────────────────────────────────────────────
        alloc_card = ctk.CTkFrame(self, corner_radius=10)
        alloc_card.grid(row=3, column=0, padx=40, pady=(16, 0), sticky="ew")
        alloc_card.grid_columnconfigure((0, 1, 2), weight=1)

        ctk.CTkLabel(
            alloc_card,
            text="Alocação do Portfólio",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="gray",
        ).grid(row=0, column=0, columnspan=3, padx=16, pady=(14, 8))

        for col, (label, pct) in enumerate([
            ("💵 Caixa", self._cash_pct),
            ("🏦 Renda Fixa", self._fixed_pct),
            ("📊 Renda Variável", self._stocks_pct),
        ]):
            ctk.CTkLabel(
                alloc_card, text=label,
                font=ctk.CTkFont(size=12), text_color="gray"
            ).grid(row=1, column=col, padx=8)
            ctk.CTkLabel(
                alloc_card, text=f"{pct:.1f}%",
                font=ctk.CTkFont(size=16, weight="bold")
            ).grid(row=2, column=col, padx=8, pady=(2, 14))

        # ── Feedback do agente ────────────────────────────────────────────────
        feedback_card = ctk.CTkFrame(self, corner_radius=10)
        feedback_card.grid(row=4, column=0, padx=40, pady=(16, 0), sticky="ew")
        feedback_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            feedback_card,
            text="🤖  Conselheiro Real",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="gray",
        ).grid(row=0, column=0, padx=20, pady=(14, 4), sticky="w")

        ctk.CTkLabel(
            feedback_card,
            text=self._agent_feedback,
            font=ctk.CTkFont(size=13),
            wraplength=460,
            justify="left",
        ).grid(row=1, column=0, padx=20, pady=(0, 16), sticky="w")

        # ── Botão continuar ───────────────────────────────────────────────────
        ctk.CTkButton(
            self,
            text="Continuar  →",
            font=ctk.CTkFont(size=15, weight="bold"),
            width=200,
            height=44,
            corner_radius=10,
            command=self._on_continue,
        ).grid(row=5, column=0, padx=40, pady=(20, 44))

    @staticmethod
    def _metric_card(parent, col: int, title: str, value: str, value_color: str = "white"):
        padx = (0, 8) if col == 0 else (8, 0)
        card = ctk.CTkFrame(parent, corner_radius=10)
        card.grid(row=0, column=col, padx=padx, sticky="ew")
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=12), text_color="gray").grid(
            row=0, column=0, padx=16, pady=(14, 2)
        )
        ctk.CTkLabel(
            card, text=value,
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color=value_color,
        ).grid(row=1, column=0, padx=16, pady=(0, 14))


# ---------------------------------------------------------------------------
# Execução standalone
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    root.title("Debriefing")
    root.geometry("600x580")
    root.resizable(False, False)

    DebriefingPage(
        master=root,
        player_name="João Silva",
        net_worth=9200.00,
        net_worth_change=450.00,
        cash_pct=15.0,
        fixed_pct=60.0,
        stocks_pct=25.0,
        cycles_played=4,
        agent_feedback=(
            "Parabéns! Você manteve uma boa reserva de emergência e diversificou "
            "corretamente entre renda fixa e variável. Para o próximo mês, considere "
            "aumentar sua exposição ao Tesouro IPCA+ para proteger o poder de compra."
        ),
        quest_completed=True,
        on_continue=lambda: print("Continuar..."),
        fg_color="transparent",
    ).pack(fill="both", expand=True)

    root.mainloop()

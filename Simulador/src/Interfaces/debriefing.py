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
        quest_score: int = 0,
        on_continue: Callable | None = None,
        goal_name: str = "",
        goal_completion_pct: float = 0.0,
        goal_remaining_r: float = 0.0,
        objective_score: int | None = None,
        allocation_score: int | None = None,
        risk_score: int | None = None,
        quest_tip: str = "",
        quest_continues: bool = False,
        quest_cycle_label: str | None = None,
        **kwargs,
    ):
        """
        Args:
            master:              Widget pai.
            player_name:         Nome do jogador.
            net_worth:           Patrimônio total atual (R$).
            net_worth_change:    Variação absoluta no período (R$, pode ser negativa).
            cash_pct:            % do portfólio em caixa.
            fixed_pct:           % em renda fixa.
            stocks_pct:          % em renda variável.
            cycles_played:       Número de ciclos/meses jogados.
            agent_feedback:      Mensagem textual do agente de IA.
            quest_score:         Pontuação de conclusão da quest definida pelo Agente (1–100).
            on_continue:         Callback ao clicar em "Continuar".
            goal_name:           Nome do objetivo financeiro do usuário.
            goal_completion_pct: % de conclusão do objetivo (0–100).
            goal_remaining_r:    R$ restantes para atingir o objetivo.
            objective_score:     Sub-pontuação do cumprimento do objetivo (0–100).
            allocation_score:    Sub-pontuação de qualidade de alocação (0–100).
            risk_score:          Sub-pontuação de gestão de risco (0–100).
            quest_tip:           Dica educativa de uma frase proveniente da IA.
            quest_continues:     True se a quest multi-ciclo ainda tem ciclos restantes.
            quest_cycle_label:   Ex: "Ciclo 1 de 3" para quests multi-ciclo.
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
        self._quest_score = quest_score
        self._on_continue = on_continue or (lambda: None)
        self._goal_name = goal_name
        self._goal_completion_pct = goal_completion_pct
        self._goal_remaining_r = goal_remaining_r
        self._objective_score = objective_score
        self._allocation_score = allocation_score
        self._risk_score = risk_score
        self._quest_tip = quest_tip
        self._quest_continues = quest_continues
        self._quest_cycle_label = quest_cycle_label
        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ── Scrollable container ──────────────────────────────────────────────
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        # All content goes into `scroll` instead of `self`
        _self = scroll

        # ── Row 0: Título ─────────────────────────────────────────────────────
        if self._quest_continues:
            quest_badge = "  ⏳ Missão em Andamento"
            badge_color = "#3b82d4"
        elif self._quest_score > 75:
            quest_badge = "  🏆 Quest Concluída!"
            badge_color = "#4caf50"
        elif self._quest_score >= 25:
            quest_badge = "  ⚡ Quase Lá!"
            badge_color = "#f0a500"
        else:
            quest_badge = "  💀 Quest Falhou"
            badge_color = "#e05c5c"

        ctk.CTkLabel(
            _self,
            text=f"Relatório de Desempenho{quest_badge}",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=badge_color,
        ).grid(row=0, column=0, padx=40, pady=(44, 4))

        # ── Row 1: Subtítulo ──────────────────────────────────────────────────
        cycle_suffix = f"  ·  {self._quest_cycle_label}" if self._quest_cycle_label else ""
        ctk.CTkLabel(
            _self,
            text=f"{self._player_name}  ·  {self._cycles_played} mês(es) jogado(s){cycle_suffix}",
            font=ctk.CTkFont(size=13),
            text_color="gray",
        ).grid(row=1, column=0, padx=40, pady=(0, 12))

        # ── Row 2: Score Breakdown (pill labels) ──────────────────────────────
        has_scores = any(
            v is not None
            for v in (self._objective_score, self._allocation_score, self._risk_score)
        )
        if has_scores:
            score_row = ctk.CTkFrame(_self, fg_color="transparent")
            score_row.grid(row=2, column=0, padx=40, pady=(0, 12), sticky="ew")
            score_row.grid_columnconfigure((0, 1, 2), weight=1)

            def _pill(parent, col: int, label: str, value: int | None, good_threshold: int = 60):
                color = (
                    "#4caf50" if (value or 0) >= good_threshold
                    else "#f0a500" if (value or 0) >= 35
                    else "#e05c5c"
                )
                text = f"{label}\n{value}/100" if value is not None else f"{label}\n—"
                pill = ctk.CTkFrame(parent, corner_radius=8, fg_color=color)
                pill.grid(row=0, column=col, padx=6, sticky="ew")
                ctk.CTkLabel(
                    pill, text=text,
                    font=ctk.CTkFont(size=12, weight="bold"),
                    text_color="white",
                    justify="center",
                ).grid(row=0, column=0, padx=12, pady=8)

            _pill(score_row, 0, "Objetivo", self._objective_score)
            _pill(score_row, 1, "Alocação", self._allocation_score)
            _pill(score_row, 2, "Gestão de Risco", self._risk_score)

        # ── Row 3: Cards de métricas ──────────────────────────────────────────
        metrics = ctk.CTkFrame(_self, fg_color="transparent")
        metrics.grid(row=3, column=0, padx=40, pady=0, sticky="ew")
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

        # ── Row 4: Alocação ───────────────────────────────────────────────────
        alloc_card = ctk.CTkFrame(_self, corner_radius=10)
        alloc_card.grid(row=4, column=0, padx=40, pady=(16, 0), sticky="ew")
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

        # ── Row 5: Goal Progress ──────────────────────────────────────────────
        if self._goal_name:
            goal_card = ctk.CTkFrame(_self, corner_radius=10)
            goal_card.grid(row=5, column=0, padx=40, pady=(16, 0), sticky="ew")
            goal_card.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(
                goal_card,
                text=f"🎯  Meta: {self._goal_name}",
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color="gray",
            ).grid(row=0, column=0, padx=16, pady=(14, 4), sticky="w")

            progress_bar = ctk.CTkProgressBar(goal_card, width=400)
            progress_bar.set(min(self._goal_completion_pct / 100.0, 1.0))
            progress_bar.grid(row=1, column=0, padx=16, pady=(0, 4), sticky="ew")

            pct_label = f"{self._goal_completion_pct:.1f}% concluído"
            remaining_label = (
                f"  ·  R$ {self._goal_remaining_r:,.2f} restantes"
                if self._goal_remaining_r > 0
                else "  ·  Meta atingida! 🎉"
            )
            ctk.CTkLabel(
                goal_card,
                text=pct_label + remaining_label,
                font=ctk.CTkFont(size=12),
                text_color="gray",
            ).grid(row=2, column=0, padx=16, pady=(0, 14), sticky="w")

        # ── Row 6: Feedback do agente ─────────────────────────────────────────
        feedback_card = ctk.CTkFrame(_self, corner_radius=10)
        feedback_card.grid(row=6, column=0, padx=40, pady=(16, 0), sticky="ew")
        feedback_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            feedback_card,
            text="🤖  Conselheiro Real",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="gray",
        ).grid(row=0, column=0, padx=20, pady=(14, 4), sticky="w")

        # Key Learning card (quest_tip) — shown prominently when available
        if self._quest_tip:
            tip_frame = ctk.CTkFrame(feedback_card, corner_radius=8, fg_color="#1a3a5c", border_width=1, border_color="#3b82d4")
            tip_frame.grid(row=1, column=0, padx=16, pady=(0, 8), sticky="ew")
            tip_frame.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(
                tip_frame,
                text="💡  Aprendizado-chave",
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color="#3b82d4",
            ).grid(row=0, column=0, padx=12, pady=(10, 2), sticky="w")
            ctk.CTkLabel(
                tip_frame,
                text=self._quest_tip,
                font=ctk.CTkFont(size=13),
                wraplength=440,
                justify="left",
            ).grid(row=1, column=0, padx=12, pady=(0, 10), sticky="w")

        ctk.CTkLabel(
            feedback_card,
            text=self._agent_feedback,
            font=ctk.CTkFont(size=13),
            wraplength=460,
            justify="left",
        ).grid(row=2, column=0, padx=20, pady=(0, 16), sticky="w")

        # ── Row 7: Botão continuar ────────────────────────────────────────────
        btn_text = "Próximo Mês  →" if self._quest_continues else "Continuar  →"
        ctk.CTkButton(
            _self,
            text=btn_text,
            font=ctk.CTkFont(size=15, weight="bold"),
            width=200,
            height=44,
            corner_radius=10,
            command=self._on_continue,
        ).grid(row=7, column=0, padx=40, pady=(20, 44))

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
        quest_score=85,
        on_continue=lambda: print("Continuar..."),
        fg_color="transparent",
    ).pack(fill="both", expand=True)

    root.mainloop()

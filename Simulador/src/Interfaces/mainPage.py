"""
mainPage.py
-----------
Página principal do simulador — hub central de navegação.

Exibe um resumo do portfólio do jogador (saldo, patrimônio, ciclo)
e botões de ação para as seções do simulador.
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk


class MainPage(ctk.CTkFrame):
    """Hub principal do simulador."""

    def __init__(
        self,
        master,
        player_name: str = "Aventureiro",
        cash: float = 0.0,
        net_worth: float = 0.0,
        cycle: int = 1,
        fixed_positions: list | None = None,
        stock_positions: list | None = None,
        active_quest: dict | None = None,
        on_low_risk: Callable | None = None,
        on_high_risk: Callable | None = None,
        on_end_month: Callable | None = None,
        **kwargs,
    ):
        """
        Args:
            master:           Widget pai.
            player_name:      Nome do jogador.
            cash:             Saldo em caixa (R$).
            net_worth:        Patrimônio total (R$).
            cycle:            Ciclo/mês atual da simulação.
            fixed_positions:  Lista de dicts do snapshot de renda fixa.
            stock_positions:  Lista de dicts do snapshot de ações.
            active_quest:     Dict com title, objective, type da missão ativa.
            on_low_risk:      Navega para Renda Fixa / baixo risco.
            on_high_risk:     Navega para Renda Variável / alto risco.
            on_end_month:     Avança para o fim do mês.
        """
        super().__init__(master, **kwargs)
        self._player_name = player_name
        self._cash = cash
        self._net_worth = net_worth
        self._cycle = cycle
        self._fixed_positions = fixed_positions or []
        self._stock_positions = stock_positions or []
        self._active_quest = active_quest or {}
        self._on_low_risk = on_low_risk or (lambda: None)
        self._on_high_risk = on_high_risk or (lambda: None)
        self._on_end_month = on_end_month or (lambda: None)
        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)

        # ── Cabeçalho ────────────────────────────────────────────────────────
        ctk.CTkLabel(
            self,
            text=f"Bem-vindo, {self._player_name}!",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).grid(row=0, column=0, padx=40, pady=(28, 4))

        ctk.CTkLabel(
            self,
            text=f"📅  Mês {self._cycle}  —  Reino das Finanças",
            font=ctk.CTkFont(size=13),
            text_color="gray",
        ).grid(row=1, column=0, padx=40, pady=(0, 16))

        # ── Cards de resumo ──────────────────────────────────────────────────
        summary_frame = ctk.CTkFrame(self, fg_color="transparent")
        summary_frame.grid(row=2, column=0, padx=40, pady=0, sticky="ew")
        summary_frame.grid_columnconfigure((0, 1), weight=1)

        self._stat_card(summary_frame, "💵  Saldo em Caixa", f"R$ {self._cash:,.2f}", 0)
        self._stat_card(summary_frame, "📈  Patrimônio Total", f"R$ {self._net_worth:,.2f}", 1)

        # ── Missão ativa ─────────────────────────────────────────────────────
        self._build_quest_card(row=3)

        # ── Holdings (scrollable) ─────────────────────────────────────────────
        self._build_holdings(row=4)

        # ── Botões de ação ───────────────────────────────────────────────────
        actions_frame = ctk.CTkFrame(self, fg_color="transparent")
        actions_frame.grid(row=5, column=0, padx=40, pady=(14, 0), sticky="ew")
        actions_frame.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            actions_frame,
            text="🏦  Renda Fixa",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=52,
            corner_radius=10,
            command=self._on_low_risk,
        ).grid(row=0, column=0, padx=(0, 8), pady=0, sticky="ew")

        ctk.CTkButton(
            actions_frame,
            text="📊  Renda Variável",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=52,
            corner_radius=10,
            command=self._on_high_risk,
        ).grid(row=0, column=1, padx=(8, 0), pady=0, sticky="ew")

        # ── Botão fim do mês ─────────────────────────────────────────────────
        ctk.CTkButton(
            self,
            text="⏭  Avançar Mês",
            font=ctk.CTkFont(size=15, weight="bold"),
            width=220,
            height=44,
            corner_radius=10,
            fg_color="#5a7a3a",
            hover_color="#4a6a2a",
            command=self._on_end_month,
        ).grid(row=6, column=0, padx=40, pady=(16, 28))

    def _build_quest_card(self, row: int):
        """Renders the active quest card, if a quest is set."""
        if not self._active_quest:
            return

        title     = self._active_quest.get("title", "Missão Ativa")
        objective = self._active_quest.get("objective", "")
        q_type    = self._active_quest.get("type", "")
        type_colors = {
            "acumulação":   "#3b82d4",
            "sobrevivência": "#c87a20",
            "evento":        "#7c5cd8",
        }
        accent = type_colors.get(q_type, "#3b82d4")

        card = ctk.CTkFrame(self, corner_radius=10)
        card.grid(row=row, column=0, padx=40, pady=(14, 0), sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        # coloured left-bar accent via a narrow frame
        bar = ctk.CTkFrame(card, width=4, corner_radius=2, fg_color=accent)
        bar.grid(row=0, column=0, rowspan=3, padx=(10, 0), pady=10, sticky="ns")
        card.grid_columnconfigure(0, minsize=14)
        card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            card,
            text="🗡  Missão Ativa",
            font=ctk.CTkFont(size=11),
            text_color="gray",
            anchor="w",
        ).grid(row=0, column=1, padx=(6, 16), pady=(10, 0), sticky="w")

        ctk.CTkLabel(
            card,
            text=title,
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w",
            wraplength=460,
        ).grid(row=1, column=1, padx=(6, 16), pady=(2, 0), sticky="w")

        if objective:
            ctk.CTkLabel(
                card,
                text=f"🎯  {objective}",
                font=ctk.CTkFont(size=12),
                text_color="#4caf50",
                anchor="w",
                wraplength=460,
            ).grid(row=2, column=1, padx=(6, 16), pady=(4, 12), sticky="w")

    def _build_holdings(self, row: int):
        """Renders a scrollable holdings card when the user has any open positions."""
        has_fixed  = bool(self._fixed_positions)
        has_stocks = bool(self._stock_positions)
        if not has_fixed and not has_stocks:
            return

        # outer card for the header label
        card = ctk.CTkFrame(self, corner_radius=10)
        card.grid(row=row, column=0, padx=40, pady=(14, 0), sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            card,
            text="📂  Posições em Aberto",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="gray",
            anchor="w",
        ).grid(row=0, column=0, padx=16, pady=(12, 4), sticky="w")

        # scrollable inner frame — max height caps at ~130 px (~3–4 rows)
        scroll = ctk.CTkScrollableFrame(card, height=120, corner_radius=6, fg_color="transparent")
        scroll.grid(row=1, column=0, padx=8, pady=(0, 8), sticky="ew")
        scroll.grid_columnconfigure(0, weight=1)

        inner_row = 0

        # Fixed income positions
        if has_fixed:
            for pos in self._fixed_positions:
                label      = pos.get("product", "Renda Fixa")
                value      = pos.get("principal_with_earnings", 0.0)
                earn       = pos.get("gross_earnings", 0.0)
                sign       = "+" if earn >= 0 else ""
                earn_color = "#4caf50" if earn >= 0 else "#e05c5c"
                redeemable = "🔓" if pos.get("can_redeem") else "🔒"
                line_frame = ctk.CTkFrame(scroll, fg_color="transparent")
                line_frame.grid(row=inner_row, column=0, padx=8, pady=2, sticky="ew")
                line_frame.grid_columnconfigure(1, weight=1)
                ctk.CTkLabel(
                    line_frame,
                    text=f"🏦 {redeemable} {label}",
                    font=ctk.CTkFont(size=12),
                    anchor="w",
                ).grid(row=0, column=0, sticky="w")
                ctk.CTkLabel(
                    line_frame,
                    text=f"R$ {value:,.2f}  ({sign}R$ {earn:,.2f})",
                    font=ctk.CTkFont(size=12, weight="bold"),
                    text_color=earn_color,
                    anchor="e",
                ).grid(row=0, column=1, sticky="e")
                inner_row += 1

        # Stock positions
        if has_stocks:
            for pos in self._stock_positions:
                ticker    = pos.get("ticker", "?")
                value     = pos.get("current_value", 0.0)
                pnl_pct   = pos.get("unrealized_pnl_pct", 0.0)
                pnl       = pos.get("unrealized_pnl", 0.0)
                sign      = "+" if pnl >= 0 else ""
                pnl_color = "#4caf50" if pnl >= 0 else "#e05c5c"
                line_frame = ctk.CTkFrame(scroll, fg_color="transparent")
                line_frame.grid(row=inner_row, column=0, padx=8, pady=2, sticky="ew")
                line_frame.grid_columnconfigure(1, weight=1)
                ctk.CTkLabel(
                    line_frame,
                    text=f"📊 {ticker}",
                    font=ctk.CTkFont(size=12),
                    anchor="w",
                ).grid(row=0, column=0, sticky="w")
                ctk.CTkLabel(
                    line_frame,
                    text=f"R$ {value:,.2f}  ({sign}{pnl_pct:.1f}%)",
                    font=ctk.CTkFont(size=12, weight="bold"),
                    text_color=pnl_color,
                    anchor="e",
                ).grid(row=0, column=1, sticky="e")
                inner_row += 1

    @staticmethod
    def _stat_card(parent, title: str, value: str, col: int):
        card = ctk.CTkFrame(parent, corner_radius=10)
        card.grid(row=0, column=col, padx=6 if col else (0, 6), sticky="ew")
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            card, text=title, font=ctk.CTkFont(size=12), text_color="gray"
        ).grid(row=0, column=0, padx=16, pady=(14, 2))
        ctk.CTkLabel(
            card, text=value, font=ctk.CTkFont(size=18, weight="bold")
        ).grid(row=1, column=0, padx=16, pady=(0, 14))


# ---------------------------------------------------------------------------
# Execução standalone
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    root.title("Simulador — Página Principal")
    root.geometry("580x400")
    root.resizable(False, False)

    MainPage(
        master=root,
        player_name="João Silva",
        cash=2500.00,
        net_worth=8750.00,
        cycle=3,
        fixed_positions=[
            {"product": "Tesouro Selic", "principal_with_earnings": 3200.00,
             "gross_earnings": 42.50, "can_redeem": True},
            {"product": "CDB 90 dias", "principal_with_earnings": 1050.10,
             "gross_earnings": 50.10, "can_redeem": False},
        ],
        stock_positions=[
            {"ticker": "BRCO3", "current_value": 1400.00,
             "unrealized_pnl": 120.00, "unrealized_pnl_pct": 9.4},
        ],
        active_quest={
            "title": "O Fundo de Emergência do Rei",
            "objective": "Acumule R$ 4.000,00 em ativos líquidos.",
            "type": "acumulação",
        },
        on_low_risk=lambda: print("→ Renda Fixa"),
        on_high_risk=lambda: print("→ Renda Variável"),
        on_end_month=lambda: print("→ Fim do Mês"),
        fg_color="transparent",
    ).pack(fill="both", expand=True)

    root.mainloop()

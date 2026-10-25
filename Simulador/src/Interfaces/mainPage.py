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
        on_low_risk: Callable | None = None,
        on_high_risk: Callable | None = None,
        on_end_month: Callable | None = None,
        **kwargs,
    ):
        """
        Args:
            master:       Widget pai.
            player_name:  Nome do jogador.
            cash:         Saldo em caixa (R$).
            net_worth:    Patrimônio total (R$).
            cycle:        Ciclo/mês atual da simulação.
            on_low_risk:  Navega para Renda Fixa / baixo risco.
            on_high_risk: Navega para Renda Variável / alto risco.
            on_end_month: Avança para o fim do mês.
        """
        super().__init__(master, **kwargs)
        self._player_name = player_name
        self._cash = cash
        self._net_worth = net_worth
        self._cycle = cycle
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
        ).grid(row=0, column=0, padx=40, pady=(40, 4))

        ctk.CTkLabel(
            self,
            text=f"📅  Mês {self._cycle}  —  Reino das Finanças",
            font=ctk.CTkFont(size=13),
            text_color="gray",
        ).grid(row=1, column=0, padx=40, pady=(0, 24))

        # ── Cards de resumo ──────────────────────────────────────────────────
        summary_frame = ctk.CTkFrame(self, fg_color="transparent")
        summary_frame.grid(row=2, column=0, padx=40, pady=0, sticky="ew")
        summary_frame.grid_columnconfigure((0, 1), weight=1)

        self._stat_card(summary_frame, "💵  Saldo em Caixa", f"R$ {self._cash:,.2f}", 0)
        self._stat_card(summary_frame, "📈  Patrimônio Total", f"R$ {self._net_worth:,.2f}", 1)

        # ── Botões de ação ───────────────────────────────────────────────────
        actions_frame = ctk.CTkFrame(self, fg_color="transparent")
        actions_frame.grid(row=3, column=0, padx=40, pady=(28, 0), sticky="ew")
        actions_frame.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            actions_frame,
            text="🏦  Renda Fixa",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=56,
            corner_radius=10,
            command=self._on_low_risk,
        ).grid(row=0, column=0, padx=(0, 8), pady=0, sticky="ew")

        ctk.CTkButton(
            actions_frame,
            text="📊  Renda Variável",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=56,
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
        ).grid(row=4, column=0, padx=40, pady=(24, 48))

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
        on_low_risk=lambda: print("→ Renda Fixa"),
        on_high_risk=lambda: print("→ Renda Variável"),
        on_end_month=lambda: print("→ Fim do Mês"),
        fg_color="transparent",
    ).pack(fill="both", expand=True)

    root.mainloop()

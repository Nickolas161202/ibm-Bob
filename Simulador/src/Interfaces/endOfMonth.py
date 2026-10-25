"""
endOfMonth.py
-------------
Tela de fim do mês — processa e exibe o que aconteceu no ciclo.

Mostra os eventos de mercado, rendimentos de renda fixa gerados
e variações dos preços das ações naquele ciclo, antes de avançar.
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk


class EndOfMonthPage(ctk.CTkFrame):
    """Tela de resumo do fim de um ciclo/mês."""

    def __init__(
        self,
        master,
        cycle: int = 1,
        market_events: list[str] | None = None,
        stock_events: list[str] | None = None,
        fixed_earnings: float = 0.0,
        selic_pct: float = 0.0,
        inflation_pct: float = 0.0,
        on_next: Callable | None = None,
        **kwargs,
    ):
        """
        Args:
            master:         Widget pai.
            cycle:          Número do ciclo/mês que acabou.
            market_events:  Lista de eventos de mercado (textos narrativos).
            stock_events:   Lista de variações de preço das ações.
            fixed_earnings: Total de rendimentos de renda fixa neste ciclo (R$).
            selic_pct:      Taxa SELIC anual atual (%).
            inflation_pct:  Inflação anual estimada (%).
            on_next:        Callback ao clicar em "Próximo Mês".
        """
        super().__init__(master, **kwargs)
        self._cycle = cycle
        self._market_events = market_events or ["Nenhum evento registrado."]
        self._stock_events = stock_events or ["Sem variações significativas."]
        self._fixed_earnings = fixed_earnings
        self._selic_pct = selic_pct
        self._inflation_pct = inflation_pct
        self._on_next = on_next or (lambda: None)
        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)

        # ── Título ────────────────────────────────────────────────────────────
        ctk.CTkLabel(
            self,
            text=f"📅  Fim do Mês {self._cycle}",
            font=ctk.CTkFont(size=24, weight="bold"),
        ).grid(row=0, column=0, padx=40, pady=(44, 4))

        ctk.CTkLabel(
            self,
            text="Confira o que aconteceu no Reino das Finanças",
            font=ctk.CTkFont(size=13),
            text_color="gray",
        ).grid(row=1, column=0, padx=40, pady=(0, 20))

        # ── Indicadores macro ─────────────────────────────────────────────────
        macro = ctk.CTkFrame(self, fg_color="transparent")
        macro.grid(row=2, column=0, padx=40, pady=0, sticky="ew")
        macro.grid_columnconfigure((0, 1, 2), weight=1)

        for col, (label, value) in enumerate([
            ("📊 SELIC a.a.", f"{self._selic_pct:.2f}%"),
            ("🏷  Inflação a.a.", f"{self._inflation_pct:.1f}%"),
            ("💹 Rend. Renda Fixa", f"+ R$ {self._fixed_earnings:,.2f}"),
        ]):
            card = ctk.CTkFrame(macro, corner_radius=10)
            padx = (0, 6) if col == 0 else (3, 3) if col == 1 else (6, 0)
            card.grid(row=0, column=col, padx=padx, sticky="ew")
            card.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(
                card, text=label, font=ctk.CTkFont(size=12), text_color="gray"
            ).grid(row=0, column=0, pady=(12, 2))
            ctk.CTkLabel(
                card, text=value, font=ctk.CTkFont(size=16, weight="bold")
            ).grid(row=1, column=0, pady=(0, 12))

        # ── Eventos de mercado ────────────────────────────────────────────────
        self._section(row=3, icon="🏛️", title="Eventos do Mercado", items=self._market_events)

        # ── Variação das ações ────────────────────────────────────────────────
        self._section(row=4, icon="📉", title="Mercado de Ações", items=self._stock_events)

        # ── Botão avançar ─────────────────────────────────────────────────────
        ctk.CTkButton(
            self,
            text="Próximo Mês  →",
            font=ctk.CTkFont(size=15, weight="bold"),
            width=220,
            height=44,
            corner_radius=10,
            command=self._on_next,
        ).grid(row=5, column=0, padx=40, pady=(20, 44))

    def _section(self, row: int, icon: str, title: str, items: list[str]):
        """Renderiza um card de lista com título e itens."""
        card = ctk.CTkFrame(self, corner_radius=10)
        card.grid(row=row, column=0, padx=40, pady=(14, 0), sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            card,
            text=f"{icon}  {title}",
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, padx=16, pady=(12, 6), sticky="w")

        for i, item in enumerate(items):
            ctk.CTkLabel(
                card,
                text=f"  • {item}",
                font=ctk.CTkFont(size=12),
                text_color="gray",
                anchor="w",
                wraplength=480,
                justify="left",
            ).grid(row=i + 1, column=0, padx=16, pady=2, sticky="w")

        # bottom padding
        ctk.CTkLabel(card, text="").grid(row=len(items) + 1, column=0, pady=4)


# ---------------------------------------------------------------------------
# Execução standalone
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    root.title("Fim do Mês")
    root.geometry("620x620")
    root.resizable(False, False)

    EndOfMonthPage(
        master=root,
        cycle=3,
        market_events=[
            "O Banco Central manteve a SELIC em 10,75% a.a.",
            "Inflação mensal ficou em 0,4%, dentro do esperado.",
        ],
        stock_events=[
            "VALE3 subiu +3,2% — forte demanda de minério de ferro.",
            "PETR4 caiu -1,8% — queda no preço do petróleo.",
            "ITUB4 ficou estável (+0,1%).",
        ],
        fixed_earnings=87.50,
        selic_pct=10.75,
        inflation_pct=4.8,
        on_next=lambda: print("→ Próximo mês"),
        fg_color="transparent",
    ).pack(fill="both", expand=True)

    root.mainloop()

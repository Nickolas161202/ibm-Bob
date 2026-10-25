"""
highRiskInvestments.py
----------------------
Tela de investimentos de alto risco (Renda Variável / Ações).

Lista os tickers disponíveis no mercado com preço e tendência atual,
e permite comprar ou vender ações.
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk


# Stocks placeholder — serão substituídos pelos dados reais do engine
_PLACEHOLDER_STOCKS = [
    {"ticker": "VALE3", "name": "Vale S.A.", "price": 72.40, "trend": "alta"},
    {"ticker": "PETR4", "name": "Petrobras", "price": 38.15, "trend": "queda"},
    {"ticker": "ITUB4", "name": "Itaú Unibanco", "price": 28.90, "trend": "estável"},
    {"ticker": "BBDC4", "name": "Bradesco", "price": 14.55, "trend": "alta"},
    {"ticker": "MGLU3", "name": "Magazine Luiza", "price": 9.80, "trend": "queda"},
]

_TREND_COLOR = {
    "alta": "#4caf50",
    "queda": "#e05c5c",
    "estável": "gray",
}
_TREND_ICON = {"alta": "▲", "queda": "▼", "estável": "●"}


class HighRiskInvestmentsPage(ctk.CTkFrame):
    """Tela de Renda Variável / ações."""

    def __init__(
        self,
        master,
        stocks: list[dict] | None = None,
        on_buy: Callable[[str, float], None] | None = None,
        on_sell: Callable[[str, float], None] | None = None,
        on_back: Callable | None = None,
        **kwargs,
    ):
        """
        Args:
            master:   Widget pai.
            stocks:   Lista de stocks (dicts com ticker, name, price, trend).
            on_buy:   Callback(ticker, amount_brl) ao comprar.
            on_sell:  Callback(ticker, shares) ao vender.
            on_back:  Callback para voltar.
        """
        super().__init__(master, **kwargs)
        self._stocks = stocks or _PLACEHOLDER_STOCKS
        self._on_buy = on_buy or (lambda t, a: None)
        self._on_sell = on_sell or (lambda t, s: None)
        self._on_back = on_back or (lambda: None)
        self._selected_ticker: str | None = None
        self._error_text = ctk.StringVar(value="")
        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)

        # ── Cabeçalho ────────────────────────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, padx=40, pady=(36, 0), sticky="ew")
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(
            header,
            text="←",
            width=36,
            height=36,
            corner_radius=8,
            fg_color="gray25",
            hover_color="gray30",
            command=self._on_back,
        ).grid(row=0, column=0, padx=(0, 12))

        ctk.CTkLabel(
            header,
            text="📊  Renda Variável",
            font=ctk.CTkFont(size=22, weight="bold"),
            anchor="w",
        ).grid(row=0, column=1, sticky="w")

        ctk.CTkLabel(
            self,
            text="Selecione uma ação e informe o valor (compra) ou qtd. de cotas (venda)",
            font=ctk.CTkFont(size=13),
            text_color="gray",
        ).grid(row=1, column=0, padx=40, pady=(4, 20))

        # ── Tabela de ações ──────────────────────────────────────────────────
        scroll = ctk.CTkScrollableFrame(self, height=200, corner_radius=10)
        scroll.grid(row=2, column=0, padx=40, pady=0, sticky="ew")
        scroll.grid_columnconfigure(0, weight=1)

        self._stock_buttons: list[ctk.CTkButton] = []
        for i, stock in enumerate(self._stocks):
            icon = _TREND_ICON.get(stock["trend"], "●")
            btn = ctk.CTkButton(
                scroll,
                text=(
                    f"{stock['ticker']}  —  {stock['name']}"
                    f"    R$ {stock['price']:,.2f}    {icon} {stock['trend'].capitalize()}"
                ),
                font=ctk.CTkFont(size=12),
                height=40,
                corner_radius=8,
                fg_color="gray20",
                hover_color="gray30",
                anchor="w",
                command=lambda t=stock["ticker"]: self._select_ticker(t),
            )
            btn.grid(row=i, column=0, pady=4, sticky="ew")
            self._stock_buttons.append(btn)

        # ── Input de valor/quantidade ────────────────────────────────────────
        input_frame = ctk.CTkFrame(self, fg_color="transparent")
        input_frame.grid(row=3, column=0, padx=40, pady=(20, 0), sticky="ew")
        input_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            input_frame,
            text="Valor / Qtd.",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=0, column=0, padx=(0, 12))

        self.amount_entry = ctk.CTkEntry(
            input_frame,
            placeholder_text="Ex: 500.00",
            height=38,
        )
        self.amount_entry.grid(row=0, column=1, sticky="ew")

        # ── Erro ─────────────────────────────────────────────────────────────
        ctk.CTkLabel(
            self,
            textvariable=self._error_text,
            text_color="#e05c5c",
            font=ctk.CTkFont(size=12),
        ).grid(row=4, column=0, padx=40, pady=(10, 0))

        # ── Botões comprar / vender ───────────────────────────────────────────
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=5, column=0, padx=40, pady=(12, 36))
        btn_frame.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            btn_frame,
            text="Comprar  →",
            font=ctk.CTkFont(size=14, weight="bold"),
            width=160,
            height=44,
            corner_radius=10,
            fg_color="#3b82d4",
            command=self._on_buy_click,
        ).grid(row=0, column=0, padx=(0, 10))

        ctk.CTkButton(
            btn_frame,
            text="Vender  ↓",
            font=ctk.CTkFont(size=14, weight="bold"),
            width=160,
            height=44,
            corner_radius=10,
            fg_color="#7c5cd8",
            command=self._on_sell_click,
        ).grid(row=0, column=1, padx=(10, 0))

    def _select_ticker(self, ticker: str):
        self._selected_ticker = ticker
        for btn in self._stock_buttons:
            text = btn.cget("text")
            if text.startswith(ticker):
                btn.configure(fg_color="#3b82d4")
            else:
                btn.configure(fg_color="gray20")

    def _parse_amount(self) -> float | None:
        raw = self.amount_entry.get().strip().replace(",", ".")
        try:
            val = float(raw)
            if val <= 0:
                raise ValueError
            return val
        except ValueError:
            self._error_text.set("⚠  Valor inválido. Use um número positivo.")
            return None

    def _on_buy_click(self):
        if not self._selected_ticker:
            self._error_text.set("⚠  Selecione uma ação primeiro.")
            return
        amount = self._parse_amount()
        if amount is None:
            return
        self._error_text.set("")
        self._on_buy(self._selected_ticker, amount)

    def _on_sell_click(self):
        if not self._selected_ticker:
            self._error_text.set("⚠  Selecione uma ação primeiro.")
            return
        shares = self._parse_amount()
        if shares is None:
            return
        self._error_text.set("")
        self._on_sell(self._selected_ticker, shares)


# ---------------------------------------------------------------------------
# Execução standalone
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    root.title("Renda Variável")
    root.geometry("700x540")
    root.resizable(False, False)

    HighRiskInvestmentsPage(
        master=root,
        on_buy=lambda t, a: print(f"Comprar R$ {a:.2f} de {t}"),
        on_sell=lambda t, s: print(f"Vender {s} cotas de {t}"),
        on_back=lambda: print("← Voltar"),
        fg_color="transparent",
    ).pack(fill="both", expand=True)

    root.mainloop()

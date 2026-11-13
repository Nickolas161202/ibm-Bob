"""
highRiskInvestments.py
----------------------
Tela de investimentos de alto risco (Renda Variável / Ações).

Exibe os tickers disponíveis com preço e tendência reais do engine,
as posições já detidas pelo jogador (com P&L), e permite comprar ou vender.

Callbacks:
  on_buy(ticker: str, amount_brl: float)   → comprar pelo valor em R$
  on_sell(ticker: str, shares: float)      → vender quantidade de cotas
  on_back()                                → voltar
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk


def _confirm_popup(
    master,
    title: str,
    message: str,
    on_yes: Callable,
) -> None:
    """
    Exibe um popup modal de confirmação com botões Confirmar / Cancelar.
    Chama `on_yes` apenas se o usuário confirmar.
    """
    dialog = ctk.CTkToplevel(master)
    dialog.title(title)
    dialog.resizable(False, False)
    dialog.grab_set()
    dialog.lift()
    dialog.focus_force()

    dialog.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(
        dialog,
        text=message,
        font=ctk.CTkFont(size=14),
        wraplength=340,
        justify="center",
    ).grid(row=0, column=0, padx=32, pady=(28, 20))

    btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
    btn_frame.grid(row=1, column=0, padx=32, pady=(0, 24))
    btn_frame.grid_columnconfigure((0, 1), weight=1)

    def _yes():
        dialog.destroy()
        on_yes()

    ctk.CTkButton(
        btn_frame,
        text="✅  Confirmar",
        font=ctk.CTkFont(size=13, weight="bold"),
        width=130, height=38,
        corner_radius=8,
        fg_color="#3b7a3a",
        hover_color="#2f6030",
        command=_yes,
    ).grid(row=0, column=0, padx=(0, 8))

    ctk.CTkButton(
        btn_frame,
        text="✖  Cancelar",
        font=ctk.CTkFont(size=13),
        width=130, height=38,
        corner_radius=8,
        fg_color="gray25",
        hover_color="gray35",
        command=dialog.destroy,
    ).grid(row=0, column=1, padx=(8, 0))

    master.update_idletasks()
    mw = master.winfo_width()
    mh = master.winfo_height()
    mx = master.winfo_rootx()
    my = master.winfo_rooty()
    dialog.update_idletasks()
    dw = dialog.winfo_reqwidth()
    dh = dialog.winfo_reqheight()
    x = mx + (mw - dw) // 2
    y = my + (mh - dh) // 2
    dialog.geometry(f"+{x}+{y}")


_TREND_COLOR = {
    "📈 Alta":      "#4caf50",
    "📉 Baixa":     "#e05c5c",
    "➡️  Estável":  "gray",
    "🌀 Caótico":   "#f5a623",
}


class HighRiskInvestmentsPage(ctk.CTkFrame):
    """Tela de Renda Variável / ações."""

    def __init__(
        self,
        master,
        stocks: list[dict] | None = None,
        portfolio_positions: list[dict] | None = None,
        cash: float = 0.0,
        on_buy: Callable[[str, float], None] | None = None,
        on_sell: Callable[[str, float], None] | None = None,
        on_back: Callable | None = None,
        **kwargs,
    ):
        """
        Args:
            master:               Widget pai.
            stocks:               Lista de dicts do engine (market_snapshot → stocks):
                                    ticker (str)
                                    name (str)
                                    sector (str)
                                    price (float)
                                    change_pct (float)   – variação no último ciclo
                                    trend (str)          – Trend.value
                                    cycles_in_trend (int)
            portfolio_positions:  Lista de dicts do snapshot do portfólio
                                  (full_snapshot → stock_positions), cada um com:
                                    ticker (str)
                                    shares (float)
                                    avg_purchase_price (float)
                                    current_price (float)
                                    current_value (float)
                                    unrealized_pnl (float)
                                    unrealized_pnl_pct (float)
            cash:                 Saldo disponível em caixa.
            on_buy:               Callback(ticker, amount_brl).
            on_sell:              Callback(ticker, shares).
            on_back:              Callback para voltar.
        """
        super().__init__(master, **kwargs)
        self._stocks = stocks or []
        self._portfolio_positions = portfolio_positions or []
        self._cash = cash
        self._on_buy = on_buy or (lambda t, a: None)
        self._on_sell = on_sell or (lambda t, s: None)
        self._on_back = on_back or (lambda: None)
        self._selected_ticker: str | None = None
        self._mode = ctk.StringVar(value="buy")   # "buy" | "sell"
        self._error_text = ctk.StringVar(value="")
        self._build()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ── Scrollable container ─────────────────────────────────────────────
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)
        _s = scroll

        # ── Cabeçalho ────────────────────────────────────────────────────────
        header = ctk.CTkFrame(_s, fg_color="transparent")
        header.grid(row=0, column=0, padx=40, pady=(28, 0), sticky="ew")
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(
            header,
            text="←",
            width=36, height=36,
            corner_radius=8,
            fg_color="gray25", hover_color="gray30",
            command=self._on_back,
        ).grid(row=0, column=0, padx=(0, 12))

        ctk.CTkLabel(
            header,
            text="📊  Renda Variável",
            font=ctk.CTkFont(size=22, weight="bold"),
            anchor="w",
        ).grid(row=0, column=1, sticky="w")

        ctk.CTkLabel(
            header,
            text=f"💵  Disponível: R$ {self._cash:,.2f}",
            font=ctk.CTkFont(size=13),
            text_color="#4caf50",
            anchor="e",
        ).grid(row=0, column=2, sticky="e")

        # ── Tabela de ações do mercado ────────────────────────────────────────
        ctk.CTkLabel(
            _s,
            text="Mercado — selecione uma ação",
            font=ctk.CTkFont(size=13),
            text_color="gray",
        ).grid(row=1, column=0, padx=40, pady=(14, 6), sticky="w")

        scroll_mkt = ctk.CTkScrollableFrame(_s, height=160, corner_radius=10)
        scroll_mkt.grid(row=2, column=0, padx=40, pady=0, sticky="ew")
        scroll_mkt.grid_columnconfigure(0, weight=1)

        self._stock_buttons: list[ctk.CTkButton] = []
        if self._stocks:
            for i, stock in enumerate(self._stocks):
                chg = stock.get("change_pct", 0.0)
                chg_sign = "+" if chg >= 0 else ""
                btn = ctk.CTkButton(
                    scroll_mkt,
                    text=(
                        f"{stock['ticker']:<7}  {stock.get('name', ''):<24}"
                        f"  R$ {stock['price']:>8.2f}"
                        f"  {chg_sign}{chg:.1f}%"
                    ),
                    font=ctk.CTkFont(size=12, family="Courier"),
                    height=40,
                    corner_radius=8,
                    fg_color="gray20",
                    hover_color="gray30",
                    anchor="w",
                    command=lambda t=stock["ticker"]: self._select_ticker(t),
                )
                btn.grid(row=i, column=0, pady=3, sticky="ew")
                self._stock_buttons.append(btn)
        else:
            ctk.CTkLabel(
                scroll_mkt, text="Nenhuma ação disponível.", text_color="gray"
            ).grid(row=0, column=0, pady=12)

        # ── Modo compra / venda + input ───────────────────────────────────────
        action_frame = ctk.CTkFrame(_s, fg_color="transparent")
        action_frame.grid(row=3, column=0, padx=40, pady=(14, 0), sticky="ew")
        action_frame.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(
            action_frame,
            text="Operação:",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=0, column=0, padx=(0, 8))

        ctk.CTkRadioButton(
            action_frame,
            text="Comprar (R$)",
            variable=self._mode,
            value="buy",
            font=ctk.CTkFont(size=13),
            command=self._update_hint,
        ).grid(row=0, column=1, padx=(0, 16))

        ctk.CTkRadioButton(
            action_frame,
            text="Vender (cotas)",
            variable=self._mode,
            value="sell",
            font=ctk.CTkFont(size=13),
            command=self._update_hint,
        ).grid(row=0, column=2, sticky="w")

        input_frame = ctk.CTkFrame(_s, fg_color="transparent")
        input_frame.grid(row=4, column=0, padx=40, pady=(10, 0), sticky="ew")
        input_frame.grid_columnconfigure(1, weight=1)

        self._hint_label = ctk.CTkLabel(
            input_frame,
            text="Valor (R$)",
            font=ctk.CTkFont(size=13, weight="bold"),
            width=110,
        )
        self._hint_label.grid(row=0, column=0, padx=(0, 12))

        self.amount_entry = ctk.CTkEntry(
            input_frame,
            placeholder_text="Ex: 500.00",
            height=38,
        )
        self.amount_entry.grid(row=0, column=1, sticky="ew")

        # ── Erro + botão confirmar ────────────────────────────────────────────
        ctk.CTkLabel(
            _s,
            textvariable=self._error_text,
            text_color="#e05c5c",
            font=ctk.CTkFont(size=12),
        ).grid(row=5, column=0, padx=40, pady=(6, 0))

        ctk.CTkButton(
            _s,
            text="Confirmar  →",
            font=ctk.CTkFont(size=15, weight="bold"),
            width=200, height=44,
            corner_radius=10,
            command=self._on_confirm,
        ).grid(row=6, column=0, padx=40, pady=(8, 0))

        # ── Posições do portfólio ─────────────────────────────────────────────
        if self._portfolio_positions:
            ctk.CTkLabel(
                _s,
                text="Sua carteira",
                font=ctk.CTkFont(size=13, weight="bold"),
                anchor="w",
            ).grid(row=7, column=0, padx=40, pady=(16, 4), sticky="w")

            scroll_port = ctk.CTkScrollableFrame(_s, height=100, corner_radius=10)
            scroll_port.grid(row=8, column=0, padx=40, pady=(0, 24), sticky="ew")
            scroll_port.grid_columnconfigure(0, weight=1)

            for i, pos in enumerate(self._portfolio_positions):
                pnl = pos.get("unrealized_pnl", 0.0)
                pnl_pct = pos.get("unrealized_pnl_pct", 0.0)
                sign = "+" if pnl >= 0 else ""
                pnl_color = "#4caf50" if pnl >= 0 else "#e05c5c"
                # Clique na posição seleciona o ticker automaticamente
                btn = ctk.CTkButton(
                    scroll_port,
                    text=(
                        f"{pos['ticker']:<7}"
                        f"  {pos['shares']:.4f} cotas"
                        f"  @ R$ {pos['avg_purchase_price']:.2f}"
                        f"  →  R$ {pos['current_value']:,.2f}"
                        f"  ({sign}{pnl_pct:.1f}%)"
                    ),
                    font=ctk.CTkFont(size=12, family="Courier"),
                    height=38,
                    corner_radius=8,
                    fg_color="gray20",
                    hover_color="gray30",
                    anchor="w",
                    command=lambda t=pos["ticker"]: self._select_ticker(t),
                )
                btn.grid(row=i, column=0, pady=3, sticky="ew")
        else:
            ctk.CTkFrame(_s, height=24, fg_color="transparent").grid(row=7, column=0)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _update_hint(self):
        if self._mode.get() == "buy":
            self._hint_label.configure(text="Valor (R$)")
            self.amount_entry.configure(placeholder_text="Ex: 500.00")
        else:
            self._hint_label.configure(text="Qtd. cotas")
            self.amount_entry.configure(placeholder_text="Ex: 10.5")
        self._error_text.set("")

    def _select_ticker(self, ticker: str):
        self._selected_ticker = ticker
        self._error_text.set("")
        for btn in self._stock_buttons:
            txt = btn.cget("text")
            btn.configure(
                fg_color="#3b82d4" if txt.startswith(ticker) else "gray20"
            )

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

    def _on_confirm(self):
        if not self._selected_ticker:
            self._error_text.set("⚠  Selecione uma ação primeiro.")
            return
        amount = self._parse_amount()
        if amount is None:
            return

        if self._mode.get() == "buy":
            if amount > self._cash:
                self._error_text.set(
                    f"⚠  Saldo insuficiente. Disponível: R$ {self._cash:,.2f}"
                )
                return
            self._error_text.set("")
            ticker = self._selected_ticker
            _confirm_popup(
                master=self,
                title="Confirmar Compra",
                message=f"Comprar R$ {amount:,.2f} de {ticker}?",
                on_yes=lambda: self._on_buy(ticker, amount),
            )
        else:
            # Verificar se tem cotas suficientes
            pos = next(
                (p for p in self._portfolio_positions
                 if p["ticker"] == self._selected_ticker),
                None,
            )
            if pos is None:
                self._error_text.set(
                    f"⚠  Você não possui cotas de {self._selected_ticker}."
                )
                return
            if amount > pos.get("shares", 0):
                self._error_text.set(
                    f"⚠  Você possui apenas {pos['shares']:.4f} cotas de {self._selected_ticker}."
                )
                return
            self._error_text.set("")
            ticker = self._selected_ticker
            _confirm_popup(
                master=self,
                title="Confirmar Venda",
                message=f"Vender {amount} cotas de {ticker}?",
                on_yes=lambda: self._on_sell(ticker, amount),
            )


# ---------------------------------------------------------------------------
# Execução standalone
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    root.title("Renda Variável")
    root.geometry("700x620")
    root.minsize(540, 440)
    root.resizable(True, True)

    _demo_stocks = [
        {"ticker": "BRCO3", "name": "Banco do Reinos S.A.", "sector": "Financeiro",
         "price": 28.50, "change_pct": +1.2},
        {"ticker": "PTRX4", "name": "PetroReinos S.A.",     "sector": "Energia",
         "price": 35.00, "change_pct": -2.5},
        {"ticker": "GLDX3", "name": "Guildas de Ouro S.A.", "sector": "Mineração",
         "price": 55.00, "change_pct": 0.1},
    ]
    _demo_portfolio = [
        {"ticker": "BRCO3", "shares": 35.0877, "avg_purchase_price": 27.10,
         "current_price": 28.50, "current_value": 1000.00,
         "unrealized_pnl": +49.23, "unrealized_pnl_pct": +5.16},
    ]

    HighRiskInvestmentsPage(
        master=root,
        stocks=_demo_stocks,
        portfolio_positions=_demo_portfolio,
        cash=2500.00,
        on_buy=lambda t, a: print(f"Comprar R$ {a:.2f} de {t}"),
        on_sell=lambda t, s: print(f"Vender {s} cotas de {t}"),
        on_back=lambda: print("← Voltar"),
        fg_color="transparent",
    ).pack(fill="both", expand=True)

    root.mainloop()

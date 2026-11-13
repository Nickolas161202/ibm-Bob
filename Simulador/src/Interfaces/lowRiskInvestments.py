"""
lowRiskInvestments.py
---------------------
Tela de investimentos de baixo risco (Renda Fixa).

Exibe os produtos disponíveis com dados reais do engine (taxa, prazo, mínimo)
e as posições abertas do portfólio para resgate.

Callbacks:
  on_invest(product_key: str, amount: float, emergency_fund: bool)  → comprar novo produto
  on_redeem(position_index: int)                                     → resgatar posição existente
  on_back()                                                          → voltar
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
    Exibe um popup modal de confirmação com botões Sim / Cancelar.
    Chama `on_yes` apenas se o usuário confirmar.
    """
    dialog = ctk.CTkToplevel(master)
    dialog.title(title)
    dialog.resizable(False, False)
    dialog.grab_set()          # modal
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

    # Centre the dialog over the master window
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


class LowRiskInvestmentsPage(ctk.CTkFrame):
    """Tela de Renda Fixa / investimentos de baixo risco."""

    def __init__(
        self,
        master,
        products: list[dict] | None = None,
        open_positions: list[dict] | None = None,
        cash: float = 0.0,
        on_invest: Callable[[str, float, bool], None] | None = None,
        on_redeem: Callable[[int], None] | None = None,
        on_back: Callable | None = None,
        **kwargs,
    ):
        """
        Args:
            master:          Widget pai.
            products:        Lista de dicts com:
                               key (str)              – FixedIncomeType.value
                               label (str)
                               rate_display (str)     – ex: "100% CDI"
                               maturity (str)         – ex: "Liquidez diária"
                               min_investment (float)
                               ir_exempt (bool)
                               description (str)
            open_positions:  Lista de dicts com campos do snapshot da posição:
                               index (int)                  – índice em fixed_positions
                               label (str)
                               principal_with_earnings (float)
                               gross_earnings (float)
                               months_held (int)
                               can_redeem (bool)
                               is_mature (bool)
                               is_emergency_fund (bool)
            cash:            Saldo disponível em caixa.
            on_invest:       Callback(product_key, amount, emergency_fund).
            on_redeem:       Callback(position_index).
            on_back:         Callback para voltar.
        """
        super().__init__(master, **kwargs)
        self._products = products or []
        self._open_positions = open_positions or []
        self._cash = cash
        self._on_invest = on_invest or (lambda key, amt, ef: None)
        self._on_redeem = on_redeem or (lambda idx: None)
        self._on_back = on_back or (lambda: None)
        self._selected_product_key: str | None = None
        self._error_text = ctk.StringVar(value="")
        self._is_emergency_fund = ctk.BooleanVar(value=False)
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
            text="🏦  Renda Fixa",
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

        # ── Produtos disponíveis ──────────────────────────────────────────────
        ctk.CTkLabel(
            _s,
            text="Produtos disponíveis — selecione e informe o valor",
            font=ctk.CTkFont(size=13),
            text_color="gray",
        ).grid(row=1, column=0, padx=40, pady=(14, 6), sticky="w")

        scroll_prod = ctk.CTkScrollableFrame(_s, height=160, corner_radius=10)
        scroll_prod.grid(row=2, column=0, padx=40, pady=0, sticky="ew")
        scroll_prod.grid_columnconfigure(0, weight=1)

        self._product_buttons: list[ctk.CTkButton] = []
        if self._products:
            for i, prod in enumerate(self._products):
                exempt_tag = "  ✅ Isento IR" if prod.get("ir_exempt") else ""
                can_afford = self._cash >= prod.get("min_investment", 0)
                fg = "gray20" if can_afford else "gray15"
                btn = ctk.CTkButton(
                    scroll_prod,
                    text=(
                        f"{prod['label']}   |   {prod['rate_display']}"
                        f"   |   Venc: {prod['maturity']}"
                        f"   |   Mín: R$ {prod['min_investment']:,.2f}"
                        f"{exempt_tag}"
                    ),
                    font=ctk.CTkFont(size=12),
                    height=40,
                    corner_radius=8,
                    fg_color=fg,
                    hover_color="gray30" if can_afford else "gray15",
                    anchor="w",
                    state="normal" if can_afford else "disabled",
                    command=lambda k=prod["key"]: self._select_product(k),
                )
                btn.grid(row=i, column=0, pady=3, sticky="ew")
                self._product_buttons.append(btn)
        else:
            ctk.CTkLabel(
                scroll_prod, text="Nenhum produto disponível.", text_color="gray"
            ).grid(row=0, column=0, pady=12)

        # ── Input + botões investir / reserva de emergência ───────────────────
        input_frame = ctk.CTkFrame(_s, fg_color="transparent")
        input_frame.grid(row=3, column=0, padx=40, pady=(12, 0), sticky="ew")
        input_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            input_frame,
            text="Valor (R$)",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=0, column=0, padx=(0, 12))

        self.amount_entry = ctk.CTkEntry(
            input_frame,
            placeholder_text="Ex: 1000.00",
            height=38,
        )
        self.amount_entry.grid(row=0, column=1, sticky="ew")

        ctk.CTkLabel(
            _s,
            textvariable=self._error_text,
            text_color="#e05c5c",
            font=ctk.CTkFont(size=12),
        ).grid(row=4, column=0, padx=40, pady=(6, 0))

        # ── Action buttons row ────────────────────────────────────────────────
        action_frame = ctk.CTkFrame(_s, fg_color="transparent")
        action_frame.grid(row=5, column=0, padx=40, pady=(8, 0))

        ctk.CTkButton(
            action_frame,
            text="Investir  →",
            font=ctk.CTkFont(size=15, weight="bold"),
            width=200, height=44,
            corner_radius=10,
            command=self._on_confirm,
        ).grid(row=0, column=0, padx=(0, 12))

        self._ef_btn = ctk.CTkButton(
            action_frame,
            text="🛡  Reserva de Emergência",
            font=ctk.CTkFont(size=13),
            width=220, height=44,
            corner_radius=10,
            fg_color="gray25",
            hover_color="gray35",
            command=self._toggle_emergency_fund,
        )
        self._ef_btn.grid(row=0, column=1)

        # ── Posições abertas ──────────────────────────────────────────────────
        if self._open_positions:
            ctk.CTkLabel(
                _s,
                text="Posições abertas  (clique para resgatar)",
                font=ctk.CTkFont(size=13, weight="bold"),
                anchor="w",
            ).grid(row=6, column=0, padx=40, pady=(18, 4), sticky="w")

            scroll_pos = ctk.CTkScrollableFrame(_s, height=110, corner_radius=10)
            scroll_pos.grid(row=7, column=0, padx=40, pady=(0, 24), sticky="ew")
            scroll_pos.grid_columnconfigure(0, weight=1)

            for pos in self._open_positions:
                mature_tag = "  🔓 Disponível" if pos.get("can_redeem") else "  🔒 Em carência"
                ef_tag = "  🛡 Emergência" if pos.get("is_emergency_fund") else ""
                fg = "#3b5a2a" if pos.get("can_redeem") else "gray20"
                hv = "#4a7a3a" if pos.get("can_redeem") else "gray20"
                ctk.CTkButton(
                    scroll_pos,
                    text=(
                        f"[{pos['index']+1}] {pos['label']}"
                        f"   |   R$ {pos['principal_with_earnings']:,.2f}"
                        f"  (+R$ {pos['gross_earnings']:,.2f})"
                        f"   |   {pos['months_held']} mês(es)"
                        f"{mature_tag}{ef_tag}"
                    ),
                    font=ctk.CTkFont(size=12),
                    height=38,
                    corner_radius=8,
                    fg_color=fg,
                    hover_color=hv,
                    anchor="w",
                    state="normal" if pos.get("can_redeem") else "disabled",
                    command=lambda idx=pos["index"], lbl=pos["label"], val=pos["principal_with_earnings"]: self._ask_redeem(idx, lbl, val),
                ).grid(row=pos["index"], column=0, pady=3, sticky="ew")
        else:
            ctk.CTkFrame(_s, height=24, fg_color="transparent").grid(row=6, column=0)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _toggle_emergency_fund(self):
        new_val = not self._is_emergency_fund.get()
        self._is_emergency_fund.set(new_val)
        if new_val:
            self._ef_btn.configure(
                fg_color="#7c5cd8",
                hover_color="#6a4ec0",
                text="🛡  Reserva de Emergência  ✔",
            )
        else:
            self._ef_btn.configure(
                fg_color="gray25",
                hover_color="gray35",
                text="🛡  Reserva de Emergência",
            )

    def _select_product(self, key: str):
        self._selected_product_key = key
        self._error_text.set("")
        for btn in self._product_buttons:
            txt = btn.cget("text")
            matched = any(
                p["key"] == key and txt.startswith(p["label"])
                for p in self._products
            )
            btn.configure(fg_color="#3b82d4" if matched else "gray20")

    def _on_confirm(self):
        if not self._selected_product_key:
            self._error_text.set("⚠  Selecione um produto antes de investir.")
            return

        raw = self.amount_entry.get().strip().replace(",", ".")
        try:
            amount = float(raw)
            if amount <= 0:
                raise ValueError
        except ValueError:
            self._error_text.set("⚠  Valor inválido. Use um número positivo.")
            return

        prod = next(
            (p for p in self._products if p["key"] == self._selected_product_key), None
        )
        if prod and amount < prod.get("min_investment", 0):
            self._error_text.set(
                f"⚠  Mínimo para {prod['label']}: R$ {prod['min_investment']:,.2f}"
            )
            return
        if amount > self._cash:
            self._error_text.set(
                f"⚠  Saldo insuficiente. Disponível: R$ {self._cash:,.2f}"
            )
            return

        self._error_text.set("")

        ef = self._is_emergency_fund.get()
        ef_note = "\n\n🛡  Marcado como Reserva de Emergência." if ef else ""
        label = prod["label"] if prod else self._selected_product_key

        _confirm_popup(
            master=self,
            title="Confirmar Investimento",
            message=(
                f"Investir R$ {amount:,.2f} em\n{label}?{ef_note}"
            ),
            on_yes=lambda: self._on_invest(self._selected_product_key, amount, ef),
        )

    def _ask_redeem(self, position_index: int, label: str, value: float):
        _confirm_popup(
            master=self,
            title="Confirmar Resgate",
            message=f"Resgatar posição [{position_index+1}] {label}\n(R$ {value:,.2f})?",
            on_yes=lambda: self._on_redeem(position_index),
        )


# ---------------------------------------------------------------------------
# Execução standalone
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    root.title("Renda Fixa")
    root.geometry("680x580")
    root.minsize(520, 420)
    root.resizable(True, True)

    _demo_products = [
        {"key": "Tesouro Selic", "label": "Tesouro Selic", "rate_display": "100% SELIC",
         "maturity": "Liquidez diária", "min_investment": 100.0, "ir_exempt": False,
         "description": "Rendimento atrelado à SELIC."},
        {"key": "LCI 6 meses", "label": "LCI 6 meses", "rate_display": "93% CDI",
         "maturity": "6 meses", "min_investment": 5000.0, "ir_exempt": True,
         "description": "Isento de IR."},
    ]
    _demo_positions = [
        {"index": 0, "label": "Tesouro Selic", "principal_with_earnings": 2050.30,
         "gross_earnings": 50.30, "months_held": 3, "can_redeem": True, "is_mature": False,
         "is_emergency_fund": True},
        {"index": 1, "label": "CDB 90 dias", "principal_with_earnings": 1025.10,
         "gross_earnings": 25.10, "months_held": 2, "can_redeem": False, "is_mature": False,
         "is_emergency_fund": False},
    ]

    LowRiskInvestmentsPage(
        master=root,
        products=_demo_products,
        open_positions=_demo_positions,
        cash=3500.00,
        on_invest=lambda key, amt, ef: print(f"Investir R$ {amt:.2f} em '{key}' | emergência={ef}"),
        on_redeem=lambda idx: print(f"Resgatar posição {idx}"),
        on_back=lambda: print("← Voltar"),
        fg_color="transparent",
    ).pack(fill="both", expand=True)

    root.mainloop()

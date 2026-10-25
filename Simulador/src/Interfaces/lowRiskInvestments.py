"""
lowRiskInvestments.py
---------------------
Tela de investimentos de baixo risco (Renda Fixa).

Exibe os produtos disponíveis em cards e permite que o usuário
selecione um produto e insira um valor para investir.
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk


# Produtos placeholder — serão substituídos pelos dados reais do engine
_PLACEHOLDER_PRODUCTS = [
    {
        "label": "Tesouro Selic",
        "indexer": "SELIC",
        "rate": "SELIC + 0,0%",
        "maturity": "Liquidez diária",
        "min": "R$ 100,00",
        "ir_exempt": False,
    },
    {
        "label": "CDB Diário",
        "indexer": "CDI",
        "rate": "100% CDI",
        "maturity": "Liquidez diária",
        "min": "R$ 500,00",
        "ir_exempt": False,
    },
    {
        "label": "LCI 90 dias",
        "indexer": "CDI",
        "rate": "92% CDI",
        "maturity": "90 dias",
        "min": "R$ 1.000,00",
        "ir_exempt": True,
    },
    {
        "label": "Tesouro IPCA+",
        "indexer": "IPCA",
        "rate": "IPCA + 5,5%",
        "maturity": "5 anos",
        "min": "R$ 100,00",
        "ir_exempt": False,
    },
]


class LowRiskInvestmentsPage(ctk.CTkFrame):
    """Tela de Renda Fixa / investimentos de baixo risco."""

    def __init__(
        self,
        master,
        products: list[dict] | None = None,
        on_invest: Callable[[str, float], None] | None = None,
        on_back: Callable | None = None,
        **kwargs,
    ):
        """
        Args:
            master:     Widget pai.
            products:   Lista de produtos (dicts com label, rate, maturity, min,
                        ir_exempt). Se None, usa placeholders.
            on_invest:  Callback(product_label, amount) chamado ao confirmar.
            on_back:    Callback para voltar à página anterior.
        """
        super().__init__(master, **kwargs)
        self._products = products or _PLACEHOLDER_PRODUCTS
        self._on_invest = on_invest or (lambda label, amt: None)
        self._on_back = on_back or (lambda: None)
        self._selected_product: str | None = None
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
            text="🏦  Renda Fixa",
            font=ctk.CTkFont(size=22, weight="bold"),
            anchor="w",
        ).grid(row=0, column=1, sticky="w")

        ctk.CTkLabel(
            self,
            text="Selecione um produto e informe o valor a investir",
            font=ctk.CTkFont(size=13),
            text_color="gray",
        ).grid(row=1, column=0, padx=40, pady=(4, 20))

        # ── Lista de produtos ────────────────────────────────────────────────
        scroll = ctk.CTkScrollableFrame(self, height=200, corner_radius=10)
        scroll.grid(row=2, column=0, padx=40, pady=0, sticky="ew")
        scroll.grid_columnconfigure(0, weight=1)

        self._product_buttons: list[ctk.CTkButton] = []
        for i, prod in enumerate(self._products):
            exempt_tag = "  ✅ Isento IR" if prod.get("ir_exempt") else ""
            btn = ctk.CTkButton(
                scroll,
                text=f"{prod['label']}   |   {prod['rate']}   |   Venc: {prod['maturity']}   |   Mín: {prod['min']}{exempt_tag}",
                font=ctk.CTkFont(size=12),
                height=40,
                corner_radius=8,
                fg_color="gray20",
                hover_color="gray30",
                anchor="w",
                command=lambda p=prod["label"]: self._select_product(p),
            )
            btn.grid(row=i, column=0, pady=4, sticky="ew")
            self._product_buttons.append(btn)

        # ── Input de valor ───────────────────────────────────────────────────
        input_frame = ctk.CTkFrame(self, fg_color="transparent")
        input_frame.grid(row=3, column=0, padx=40, pady=(20, 0), sticky="ew")
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

        # ── Erro + botão ─────────────────────────────────────────────────────
        ctk.CTkLabel(
            self,
            textvariable=self._error_text,
            text_color="#e05c5c",
            font=ctk.CTkFont(size=12),
        ).grid(row=4, column=0, padx=40, pady=(10, 0))

        ctk.CTkButton(
            self,
            text="Investir  →",
            font=ctk.CTkFont(size=15, weight="bold"),
            width=200,
            height=44,
            corner_radius=10,
            command=self._on_confirm,
        ).grid(row=5, column=0, padx=40, pady=(12, 36))

    def _select_product(self, label: str):
        self._selected_product = label
        for btn in self._product_buttons:
            text = btn.cget("text")
            if text.startswith(label):
                btn.configure(fg_color="#3b82d4")
            else:
                btn.configure(fg_color="gray20")

    def _on_confirm(self):
        if not self._selected_product:
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

        self._error_text.set("")
        self._on_invest(self._selected_product, amount)


# ---------------------------------------------------------------------------
# Execução standalone
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    root.title("Renda Fixa")
    root.geometry("680x520")
    root.resizable(False, False)

    LowRiskInvestmentsPage(
        master=root,
        on_invest=lambda label, amt: print(f"Investir R$ {amt:.2f} em {label}"),
        on_back=lambda: print("← Voltar"),
        fg_color="transparent",
    ).pack(fill="both", expand=True)

    root.mainloop()

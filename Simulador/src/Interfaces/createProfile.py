"""
createProfile.py
----------------
Página de criação de perfil do investidor.

Campos exibidos nesta versão:
  - Nome
  - Renda mensal (income)
  - Gastos mensais (outcomes)
  - Objetivo financeiro (goal)
  - Perfil de risco (risk_profile)
  - Nível de conhecimento (knowledge_level)

Ao confirmar, chama o callback `on_submit` com um InvestorProfile
preenchido com os valores fornecidos e defaults para os demais campos.
"""

from __future__ import annotations

import uuid
from typing import Callable

import customtkinter as ctk

from src.Simulator.portfolio import InvestorProfile


class CreateProfilePage(ctk.CTkFrame):
    """Frame de criação de perfil — Nome, Renda, Gastos, Objetivo, Risco e Conhecimento."""

    def __init__(self, master, on_submit: Callable[[InvestorProfile], None], **kwargs):
        """
        Args:
            master:     Widget pai.
            on_submit:  Callback chamado com o InvestorProfile criado.
        """
        super().__init__(master, **kwargs)
        self._on_submit = on_submit
        self._error_text = ctk.StringVar(value="")
        # Declared here so static analysers resolve them; assigned in _build.
        self.name_entry: ctk.CTkEntry
        self.income_entry: ctk.CTkEntry
        self.outcomes_entry: ctk.CTkEntry
        self.goal_entry: ctk.CTkEntry
        self.risk_var: ctk.StringVar
        self.knowledge_var: ctk.StringVar
        self._build()

    # -----------------------------------------------------------------------
    # Construção da UI
    # -----------------------------------------------------------------------

    # Free-text fields: (attr, label, placeholder)
    _FIELDS = [
        ("name_entry",     "Nome",                "Ex: João Silva"),
        ("income_entry",   "Renda mensal (R$)",   "Ex: 5000.00"),
        ("outcomes_entry", "Gastos mensais (R$)", "Ex: 3000.00"),
        ("goal_entry",     "Objetivo em reais (R$)", "Ex: 100000.00"),
    ]

    # Dropdown fields: (var_attr, label, options)
    _DROPDOWNS = [
        ("risk_var",      "Perfil de risco",        ["conservador", "moderado", "arrojado"]),
        ("knowledge_var", "Nível de conhecimento",  ["iniciante", "intermediário", "avançado"]),
    ]

    def _build(self):
        title_font  = ctk.CTkFont(size=24, weight="bold")
        label_font  = ctk.CTkFont(size=13, weight="bold")
        button_font = ctk.CTkFont(size=15, weight="bold")

        self.grid_columnconfigure(0, weight=1)

        # ── Título ───────────────────────────────────────────────────────────
        ctk.CTkLabel(
            self,
            text="Criar Perfil",
            font=title_font,
        ).grid(row=0, column=0, padx=40, pady=(48, 4))

        ctk.CTkLabel(
            self,
            text="Preencha suas informações financeiras básicas",
            font=ctk.CTkFont(size=13),
            text_color="gray",
        ).grid(row=1, column=0, padx=40, pady=(0, 28))

        # ── Campos ───────────────────────────────────────────────────────────
        form_frame = ctk.CTkFrame(self, fg_color="transparent")
        form_frame.grid(row=2, column=0, padx=60, pady=0, sticky="ew")
        form_frame.grid_columnconfigure(1, weight=1)

        n_text = len(self._FIELDS)
        for row, (attr, label, placeholder) in enumerate(self._FIELDS):
            setattr(self, attr, self._add_field(form_frame, row, label, placeholder, label_font))

        for i, (var_attr, label, options) in enumerate(self._DROPDOWNS):
            setattr(self, var_attr, self._add_dropdown(form_frame, n_text + i, label, options, label_font))

        # ── Mensagem de erro ─────────────────────────────────────────────────
        self.error_label = ctk.CTkLabel(
            self,
            textvariable=self._error_text,
            text_color="#e05c5c",
            font=ctk.CTkFont(size=12),
        )
        self.error_label.grid(row=3, column=0, padx=40, pady=(16, 0))

        # ── Botão confirmar ──────────────────────────────────────────────────
        ctk.CTkButton(
            self,
            text="Confirmar  →",
            font=button_font,
            width=200,
            height=44,
            corner_radius=10,
            command=self._on_confirm,
        ).grid(row=4, column=0, padx=40, pady=(20, 56))

    def _add_field(
        self,
        frame: ctk.CTkFrame,
        row: int,
        label: str,
        placeholder: str,
        font: ctk.CTkFont,
    ) -> ctk.CTkEntry:
        """Add a label+entry pair to *frame* at the given grid *row*."""
        top_pad = 0 if row == 0 else 12
        ctk.CTkLabel(
            frame,
            text=label,
            font=font,
            anchor="w",
        ).grid(row=row, column=0, padx=(0, 16), pady=(top_pad, 6), sticky="w")

        entry = ctk.CTkEntry(frame, placeholder_text=placeholder, height=38)
        entry.grid(row=row, column=1, pady=(top_pad, 6), sticky="ew")
        return entry

    def _add_dropdown(
        self,
        frame: ctk.CTkFrame,
        row: int,
        label: str,
        options: list[str],
        font: ctk.CTkFont,
    ) -> ctk.StringVar:
        """Add a label+option-menu pair to *frame*; returns the backing StringVar."""
        ctk.CTkLabel(
            frame,
            text=label,
            font=font,
            anchor="w",
        ).grid(row=row, column=0, padx=(0, 16), pady=(12, 6), sticky="w")

        var = ctk.StringVar(value=options[0])
        ctk.CTkOptionMenu(frame, variable=var, values=options, height=38).grid(
            row=row, column=1, pady=(12, 6), sticky="ew"
        )
        return var

    # -----------------------------------------------------------------------
    # Validação e submit
    # -----------------------------------------------------------------------

    def _on_confirm(self):
        name        = self.name_entry.get().strip()
        income_raw  = self.income_entry.get().strip().replace(",", ".")
        outcomes_raw = self.outcomes_entry.get().strip().replace(",", ".")
        goal_raw    = self.goal_entry.get().strip().replace(",", ".")
        risk        = self.risk_var.get()
        knowledge   = self.knowledge_var.get()

        # Validação
        if not name:
            self._error_text.set("⚠  Por favor, informe seu nome.")
            return

        try:
            income = float(income_raw)
            if income < 0:
                raise ValueError
        except ValueError:
            self._error_text.set("⚠  Renda mensal inválida. Use um número positivo.")
            return

        try:
            outcomes = float(outcomes_raw)
            if outcomes < 0:
                raise ValueError
        except ValueError:
            self._error_text.set("⚠  Gastos mensais inválidos. Use um número positivo.")
            return

        try:
            goal_amount = float(goal_raw)
            if goal_amount <= 0:
                raise ValueError
        except ValueError:
            self._error_text.set("⚠  Objetivo inválido. Use um valor positivo em reais.")
            return

        self._error_text.set("")

        profile = InvestorProfile(
            user_id=str(uuid.uuid4()),
            name=name,
            monthly_income=income,
            monthly_expenses=outcomes,
            risk_profile=risk,
            knowledge_level=knowledge,
            goal="Independência financeira",
            goal_amount=goal_amount,
            goal_deadline_months=12,
        )

        self._on_submit(profile)


# ---------------------------------------------------------------------------
# Execução standalone
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    root.title("Criar Perfil")
    root.geometry("560x680")
    root.resizable(False, False)

    def on_submit(profile: InvestorProfile):
        print(f"Perfil criado: {profile}")

    page = CreateProfilePage(master=root, on_submit=on_submit, fg_color="transparent")
    page.pack(fill="both", expand=True)

    root.mainloop()

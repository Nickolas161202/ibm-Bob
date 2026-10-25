"""
createProfile.py
----------------
Página de criação de perfil do investidor.

Campos exibidos nesta versão:
  - Nome
  - Renda mensal (income)
  - Gastos mensais (outcomes)

Ao confirmar, chama o callback `on_submit` com um InvestorProfile
preenchido com os valores fornecidos e defaults para os demais campos.
"""

from __future__ import annotations

import uuid
from typing import Callable

import customtkinter as ctk

from src.Simulator.portfolio import InvestorProfile


class CreateProfilePage(ctk.CTkFrame):
    """Frame de criação de perfil — Nome, Renda e Gastos."""

    def __init__(self, master, on_submit: Callable[[InvestorProfile], None], **kwargs):
        """
        Args:
            master:     Widget pai.
            on_submit:  Callback chamado com o InvestorProfile criado.
        """
        super().__init__(master, **kwargs)
        self._on_submit = on_submit
        self._error_text = ctk.StringVar(value="")
        self._build()

    # -----------------------------------------------------------------------
    # Construção da UI
    # -----------------------------------------------------------------------

    def _build(self):
        self.grid_columnconfigure(0, weight=1)

        # ── Título ───────────────────────────────────────────────────────────
        ctk.CTkLabel(
            self,
            text="Criar Perfil",
            font=ctk.CTkFont(size=24, weight="bold"),
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

        # Nome
        ctk.CTkLabel(
            form_frame,
            text="Nome",
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, padx=(0, 16), pady=(0, 6), sticky="w")

        self.name_entry = ctk.CTkEntry(
            form_frame,
            placeholder_text="Ex: João Silva",
            height=38,
        )
        self.name_entry.grid(row=0, column=1, pady=(0, 6), sticky="ew")

        # Renda mensal
        ctk.CTkLabel(
            form_frame,
            text="Renda mensal (R$)",
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        ).grid(row=1, column=0, padx=(0, 16), pady=(12, 6), sticky="w")

        self.income_entry = ctk.CTkEntry(
            form_frame,
            placeholder_text="Ex: 5000.00",
            height=38,
        )
        self.income_entry.grid(row=1, column=1, pady=(12, 6), sticky="ew")

        # Gastos mensais
        ctk.CTkLabel(
            form_frame,
            text="Gastos mensais (R$)",
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        ).grid(row=2, column=0, padx=(0, 16), pady=(12, 6), sticky="w")

        self.outcomes_entry = ctk.CTkEntry(
            form_frame,
            placeholder_text="Ex: 3000.00",
            height=38,
        )
        self.outcomes_entry.grid(row=2, column=1, pady=(12, 6), sticky="ew")

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
            font=ctk.CTkFont(size=15, weight="bold"),
            width=200,
            height=44,
            corner_radius=10,
            command=self._on_confirm,
        ).grid(row=4, column=0, padx=40, pady=(20, 56))

    # -----------------------------------------------------------------------
    # Validação e submit
    # -----------------------------------------------------------------------

    def _on_confirm(self):
        name = self.name_entry.get().strip()
        income_raw = self.income_entry.get().strip().replace(",", ".")
        outcomes_raw = self.outcomes_entry.get().strip().replace(",", ".")

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

        self._error_text.set("")

        profile = InvestorProfile(
            user_id=str(uuid.uuid4()),
            name=name,
            monthly_income=income,
            monthly_expenses=outcomes,
            # Defaults — serão definidos em etapas futuras do onboarding
            risk_profile="moderado",
            knowledge_level="iniciante",
            goal="Independência financeira",
            goal_amount=0.0,
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
    root.geometry("560x480")
    root.resizable(False, False)

    def on_submit(profile: InvestorProfile):
        print(f"Perfil criado: {profile}")

    page = CreateProfilePage(master=root, on_submit=on_submit, fg_color="transparent")
    page.pack(fill="both", expand=True)

    root.mainloop()

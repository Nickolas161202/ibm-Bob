from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

# Adiciona o diretório raiz (Simulador) ao sys.path
_project_root = Path(__file__).resolve().parents[2]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Agora os imports relativos à pasta 'src' funcionarão perfeitamente:
from src.Simulator.portfolio import InvestorProfile
import customtkinter as ctk
"""
editIncome.py
-------------
Tela de edição de renda do usuário.

Permite ao jogador atualizar sua renda mensal e seus gastos mensais sem
precisar recriar o perfil inteiro. Após salvar, o saldo mensal disponível
para investimento (monthly_surplus) é recalculado automaticamente.

Campos exibidos:
  - Renda mensal (monthly_income)
  - Gastos mensais (monthly_expenses)
"""
class EditIncomePage(ctk.CTkFrame):
    """Frame de edição de renda — atualiza income e expenses do perfil."""

    def __init__(
        self,
        master,
        profile: InvestorProfile,
        on_save: Callable[[float, float], None],
        on_cancel: Callable | None = None,
        **kwargs,
    ):
        """
        Args:
            master:     Widget pai.
            profile:    Perfil atual do investidor (usado como valores iniciais).
            on_save:    Callback chamado com (nova_renda, novos_gastos) ao salvar.
            on_cancel:  Callback chamado ao cancelar (volta para a tela anterior).
        """
        super().__init__(master, **kwargs)
        self._profile = profile
        self._on_save = on_save
        self._on_cancel = on_cancel or (lambda: None)
        self._error_text = ctk.StringVar(value="")
        self._build()

    # -------------------------------------------------------------------------
    # Construção da UI
    # -------------------------------------------------------------------------

    def _build(self):
        title_font  = ctk.CTkFont(size=24, weight="bold")
        label_font  = ctk.CTkFont(size=13, weight="bold")
        button_font = ctk.CTkFont(size=15, weight="bold")
        muted_font  = ctk.CTkFont(size=12)

        self.grid_columnconfigure(0, weight=1)

        # ── Título ────────────────────────────────────────────────────────────
        ctk.CTkLabel(
            self,
            text="Editar Renda",
            font=title_font,
        ).grid(row=0, column=0, padx=40, pady=(48, 4))

        ctk.CTkLabel(
            self,
            text="Atualize sua renda e gastos mensais",
            font=ctk.CTkFont(size=13),
            text_color="gray",
        ).grid(row=1, column=0, padx=40, pady=(0, 28))

        # ── Formulário ────────────────────────────────────────────────────────
        form_frame = ctk.CTkFrame(self, fg_color="transparent")
        form_frame.grid(row=2, column=0, padx=60, pady=0, sticky="ew")
        form_frame.grid_columnconfigure(1, weight=1)

        # Renda mensal
        ctk.CTkLabel(
            form_frame,
            text="Renda mensal (R$)",
            font=label_font,
            anchor="w",
        ).grid(row=0, column=0, padx=(0, 16), pady=(0, 6), sticky="w")

        self._income_entry = ctk.CTkEntry(
            form_frame,
            placeholder_text="Ex: 5000.00",
            height=38,
        )
        self._income_entry.grid(row=0, column=1, pady=(0, 6), sticky="ew")
        self._income_entry.insert(0, f"{self._profile.monthly_income:.2f}")
        self._income_entry.bind("<KeyRelease>", lambda e: self._update_surplus_preview())

        # Gastos mensais
        ctk.CTkLabel(
            form_frame,
            text="Gastos mensais (R$)",
            font=label_font,
            anchor="w",
        ).grid(row=1, column=0, padx=(0, 16), pady=(12, 6), sticky="w")

        self._expenses_entry = ctk.CTkEntry(
            form_frame,
            placeholder_text="Ex: 3000.00",
            height=38,
        )
        self._expenses_entry.grid(row=1, column=1, pady=(12, 6), sticky="ew")
        self._expenses_entry.insert(0, f"{self._profile.monthly_expenses:.2f}")
        self._expenses_entry.bind("<KeyRelease>", lambda e: self._update_surplus_preview())

        # Guarda os valores originais para o botão de reset
        self._original_income   = self._profile.monthly_income
        self._original_expenses = self._profile.monthly_expenses

        # ── Card informativo: saldo disponível atual ──────────────────────────
        info_card = ctk.CTkFrame(self, corner_radius=10)
        info_card.grid(row=3, column=0, padx=60, pady=(20, 0), sticky="ew")
        info_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            info_card,
            text="💡  Saldo disponível para investimento (atual)",
            font=muted_font,
            text_color="gray",
        ).grid(row=0, column=0, padx=16, pady=(12, 2))

        self._surplus_label = ctk.CTkLabel(
            info_card,
            text="",
            font=ctk.CTkFont(size=18, weight="bold"),
        )
        self._surplus_label.grid(row=1, column=0, padx=16, pady=(0, 12))

        # ── Mensagem de erro ──────────────────────────────────────────────────
        ctk.CTkLabel(
            self,
            textvariable=self._error_text,
            text_color="#e05c5c",
            font=ctk.CTkFont(size=12),
        ).grid(row=4, column=0, padx=40, pady=(14, 0))

        # Popula o label de saldo assim que a UI está montada
        self._update_surplus_preview()

        # ── Botões ────────────────────────────────────────────────────────────
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=5, column=0, padx=40, pady=(20, 52))

        ctk.CTkButton(
            btn_frame,
            text="← Cancelar",
            font=button_font,
            width=160,
            height=44,
            corner_radius=10,
            fg_color="gray30",
            hover_color="gray40",
            command=self._on_cancel,
        ).pack(side="left", padx=(0, 12))

        ctk.CTkButton(
            btn_frame,
            text="↺ Reset",
            font=button_font,
            width=130,
            height=44,
            corner_radius=10,
            fg_color="gray30",
            hover_color="gray40",
            command=self._on_reset,
        ).pack(side="left", padx=(0, 12))

        ctk.CTkButton(
            btn_frame,
            text="Salvar  →",
            font=button_font,
            width=160,
            height=44,
            corner_radius=10,
            command=self._on_confirm,
        ).pack(side="left")

    # -------------------------------------------------------------------------
    # Preview de saldo e reset
    # -------------------------------------------------------------------------

    def _update_surplus_preview(self):
        """Recalcula e exibe o saldo disponível com base nos valores dos campos."""
        try:
            income   = float(self._income_entry.get().strip().replace(",", "."))
            expenses = float(self._expenses_entry.get().strip().replace(",", "."))
            surplus  = max(0.0, income - expenses)
            color    = "#4caf50" if surplus > 0 else "#e05c5c"
            text     = f"R$ {surplus:,.2f} / mês"
        except ValueError:
            color = "#e05c5c"
            text  = "Valores inválidos"
        self._surplus_label.configure(text=text, text_color=color)

    def _on_reset(self):
        """Restaura os campos para os valores originais ao entrar na tela."""
        self._income_entry.delete(0, "end")
        self._income_entry.insert(0, f"{self._original_income:.2f}")
        self._expenses_entry.delete(0, "end")
        self._expenses_entry.insert(0, f"{self._original_expenses:.2f}")
        self._error_text.set("")
        self._update_surplus_preview()

    # -------------------------------------------------------------------------
    # Validação e save
    # -------------------------------------------------------------------------

    def _on_confirm(self):
        income_raw   = self._income_entry.get().strip().replace(",", ".")
        expenses_raw = self._expenses_entry.get().strip().replace(",", ".")

        try:
            income = float(income_raw)
            if income < 0:
                raise ValueError
        except ValueError:
            self._error_text.set("⚠  Renda mensal inválida. Use um número positivo.")
            return

        try:
            expenses = float(expenses_raw)
            if expenses < 0:
                raise ValueError
        except ValueError:
            self._error_text.set("⚠  Gastos mensais inválidos. Use um número positivo.")
            return

        self._error_text.set("")
        self._on_save(income, expenses)


# -----------------------------------------------------------------------------
# Execução standalone
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import uuid
    from pathlib import Path

    # Allow running this file directly: add the project root (Simulador/) to
    # sys.path so that `from src.X import Y` works regardless of cwd.
    _project_root = Path(__file__).resolve().parents[2]
    if str(_project_root) not in sys.path:
        sys.path.insert(0, str(_project_root))

    from src.Simulator.portfolio import InvestorProfile

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    root.title("Editar Renda")
    root.geometry("560x480")
    root.resizable(False, False)

    _profile = InvestorProfile(
        user_id=str(uuid.uuid4()),
        name="João Silva",
        monthly_income=5000.00,
        monthly_expenses=3200.00,
        risk_profile="moderado",
        knowledge_level="iniciante",
        goal="Independência financeira",
        goal_amount=100_000.00,
        goal_deadline_months=24,
    )

    EditIncomePage(
        master=root,
        profile=_profile,
        on_save=lambda inc, exp: print(f"Salvo — Renda: R$ {inc:.2f}  Gastos: R$ {exp:.2f}"),
        on_cancel=lambda: print("Cancelado"),
        fg_color="transparent",
    ).pack(fill="both", expand=True)

    root.mainloop()

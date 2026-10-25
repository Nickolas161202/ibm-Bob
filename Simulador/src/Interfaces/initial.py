"""
initial.py
----------
Página inicial da interface do Simulador de Investimentos.

Exibe o nome do app, uma mensagem de boas-vindas e um botão
para avançar para a próxima tela.
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk


class InitialPage(ctk.CTkFrame):
    """Frame da página inicial — nome, boas-vindas e botão de próxima página."""

    def __init__(self, master, on_next: Callable, **kwargs):
        """
        Args:
            master:   Widget pai (janela ou frame contenedor).
            on_next:  Callback chamado quando o usuário clica em "Próxima página".
        """
        super().__init__(master, **kwargs)
        self._on_next = on_next
        self._build()

    def _build(self):
        # Permite que a coluna central se expanda
        self.grid_columnconfigure(0, weight=1)

        # ── Título / Nome do aplicativo ──────────────────────────────────────
        self.title_label = ctk.CTkLabel(
            self,
            text="💰 Simulador de Investimentos",
            font=ctk.CTkFont(size=28, weight="bold"),
        )
        self.title_label.grid(row=0, column=0, padx=40, pady=(60, 8))

        # ── Subtítulo temático ───────────────────────────────────────────────
        self.subtitle_label = ctk.CTkLabel(
            self,
            text="O Reino das Finanças",
            font=ctk.CTkFont(size=16, slant="italic"),
            text_color="gray",
        )
        self.subtitle_label.grid(row=1, column=0, padx=40, pady=(0, 32))

        # ── Mensagem de boas-vindas ──────────────────────────────────────────
        self.welcome_label = ctk.CTkLabel(
            self,
            text=(
                "Bem-vindo, aventureiro!\n\n"
                "Neste simulador você aprenderá a gerenciar seu portfólio,\n"
                "investir em renda fixa e variável, e conquistar sua\n"
                "independência financeira no Reino das Finanças."
            ),
            font=ctk.CTkFont(size=14),
            justify="center",
            wraplength=440,
        )
        self.welcome_label.grid(row=2, column=0, padx=40, pady=(0, 48))

        # ── Botão próxima página ─────────────────────────────────────────────
        self.next_button = ctk.CTkButton(
            self,
            text="Começar Jornada  →",
            font=ctk.CTkFont(size=15, weight="bold"),
            width=220,
            height=44,
            corner_radius=10,
            command=self._on_next,
        )
        self.next_button.grid(row=3, column=0, padx=40, pady=(0, 60))


# ---------------------------------------------------------------------------
# Execução standalone — útil para visualizar a tela isoladamente
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    root.title("Simulador de Investimentos")
    root.geometry("560x420")
    root.resizable(False, False)

    def on_next():
        print("Navegar para a próxima página...")

    page = InitialPage(master=root, on_next=on_next, fg_color="transparent")
    page.pack(fill="both", expand=True)

    root.mainloop()

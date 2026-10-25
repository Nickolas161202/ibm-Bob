"""
questGenerated.py
-----------------
Tela exibida após a geração de uma quest pelo agente de IA.

Mostra o título, descrição e objetivo da quest, além de um botão
para iniciar a simulação.
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk


class QuestGeneratedPage(ctk.CTkFrame):
    """Tela de apresentação de uma quest gerada pelo agente."""

    def __init__(
        self,
        master,
        quest_title: str = "Quest gerada",
        quest_description: str = "Descrição da quest...",
        quest_objective: str = "Objetivo: —",
        on_start: Callable | None = None,
        **kwargs,
    ):
        """
        Args:
            master:            Widget pai.
            quest_title:       Título da quest.
            quest_description: Texto narrativo da quest.
            quest_objective:   Meta/objetivo mensurável.
            on_start:          Callback ao clicar em "Iniciar Quest".
        """
        super().__init__(master, **kwargs)
        self._quest_title = quest_title
        self._quest_description = quest_description
        self._quest_objective = quest_objective
        self._on_start = on_start or (lambda: None)
        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)

        # ── Cabeçalho ────────────────────────────────────────────────────────
        ctk.CTkLabel(
            self,
            text="⚔️  Nova Quest",
            font=ctk.CTkFont(size=14),
            text_color="gray",
        ).grid(row=0, column=0, padx=40, pady=(52, 4))

        ctk.CTkLabel(
            self,
            text=self._quest_title,
            font=ctk.CTkFont(size=26, weight="bold"),
            wraplength=480,
            justify="center",
        ).grid(row=1, column=0, padx=40, pady=(0, 24))

        # ── Card de descrição ────────────────────────────────────────────────
        card = ctk.CTkFrame(self, corner_radius=12)
        card.grid(row=2, column=0, padx=48, pady=0, sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            card,
            text=self._quest_description,
            font=ctk.CTkFont(size=13),
            wraplength=420,
            justify="left",
        ).grid(row=0, column=0, padx=24, pady=(20, 12), sticky="w")

        # Divider
        ctk.CTkFrame(card, height=1, fg_color="gray40").grid(
            row=1, column=0, padx=24, pady=0, sticky="ew"
        )

        # Objetivo
        ctk.CTkLabel(
            card,
            text=self._quest_objective,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#3b82d4",
            wraplength=420,
            justify="left",
        ).grid(row=2, column=0, padx=24, pady=(12, 20), sticky="w")

        # ── Botão iniciar ────────────────────────────────────────────────────
        ctk.CTkButton(
            self,
            text="Iniciar Quest  →",
            font=ctk.CTkFont(size=15, weight="bold"),
            width=220,
            height=44,
            corner_radius=10,
            command=self._on_start,
        ).grid(row=3, column=0, padx=40, pady=(32, 56))


# ---------------------------------------------------------------------------
# Execução standalone
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    root.title("Quest Gerada")
    root.geometry("580x480")
    root.resizable(False, False)

    QuestGeneratedPage(
        master=root,
        quest_title="O Fundo de Emergência do Rei",
        quest_description=(
            "O reino enfrenta tempos incertos. O conselheiro real recomenda que "
            "todo cidadão mantenha uma reserva segura para cobrir ao menos "
            "4 meses de despesas fixas antes de aventurar-se nos mercados."
        ),
        quest_objective="🎯  Objetivo: acumular R$ 12.000 em ativos líquidos.",
        on_start=lambda: print("Quest iniciada!"),
        fg_color="transparent",
    ).pack(fill="both", expand=True)

    root.mainloop()

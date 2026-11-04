"""
profileConfirm.py
-----------------
Diálogo de confirmação exibido quando o agente infere uma mudança de perfil
(risco ou nível de conhecimento) e decide perguntar ao usuário antes de aplicar.
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk


class ProfileConfirmDialog(ctk.CTkToplevel):
    """Diálogo modal — pergunta se o usuário aceita a atualização de perfil inferida."""

    def __init__(
        self,
        master,
        current_risk: str,
        current_level: str,
        inferred_risk: str,
        inferred_level: str,
        reasoning: str,
        on_confirm: Callable,
        on_reject: Callable,
        **kwargs,
    ):
        super().__init__(master, **kwargs)
        self.title("Atualizar Perfil?")
        self.geometry("440x280")
        self.resizable(False, False)
        self.grab_set()

        ctk.CTkLabel(
            self,
            text="O agente identificou mudanças no seu perfil:",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(pady=(22, 6), padx=24)

        ctk.CTkLabel(
            self,
            text=(
                f"Risco: {current_risk}  →  {inferred_risk}\n"
                f"Nível: {current_level}  →  {inferred_level}\n\n"
                f"{reasoning}"
            ),
            justify="left",
            wraplength=390,
        ).pack(padx=24, pady=(0, 18))

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=(0, 22))
        ctk.CTkButton(
            btn_frame,
            text="Confirmar",
            width=120,
            command=lambda: (on_confirm(), self.destroy()),
        ).pack(side="left", padx=10)
        ctk.CTkButton(
            btn_frame,
            text="Ignorar",
            width=120,
            fg_color="gray30",
            hover_color="gray40",
            command=lambda: (on_reject(), self.destroy()),
        ).pack(side="left", padx=10)

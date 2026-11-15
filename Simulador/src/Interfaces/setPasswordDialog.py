"""
setPasswordDialog.py
--------------------
Diálogo modal para definição de senha ao criar um novo perfil.

O usuário pode deixar em branco para criar um perfil sem senha.
Se preencher, deve confirmar no segundo campo.
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk


class SetPasswordDialog(ctk.CTkToplevel):
    """Modal para definir (ou pular) a senha de um novo perfil."""

    def __init__(
        self,
        master,
        profile_name: str,
        on_confirm: Callable[[str], None],
        **kwargs,
    ):
        """
        Args:
            master:       Widget pai.
            profile_name: Nome do perfil recém-criado (exibido no título).
            on_confirm:   Callback(senha) — senha vazia = sem senha.
        """
        super().__init__(master, **kwargs)
        self.title("Definir Senha")
        self.geometry("440x420")
        self.minsize(380, 360)
        self.resizable(True, True)
        self.grab_set()

        self._profile_name = profile_name
        self._on_confirm = on_confirm
        self._error_var = ctk.StringVar(value="")
        self._show_pwd = False
        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)
        _s = scroll

        # ── Título ────────────────────────────────────────────────────────────
        ctk.CTkLabel(
            _s,
            text=f"Proteger '{self._profile_name}'?",
            font=ctk.CTkFont(size=16, weight="bold"),
            wraplength=360,
            justify="center",
        ).grid(row=0, column=0, padx=32, pady=(32, 4))

        ctk.CTkLabel(
            _s,
            text="Deixe em branco para entrar sem senha.",
            font=ctk.CTkFont(size=12),
            text_color="gray",
        ).grid(row=1, column=0, padx=32, pady=(0, 24))

        # ── Campo senha ───────────────────────────────────────────────────────
        ctk.CTkLabel(
            _s,
            text="Senha",
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        ).grid(row=2, column=0, padx=32, pady=(0, 4), sticky="w")

        pwd_row = ctk.CTkFrame(_s, fg_color="transparent")
        pwd_row.grid(row=3, column=0, padx=32, pady=(0, 12), sticky="ew")
        pwd_row.grid_columnconfigure(0, weight=1)

        self._pwd_entry = ctk.CTkEntry(
            pwd_row,
            placeholder_text="Nova senha (opcional)",
            show="●",
            height=38,
        )
        self._pwd_entry.grid(row=0, column=0, sticky="ew")

        self._toggle_btn = ctk.CTkButton(
            pwd_row,
            text="👁",
            width=38,
            height=38,
            corner_radius=8,
            fg_color="transparent",
            border_width=1,
            border_color="gray40",
            hover_color=("gray20", "gray17"),
            command=self._toggle_visibility,
        )
        self._toggle_btn.grid(row=0, column=1, padx=(6, 0))

        # ── Campo confirmar senha ─────────────────────────────────────────────
        ctk.CTkLabel(
            _s,
            text="Confirmar senha",
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        ).grid(row=4, column=0, padx=32, pady=(0, 4), sticky="w")

        self._confirm_entry = ctk.CTkEntry(
            _s,
            placeholder_text="Repita a senha",
            show="●",
            height=38,
        )
        self._confirm_entry.grid(row=5, column=0, padx=32, sticky="ew")
        self._confirm_entry.bind("<Return>", lambda _: self._on_ok())

        # ── Mensagem de erro ──────────────────────────────────────────────────
        ctk.CTkLabel(
            _s,
            textvariable=self._error_var,
            text_color="#e05c5c",
            font=ctk.CTkFont(size=12),
        ).grid(row=6, column=0, padx=32, pady=(6, 0))

        # ── Botões de ação ────────────────────────────────────────────────────
        btn_row = ctk.CTkFrame(_s, fg_color="transparent")
        btn_row.grid(row=7, column=0, pady=(24, 32))

        ctk.CTkButton(
            btn_row,
            text="Pular (sem senha)",
            font=ctk.CTkFont(size=13),
            width=160,
            height=38,
            corner_radius=10,
            fg_color="transparent",
            border_width=1,
            border_color="gray40",
            hover_color=("gray20", "gray17"),
            command=self._on_skip,
        ).grid(row=0, column=0, padx=(0, 10))

        ctk.CTkButton(
            btn_row,
            text="Confirmar  →",
            font=ctk.CTkFont(size=13, weight="bold"),
            width=140,
            height=38,
            corner_radius=10,
            command=self._on_ok,
        ).grid(row=0, column=1)

    # -------------------------------------------------------------------------
    # Interações
    # -------------------------------------------------------------------------

    def _toggle_visibility(self):
        """Alterna exibição dos caracteres da senha."""
        self._show_pwd = not self._show_pwd
        char = "" if self._show_pwd else "●"
        self._pwd_entry.configure(show=char)
        self._confirm_entry.configure(show=char)
        self._toggle_btn.configure(text="🙈" if self._show_pwd else "👁")

    def _on_skip(self):
        self._on_confirm("")
        self.destroy()

    def _on_ok(self):
        pwd = self._pwd_entry.get()
        confirm = self._confirm_entry.get()

        if pwd == "":
            self._on_confirm("")
            self.destroy()
            return

        if pwd != confirm:
            self._error_var.set("⚠  As senhas não coincidem.")
            return

        if len(pwd) < 4:
            self._error_var.set("⚠  A senha deve ter ao menos 4 caracteres.")
            return

        self._error_var.set("")
        self._on_confirm(pwd)
        self.destroy()

"""
loginPage.py
------------
Tela de seleção e login de perfil.

Exibe todos os perfis salvos como cards clicáveis.
Ao clicar em um perfil, se ele tiver senha, abre um campo para digitá-la.
Também oferece um botão para criar um novo perfil.

Callbacks esperados:
    on_select(profile_id: str, password: str) → App valida a senha e faz o login
    on_create_new()                           → App navega para CREATE_PROFILE
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk


class LoginPage(ctk.CTkFrame):
    """Tela de seleção de perfil com autenticação por senha."""

    def __init__(
        self,
        master,
        profiles: list[dict],
        on_select: Callable[[str, str], None],
        on_create_new: Callable,
        error_message: str = "",
        **kwargs,
    ):
        """
        Args:
            master:        Widget pai.
            profiles:      Lista de dicts com chaves: user_id, name, goal (sem hash).
            on_select:     Callback(user_id, password) chamado ao confirmar login.
            on_create_new: Callback chamado ao clicar "Criar novo perfil".
            error_message: Mensagem de erro exibida abaixo do campo de senha
                           (ex: "Senha incorreta").
        """
        super().__init__(master, **kwargs)
        self._profiles = profiles
        self._on_select = on_select
        self._on_create_new = on_create_new
        self._error_message = error_message

        self._selected_id: str | None = None
        self._profile_buttons: dict[str, ctk.CTkButton] = {}

        self._build()

    # -------------------------------------------------------------------------
    # Construção da UI
    # -------------------------------------------------------------------------

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
            text="💰 Simulador de Investimentos",
            font=ctk.CTkFont(size=26, weight="bold"),
        ).grid(row=0, column=0, padx=40, pady=(48, 4))

        ctk.CTkLabel(
            _s,
            text="Selecione seu perfil para continuar",
            font=ctk.CTkFont(size=14),
            text_color="gray",
        ).grid(row=1, column=0, padx=40, pady=(0, 28))

        # ── Cards de perfis ───────────────────────────────────────────────────
        if self._profiles:
            profiles_frame = ctk.CTkFrame(_s, fg_color="transparent")
            profiles_frame.grid(row=2, column=0, padx=48, pady=0, sticky="ew")
            profiles_frame.grid_columnconfigure(0, weight=1)

            for i, p in enumerate(self._profiles):
                self._make_profile_card(profiles_frame, i, p)

        else:
            ctk.CTkLabel(
                _s,
                text="Nenhum perfil encontrado.",
                font=ctk.CTkFont(size=13),
                text_color="gray",
            ).grid(row=2, column=0, padx=40, pady=24)

        # ── Campo de senha (oculto até selecionar um perfil protegido) ─────────
        self._password_section = ctk.CTkFrame(_s, fg_color="transparent")
        self._password_section.grid(row=3, column=0, padx=48, pady=(16, 0), sticky="ew")
        self._password_section.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self._password_section,
            text="Senha",
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, pady=(0, 4), sticky="w")

        self._password_entry = ctk.CTkEntry(
            self._password_section,
            placeholder_text="Digite sua senha",
            show="●",
            height=38,
        )
        self._password_entry.grid(row=1, column=0, sticky="ew")
        self._password_entry.bind("<Return>", lambda _: self._on_confirm())

        # Mensagem de erro
        self._error_var = ctk.StringVar(value=self._error_message)
        ctk.CTkLabel(
            self._password_section,
            textvariable=self._error_var,
            text_color="#e05c5c",
            font=ctk.CTkFont(size=12),
        ).grid(row=2, column=0, pady=(6, 0), sticky="w")

        # Inicialmente oculto
        self._password_section.grid_remove()

        # ── Botão confirmar ───────────────────────────────────────────────────
        self._confirm_btn = ctk.CTkButton(
            _s,
            text="Entrar  →",
            font=ctk.CTkFont(size=15, weight="bold"),
            width=200,
            height=44,
            corner_radius=10,
            command=self._on_confirm,
        )
        self._confirm_btn.grid(row=4, column=0, padx=40, pady=(16, 0))
        self._confirm_btn.grid_remove()  # oculto até selecionar perfil

        # ── Separador e botão de criar novo perfil ────────────────────────────
        ctk.CTkFrame(_s, height=1, fg_color="gray30").grid(
            row=5, column=0, padx=60, pady=(28, 20), sticky="ew"
        )

        ctk.CTkButton(
            _s,
            text="+ Criar novo perfil",
            font=ctk.CTkFont(size=13),
            width=200,
            height=38,
            corner_radius=10,
            fg_color="transparent",
            border_width=1,
            border_color="gray40",
            hover_color=("gray20", "gray17"),
            command=self._on_create_new,
        ).grid(row=6, column=0, padx=40, pady=(0, 48))

    # -------------------------------------------------------------------------
    # Construção de um card de perfil
    # -------------------------------------------------------------------------

    def _make_profile_card(self, parent: ctk.CTkFrame, row: int, p: dict):
        """Cria um card-botão clicável para o perfil p na linha row de parent."""
        uid = p["user_id"]
        has_pwd = bool(p.get("has_password", False))

        # Usamos o mesmo padrão do hub.py: o card é um CTkButton com texto
        # vazio e todos os widgets de conteúdo dentro de um frame sobreposto.
        # Os cliques nos filhos são encaminhados para o botão via bind.
        card = ctk.CTkButton(
            parent,
            text="",
            height=68,
            corner_radius=12,
            fg_color=("gray20", "gray17"),
            hover_color=("gray30", "gray25"),
            command=lambda: self._select_profile(uid),
        )
        card.grid(row=row, column=0, pady=(0, 10), sticky="ew")
        self._profile_buttons[uid] = card

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.place(relx=0.0, rely=0.0, relwidth=1.0, relheight=1.0)
        inner.grid_columnconfigure(1, weight=1)

        # Ícone de avatar
        avatar = ctk.CTkLabel(
            inner,
            text="👤",
            font=ctk.CTkFont(size=26),
            width=48,
        )
        avatar.grid(row=0, column=0, rowspan=2, padx=(16, 10), pady=10)

        # Nome
        name_lbl = ctk.CTkLabel(
            inner,
            text=p["name"],
            font=ctk.CTkFont(size=15, weight="bold"),
            anchor="w",
        )
        name_lbl.grid(row=0, column=1, padx=(0, 12), pady=(14, 1), sticky="w")

        # Objetivo
        goal_lbl = ctk.CTkLabel(
            inner,
            text=p.get("goal", ""),
            font=ctk.CTkFont(size=11),
            text_color="gray",
            anchor="w",
        )
        goal_lbl.grid(row=1, column=1, padx=(0, 12), pady=(1, 14), sticky="w")

        # Ícone de cadeado
        lock_lbl = ctk.CTkLabel(
            inner,
            text="🔒" if has_pwd else "🔓",
            font=ctk.CTkFont(size=14),
            width=32,
        )
        lock_lbl.grid(row=0, column=2, rowspan=2, padx=(0, 16))

        # Encaminha cliques no overlay e nos filhos para o botão
        for widget in (inner, avatar, name_lbl, goal_lbl, lock_lbl):
            widget.bind("<Button-1>", lambda e, u=uid: self._select_profile(u))

    # -------------------------------------------------------------------------
    # Interações
    # -------------------------------------------------------------------------

    def _select_profile(self, user_id: str):
        """Seleciona um perfil, destacando o card e mostrando o campo de senha se necessário."""
        self._selected_id = user_id

        # Recolore todos os botões e destaca o selecionado
        for uid, btn in self._profile_buttons.items():
            if uid == user_id:
                btn.configure(fg_color=("#3b5bdb", "#2f4ac9"), hover_color=("#3b5bdb", "#2f4ac9"))
            else:
                btn.configure(fg_color=("gray20", "gray17"), hover_color=("gray30", "gray25"))

        # Encontra o perfil selecionado
        selected = next((p for p in self._profiles if p["user_id"] == user_id), None)
        has_password = selected and selected.get("has_password", False)

        if has_password:
            self._password_section.grid()
            self._password_entry.delete(0, "end")
            self._password_entry.focus_set()
        else:
            self._password_section.grid_remove()

        self._error_var.set("")
        self._confirm_btn.grid()

    def _on_confirm(self):
        if self._selected_id is None:
            return
        password = self._password_entry.get()
        self._on_select(self._selected_id, password)

    def show_error(self, message: str):
        """Exibe mensagem de erro (chamado externamente quando a senha está errada)."""
        self._error_var.set(message)

"""
hub.py
------
Menu principal (Hub) do simulador — tela central de navegação exibida
logo após a criação de perfil e no retorno de cada ciclo.

Opções disponíveis:
  1. Realizar Missões   → entra no simulador (quest + mainPage)
  2. Material de Estudo → área de conteúdo educativo
  3. Editar Perfil → abre EditIncomePage com nome + renda + gastos
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk


class HubPage(ctk.CTkFrame):
    """Menu principal — ponto de entrada após o onboarding."""

    def __init__(
        self,
        master,
        player_name: str = "Aventureiro",
        cycle: int = 0,
        net_worth: float = 0.0,
        on_missions: Callable | None = None,
        on_study: Callable | None = None,
        on_reconfigure: Callable | None = None,
        **kwargs,
    ):
        """
        Args:
            master:          Widget pai.
            player_name:     Nome do jogador, exibido no cabeçalho.
            cycle:           Ciclo atual (0 = início da jornada).
            net_worth:       Patrimônio atual (R$), exibido como resumo.
            on_missions:     Callback ao escolher "Realizar Missões".
            on_study:        Callback ao escolher "Material de Estudo".
            on_reconfigure:  Callback ao escolher "Editar Perfil".
        """
        super().__init__(master, **kwargs)
        self._player_name = player_name
        self._cycle = cycle
        self._net_worth = net_worth
        self._on_missions = on_missions or (lambda: None)
        self._on_study = on_study or (lambda: None)
        self._on_reconfigure = on_reconfigure or (lambda: None)
        self._build()

    # -------------------------------------------------------------------------
    # Construção da UI
    # -------------------------------------------------------------------------

    def _build(self):
        self.grid_columnconfigure(0, weight=1)

        # ── Saudação ──────────────────────────────────────────────────────────
        ctk.CTkLabel(
            self,
            text=f"Olá, {self._player_name}!",
            font=ctk.CTkFont(size=26, weight="bold"),
        ).grid(row=0, column=0, padx=40, pady=(52, 4))

        cycle_text = "Início da Jornada" if self._cycle == 0 else f"Mês {self._cycle}"
        ctk.CTkLabel(
            self,
            text=f"📅  {cycle_text}  —  Reino das Finanças",
            font=ctk.CTkFont(size=13),
            text_color="gray",
        ).grid(row=1, column=0, padx=40, pady=(0, 8))

        # ── Card de patrimônio (só exibe a partir do ciclo 1) ─────────────────
        if self._cycle > 0:
            worth_card = ctk.CTkFrame(self, corner_radius=10)
            worth_card.grid(row=2, column=0, padx=80, pady=(0, 24), sticky="ew")
            worth_card.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(
                worth_card,
                text="💰  Patrimônio atual",
                font=ctk.CTkFont(size=12),
                text_color="gray",
            ).grid(row=0, column=0, pady=(12, 2))
            ctk.CTkLabel(
                worth_card,
                text=f"R$ {self._net_worth:,.2f}",
                font=ctk.CTkFont(size=20, weight="bold"),
            ).grid(row=1, column=0, pady=(0, 12))
        else:
            # Espaço reservado para alinhar com o layout do ciclo > 0
            ctk.CTkLabel(self, text="").grid(row=2, column=0, pady=12)

        # ── Separador ─────────────────────────────────────────────────────────
        ctk.CTkLabel(
            self,
            text="O que você deseja fazer?",
            font=ctk.CTkFont(size=14),
            text_color="gray",
        ).grid(row=3, column=0, padx=40, pady=(0, 16))

        # ── Botões de navegação ───────────────────────────────────────────────
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=4, column=0, padx=48, pady=0, sticky="ew")
        btn_frame.grid_columnconfigure(0, weight=1)

        self._menu_button(
            parent=btn_frame,
            row=0,
            icon="⚔️",
            title="Realizar Missões",
            subtitle="Entre no simulador e execute sua quest atual",
            command=self._on_missions,
            accent=True,
        )

        self._menu_button(
            parent=btn_frame,
            row=1,
            icon="📚",
            title="Material de Estudo",
            subtitle="Acesse conteúdos educativos sobre investimentos",
            command=self._on_study,
            accent=False,
        )

        self._menu_button(
            parent=btn_frame,
            row=2,
            icon="⚙️",
            title="Editar Perfil",
            subtitle="Atualize seu nome, renda ou gastos mensais",
            command=self._on_reconfigure,
            accent=False,
        )

    # -------------------------------------------------------------------------
    # Helper — botão de menu com ícone, título e subtítulo
    # -------------------------------------------------------------------------

    def _menu_button(
        self,
        parent: ctk.CTkFrame,
        row: int,
        icon: str,
        title: str,
        subtitle: str,
        command: Callable,
        accent: bool,
    ):
        """
        Renderiza um card-botão clicável com ícone, título e subtítulo.
        O card `accent=True` usa a cor de destaque do tema.

        Implementado como CTkButton de texto vazio com anchor w, para garantir
        que o command é disparado independentemente de onde o clique ocorra.
        """
        fg  = ("#2b5f8c", "#1a3a5c") if accent else ("gray20", "gray17")
        hov = ("#3a7ab8", "#2a5080") if accent else ("gray30", "gray25")

        # O botão ocupa toda a largura e exibe o conteúdo textual diretamente.
        # Usar um CTkButton com text formatado evita o problema de widgets
        # filhos interceptando os eventos de clique.
        card = ctk.CTkButton(
            parent,
            text=f"{icon}   {title}\n        {subtitle}",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=72,
            corner_radius=12,
            fg_color=fg,
            hover_color=hov,
            anchor="w",
            command=command,
        )
        card.grid(row=row, column=0, pady=(0, 10), sticky="ew")

        # layout interno do card
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.place(relx=0.0, rely=0.0, relwidth=1.0, relheight=1.0)
        inner.grid_columnconfigure(1, weight=1)

        # ícone
        icon_lbl = ctk.CTkLabel(
            inner,
            text=icon,
            font=ctk.CTkFont(size=28),
            width=52,
        )
        icon_lbl.grid(row=0, column=0, rowspan=2, padx=(20, 12), pady=12)

        # título
        title_lbl = ctk.CTkLabel(
            inner,
            text=title,
            font=ctk.CTkFont(size=15, weight="bold"),
            anchor="w",
        )
        title_lbl.grid(row=0, column=1, padx=(0, 16), pady=(14, 1), sticky="w")

        # subtítulo
        subtitle_lbl = ctk.CTkLabel(
            inner,
            text=subtitle,
            font=ctk.CTkFont(size=12),
            text_color="gray70",
            anchor="w",
            wraplength=340,
            justify="left",
        )
        subtitle_lbl.grid(row=1, column=1, padx=(0, 16), pady=(1, 14), sticky="w")

        # Forward clicks on the overlay frame and its children to the button
        for widget in (inner, icon_lbl, title_lbl, subtitle_lbl):
            widget.bind("<Button-1>", lambda e: command())


# -----------------------------------------------------------------------------
# Execução standalone
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    root.title("Hub — Menu Principal")
    root.geometry("620x480")
    root.resizable(False, False)

    HubPage(
        master=root,
        player_name="João Silva",
        cycle=3,
        net_worth=9_250.00,
        on_missions=lambda: print("→ Missões"),
        on_study=lambda: print("→ Estudos"),
        on_reconfigure=lambda: print("→ Reconfigurar"),
        fg_color="transparent",
    ).pack(fill="both", expand=True)

    root.mainloop()

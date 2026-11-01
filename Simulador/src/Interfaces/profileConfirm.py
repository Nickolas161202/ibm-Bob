"""
profileConfirm.py
-----------------
Diálogo modal de confirmação de atualização de perfil inferido.

Exibido pelo agente quando detecta uma mudança drástica no perfil do usuário
ou após muitas atualizações silenciosas. Mostra o que o agente inferiu e
pede confirmação antes de aplicar.

Uso:
    dlg = ProfileConfirmDialog(
        master=root,
        current_risk="moderado",
        current_level="iniciante",
        inferred_risk="arrojado",
        inferred_level="intermediário",
        reasoning="Você alocou 70% em ações nas últimas 3 quests...",
        on_confirm=lambda: app.apply_profile_update(),
        on_reject=lambda: app.keep_profile(),
    )
    dlg.grab_set()   # bloqueia a janela pai

O diálogo destrói-se automaticamente quando o usuário escolhe uma opção.
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk


# Rótulos legíveis para os valores de perfil
_RISK_LABELS = {
    "conservador":  "Conservador  (prefere segurança, menor retorno)",
    "moderado":     "Moderado  (equilíbrio entre risco e retorno)",
    "arrojado":     "Arrojado  (aceita risco maior em busca de retorno maior)",
}
_LEVEL_LABELS = {
    "iniciante":      "Iniciante",
    "intermediário":  "Intermediário",
    "avancado":       "Avançado",
    # normalização sem acento (vindo do JSON do agente)
    "intermediario":  "Intermediário",
}


class ProfileConfirmDialog(ctk.CTkToplevel):
    """
    Janela modal que pede confirmação antes de atualizar o perfil inferido.

    Sempre use `.grab_set()` após instanciar para garantir o comportamento
    modal (bloqueia cliques na janela pai).
    """

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
        """
        Args:
            master:         Widget pai (janela principal).
            current_risk:   Perfil de risco atual do usuário.
            current_level:  Nível de conhecimento atual.
            inferred_risk:  Perfil de risco que o agente inferiu.
            inferred_level: Nível de conhecimento que o agente inferiu.
            reasoning:      Explicação do agente (2-3 frases).
            on_confirm:     Chamado se o usuário confirmar a atualização.
            on_reject:      Chamado se o usuário rejeitar.
        """
        super().__init__(master, **kwargs)
        self.title("Atualização de Perfil")
        self.geometry("560x460")
        self.resizable(False, False)

        self._on_confirm = on_confirm
        self._on_reject  = on_reject

        self._current_risk    = current_risk
        self._current_level   = current_level
        self._inferred_risk   = inferred_risk
        self._inferred_level  = inferred_level
        self._reasoning       = reasoning

        self._build()

        # Centraliza sobre a janela pai
        self.after(10, self._center_on_parent)

    # -------------------------------------------------------------------------
    # Construção da UI
    # -------------------------------------------------------------------------

    def _build(self):
        self.grid_columnconfigure(0, weight=1)

        # ── Cabeçalho ─────────────────────────────────────────────────────────
        ctk.CTkLabel(
            self,
            text="🤖  O Conselheiro Atualizou sua Análise",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).grid(row=0, column=0, padx=32, pady=(32, 4))

        ctk.CTkLabel(
            self,
            text="Com base no seu comportamento nas missões, o agente identificou um novo perfil para você.",
            font=ctk.CTkFont(size=13),
            text_color="gray",
            wraplength=460,
            justify="center",
        ).grid(row=1, column=0, padx=32, pady=(0, 20))

        # ── Card de comparação ────────────────────────────────────────────────
        compare_card = ctk.CTkFrame(self, corner_radius=12)
        compare_card.grid(row=2, column=0, padx=32, pady=0, sticky="ew")
        compare_card.grid_columnconfigure((0, 1, 2), weight=1)

        # cabeçalho da tabela
        for col, text in enumerate(["", "Atual", "Inferido"]):
            ctk.CTkLabel(
                compare_card,
                text=text,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color="gray",
            ).grid(row=0, column=col, padx=12, pady=(14, 6))

        # linha de risco
        changed_risk  = self._inferred_risk  != self._current_risk
        changed_level = self._inferred_level != self._current_level

        self._compare_row(
            compare_card, row=1,
            label="Perfil de Risco",
            current=_RISK_LABELS.get(self._current_risk, self._current_risk),
            inferred=_RISK_LABELS.get(self._inferred_risk, self._inferred_risk),
            changed=changed_risk,
        )
        self._compare_row(
            compare_card, row=2,
            label="Nível de Conhecimento",
            current=_LEVEL_LABELS.get(self._current_level, self._current_level),
            inferred=_LEVEL_LABELS.get(self._inferred_level, self._inferred_level),
            changed=changed_level,
        )

        ctk.CTkLabel(compare_card, text="").grid(row=3, column=0, pady=4)

        # ── Raciocínio do agente ──────────────────────────────────────────────
        reason_card = ctk.CTkFrame(self, corner_radius=12)
        reason_card.grid(row=3, column=0, padx=32, pady=(14, 0), sticky="ew")
        reason_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            reason_card,
            text="Por que o agente chegou a essa conclusão?",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="gray",
            anchor="w",
        ).grid(row=0, column=0, padx=16, pady=(12, 4), sticky="w")

        ctk.CTkLabel(
            reason_card,
            text=self._reasoning,
            font=ctk.CTkFont(size=13),
            wraplength=460,
            justify="left",
        ).grid(row=1, column=0, padx=16, pady=(0, 14), sticky="w")

        # ── Botões ────────────────────────────────────────────────────────────
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=4, column=0, padx=32, pady=(20, 32))
        btn_frame.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            btn_frame,
            text="Manter perfil atual",
            font=ctk.CTkFont(size=13),
            width=180, height=42, corner_radius=10,
            fg_color="gray25", hover_color="gray30",
            command=self._reject,
        ).grid(row=0, column=0, padx=(0, 8))

        ctk.CTkButton(
            btn_frame,
            text="Confirmar atualização  ✓",
            font=ctk.CTkFont(size=13, weight="bold"),
            width=200, height=42, corner_radius=10,
            fg_color="#3b82d4", hover_color="#2a6ab8",
            command=self._confirm,
        ).grid(row=0, column=1, padx=(8, 0))

    @staticmethod
    def _compare_row(
        parent, row: int,
        label: str, current: str, inferred: str, changed: bool,
    ):
        """Renderiza uma linha da tabela de comparação."""
        ctk.CTkLabel(
            parent,
            text=label,
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
        ).grid(row=row, column=0, padx=(16, 8), pady=4, sticky="w")

        ctk.CTkLabel(
            parent,
            text=current,
            font=ctk.CTkFont(size=12),
            text_color="gray",
            anchor="w",
            wraplength=140,
        ).grid(row=row, column=1, padx=8, pady=4, sticky="w")

        inferred_color = "#f0a832" if changed else "gray"
        ctk.CTkLabel(
            parent,
            text=inferred + (" ← novo" if changed else ""),
            font=ctk.CTkFont(size=12, weight="bold" if changed else "normal"),
            text_color=inferred_color,
            anchor="w",
            wraplength=160,
        ).grid(row=row, column=2, padx=(8, 16), pady=4, sticky="w")

    # -------------------------------------------------------------------------
    # Handlers
    # -------------------------------------------------------------------------

    def _confirm(self):
        self.destroy()
        self._on_confirm()

    def _reject(self):
        self.destroy()
        self._on_reject()

    def _center_on_parent(self):
        try:
            px = self.master.winfo_x()
            py = self.master.winfo_y()
            pw = self.master.winfo_width()
            ph = self.master.winfo_height()
            w, h = 560, 460
            x = px + (pw - w) // 2
            y = py + (ph - h) // 2
            self.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# Execução standalone
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    root.title("App Principal")
    root.geometry("680x560")

    ctk.CTkLabel(root, text="Janela principal (bloqueada enquanto diálogo aberto)").pack(
        expand=True
    )

    def open_dialog():
        dlg = ProfileConfirmDialog(
            master=root,
            current_risk="moderado",
            current_level="iniciante",
            inferred_risk="arrojado",
            inferred_level="intermediário",
            reasoning=(
                "Nas últimas 3 quests você alocou entre 60% e 80% do patrimônio "
                "em renda variável, muito acima do esperado para um perfil moderado. "
                "Além disso, suas escolhas de ativos demonstram compreensão de "
                "conceitos como diversificação setorial e timing de entrada."
            ),
            on_confirm=lambda: print("Perfil atualizado!"),
            on_reject=lambda: print("Perfil mantido."),
        )
        dlg.grab_set()

    root.after(500, open_dialog)
    root.mainloop()

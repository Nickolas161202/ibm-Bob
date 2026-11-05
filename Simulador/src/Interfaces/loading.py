"""
loading.py
----------
Tela de carregamento exibida enquanto o agente de IA está processando.

Mostra uma mensagem de status e um indicador de progresso animado
(barra indeterminada) para deixar claro que a operação está em andamento.
"""

from __future__ import annotations

import customtkinter as ctk


class LoadingPage(ctk.CTkFrame):
    """Tela de espera com barra de progresso indeterminada."""

    _ANIMATION_STEP_MS = 20  # intervalo de atualização da animação (ms)

    def __init__(
        self,
        master,
        message: str = "O Conselheiro Real está pensando…",
        sub_message: str = "Isso pode levar alguns segundos.",
        **kwargs,
    ):
        """
        Args:
            master:      Widget pai.
            message:     Mensagem principal exibida ao usuário.
            sub_message: Texto secundário complementar.
        """
        super().__init__(master, **kwargs)
        self._message = message
        self._sub_message = sub_message
        self._progress_value = 0.0
        self._direction = 1
        self._after_id: str | None = None
        self._build()

    # -------------------------------------------------------------------------
    # Construção da UI
    # -------------------------------------------------------------------------

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure((0, 1, 2, 3, 4), weight=1)

        # Ícone
        ctk.CTkLabel(
            self,
            text="🤖",
            font=ctk.CTkFont(size=52),
        ).grid(row=1, column=0, padx=40, pady=(0, 8))

        # Mensagem principal
        ctk.CTkLabel(
            self,
            text=self._message,
            font=ctk.CTkFont(size=18, weight="bold"),
            wraplength=400,
            justify="center",
        ).grid(row=2, column=0, padx=40, pady=(0, 6))

        # Mensagem secundária
        ctk.CTkLabel(
            self,
            text=self._sub_message,
            font=ctk.CTkFont(size=13),
            text_color="gray",
            wraplength=400,
            justify="center",
        ).grid(row=3, column=0, padx=40, pady=(0, 24))

        # Barra de progresso indeterminada
        self._progress_bar = ctk.CTkProgressBar(
            self,
            width=320,
            mode="indeterminate",
        )
        self._progress_bar.grid(row=4, column=0, padx=40, pady=(0, 0))
        self._progress_bar.start()

    # -------------------------------------------------------------------------
    # Controle da animação
    # -------------------------------------------------------------------------

    def start(self):
        """Inicia a animação da barra de progresso."""
        self._progress_bar.start()

    def stop(self):
        """Para a animação da barra de progresso."""
        self._progress_bar.stop()
        if self._after_id is not None:
            self.after_cancel(self._after_id)
            self._after_id = None


# -----------------------------------------------------------------------------
# Execução standalone
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    root.title("Carregando…")
    root.geometry("520x380")
    root.resizable(False, False)

    LoadingPage(
        master=root,
        message="O Conselheiro Real está gerando sua próxima quest…",
        sub_message="Isso pode levar alguns segundos.",
        fg_color="transparent",
    ).pack(fill="both", expand=True)

    root.mainloop()

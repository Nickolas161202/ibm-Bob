"""
studyPage.py
------------
Tela de estudos — biblioteca de conteúdo educativo do usuário.

Organizada em três vistas internas gerenciadas por um único CTkFrame:

  LISTA      → cards clicáveis de cada conteúdo disponível
               + campo de busca por tema e botão "Pedir novo tema"
  CONTEÚDO   → texto adaptado (padrão) com botão para alternar para o original
               + botão "Fazer Quiz" (disponível se há quiz associado)
  QUIZ       → perguntas sequenciais com 4 opções; ao final, resultado + botão voltar

Callbacks esperados pelo main.py:
  on_back              : Callable        — volta ao Hub
  on_request_topic     : Callable[str]   — usuário pediu um tema específico
  on_quiz_completed    : Callable[str, int, int]  — (content_id, corretas, total)
"""

from __future__ import annotations

from typing import Callable, Optional

import customtkinter as ctk

from src.Study.library import StudyContent, QuizQuestion


# ─────────────────────────────────────────────────────────────────────────────
# StudyPage
# ─────────────────────────────────────────────────────────────────────────────

class StudyPage(ctk.CTkFrame):
    """Hub de estudos — lista, leitura e quiz de conteúdo educativo."""

    def __init__(
        self,
        master,
        contents: list[StudyContent] | None = None,
        on_back: Callable | None = None,
        on_request_topic: Callable[[str], None] | None = None,
        on_quiz_completed: Callable[[str, int, int], None] | None = None,
        **kwargs,
    ):
        """
        Args:
            master:             Widget pai.
            contents:           Lista de StudyContent disponíveis para o usuário.
            on_back:            Callback para voltar ao Hub.
            on_request_topic:   Callback(topic_text) quando o usuário pede um tema.
            on_quiz_completed:  Callback(content_id, correct, total) após quiz.
        """
        super().__init__(master, **kwargs)
        self._contents: list[StudyContent] = contents or []
        self._on_back = on_back or (lambda: None)
        self._on_request_topic = on_request_topic or (lambda t: None)
        self._on_quiz_completed = on_quiz_completed or (lambda cid, c, t: None)

        # estado de navegação interna
        self._active_content: Optional[StudyContent] = None
        self._show_source = False       # False = adaptado, True = original
        self._quiz_index = 0
        self._quiz_answers: list[Optional[int]] = []

        self._build_list_view()

    # =========================================================================
    # VISTA 1 — Lista de conteúdos
    # =========================================================================

    def _build_list_view(self):
        self._clear()
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ── Scrollable container ──────────────────────────────────────────────
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)
        _s = scroll

        # ── Cabeçalho ─────────────────────────────────────────────────────────
        header = ctk.CTkFrame(_s, fg_color="transparent")
        header.grid(row=0, column=0, padx=40, pady=(36, 0), sticky="ew")
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(
            header, text="←", width=36, height=36, corner_radius=8,
            fg_color="gray25", hover_color="gray30",
            command=self._on_back,
        ).grid(row=0, column=0, padx=(0, 12))

        ctk.CTkLabel(
            header,
            text="📚  Material de Estudo",
            font=ctk.CTkFont(size=22, weight="bold"),
            anchor="w",
        ).grid(row=0, column=1, sticky="w")

        ctk.CTkLabel(
            _s,
            text="Selecione um conteúdo para estudar ou peça um tema novo",
            font=ctk.CTkFont(size=13),
            text_color="gray",
        ).grid(row=1, column=0, padx=40, pady=(4, 16))

        # ── Campo de pedido de tema ────────────────────────────────────────────
        request_frame = ctk.CTkFrame(_s, corner_radius=10)
        request_frame.grid(row=2, column=0, padx=40, pady=(0, 16), sticky="ew")
        request_frame.grid_columnconfigure(0, weight=1)

        inner = ctk.CTkFrame(request_frame, fg_color="transparent")
        inner.grid(row=0, column=0, padx=16, pady=12, sticky="ew")
        inner.grid_columnconfigure(0, weight=1)

        self._topic_entry = ctk.CTkEntry(
            inner,
            placeholder_text="Ex: Tesouro IPCA+, Diversificação, Juros compostos...",
            height=38,
        )
        self._topic_entry.grid(row=0, column=0, padx=(0, 10), sticky="ew")

        ctk.CTkButton(
            inner,
            text="Pedir tema  →",
            font=ctk.CTkFont(size=13, weight="bold"),
            width=130,
            height=38,
            corner_radius=8,
            command=self._on_request_click,
        ).grid(row=0, column=1)

        # ── Lista de conteúdos ────────────────────────────────────────────────
        if not self._contents:
            ctk.CTkLabel(
                _s,
                text=(
                    "Ainda não há conteúdos gerados para você.\n"
                    "Complete quests no simulador ou peça um tema acima."
                ),
                font=ctk.CTkFont(size=13),
                text_color="gray",
                justify="center",
            ).grid(row=3, column=0, padx=40, pady=40)
            return

        content_list = ctk.CTkFrame(_s, fg_color="transparent")
        content_list.grid(row=3, column=0, padx=40, pady=(0, 24), sticky="ew")
        content_list.grid_columnconfigure(0, weight=1)

        for i, content in enumerate(self._contents):
            self._content_card(content_list, content, row=i)

    def _content_card(self, parent, content: StudyContent, row: int):
        """Card clicável para um conteúdo na lista."""
        best = content.best_quiz_score
        attempts = content.attempts

        if content.mastered:
            badge = "  ✅ Dominado"
            badge_color = "#4caf50"
        elif best is not None:
            badge = f"  Quiz: {best}/100"
            badge_color = "#3b82d4" if best >= 70 else "#e09c3c"
        else:
            badge = "  Novo"
            badge_color = "gray"

        card = ctk.CTkButton(
            parent,
            text="",
            height=64,
            corner_radius=10,
            fg_color=("gray20", "gray17"),
            hover_color=("gray30", "gray25"),
            command=lambda c=content: self._open_content(c),
        )
        card.grid(row=row, column=0, pady=(0, 8), sticky="ew")

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.place(relx=0.0, rely=0.0, relwidth=1.0, relheight=1.0)
        inner.grid_columnconfigure(1, weight=1)

        # ícone temático
        ctk.CTkLabel(
            inner, text="📖", font=ctk.CTkFont(size=24), width=44,
        ).grid(row=0, column=0, rowspan=2, padx=(16, 10), pady=10)

        # título
        ctk.CTkLabel(
            inner,
            text=content.topic,
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w",
        ).grid(row=0, column=1, padx=(0, 8), pady=(12, 1), sticky="w")

        # subtítulo: tentativas + badge
        sub_text = f"{attempts} tentativa(s) de quiz"
        ctk.CTkLabel(
            inner,
            text=sub_text,
            font=ctk.CTkFont(size=11),
            text_color="gray",
            anchor="w",
        ).grid(row=1, column=1, padx=(0, 8), pady=(1, 12), sticky="w")

        # badge de status
        ctk.CTkLabel(
            inner,
            text=badge,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=badge_color,
            anchor="e",
            width=100,
        ).grid(row=0, column=2, rowspan=2, padx=(0, 16))

    def _on_request_click(self):
        topic = self._topic_entry.get().strip()
        if topic:
            self._on_request_topic(topic)
            self._topic_entry.delete(0, "end")

    # =========================================================================
    # VISTA 2 — Conteúdo (adaptado ou original)
    # =========================================================================

    def _open_content(self, content: StudyContent):
        self._active_content = content
        self._show_source = False
        self._build_content_view()

    def _build_content_view(self):
        self._clear()
        content = self._active_content
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ── Scrollable container ──────────────────────────────────────────────
        scroll_outer = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll_outer.grid(row=0, column=0, sticky="nsew")
        scroll_outer.grid_columnconfigure(0, weight=1)
        _s = scroll_outer

        # ── Cabeçalho ─────────────────────────────────────────────────────────
        header = ctk.CTkFrame(_s, fg_color="transparent")
        header.grid(row=0, column=0, padx=40, pady=(36, 0), sticky="ew")
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(
            header, text="←", width=36, height=36, corner_radius=8,
            fg_color="gray25", hover_color="gray30",
            command=self._build_list_view,
        ).grid(row=0, column=0, padx=(0, 12))

        ctk.CTkLabel(
            header,
            text=content.topic,
            font=ctk.CTkFont(size=20, weight="bold"),
            anchor="w",
            wraplength=480,
        ).grid(row=0, column=1, sticky="w")

        # ── Toggle adaptado / original ─────────────────────────────────────────
        toggle_frame = ctk.CTkFrame(_s, fg_color="transparent")
        toggle_frame.grid(row=1, column=0, padx=40, pady=(12, 0), sticky="w")

        adapted_color  = "#3b82d4" if not self._show_source else "gray25"
        original_color = "#3b82d4" if self._show_source     else "gray25"

        ctk.CTkButton(
            toggle_frame,
            text="Versão Adaptada",
            font=ctk.CTkFont(size=12),
            width=140, height=30, corner_radius=8,
            fg_color=adapted_color,
            command=self._show_adapted,
        ).grid(row=0, column=0, padx=(0, 6))

        ctk.CTkButton(
            toggle_frame,
            text="Conteúdo Original",
            font=ctk.CTkFont(size=12),
            width=140, height=30, corner_radius=8,
            fg_color=original_color,
            command=self._show_original,
        ).grid(row=0, column=1)

        # ── Área de texto ─────────────────────────────────────────────────────
        text_body = content.source_text if self._show_source else content.adapted_text
        label_mode = "Conteúdo Original (técnico)" if self._show_source else "Versão Simplificada"

        ctk.CTkLabel(
            _s,
            text=label_mode,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="gray",
            anchor="w",
        ).grid(row=2, column=0, padx=40, pady=(16, 4), sticky="w")

        ctk.CTkLabel(
            _s,
            text=text_body,
            font=ctk.CTkFont(size=13),
            wraplength=520,
            justify="left",
            anchor="nw",
        ).grid(row=3, column=0, padx=52, pady=(0, 8), sticky="w")

        # ── Botão do quiz ──────────────────────────────────────────────────────
        quiz_frame = ctk.CTkFrame(_s, fg_color="transparent")
        quiz_frame.grid(row=4, column=0, padx=40, pady=(20, 40))

        if content.quiz:
            best = content.best_quiz_score
            quiz_label = (
                f"Refazer Quiz  (melhor: {best}/100)" if best is not None
                else "Fazer Quiz  →"
            )
            ctk.CTkButton(
                quiz_frame,
                text=quiz_label,
                font=ctk.CTkFont(size=14, weight="bold"),
                width=220, height=44, corner_radius=10,
                command=self._start_quiz,
            ).grid(row=0, column=0)
        else:
            ctk.CTkLabel(
                quiz_frame,
                text="Nenhum quiz disponível para este conteúdo.",
                font=ctk.CTkFont(size=13),
                text_color="gray",
            ).grid(row=0, column=0)

    def _show_adapted(self):
        if self._show_source:
            self._show_source = False
            self._build_content_view()

    def _show_original(self):
        if not self._show_source:
            self._show_source = True
            self._build_content_view()

    # =========================================================================
    # VISTA 3 — Quiz
    # =========================================================================

    def _start_quiz(self):
        self._quiz_index = 0
        self._quiz_answers = [None] * len(self._active_content.quiz)
        self._build_quiz_view()

    def _build_quiz_view(self):
        self._clear()
        content = self._active_content
        q_idx   = self._quiz_index
        q       = content.quiz[q_idx]
        total   = len(content.quiz)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)
        _s = scroll

        # ── Cabeçalho ─────────────────────────────────────────────────────────
        header = ctk.CTkFrame(_s, fg_color="transparent")
        header.grid(row=0, column=0, padx=40, pady=(36, 0), sticky="ew")
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(
            header, text="←", width=36, height=36, corner_radius=8,
            fg_color="gray25", hover_color="gray30",
            command=self._build_content_view,
        ).grid(row=0, column=0, padx=(0, 12))

        ctk.CTkLabel(
            header,
            text=f"Quiz — {content.topic}",
            font=ctk.CTkFont(size=20, weight="bold"),
            anchor="w",
        ).grid(row=0, column=1, sticky="w")

        # progresso
        ctk.CTkLabel(
            _s,
            text=f"Pergunta {q_idx + 1} de {total}",
            font=ctk.CTkFont(size=13),
            text_color="gray",
        ).grid(row=1, column=0, padx=40, pady=(8, 0))

        progress = ctk.CTkProgressBar(_s, width=400)
        progress.set((q_idx) / total)
        progress.grid(row=2, column=0, padx=40, pady=(4, 20))

        # ── Pergunta ──────────────────────────────────────────────────────────
        q_card = ctk.CTkFrame(_s, corner_radius=12)
        q_card.grid(row=3, column=0, padx=40, pady=0, sticky="ew")
        q_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            q_card,
            text=q.question,
            font=ctk.CTkFont(size=14),
            wraplength=500,
            justify="left",
        ).grid(row=0, column=0, padx=20, pady=(16, 16), sticky="w")

        # ── Opções ────────────────────────────────────────────────────────────
        opts_frame = ctk.CTkFrame(_s, fg_color="transparent")
        opts_frame.grid(row=4, column=0, padx=40, pady=(12, 24), sticky="ew")
        opts_frame.grid_columnconfigure(0, weight=1)

        option_labels = ["A", "B", "C", "D"]
        for i, opt in enumerate(q.options[:4]):
            ctk.CTkButton(
                opts_frame,
                text=f"  {option_labels[i]}.  {opt}",
                font=ctk.CTkFont(size=13),
                height=46,
                corner_radius=10,
                fg_color="gray20",
                hover_color="gray30",
                anchor="w",
                command=lambda idx=i: self._answer_question(idx),
            ).grid(row=i, column=0, pady=(0, 8), sticky="ew")

    def _answer_question(self, chosen_idx: int):
        """Processa a resposta de uma pergunta e avança ou finaliza."""
        content = self._active_content
        q       = content.quiz[self._quiz_index]
        correct = chosen_idx == q.correct_index

        self._quiz_answers[self._quiz_index] = chosen_idx
        self._show_answer_feedback(q, chosen_idx, correct)

    def _show_answer_feedback(
        self, q: QuizQuestion, chosen_idx: int, correct: bool
    ):
        """Exibe feedback imediato após a resposta antes de avançar."""
        self._clear()
        total = len(self._active_content.quiz)
        q_idx = self._quiz_index
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)
        _s = scroll

        # ── Resultado da resposta ─────────────────────────────────────────────
        result_text = "✅  Correto!" if correct else "❌  Incorreto"
        result_color = "#4caf50" if correct else "#e05c5c"

        ctk.CTkLabel(
            _s,
            text=result_text,
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=result_color,
        ).grid(row=0, column=0, padx=40, pady=(52, 8))

        # resposta escolhida e correta (se errou)
        labels = ["A", "B", "C", "D"]
        if not correct:
            ctk.CTkLabel(
                _s,
                text=(
                    f"Você escolheu: {labels[chosen_idx]}. {q.options[chosen_idx]}\n"
                    f"Resposta correta: {labels[q.correct_index]}. {q.options[q.correct_index]}"
                ),
                font=ctk.CTkFont(size=13),
                text_color="gray",
                justify="center",
                wraplength=460,
            ).grid(row=1, column=0, padx=40, pady=(0, 12))

        # explicação
        exp_card = ctk.CTkFrame(_s, corner_radius=12)
        exp_card.grid(row=2, column=0, padx=40, pady=0, sticky="ew")
        exp_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            exp_card,
            text="💡  Explicação",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="gray",
            anchor="w",
        ).grid(row=0, column=0, padx=20, pady=(14, 4), sticky="w")

        ctk.CTkLabel(
            exp_card,
            text=q.explanation,
            font=ctk.CTkFont(size=13),
            wraplength=480,
            justify="left",
        ).grid(row=1, column=0, padx=20, pady=(0, 16), sticky="w")

        # progresso
        ctk.CTkLabel(
            _s,
            text=f"Pergunta {q_idx + 1} de {total}",
            font=ctk.CTkFont(size=13),
            text_color="gray",
        ).grid(row=3, column=0, padx=40, pady=(20, 4))

        # botão avançar
        is_last = (q_idx + 1 >= total)
        btn_text = "Ver Resultado  →" if is_last else "Próxima  →"
        ctk.CTkButton(
            _s,
            text=btn_text,
            font=ctk.CTkFont(size=14, weight="bold"),
            width=200, height=44, corner_radius=10,
            command=self._next_question if not is_last else self._finish_quiz,
        ).grid(row=4, column=0, padx=40, pady=(8, 40))

    def _next_question(self):
        self._quiz_index += 1
        self._build_quiz_view()

    def _finish_quiz(self):
        content = self._active_content
        answers = self._quiz_answers
        total   = len(content.quiz)
        correct = sum(
            1 for i, ans in enumerate(answers)
            if ans is not None and ans == content.quiz[i].correct_index
        )

        # notifica o main.py para persistir o resultado
        self._on_quiz_completed(content.id, correct, total)

        # ── Tela de resultado final ───────────────────────────────────────────
        self._clear()
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        score = round(correct / total * 100) if total > 0 else 0

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)
        _s = scroll

        result_icon = "🏆" if score >= 75 else ("📈" if score >= 50 else "📚")
        result_msg  = (
            "Excelente! Você demonstrou bom domínio deste tema."
            if score >= 75 else
            "Bom esforço! Revise o conteúdo e tente novamente."
            if score >= 50 else
            "Continue estudando! Releia o conteúdo adaptado e tente de novo."
        )

        ctk.CTkLabel(
            _s,
            text=f"{result_icon}  Quiz Concluído",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).grid(row=0, column=0, padx=40, pady=(52, 8))

        ctk.CTkLabel(
            _s,
            text=f"{correct}/{total} respostas corretas",
            font=ctk.CTkFont(size=32, weight="bold"),
            text_color="#3b82d4",
        ).grid(row=1, column=0, padx=40, pady=(0, 4))

        ctk.CTkLabel(
            _s,
            text=f"Score: {score}/100",
            font=ctk.CTkFont(size=16),
            text_color="gray",
        ).grid(row=2, column=0, padx=40, pady=(0, 20))

        msg_card = ctk.CTkFrame(_s, corner_radius=12)
        msg_card.grid(row=3, column=0, padx=60, pady=0, sticky="ew")
        msg_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            msg_card,
            text=result_msg,
            font=ctk.CTkFont(size=13),
            wraplength=440,
            justify="center",
        ).grid(row=0, column=0, padx=20, pady=16)

        btn_row = ctk.CTkFrame(_s, fg_color="transparent")
        btn_row.grid(row=4, column=0, padx=40, pady=(24, 48))
        btn_row.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            btn_row,
            text="Rever Conteúdo",
            font=ctk.CTkFont(size=13),
            width=160, height=40, corner_radius=10,
            fg_color="gray25", hover_color="gray30",
            command=self._build_content_view,
        ).grid(row=0, column=0, padx=(0, 8))

        ctk.CTkButton(
            btn_row,
            text="← Voltar à Lista",
            font=ctk.CTkFont(size=13, weight="bold"),
            width=160, height=40, corner_radius=10,
            command=self._build_list_view,
        ).grid(row=0, column=1, padx=(8, 0))

    # =========================================================================
    # Helpers
    # =========================================================================

    def _clear(self):
        """Destrói todos os widgets filhos para redesenhar a vista atual."""
        for widget in self.winfo_children():
            widget.destroy()

    def refresh_contents(self, contents: list[StudyContent]):
        """Permite ao main.py atualizar a lista sem recriar o frame."""
        self._contents = contents
        self._build_list_view()


# ─────────────────────────────────────────────────────────────────────────────
# Execução standalone
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

    from src.Study.library import StudyContent, QuizQuestion

    sample = StudyContent(
        id="sample-001",
        topic="Tesouro Selic",
        source_text=(
            "O Tesouro Selic é um título público federal pós-fixado emitido pelo Tesouro Nacional "
            "e comercializado via plataforma Tesouro Direto. Sua remuneração acompanha a taxa SELIC "
            "overnight (taxa básica de juros da economia brasileira), definida pelo Copom a cada 45 dias.\n\n"
            "Tecnicamente, o título remunera o investidor pela variação da taxa SELIC acumulada no período, "
            "calculada de forma composta. A marcação a mercado é diária, e o preço flutua levemente em "
            "função das expectativas de mercado para a SELIC futura, embora de forma muito menos acentuada "
            "que os títulos prefixados ou IPCA+.\n\n"
            "Por possuir liquidez diária (resgate em D+1) e baixíssima volatilidade, o Tesouro Selic é "
            "amplamente utilizado como reserva de emergência e como alternativa à poupança ou ao CDB de "
            "liquidez diária, especialmente quando a SELIC está acima de 8% a.a."
        ),
        adapted_text=(
            "O Tesouro Selic é como um 'cofre inteligente' do governo brasileiro. Cada real que você "
            "investe lá começa a render automaticamente todo dia, acompanhando a taxa básica de juros "
            "(a SELIC). Se a SELIC está em 10,75% ao ano, seu dinheiro cresce aproximadamente isso.\n\n"
            "A grande vantagem é que você pode resgatar quando quiser (no dia útil seguinte). Por isso, "
            "é o investimento mais indicado para sua reserva de emergência — aquele dinheiro que você "
            "precisa ter disponível para imprevistos, mas que também não pode ficar parado na conta.\n\n"
            "Exemplo prático: se você tem R$ 12.000 de reserva de emergência no Tesouro Selic com SELIC "
            "a 10,75% a.a., em 12 meses você teria aproximadamente R$ 13.290 — sem nenhum esforço!"
        ),
        quiz=[
            QuizQuestion(
                question="O Tesouro Selic é um investimento pós-fixado. O que isso significa?",
                options=[
                    "A taxa de rendimento é definida no momento da compra e não muda.",
                    "O rendimento acompanha um indicador (a SELIC) que pode variar ao longo do tempo.",
                    "O investimento só pode ser resgatado no vencimento.",
                    "O rendimento é calculado com base na inflação.",
                ],
                correct_index=1,
                explanation=(
                    "Pós-fixado significa que a rentabilidade não é travada na compra — ela segue "
                    "um índice de referência, no caso do Tesouro Selic, a própria taxa SELIC. "
                    "Se a SELIC subir, seu rendimento sobe; se cair, o rendimento cai."
                ),
            ),
            QuizQuestion(
                question="Por que o Tesouro Selic é recomendado para reserva de emergência?",
                options=[
                    "Porque tem o maior rendimento entre todos os investimentos.",
                    "Porque é emitido pelo governo e portanto não tem risco algum.",
                    "Porque combina segurança, liquidez diária e rendimento acima da poupança.",
                    "Porque é isento de Imposto de Renda.",
                ],
                correct_index=2,
                explanation=(
                    "A reserva de emergência precisa de dois atributos: estar disponível quando "
                    "precisar (liquidez) e não perder poder de compra (rendimento). O Tesouro Selic "
                    "entrega os dois. Não é isento de IR (alternativas C e D) nem tem o maior "
                    "rendimento do mercado — mas equilibra perfeitamente esses critérios."
                ),
            ),
            QuizQuestion(
                question="Se a SELIC cair de 10,75% para 8% ao ano, o que acontece com seu Tesouro Selic?",
                options=[
                    "Você perde todo o rendimento já acumulado.",
                    "O rendimento futuro diminui, mas o rendimento já acumulado é mantido.",
                    "O título é cancelado e você recebe de volta apenas o valor investido.",
                    "Nada muda, pois a taxa foi travada no momento da compra.",
                ],
                correct_index=1,
                explanation=(
                    "Como é pós-fixado, o que você já rendeu fica garantido. Mas os próximos dias "
                    "renderão à taxa nova (8% a.a.). É por isso que, quando se espera queda da SELIC, "
                    "títulos prefixados (que travam a taxa atual) podem ser mais vantajosos."
                ),
            ),
            QuizQuestion(
                question="Quanto tempo leva para resgatar o Tesouro Selic após solicitar?",
                options=["Imediatamente (D+0).", "1 dia útil (D+1).", "3 dias úteis (D+3).", "Só no vencimento."],
                correct_index=1,
                explanation=(
                    "O Tesouro Selic tem liquidez diária com resgate em D+1 — o dinheiro cai na "
                    "sua conta no próximo dia útil após a solicitação. Isso o diferencia, por exemplo, "
                    "de um CDB com carência, que só pode ser resgatado no vencimento."
                ),
            ),
        ],
        created_cycle=1,
        sim_score_at_creation=45.0,
    )

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    root.title("Material de Estudo — Demo")
    root.geometry("680x600")
    root.resizable(False, False)

    StudyPage(
        master=root,
        contents=[sample],
        on_back=lambda: print("← Voltar"),
        on_request_topic=lambda t: print(f"Pedindo tema: {t}"),
        on_quiz_completed=lambda cid, c, t: print(f"Quiz: {c}/{t} corretas — id={cid}"),
        fg_color="transparent",
    ).pack(fill="both", expand=True)

    root.mainloop()

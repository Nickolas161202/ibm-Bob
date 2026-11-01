"""
library.py
----------
Modelo de dados da biblioteca de estudo do usuário.

Responsabilidades:
  - Armazenar conteúdos gerados pelo agente (StudyContent)
  - Persistir a biblioteca em JSON no disco (um arquivo por usuário)
  - Expor métricas de domínio para o agente decidir quando gerar novo conteúdo

Estrutura de um StudyContent:
  - id          : UUID único do conteúdo
  - topic       : tema financeiro (ex: "Tesouro Selic", "Juros Compostos")
  - source_text : conteúdo original / técnico (completo, sem simplificação)
  - adapted_text: versão simplificada gerada pelo agente para o perfil do usuário
  - quiz        : lista de QuizQuestion (geradas pelo agente junto com o conteúdo)
  - quiz_results: histórico de resultados dos quizzes realizados pelo usuário
  - sim_score_at_creation : pontuação média no simulador quando o conteúdo foi criado
  - created_cycle : ciclo do simulador em que o conteúdo foi gerado
  - mastered    : True quando o agente avaliou como dominado
  - requested_by_user : True se o usuário pediu explicitamente este tema
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field, asdict
from typing import Optional


# ---------------------------------------------------------------------------
# QuizQuestion
# ---------------------------------------------------------------------------

@dataclass
class QuizQuestion:
    question: str
    options: list[str]          # exatamente 4 opções (A–D)
    correct_index: int          # índice da opção correta (0–3)
    explanation: str            # explicação exibida após resposta


# ---------------------------------------------------------------------------
# QuizResult — uma tentativa de quiz armazenada
# ---------------------------------------------------------------------------

@dataclass
class QuizResult:
    cycle: int
    score: int          # 0–100 proporcional às respostas corretas
    correct: int
    total: int


# ---------------------------------------------------------------------------
# StudyContent — um conteúdo de estudo completo
# ---------------------------------------------------------------------------

@dataclass
class StudyContent:
    id: str
    topic: str
    source_text: str            # conteúdo técnico original
    adapted_text: str           # versão simplificada pelo agente
    quiz: list[QuizQuestion]    # perguntas geradas junto com o conteúdo
    sim_score_at_creation: float = 0.0
    created_cycle: int = 0
    mastered: bool = False
    requested_by_user: bool = False
    quiz_results: list[QuizResult] = field(default_factory=list)

    @property
    def best_quiz_score(self) -> Optional[int]:
        if not self.quiz_results:
            return None
        return max(r.score for r in self.quiz_results)

    @property
    def attempts(self) -> int:
        return len(self.quiz_results)

    def record_quiz(self, correct: int, cycle: int):
        total = len(self.quiz)
        score = round(correct / total * 100) if total > 0 else 0
        self.quiz_results.append(QuizResult(
            cycle=cycle, score=score, correct=correct, total=total,
        ))


# ---------------------------------------------------------------------------
# StudyLibrary — coleção de conteúdos de um usuário
# ---------------------------------------------------------------------------

class StudyLibrary:
    """
    Biblioteca de conteúdo educativo de um único usuário.

    Persiste em JSON: <data_dir>/<user_id>_study.json
    """

    def __init__(self, user_id: str, data_dir: str = "."):
        self.user_id = user_id
        self._path = os.path.join(data_dir, f"{user_id}_study.json")
        self._contents: list[StudyContent] = []
        self._load()

    # -----------------------------------------------------------------------
    # CRUD
    # -----------------------------------------------------------------------

    def add(self, content: StudyContent):
        self._contents.append(content)
        self._save()

    def get_all(self) -> list[StudyContent]:
        return list(self._contents)

    def get_by_id(self, content_id: str) -> Optional[StudyContent]:
        for c in self._contents:
            if c.id == content_id:
                return c
        return None

    def mark_mastered(self, content_id: str):
        c = self.get_by_id(content_id)
        if c:
            c.mastered = True
            self._save()

    def record_quiz_result(self, content_id: str, correct: int, cycle: int):
        c = self.get_by_id(content_id)
        if c:
            c.record_quiz(correct, cycle)
            self._save()

    # -----------------------------------------------------------------------
    # Métricas para o agente
    # -----------------------------------------------------------------------

    def unmastered_topics(self) -> list[str]:
        return [c.topic for c in self._contents if not c.mastered]

    def covered_topics(self) -> list[str]:
        return [c.topic for c in self._contents]

    def mastery_summary(self) -> dict:
        """Resumo compacto do estado da biblioteca — enviado ao agente."""
        return {
            "total_contents": len(self._contents),
            "mastered": sum(1 for c in self._contents if c.mastered),
            "unmastered": sum(1 for c in self._contents if not c.mastered),
            "topics_covered": self.covered_topics(),
            "best_quiz_scores": {
                c.topic: c.best_quiz_score
                for c in self._contents
            },
            "quiz_attempts": {
                c.topic: c.attempts
                for c in self._contents
            },
        }

    # -----------------------------------------------------------------------
    # Persistência JSON
    # -----------------------------------------------------------------------

    def _save(self):
        data = []
        for c in self._contents:
            d = asdict(c)
            data.append(d)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load(self):
        if not os.path.exists(self._path):
            return
        with open(self._path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for d in data:
            quiz = [QuizQuestion(**q) for q in d.pop("quiz", [])]
            quiz_results = [QuizResult(**r) for r in d.pop("quiz_results", [])]
            self._contents.append(StudyContent(quiz=quiz, quiz_results=quiz_results, **d))

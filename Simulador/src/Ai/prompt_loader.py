"""
prompt_loader.py
----------------
Carrega e formata templates de prompts a partir dos arquivos JSON em
``src/Ai/prompts/``.

Uso
---
    from src.Ai.prompt_loader import PromptLoader

    loader = PromptLoader()
    prompt = loader.format("quest", "generate_quest", monthly_surplus=3000, ...)

Cada arquivo JSON mapeado possui chaves correspondentes ao nome do método que
utiliza o prompt. Os valores são strings de template com placeholders no estilo
``str.format_map`` do Python (``{nome}`` ou ``{valor:.2f}``).

A chave especial ``"_comment"`` em cada arquivo é ignorada automaticamente.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# Caminho para o diretório de prompts relativo a este arquivo
_PROMPTS_DIR = Path(__file__).parent / "prompts"

# Arquivos disponíveis — mapeados por nome lógico
_FILES: dict[str, str] = {
    "session": "session.json",
    "quest":   "quest.json",
    "study":   "study.json",
}


class PromptLoader:
    """
    Carregador de templates de prompts.

    Parâmetros
    ----------
    prompts_dir : Path | None
        Diretório onde os arquivos JSON estão armazenados.
        Padrão: ``src/Ai/prompts/`` (relativo a este arquivo).

    Exemplo
    -------
    >>> loader = PromptLoader()
    >>> text = loader.format("quest", "generate_quest", monthly_surplus=3000.0, ...)
    """

    def __init__(self, prompts_dir: Path | None = None):
        self._dir = prompts_dir or _PROMPTS_DIR
        self._cache: dict[str, dict[str, str]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_template(self, file_key: str, prompt_key: str) -> str:
        """
        Retorna o template bruto (sem formatação) para a chave fornecida.

        Parameters
        ----------
        file_key   : chave lógica do arquivo (``"session"``, ``"quest"``, ``"study"``)
        prompt_key : chave dentro do arquivo JSON

        Raises
        ------
        KeyError
            Se ``file_key`` ou ``prompt_key`` não existirem.
        FileNotFoundError
            Se o arquivo JSON correspondente não for encontrado.
        """
        data = self._load(file_key)
        if prompt_key not in data:
            raise KeyError(
                f"Prompt '{prompt_key}' não encontrado em '{file_key}.json'. "
                f"Chaves disponíveis: {[k for k in data if k != '_comment']}"
            )
        return data[prompt_key]

    def format(self, file_key: str, prompt_key: str, **kwargs: Any) -> str:
        """
        Carrega o template e substitui os placeholders com os valores fornecidos.

        Usa ``str.format_map`` — aceita especificadores de formato como
        ``{valor:.2f}`` e ``{texto!r}``.

        Parameters
        ----------
        file_key   : chave lógica do arquivo
        prompt_key : chave dentro do arquivo JSON
        **kwargs   : valores a substituir nos placeholders do template

        Returns
        -------
        str
            O prompt formatado, pronto para ser enviado ao modelo.

        Raises
        ------
        KeyError
            Se um placeholder no template não tiver valor correspondente em kwargs.
        """
        template = self.get_template(file_key, prompt_key)
        try:
            return template.format_map(kwargs)
        except KeyError as exc:
            raise KeyError(
                f"Placeholder {exc} não fornecido ao formatar "
                f"'{file_key}/{prompt_key}'."
            ) from exc

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load(self, file_key: str) -> dict[str, str]:
        """Carrega (e faz cache) do arquivo JSON correspondente a file_key."""
        if file_key in self._cache:
            return self._cache[file_key]

        filename = _FILES.get(file_key)
        if filename is None:
            raise KeyError(
                f"Arquivo de prompts '{file_key}' desconhecido. "
                f"Opções válidas: {list(_FILES.keys())}"
            )

        path = self._dir / filename
        if not path.exists():
            raise FileNotFoundError(
                f"Arquivo de prompts não encontrado: {path}"
            )

        data: dict[str, str] = json.loads(path.read_text(encoding="utf-8"))
        # Remove the metadata key so callers never accidentally use it
        data.pop("_comment", None)
        self._cache[file_key] = data
        return data

    def reload(self) -> None:
        """Limpa o cache, forçando releitura dos arquivos no próximo acesso."""
        self._cache.clear()

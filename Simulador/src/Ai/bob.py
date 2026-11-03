import json
import os
import shutil
import subprocess
import tempfile


class Bob:

    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password
        if password:
            os.environ["BOB_API_KEY"] = password
        self._authenticated = False

    def login(self) -> None:
        """
        Authenticates using the API key stored in BOB_API_KEY.
        The key was set from `password` during __init__.
        """
        if not os.environ.get("BOB_API_KEY"):
            raise RuntimeError("BOB_API_KEY is not set. Provide a valid API key as password.")
        self._authenticated = True

    def send_prompt(self, prompt: str) -> str:
        """
        Sends a prompt to IBM Bob via `bob run -f json`.

        The prompt is written to a temporary file and fed via stdin to avoid
        shell argument length/encoding issues with long multi-line prompts.

        Flags used:
          --disable-mcp     — disables MCP servers for a clean, fast call.
          --workspace <tmp> — neutral empty workspace so Bob has no project
                              context and treats the prompt as a standalone
                              data-generation task, not a code query.
          -f json           — structured single-line JSON output; we extract
                              `last_message` for the bare reply text.

        Returns the assistant's reply text.
        Raises RuntimeError if the CLI call fails.
        """
        if not self._authenticated:
            raise RuntimeError("Not authenticated. Call login() first.")

        bob_exe = shutil.which("bob")
        if bob_exe is None:
            raise RuntimeError(
                "Bob Shell CLI not found. Install it from "
                "https://bob.ibm.com/download/bobshell.ps1 "
                "and ensure it is on PATH."
            )

        # Neutral workspace: empty temp dir so Bob has no project context.
        neutral_dir = os.path.join(tempfile.gettempdir(), "bob_neutral")
        os.makedirs(neutral_dir, exist_ok=True)

        # Write prompt to a temp file to avoid shell arg-length / encoding limits.
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", encoding="utf-8", delete=False
        ) as f:
            f.write(prompt)
            prompt_file = f.name

        try:
            with open(prompt_file, "r", encoding="utf-8") as stdin_f:
                result = subprocess.run(
                    [
                        bob_exe, "run",
                        "-f", "json",
                        "--disable-mcp",
                        "--workspace", neutral_dir,
                        "-",          # read prompt from stdin
                    ],
                    stdin=stdin_f,
                    capture_output=True,
                    text=True,
                    cwd=neutral_dir,
                )
        finally:
            os.unlink(prompt_file)

        if result.returncode != 0:
            raise RuntimeError(f"Bob CLI error: {result.stderr.strip()}")

        try:
            data = json.loads(result.stdout.strip())
            return self._strip_markdown_fence(data["last_message"])
        except (json.JSONDecodeError, KeyError) as exc:
            raise RuntimeError(
                f"Unexpected Bob CLI output: {result.stdout[:200]}"
            ) from exc

    @staticmethod
    def _strip_markdown_fence(text: str) -> str:
        """Remove a leading ```json / ``` or ``` / ``` code fence if present."""
        stripped = text.strip()
        if stripped.startswith("```"):
            # Drop first line (```json or ```) and last line (```)
            lines = stripped.splitlines()
            if lines[-1].strip() == "```":
                lines = lines[1:-1]
            else:
                lines = lines[1:]
            return "\n".join(lines).strip()
        return stripped

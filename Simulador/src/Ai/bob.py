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

        # Encode prompt to UTF-8 bytes and pass via stdin pipe.
        # Capturing raw bytes (no text= / encoding= on subprocess) and then
        # decoding explicitly with UTF-8 is the only reliable way to avoid
        # Windows cp1252 locale corrupting accented characters in both the
        # prompt sent and the response received.
        result = subprocess.run(
            [
                bob_exe, "run",
                "-f", "json",
                "--disable-mcp",
                "--workspace", neutral_dir,
            ],
            input=prompt.encode("utf-8"),
            capture_output=True,
            cwd=neutral_dir,
        )

        if result.returncode != 0:
            stderr_text = result.stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"Bob CLI error: {stderr_text}")

        try:
            stdout_text = result.stdout.decode("utf-8")
            data = json.loads(stdout_text.strip())
            last_message = data.get("last_message")
            if last_message is None:
                raise RuntimeError(
                    f"Bob returned null last_message. Full output: {stdout_text[:300]}"
                )
            return self._strip_markdown_fence(last_message)
        except (json.JSONDecodeError, KeyError) as exc:
            stdout_preview = result.stdout.decode("utf-8", errors="replace")[:200]
            raise RuntimeError(
                f"Unexpected Bob CLI output: {stdout_preview}"
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

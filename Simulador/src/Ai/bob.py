import os
import subprocess

class Bob:

    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password
        os.environ["BOBSHELL_API_KEY"] = password
        self._authenticated = False

    def login(self) -> None:
        """
        Authenticates using the API key stored in BOBSHELL_API_KEY.
        The key was set from `password` during __init__.
        """
        if not os.environ.get("BOBSHELL_API_KEY"):
            raise RuntimeError("BOBSHELL_API_KEY is not set. Provide a valid API key as password.")
        self._authenticated = True
        print(f"[Bob] Authenticated as {self.email} via API key.")

    def send_prompt(self, prompt: str) -> str:
        """
        Sends a prompt to IBM Bob via the Bob Shell CLI (`bob --auth-method api-key -p`).
        Requires login() to have been called first.

        Returns the response text from Bob.
        Raises RuntimeError if the CLI call fails.
        """
        if not self._authenticated:
            raise RuntimeError("Not authenticated. Call login() first.")

        result = subprocess.run(
            ["bob", "--auth-method", "api-key", "-p", prompt],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Bob CLI error: {result.stderr.strip()}")

        return result.stdout.strip()


from pathlib import Path

TEMPLATE = Path(__file__).resolve().parents[1] / ".env.example"


def test_env_template_has_no_secrets():
    """Real keys belong in the git-ignored .env, never in the committed template."""
    filled = [line.split("=")[0] for line in TEMPLATE.read_text(encoding="utf-8").splitlines()
              if "KEY=" in line and line.split("=", 1)[1].split("#")[0].strip()]
    assert not filled, f"Secrets in .env.example: {filled} — move them to .env"

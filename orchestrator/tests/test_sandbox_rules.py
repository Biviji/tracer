"""Pure rules of the Docker driver: which repos may be cloned, what gets installed."""

import pytest

pytest.importorskip("docker")

from app.sandbox.docker_driver import CloneError, install_command, is_demo, normalize_repo_url  # noqa: E402

HOSTS = {"github.com", "gitlab.com"}


@pytest.mark.parametrize(
    ("given", "url"),
    [
        ("github.com/owner/name", "https://github.com/owner/name"),
        ("https://gitlab.com/group/sub/name.git", "https://gitlab.com/group/sub/name.git"),
    ],
)
def test_allowed_hosts_pass(given, url):
    assert normalize_repo_url(given, HOSTS) == url


@pytest.mark.parametrize(
    "repo",
    [
        "https://169.254.169.254/latest/meta-data",  # cloud metadata
        "https://10.0.0.5/repo",  # private network
        "https://localhost/repo",
        "https://github.com.evil.example/x/y",
        "file:///etc",
        "git@github.com:owner/name.git",
        "http://github.com/owner/name",
    ],
)
def test_everything_else_is_refused(repo):
    with pytest.raises(CloneError):
        normalize_repo_url(repo, HOSTS)


def test_star_allows_any_public_https_host():
    assert normalize_repo_url("https://git.example.org/x/y", {"*"}) == "https://git.example.org/x/y"


def test_demo_names():
    assert is_demo(" Demo ") and is_demo("demo-repo") and not is_demo("github.com/demo/x")


def test_install_command(tmp_path):
    assert install_command(tmp_path) is None
    (tmp_path / "pyproject.toml").write_text("[tool.pytest.ini_options]\n")  # config only: not a package
    assert install_command(tmp_path) is None
    (tmp_path / "requirements.txt").write_text("requests\n")
    (tmp_path / "package.json").write_text("{}")
    cmd = install_command(tmp_path)
    assert "-r requirements.txt" in cmd and "-e ." not in cmd
    assert "npm install --ignore-scripts" in cmd

"""Everything around the agent loop that should NOT be left to the model.

    prepare_repo("Ar4l/simple-todo-app")           -> clone (fork if needed)
    solve_issue(url, agent_loop, tools, model=...)  -> branch, loop, commit, draft PR

The model only reads, edits and runs commands.  Git plumbing and the PR are
deterministic code.  Nothing is tested automatically: a human reviews the PR.
"""
import json
import re
import subprocess
from pathlib import Path

from . import set_workdir, trace, workdir

SYSTEM = """You are a coding agent fixing ONE GitHub issue in a small vanilla-JS todo app.
The working directory is the repo root; every path is relative to it
(app.js, index.html, style.css). Never use `cd`, never run git.
Work step by step with the tools:
1. read the issue carefully, then read the code it points at (app.js first),
2. make the smallest change that resolves the issue (edit_file for small
   changes, write_file with the complete file for larger ones),
3. run `node --check app.js` to catch syntax errors,
4. re-read the changed region once to confirm it does what the issue asks.
Do not add tests, dependencies or a build step. Fix only this issue.
When you are done, answer WITHOUT tool calls: a short summary of the change for the PR."""


# ---------------------------------------------------------------- shell helpers
def sh(*args, cwd=None, check=False, timeout=120) -> subprocess.CompletedProcess:
    return subprocess.run(list(args), cwd=cwd or workdir(), text=True, timeout=timeout,
                          check=check, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def gh_json(*args) -> dict:
    return json.loads(sh("gh", *args, check=True).stdout)


def parse_issue_url(url: str):
    m = re.fullmatch(r"https?://github\.com/([^/]+)/([^/]+)/issues/(\d+)/?", url.strip())
    if not m:
        raise ValueError(f"not a GitHub issue URL: {url}")
    return m.group(1), m.group(2), int(m.group(3))


# ---------------------------------------------------------------- repo plumbing
def prepare_repo(full_name: str, root: Path) -> Path:
    """Clone OWNER/REPO under `root` (forking first unless you own it); return the path."""
    owner, repo = full_name.split("/")
    me = gh_json("api", "user")["login"]
    dest = Path(root) / repo
    if not dest.exists():
        Path(root).mkdir(parents=True, exist_ok=True)
        if me != owner:
            sh("gh", "repo", "fork", full_name, "--clone=false", cwd=root)
            sh("gh", "repo", "clone", f"{me}/{repo}", str(dest), cwd=root, check=True)
            sh("git", "remote", "add", "upstream", f"https://github.com/{full_name}", cwd=dest)
        else:
            sh("gh", "repo", "clone", full_name, str(dest), cwd=root, check=True)
    return set_workdir(dest)


def fresh_branch(name: str) -> None:
    """Throw away local changes and start `name` from the upstream default branch."""
    remotes = sh("git", "remote").stdout.split()
    base = "upstream" if "upstream" in remotes else "origin"
    sh("git", "fetch", "-q", base, check=True)
    sh("git", "reset", "-q", "--hard", check=True)
    sh("git", "clean", "-qfd", check=True)
    sh("git", "checkout", "-q", "--no-track", "-B", name, f"{base}/main", check=True)


# ---------------------------------------------------------------- driver
def solve_issue(url: str, agent_loop, tools: dict, *, model: str, options: dict,
                root: Path, open_pr: bool = True) -> dict:
    owner, repo, n = parse_issue_url(url)
    issue = gh_json("issue", "view", str(n), "-R", f"{owner}/{repo}", "--json", "title,body")
    issue_text = f"# {issue['title']}\n\n{issue['body']}"
    prepare_repo(f"{owner}/{repo}", root)
    branch = f"agent/issue-{n}-{re.sub(r'[^a-z0-9]+', '-', model.lower()).strip('-')}"
    fresh_branch(branch)
    trace.note(f"{workdir()} on branch {branch}")

    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": f"Please fix this issue.\n\n{issue_text}"}]
    stop = _run(agent_loop, messages, tools)

    trace.rule("result")
    changed = [line.split()[-1] for line in sh("git", "status", "--porcelain").stdout.splitlines()]
    result = dict(issue=n, model=model, stop=stop, branch=branch, changed=changed, pr=None)
    if not changed:
        trace.verdict(False, f"agent stopped ({stop}) without changing a file; nothing pushed")
        return result
    trace.note(f"agent stopped ({stop}); changed: {', '.join(changed)}")

    summary = next((m.content for m in reversed(messages) if getattr(m, "role", None) == "assistant" and m.content), "")
    if open_pr:
        result["pr"] = _open_pr(owner, repo, n, issue["title"], branch, model, summary)
        trace.verdict(True, f"draft PR opened for a human to review: {result['pr']}")
    else:
        trace.note(f"dry run: PR not opened; the diff is on branch {branch} in {workdir()}")
    return result


def _run(agent_loop, messages, tools) -> str:
    """Call the student's loop; a model/server error becomes a stop reason instead of a crash."""
    try:
        return agent_loop(messages, tools)
    except Exception as e:  # e.g. Ollama 500 when the context overflowed
        trace.verdict(False, f"model call failed: {type(e).__name__}: {str(e)[:200]}")
        return f"error ({type(e).__name__})"


def _open_pr(owner, repo, n, title, branch, model, summary) -> str:
    me = gh_json("api", "user")["login"]
    sh("git", "add", "-A", check=True)
    sh("git", "-c", "user.name=local-agent", "-c", "user.email=agent@localhost",
       "commit", "-qm", f"Fix #{n}: {title}\n\nGenerated locally by {model}.", check=True)
    sh("git", "push", "-q", "--force", "origin", f"HEAD:refs/heads/{branch}", check=True)  # explicit refspec
    body = (f"Addresses #{n}.\n\nWritten by a local agent running `{model}` via Ollama. "
            f"Nothing was tested automatically: please review before merging.\n\n{summary}")
    head = branch if me == owner else f"{me}:{branch}"
    out = sh("gh", "pr", "create", "--repo", f"{owner}/{repo}", "--base", "main", "--head", head,
             "--draft", "--title", f"Fix #{n}: {title}", "--body", body, check=True).stdout
    return out.strip().splitlines()[-1]

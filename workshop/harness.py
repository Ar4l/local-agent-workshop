"""Everything around the agent loop that should NOT be left to the model.

    prepare_repo("Ar4l/simple-todo-app")           -> clone (fork if needed)
    solve_issue(url, agent_loop, tools, model=...)  -> branch, loop, gate, review, PR

The model only reads, edits and runs tests.  Git plumbing, the test gate and
the decision to open a PR are deterministic code.
"""
import json
import re
import subprocess
from pathlib import Path

import ollama

from . import set_workdir, trace, workdir

SYSTEM = """You are a coding agent fixing ONE GitHub issue in a small vanilla-JS todo app.
The working directory is the repo root; every path is relative to it
(app.js, index.html, style.css, tests/). Never use `cd`, never run git.
Work step by step with the tools:
1. run `node --test tests/issue-{n}.test.js` and read the failure,
2. read the test file and the source it exercises,
3. make the smallest change that satisfies the test (edit_file for small
   changes, write_file with the complete file for larger ones),
4. re-run the issue test, then `node --test tests/baseline.test.js` to check nothing else broke.
Tests for OTHER issues (tests/issue-*.test.js) may fail; that is expected, leave them alone.
tests/dom-stub.js is a large fake-DOM helper for the tests: do not read it, it is not relevant.
Never modify files under tests/. Fix only this issue.
When the issue's test passes, answer WITHOUT tool calls: a short summary of the change."""

REVIEWER = """You are a strict code reviewer. You get a GitHub issue, the git diff meant to
fix it and the test output. Judge: does the diff fix THIS issue, minimally, without touching
unrelated code or tests? Answer with JSON: {"verdict": "APPROVE" | "REVISE", "reasons": [...]}"""

REVIEW_SCHEMA = {"type": "object", "required": ["verdict", "reasons"], "properties": {
    "verdict": {"type": "string", "enum": ["APPROVE", "REVISE"]},
    "reasons": {"type": "array", "items": {"type": "string"}}}}


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


# ---------------------------------------------------------------- the hard gate
def failing_tests() -> set[str]:
    """Run every test file separately; return the set of files that fail."""
    failing = set()
    for f in sorted((workdir() / "tests").glob("*.test.js")):
        if sh("node", "--test", f"tests/{f.name}").returncode != 0:
            failing.add(f.name)
    return failing


def gate(n: int, baseline: set[str]) -> list[str]:
    """Deterministic checks. Empty list == pass."""
    failing, reasons = failing_tests(), []
    if f"issue-{n}.test.js" in failing:
        out = sh("node", "--test", f"tests/issue-{n}.test.js").stdout
        reasons.append(f"tests/issue-{n}.test.js still fails:\n{out[-1500:]}")
    if regressions := sorted(failing - baseline):
        reasons.append(f"tests that passed before now fail: {regressions}")
    if changed := sh("git", "status", "--porcelain", "--", "tests/", "package.json").stdout.strip():
        reasons.append(f"do not modify tests: {changed}")
    if not sh("git", "status", "--porcelain").stdout.strip():
        reasons.append("no files were changed")
    return reasons


def llm_review(model: str, n: int, issue: str, options: dict) -> tuple[bool, list[str]]:
    diff = sh("git", "diff").stdout
    tests = sh("node", "--test", f"tests/issue-{n}.test.js", "tests/baseline.test.js").stdout
    prompt = (f"## Issue\n{issue}\n\n## git diff\n{diff[:12000]}\n\n"
              f"## node --test tests/issue-{n}.test.js tests/baseline.test.js\n{tests[-3000:]}")
    reply = ollama.chat(model, format=REVIEW_SCHEMA, options=options, messages=[
        {"role": "system", "content": REVIEWER}, {"role": "user", "content": prompt}]).message
    try:
        parsed = json.loads(reply.content or "")
        return parsed["verdict"] == "APPROVE", [str(r) for r in parsed.get("reasons", [])]
    except (ValueError, KeyError, TypeError):
        return False, [f"reviewer did not answer in JSON: {reply.content!r}"]


# ---------------------------------------------------------------- driver
def solve_issue(url: str, agent_loop, tools: dict, *, model: str, options: dict,
                root: Path, review_rounds: int = 2, open_pr: bool = True) -> dict:
    owner, repo, n = parse_issue_url(url)
    issue = gh_json("issue", "view", str(n), "-R", f"{owner}/{repo}", "--json", "title,body")
    issue_text = f"# {issue['title']}\n\n{issue['body']}"
    prepare_repo(f"{owner}/{repo}", root)
    branch = f"agent/issue-{n}-{re.sub(r'[^a-z0-9]+', '-', model.lower()).strip('-')}"
    fresh_branch(branch)
    baseline = failing_tests()
    trace.note(f"{workdir()} on branch {branch}; failing before we start: {sorted(baseline)}")

    messages = [{"role": "system", "content": SYSTEM.format(n=n)},
                {"role": "user", "content": f"Please fix this issue.\n\n{issue_text}"}]
    stop = _run(agent_loop, messages, tools)
    approved, verdicts = False, []
    for round_no in range(review_rounds + 1):
        trace.rule(f"review {round_no + 1}")
        reasons = gate(n, baseline)
        if stop != "stopped":
            reasons.append(f"the agent stopped because of {stop}; finish the fix, then summarise")
        ok = not reasons
        trace.verdict(ok, "test gate " + ("passed" if ok else "failed: " + "; ".join(r.splitlines()[0] for r in reasons)))
        if ok:
            approved, llm_reasons = llm_review(model, n, issue_text, options)
            trace.verdict(approved, f"reviewer ({model}): " + ("APPROVE" if approved else "REVISE") + " – " + " ".join(llm_reasons)[:400])
            reasons += llm_reasons
        verdicts.append("APPROVE" if approved else "REVISE")
        if approved or round_no == review_rounds:
            break
        messages.append({"role": "user", "content": "Automated review verdict: REVISE.\n- "
                         + "\n- ".join(reasons) + "\nAddress this, re-run the tests, then summarise."})
        stop = _run(agent_loop, messages, tools)

    summary = next((m.content for m in reversed(messages) if getattr(m, "role", None) == "assistant" and m.content), "")
    result = dict(issue=n, model=model, approved=approved, verdicts=verdicts, stop=stop, branch=branch, pr=None)
    if approved and open_pr:
        result["pr"] = _open_pr(owner, repo, n, issue["title"], branch, model, summary)
        trace.verdict(True, f"draft PR opened: {result['pr']}")
    elif approved:
        trace.note("approved; PR not opened (open_pr=False)")
    else:
        trace.verdict(False, "not approved after review; nothing pushed")
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
    sh("git", "-c", "user.name=local-agent", "-c", "user.email=agent@localhost",
       "commit", "-qam", f"Fix #{n}: {title}\n\nGenerated locally by {model}.", check=True)
    sh("git", "push", "-q", "--force", "origin", f"HEAD:refs/heads/{branch}", check=True)  # explicit refspec
    body = f"Addresses #{n}.\n\nWritten by a local agent running `{model}` via Ollama.\n\n{summary}"
    head = branch if me == owner else f"{me}:{branch}"
    out = sh("gh", "pr", "create", "--repo", f"{owner}/{repo}", "--base", "main", "--head", head,
             "--draft", "--title", f"Fix #{n}: {title}", "--body", body, check=True).stdout
    return out.strip().splitlines()[-1]

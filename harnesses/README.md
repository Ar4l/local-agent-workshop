# Ready-made harnesses, pointed at Ollama

Same model, same task, three harnesses. Configs verified 2026-09-07 with `qwen3.5:9b`.

## pi (earendil-works/pi) — recommended for a live demo

```bash
npm install -g @earendil-works/pi-coding-agent
mkdir -p ~/.pi/agent && cp harnesses/pi/models.json ~/.pi/agent/models.json   # edit the model id
pi --provider ollama --model qwen3.5:9b -p "How many lines does app.js have?"
```

## mini-swe-agent (SWE-agent/mini-swe-agent)

```bash
uvx --from mini-swe-agent mini -c mini.yaml -c harnesses/mini/ollama.yaml -y --exit-immediately \
    -t "How many lines does app.js have?"
```
Set `MSWEA_CONFIGURED=1` to skip the first-run wizard.

## DeepSeek Harness (deepseek-ai/deepseek-harness, `dsh`)

Developer preview (Aug 2026). Its `dsh-llm-pi-ai` provider layer is built on pi's `pi-ai`
package. Heavy install (~3.5 min, 277 MB); see the repo's docs/user/guide/providers.md.

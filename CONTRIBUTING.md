# Contributing

LLM Launcher is an alpha macOS project. Bug reports, compatibility findings, documentation improvements, tests, and focused code changes are welcome.

## Before opening a change

- Search existing issues first.
- Open an issue before a large UI redesign, new engine, new work surface, saved-data migration, or security-boundary change.
- Never attach private prompts, responses, terminal output, credentials, model weights, or personal filesystem paths.
- Keep third-party runtime behaviour evidence-based and link to authoritative documentation.

## Development setup

The launcher itself requires Python 3.10+ and Node.js 24+ for the JavaScript tests. A real model runtime is not required for the normal unit suite.

```bash
git clone https://github.com/alexanderisgood/llmLauncher.git
cd llmLauncher
node --check app.js
python3 -m unittest discover -s tests -p 'test_*.py'
for test in tests/test_*.js; do node "$test"; done
```

## Design rules

- Preserve the exact visible model, reasoning, sampling, context, output, and KV contract unless the user explicitly approves a change.
- Planning and inspection paths must remain side-effect free.
- Bind local services to loopback and keep secrets out of browser-visible state, logs, and agent configuration.
- Stop only processes and relays owned by the launcher.
- Unknown engines, work surfaces, protocol shapes, and evidence must fail closed.
- Optimisation claims require matching local measurements; availability is not proof of speed.
- Keep Focused mode understandable without hiding errors, launch state, or consequential settings.

Read [ARCHITECTURE.md](ARCHITECTURE.md) before adding an adapter or changing route construction.

## Pull requests

Keep pull requests narrow, explain user-visible and security effects, add regression tests, and report the exact test commands run. By submitting a contribution, you agree that it is licensed under the repository's Apache-2.0 licence.

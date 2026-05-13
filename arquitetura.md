O workflow em camadas

┌─────────────────────────────────────────────────────────────────┐
│ HUMANO (Rick) │
│ ↓ /meeseeks <task> │
├─────────────────────────────────────────────────────────────────┤
│ DISCORD GATEWAY (interface) │
│ ↓ interaction → defer → followup │
├─────────────────────────────────────────────────────────────────┤
│ BOT PYTHON (orquestrador determinístico) — bot.py │
│ • lifecycle de interaction, heartbeat, branching de resposta │
│ • cria worktree, symlinka node_modules, sobe dev server │
│ • adapta saídas de cada agente pra mensagem do Discord │
├─────────────────────────────────────────────────────────────────┤
│ GARAGEM (planning agent) — sub-Claude read-only │
│ • tools: Read, Glob, Grep │
│ • system prompt: skills/garagem.md │
│ • output: JSON estruturado (briefing + slug + commit msg) │
│ • CWD: TARGET (master) │
├─────────────────────────────────────────────────────────────────┤
│ MEESEEKS (execution agent) — sub-Claude full-perm │
│ • tools: tudo (Edit, Write, Bash, etc.) via --skip-perms │
│ • system prompt: skills/meeseeks.md │
│ • output: markdown (relatório no tom Meeseeks) │
│ • CWD: worktree isolada (.worktrees/<slug>/) │
│ • pipeline: test → implementar → escrever testes → test │
│ → build → commit │
├─────────────────────────────────────────────────────────────────┤
│ PROJETO-ALVO (sandbox físico) │
│ • repo git + AGENTS.md como source-of-truth │
│ • worktree em .worktrees/<slug>/ + branch meeseeks/<slug> │
│ • dev server em :5173 (bot mantém o subprocess) │
└─────────────────────────────────────────────────────────────────┘
↑
HITL — humano revisa,
mergeia ou descarta a branch

Modelos em cada camada

┌──────────┬────────────────────────────────────────────┬────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Camada │ Modelo │ Por quê │
├──────────┼────────────────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Garagem │ Claude Sonnet 4.6 (default do Claude Code) │ tarefa estruturada, baixa exploração — Haiku seria viável e mais barato/rápido, ficou pra calibrar depois │
├──────────┼────────────────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Meeseeks │ Claude Sonnet 4.6 (default do Claude Code) │ edição + uso pesado de Bash (test/build/commit) — exige modelo que segue pipelines longos sem perder o fio │
├──────────┼────────────────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Bot │ nenhum (Python puro, determinístico) │ aqui é a cola, não há decisão semântica │
└──────────┴────────────────────────────────────────────┴────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

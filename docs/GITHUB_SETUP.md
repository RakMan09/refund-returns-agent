# GitHub Setup Guide

Use this guide to publish the project cleanly as `refund-returns-agent`.

## 1) Initialize Local Git (if needed)

```bash
cd "/Users/raksh/Desktop/Refund Returns Agent"
git init
git branch -M main
```

## 2) Create GitHub Repository

1. Create a new GitHub repo named `refund-returns-agent`.
2. Do not add a README/license/gitignore from GitHub UI (repo already has them).

## 3) Connect Remote and Push

```bash
git remote add origin git@github.com:<YOUR_USERNAME>/refund-returns-agent.git
git add .
git commit -m "Initial portfolio release"
git push -u origin main
```

## 4) Optional: Git LFS for Large Artifacts

Use Git LFS only for files you intentionally keep in repo.

```bash
git lfs install
git lfs track "*.safetensors" "*.bin" "*.pt"
git add .gitattributes
git commit -m "Configure git-lfs tracking"
git push
```

## 5) CI Setup

CI is preconfigured at `.github/workflows/ci.yml`:
- lint + tests
- docker stack smoke test (`eval/stack_smoke.py`)

No extra setup required beyond standard GitHub Actions availability.

## 6) Secrets Management

Do not commit real secrets. Keep only `.env.example` in repo.

If needed, store runtime secrets in:
- GitHub repo -> Settings -> Secrets and variables -> Actions

Typical names:
- `HF_TOKEN`
- `WANDB_API_KEY`

## 7) Pre-Push Final Validation

```bash
ruff check .
pytest -q
python3 scripts/final_audit.py --output eval/results/final_audit_report.json
```

Expected:
- lint/tests pass
- audit outputs `{"ok": true, ...}`

## 8) Release Tag

```bash
git tag -a v0.1.0 -m "Initial portfolio release"
git push origin v0.1.0
```

Attach optional release artifacts:
- adapter checkpoints (`models/.../adapter`)
- evaluation reports (`eval/results/*.json`)

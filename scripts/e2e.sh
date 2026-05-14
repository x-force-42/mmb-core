#!/usr/bin/env bash
# Roda a suíte E2E (real CLI do claude, fixture em ~/llab/mmb-fixture).
# Lento (~2min/cenário) e gasta $ — chama explicitamente, não roda em CI.
#
# Override do fixture: MMB_FIXTURE_PATH=... scripts/e2e.sh
# Override do timeout: MEESEEKS_TIMEOUT_S=600 scripts/e2e.sh

set -euo pipefail

cd "$(dirname "$0")/.."

exec .venv/bin/pytest tests/e2e -v -m e2e "$@"

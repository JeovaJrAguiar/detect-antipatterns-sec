#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/docker/docker-compose.yml"
DEV_ENV_FILE="${SCRIPT_DIR}/.env"
BASE_URL="${OBSERVA_URL:-http://127.0.0.1:8000}"

if [[ ! -f "${DEV_ENV_FILE}" ]]; then
  if ! command -v openssl >/dev/null 2>&1; then
    printf '%s\n' "openssl e necessario para gerar os segredos locais." >&2
    exit 1
  fi
  umask 077
  : > "${DEV_ENV_FILE}"
fi
chmod 600 "${DEV_ENV_FILE}"

read_env_value() {
  local key="$1"
  sed -n "s/^${key}=//p" "${DEV_ENV_FILE}" | tail -n 1
}

ensure_env_value() {
  local key="$1"
  local byte_count="$2"
  if [[ -z "$(read_env_value "${key}")" ]]; then
    printf '%s=%s\n' "${key}" "$(openssl rand -hex "${byte_count}")" >> "${DEV_ENV_FILE}"
  fi
}

if ! command -v openssl >/dev/null 2>&1; then
  printf '%s\n' "openssl e necessario para gerar os segredos locais." >&2
  exit 1
fi
ensure_env_value JWT_SECRET_KEY 32
ensure_env_value DEV_ADMIN_PASSWORD 16
ensure_env_value DEV_OPERATOR_PASSWORD 16
ensure_env_value DEV_EXECUTOR_PASSWORD 16

JWT_SECRET_KEY="$(read_env_value JWT_SECRET_KEY)"
DEV_ADMIN_PASSWORD="$(read_env_value DEV_ADMIN_PASSWORD)"
DEV_OPERATOR_PASSWORD="$(read_env_value DEV_OPERATOR_PASSWORD)"
DEV_EXECUTOR_PASSWORD="$(read_env_value DEV_EXECUTOR_PASSWORD)"
if [[ ! "${JWT_SECRET_KEY}" =~ ^[0-9a-fA-F]{64}$ \
  || ! "${DEV_ADMIN_PASSWORD}" =~ ^[0-9a-fA-F]{32}$ \
  || ! "${DEV_OPERATOR_PASSWORD}" =~ ^[0-9a-fA-F]{32}$ \
  || ! "${DEV_EXECUTOR_PASSWORD}" =~ ^[0-9a-fA-F]{32}$ ]]; then
  printf '%s\n' "${DEV_ENV_FILE} esta incompleto ou invalido; remova-o para gerar novos segredos locais." >&2
  exit 1
fi
export JWT_SECRET_KEY

COMPOSE=(docker compose --env-file "${DEV_ENV_FILE}" -f "${COMPOSE_FILE}")

if ! command -v docker >/dev/null 2>&1; then
  printf '%s\n' "Docker nao foi encontrado. Instale e inicie o Docker Desktop e rode este script novamente." >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  printf '%s\n' "Este script requer Docker Compose v2 (docker compose)." >&2
  exit 1
fi

printf '%s\n' "Iniciando PostgreSQL e Observa em containers de desenvolvimento..."
"${COMPOSE[@]}" up -d --build

printf '%s\n' "Aguardando o backend aplicar as migracoes e servir a interface..."
ready=0
for ((attempt = 1; attempt <= 90; attempt++)); do
  if curl --silent --show-error --fail "${BASE_URL}/" >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 1
done

if [[ "${ready}" -ne 1 ]]; then
  printf '%s\n' "O Observa nao ficou disponivel em ${BASE_URL}. Ultimos logs:" >&2
  "${COMPOSE[@]}" logs --tail=100 observa >&2
  exit 1
fi

printf '%s\n' "Populando o banco com fontes e detector local de demonstracao..."
"${COMPOSE[@]}" exec -T -e APP_ENV=development observa python - <<'PY'
import json
import os
from pathlib import Path

from sqlalchemy import select

from observa.database.database import SessionLocal
from observa.database.models import DetectorModel, SourceModel

if os.getenv("APP_ENV") != "development":
  raise SystemExit("O seed so pode ser executado em APP_ENV=development")

sources = (
    ("Alertas de demonstracao", Path("data/alerts.json")),
    ("Alertas de demonstracao compacto", Path("data/alerts2.json")),
)
detector_name = "Detector local de alertas excessivos"

with SessionLocal() as session:
    for name, path in sources:
        if not path.is_file():
            raise FileNotFoundError(f"Massa de desenvolvimento nao encontrada: {path}")
        with path.open(encoding="utf-8") as data_file:
            json_data = json.load(data_file)
        if not isinstance(json_data, list) or not all(
            isinstance(item, dict) and "count" in item for item in json_data
        ):
            raise ValueError(f"Massa invalida para o detector de alertas: {path}")

        existing_source = session.scalar(
            select(SourceModel).where(SourceModel.name == name)
        )
        if existing_source is None:
            session.add(SourceModel(name=name, json_data=json_data))

    existing_detector = session.scalar(
        select(DetectorModel).where(DetectorModel.name == detector_name)
    )
    if existing_detector is None:
        session.add(
            DetectorModel(
                name_ap="Alertas excessivos",
                name=detector_name,
                class_path=(
                    "observa.detectors.excessive_alerts."
                    "ExcessiveAlertsDetector"
                ),
            )
        )

    session.commit()

print("Seed aplicado. Fontes e detector existentes foram preservados.")
PY

printf '%s\n' "Criando usuarios de desenvolvimento se ainda nao existirem..."
bootstrap_output="$("${COMPOSE[@]}" exec -T \
  -e APP_ENV=development \
  -e DEV_ADMIN_PASSWORD="${DEV_ADMIN_PASSWORD}" \
  -e DEV_OPERATOR_PASSWORD="${DEV_OPERATOR_PASSWORD}" \
  -e DEV_EXECUTOR_PASSWORD="${DEV_EXECUTOR_PASSWORD}" \
  observa python -m observa.auth.bootstrap_dev_users)"
printf '%s\n' "${bootstrap_output}"

printf '\n%s\n' \
  "Stack de desenvolvimento iniciada." \
  "Frontend: ${BASE_URL}/ (FastAPI serve a interface na porta 8000; nao ha container frontend separado)." \
  "Backend API: ${BASE_URL}/api/v1 (porta 8000)." \
  "Documentacao da API: ${BASE_URL}/docs." \
  "PostgreSQL: localhost:5432, banco antipatterns." \
  "" \
  "Perfil Admin: usuario admin, senha local ${DEV_ADMIN_PASSWORD}." \
  "Perfil Operador: usuario operador, senha local ${DEV_OPERATOR_PASSWORD}." \
  "Perfil Executor: usuario executor, senha local ${DEV_EXECUTOR_PASSWORD}." \
  "Banco de desenvolvimento: usuario postgres, senha postgres (credencial do Compose local)." \
  "ATENCAO: credenciais de desenvolvimento; nao exponha esta stack em rede ou producao." \
  "" \
  "Fontes: Alertas de demonstracao; Alertas de demonstracao compacto." \
  "Detector: Detector local de alertas excessivos."

if command -v open >/dev/null 2>&1; then
  open "${BASE_URL}"
fi

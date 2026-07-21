#!/usr/bin/env sh
set -eu

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
    echo "[entrypoint] Application des migrations..."
    python manage.py migrate --noinput
fi

if [ "${COLLECT_STATIC:-1}" = "1" ]; then
    echo "[entrypoint] Collecte des fichiers statiques..."
    python manage.py collectstatic --noinput --clear
fi

echo "[entrypoint] Démarrage de l'application..."
exec "$@"
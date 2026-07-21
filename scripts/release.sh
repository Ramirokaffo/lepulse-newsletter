#!/usr/bin/env bash
# Build, tag and push the Docker image to Docker Hub.
#
# Usage : scripts/release.sh [VERSION]
# VERSION : tag à publier ; par défaut, hash court du commit courant.
#
# Variables :
#   IMAGE       Image Docker (def: ramirokaffo/lepulse)
#   DOCKERFILE  Dockerfile à utiliser (def: Dockerfile)
#   CONTEXT     Contexte de build (def: .)
#   PLATFORMS   Plateformes buildx, ex: linux/amd64,linux/arm64
#   PUSH_LATEST Pousser aussi :latest (def: 1)
#   NO_CACHE    Construire sans cache (def: 0)

set -euo pipefail

IMAGE="${IMAGE:-ramirokaffo/lepulse}"
DOCKERFILE="${DOCKERFILE:-Dockerfile}"
CONTEXT="${CONTEXT:-.}"
PLATFORMS="${PLATFORMS:-}"
PUSH_LATEST="${PUSH_LATEST:-1}"
NO_CACHE="${NO_CACHE:-0}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

VERSION="${1:-}"
if [ -z "${VERSION}" ]; then
    if git rev-parse --git-dir >/dev/null 2>&1; then
        VERSION="$(git rev-parse --short HEAD)"
    else
        echo "[release] Aucune version fournie et pas de dépôt Git détecté." >&2
        echo "          Usage : scripts/release.sh <VERSION>" >&2
        exit 1
    fi
fi

if git rev-parse --git-dir >/dev/null 2>&1 && [ -n "$(git status --porcelain)" ]; then
    echo "[release] ATTENTION : modifications locales non commitées."
    read -r -p "          Continuer quand même ? [y/N] " reply
    case "${reply}" in
        y|Y|yes|YES) ;;
        *) echo "[release] Abandon."; exit 1 ;;
    esac
fi

TAG_VERSION="${IMAGE}:${VERSION}"
TAG_LATEST="${IMAGE}:latest"
TAGS=(-t "${TAG_VERSION}")
if [ "${PUSH_LATEST}" = "1" ]; then
    TAGS+=(-t "${TAG_LATEST}")
fi

EXTRA_ARGS=()
if [ "${NO_CACHE}" = "1" ]; then
    EXTRA_ARGS+=(--no-cache)
fi

echo "[release] Image     : ${IMAGE}"
echo "[release] Version   : ${VERSION}"
echo "[release] Tags      : ${TAG_VERSION}$([ "${PUSH_LATEST}" = "1" ] && echo ", ${TAG_LATEST}")"
echo "[release] Platforms : ${PLATFORMS:-(natif)}"
echo

if ! docker system info >/dev/null 2>&1; then
    echo "[release] Le démon Docker semble inaccessible." >&2
    exit 1
fi

if [ -n "${PLATFORMS}" ]; then
    if ! docker buildx inspect >/dev/null 2>&1; then
        echo "[release] Création d'un builder buildx 'multiarch'..."
        docker buildx create --name multiarch --use >/dev/null
        docker buildx inspect --bootstrap >/dev/null
    fi

    echo "[release] Build et push multi-arch (${PLATFORMS})..."
    docker buildx build \
        --platform "${PLATFORMS}" \
        -f "${DOCKERFILE}" \
        "${TAGS[@]}" \
        "${EXTRA_ARGS[@]}" \
        --push \
        "${CONTEXT}"
else
    echo "[release] Build local..."
    docker build \
        -f "${DOCKERFILE}" \
        "${TAGS[@]}" \
        "${EXTRA_ARGS[@]}" \
        "${CONTEXT}"

    echo "[release] Push de ${TAG_VERSION}..."
    docker push "${TAG_VERSION}"
    if [ "${PUSH_LATEST}" = "1" ]; then
        echo "[release] Push de ${TAG_LATEST}..."
        docker push "${TAG_LATEST}"
    fi
fi

echo
echo "[release] Terminé."
echo "          docker pull ${TAG_VERSION}"
if [ "${PUSH_LATEST}" = "1" ]; then
    echo "          docker pull ${TAG_LATEST}"
fi
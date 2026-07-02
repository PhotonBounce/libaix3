#!/usr/bin/env bash
# OpsBrief Production Deployment Script
# Usage: ./deploy.sh

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_NAME="opsbrief"

# =============================================================================
# Helper Functions
# =============================================================================

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# =============================================================================
# Prerequisites Check
# =============================================================================

check_prerequisites() {
    log_info "Checking prerequisites..."

    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    log_info "Docker found: $(docker --version)"

    if ! command -v docker-compose &> /dev/null; then
        if ! docker compose version &> /dev/null; then
            log_error "Docker Compose is not installed. Please install Docker Compose first."
            exit 1
        fi
    fi
    log_info "Docker Compose found"

    # Check if Docker daemon is running
    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running. Please start Docker."
        exit 1
    fi

    log_info "All prerequisites satisfied."
}

# =============================================================================
# Environment Setup
# =============================================================================

setup_env() {
    log_info "Setting up environment..."

    if [[ ! -f "${SCRIPT_DIR}/.env" ]]; then
        if [[ -f "${SCRIPT_DIR}/.env.example" ]]; then
            cp "${SCRIPT_DIR}/.env.example" "${SCRIPT_DIR}/.env"
            log_warn ".env file created from .env.example. Please review and update the values before deploying."
            log_warn "Critical: Set OPENAI_API_KEY, GITHUB_TOKEN, NVD_API_KEY, SECRET_KEY, and JWT_SECRET_KEY."
            log_error "Please edit .env and re-run this script."
            exit 1
        else
            log_error ".env.example not found. Cannot create .env file."
            exit 1
        fi
    else
        log_info ".env file already exists."
    fi
}

# =============================================================================
# Docker Compose Check
# =============================================================================

detect_compose_command() {
    if command -v docker-compose &> /dev/null; then
        COMPOSE_CMD="docker-compose"
    elif docker compose version &> /dev/null; then
        COMPOSE_CMD="docker compose"
    else
        log_error "Could not detect docker-compose command."
        exit 1
    fi
    log_info "Using compose command: ${COMPOSE_CMD}"
}

# =============================================================================
# Deployment
# =============================================================================

deploy() {
    log_info "Starting deployment..."

    cd "${SCRIPT_DIR}"

    # Pull latest images if not building locally
    # ${COMPOSE_CMD} pull

    # Build and start services
    log_info "Building images and starting services..."
    ${COMPOSE_CMD} up -d --build

    if [[ $? -ne 0 ]]; then
        log_error "Deployment failed. Check the logs above for errors."
        exit 1
    fi

    log_info "Deployment completed successfully!"
}

# =============================================================================
# Status
# =============================================================================

show_status() {
    log_info "Service Status:"
    echo ""
    ${COMPOSE_CMD} -f "${SCRIPT_DIR}/docker-compose.yml" ps

    echo ""
    log_info "Resource Usage:"
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.PIDs}}"

    echo ""
    log_info "Health Checks:"
    ${COMPOSE_CMD} -f "${SCRIPT_DIR}/docker-compose.yml" ps | grep -E "(Name|opsbrief_)" || true
}

# =============================================================================
# Main
# =============================================================================

main() {
    echo "========================================"
    echo "  OpsBrief Production Deployment"
    echo "========================================"
    echo ""

    check_prerequisites
    setup_env
    detect_compose_command
    deploy
    show_status

    echo ""
    log_info "OpsBrief is now running!"
    log_info "Access the application at: http://localhost"
    log_info "API available at: http://localhost/api"
    log_info "Health check: http://localhost/health"
    echo ""
    log_info "Useful commands:"
    echo "  View logs:        ${COMPOSE_CMD} logs -f"
    echo "  Stop services:    ${COMPOSE_CMD} down"
    echo "  Restart app:      ${COMPOSE_CMD} restart app"
    echo "  Shell into app:   ${COMPOSE_CMD} exec app bash"
}

main "$@"

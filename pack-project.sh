#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "Usage: $0 <project_dir> [output_zip]"
  echo "Example: $0 ~/projects/ai-gm"
  echo "Example: $0 ~/projects/ai-gm ~/ai-gm-upload.zip"
  exit 1
fi

PROJECT_DIR="${1/#\~/$HOME}"
if [[ ! -d "$PROJECT_DIR" ]]; then
  echo "Error: project directory not found: $PROJECT_DIR"
  exit 1
fi

PROJECT_DIR="$(cd "$PROJECT_DIR" && pwd)"
PROJECT_NAME="$(basename "$PROJECT_DIR")"
OUTPUT_ZIP="${2:-$HOME/${PROJECT_NAME}-upload.zip}"
OUTPUT_ZIP="${OUTPUT_ZIP/#\~/$HOME}"

if ! command -v zip >/dev/null 2>&1; then
  echo "Error: zip is not installed. Install it with: sudo apt update && sudo apt install zip"
  exit 1
fi

mkdir -p "$(dirname "$OUTPUT_ZIP")"
rm -f "$OUTPUT_ZIP"

cd "$(dirname "$PROJECT_DIR")"

zip -r "$OUTPUT_ZIP" "$PROJECT_NAME" \
  -x "*/.git/*" \
  -x "*/node_modules/*" \
  -x "*/.venv/*" \
  -x "*/venv/*" \
  -x "*/__pycache__/*" \
  -x "*/dist/*" \
  -x "*/build/*" \
  -x "*/coverage/*" \
  -x "*/.next/*" \
  -x "*/.nuxt/*" \
  -x "*/.cache/*" \
  -x "*/.pytest_cache/*" \
  -x "*/.mypy_cache/*" \
  -x "*/tmp/*" \
  -x "*/temp/*" \
  -x "*/.DS_Store" \
  -x "*/Thumbs.db" \
  -x "*/.env" \
  -x "*/.env.*"

echo "Created: $OUTPUT_ZIP"
echo "Size: $(du -h "$OUTPUT_ZIP" | cut -f1)"
unzip -l "$OUTPUT_ZIP" | head -n 20

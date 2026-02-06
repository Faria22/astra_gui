set shell := ["zsh", "-cu"]

about_file := "src/astra_gui/__about__.py"

_ensure_clean:
  @git diff --quiet
  @git diff --cached --quiet

_version:
  @sed -n "s/^__version__ = '\\(.*\\)'$/\\1/p" {{about_file}}

_next_version bump:
  @current="$(just _version)"; \
    IFS='.' read -r major minor patch <<< "$current"; \
    case "{{bump}}" in \
      major) major=$((major + 1)); minor=0; patch=0 ;; \
      minor) minor=$((minor + 1)); patch=0 ;; \
      patch) patch=$((patch + 1)) ;; \
      *) echo "part must be one of: major, minor, patch" >&2; exit 1 ;; \
    esac; \
    echo "$major.$minor.$patch"

# Bump version, commit, tag, and push to origin. Add `-d` / `--dry-run` to preview actions.
[arg("dry_run", short='d', long='dry-run', value='true', help='Print planned release commands without changing anything')]
release bump dry_run="false":
  @if [[ "{{bump}}" != "major" && "{{bump}}" != "minor" && "{{bump}}" != "patch" ]]; then \
      echo "part must be one of: major, minor, patch" >&2; \
      exit 1; \
    fi; \
    if [[ "{{dry_run}}" == "true" ]]; then \
      next_version="$(just _next_version {{bump}})"; \
      echo "[dry-run] would run: hatch version {{bump}}"; \
      echo "[dry-run] would stage: {{about_file}}"; \
      echo "[dry-run] would commit: Bump version to v$next_version"; \
      echo "[dry-run] would tag: v$next_version"; \
      echo "[dry-run] would push: origin HEAD"; \
      echo "[dry-run] would push tag: v$next_version"; \
      exit 0; \
    fi; \
    just _ensure_clean; \
    hatch version {{bump}}; \
    version="$(just _version)"; \
    if [[ -z "$version" ]]; then \
      echo "Failed to read version from {{about_file}}" >&2; \
      exit 1; \
    fi; \
    git add {{about_file}}; \
    git commit -m "Bump version to v$version"; \
    git tag "v$version"; \
    git push origin HEAD; \
    git push origin "v$version"; \
    echo "Released v$version"

# Run Ruff on `src` and `tests`.
lint:
  hatch run lint

# Run static typing checks with basedpyright.
typecheck:
  hatch run typecheck

# Run the pytest suite.
test:
  hatch run test

# Run lint, typecheck, and tests.
all:
  hatch run all

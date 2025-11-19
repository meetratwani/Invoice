# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Repository status

- As of 2025-11-19, this repository only contains the `.git` directory. There are currently no source files, configuration files, or documentation (such as `README.md`).
- Because there is no application code checked into the working tree yet, there are no build, lint, or test commands that can be reliably documented.

## Guidance for future Warp instances

1. **Re-scan the repository once code is added**
   - Before making changes, list files to understand the structure (for example, using `Get-ChildItem -Recurse -File` in PowerShell).
   - Identify any language- or framework-specific entry points (for example `package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `.sln`/`.csproj`, `pom.xml`, `build.gradle`, etc.).

2. **Derive build and test commands from project metadata**
   - When a manifest or project file exists, prefer the commands it defines over ad-hoc guesses. For example, for Node projects use `npm run`/`pnpm run`/`yarn` scripts; for Python projects look for `pyproject.toml` tools and `Makefile`/`tasks.py`; for .NET projects use `dotnet` commands surfaced by `.sln`/`.csproj` files.
   - Update this `WARP.md` with concrete commands (build, lint, run tests, run a single test) once they can be determined from the checked-in files.

3. **Document architecture once the codebase exists**
   - After source directories are present, add a high-level description of the main modules (for example, API layer, domain/services, data access, UI) and how they relate.
   - Focus this documentation on cross-cutting structure that requires reading multiple files (shared utilities, common patterns, configuration flows), not on enumerating every file.

Until real code and configuration are present in this repository, keep changes minimal and avoid inventing build or test workflows that are not grounded in the checked-in files.
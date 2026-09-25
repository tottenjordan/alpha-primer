# CI & Package Management Notes

## uv Lockfile & Internal Proxy Considerations

### Observation
- Google development workstations enforce internal package proxying via `/etc/uv/uv.toml` targeting an internal Airlock artifact mirror (`http://airlock-proxy.uplink.goog:999/...`).
- When running `uv lock` on a corporate workstation without explicitly overriding the default index, the resulting `uv.lock` file embeds URLs referencing `airlock-proxy.uplink.goog`.
- In standard GitHub Actions runners (`ubuntu-latest`), these internal URLs are unreachable, causing download timeouts (`Connection refused: os error 111`).

### Solution
- Use `uv lock --no-config --upgrade` to bypass the system-level `/etc/uv/uv.toml` Airlock proxy and generate standard public `https://pypi.org/simple` URLs in `uv.lock`.
- Use `--frozen` (`uv run --frozen ...` or `uv sync --frozen`) in local testing or CI workflows to guarantee lockfile immutability without workstation auto-sync rewriting URLs.


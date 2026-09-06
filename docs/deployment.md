# Private zero-LLM deployment

The normal deployment does not use OpenAI or any other LLM provider. No API key,
billing account, or prepaid credit is required.

1. Copy `config.example.yaml` to `config.yaml` and `.env.example` to `.env` if needed.
2. Run `tailscale ip -4` and place that single address in `.env` as
   `TAILSCALE_BIND_ADDRESS=100.x.y.z`. `tailscale status` shows the MagicDNS
   hostname when MagicDNS is enabled.
3. Run `docker compose up -d --build`.
4. Browse to `http://molkey-ai-server:3000` or `http://<tailscale-ip>:3000`.

Port 3000 is a local RAN2 search/browse UI. It uses SQLite directly and makes no
LLM request.

The MCP container has no host port mapping and remains on the private Compose
network at `http://ran2wiki-mcp:8000/mcp`.

Open WebUI and its admin-account volume are preserved under the optional `llm`
profile. It is not started normally. A deliberately configured future provider
can use it on port 3001 via `docker compose --profile llm up -d open-webui`.

Optional HTTPS: leave the Compose bind at `127.0.0.1` and use Tailscale Serve
according to the version installed on this host. Verify the generated Serve
URL from another tailnet device; do not enable Funnel, which would make it
public. Firewall/public-router port forwarding is not required.

If `tailscale status` says the daemon is unavailable, run these interactively
on the mini PC (sudo authentication and tailnet login cannot be automated):

```bash
sudo systemctl enable --now tailscaled
sudo tailscale up
tailscale ip -4
tailscale status
```

## Long-running updates

The initial historical backfill can continue independently of a terminal or
Codex session:

```bash
docker compose --profile jobs up -d --build ran2wiki-update
docker compose logs -f ran2wiki-update
```

The job exits after sync, extraction, and indexing. Later monthly updates use
the same command and normally perform little work. Downloads are committed
incrementally and safely resume after network or machine interruption.

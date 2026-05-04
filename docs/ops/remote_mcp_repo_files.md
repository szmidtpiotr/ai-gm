# MCP zdalny — edycja plików repozytorium AI-GM

Serwer **`local-repo-mcp`** na hoście deweloperskim udostępnia **jeden katalog** (klon AI-GM) przez MCP (**Streamable HTTP**). To **osobna** usługa od MCP logów Loki (`aigm-mcp*.studio-colorbox.com`).

## Zakres na serwerze

| Ustawienie | Wartość |
|------------|---------|
| Katalog (`ALLOWED_ROOT`) | `/home/piotrszmidt/ai-gm` na `192.168.1.61` |
| Tryb | **`read_write`** — narzędzia m.in. odczyt, zapis plików, `mkdir` (wg wersji serwera) |
| Port upstream | **8765** (`BIND_HOST=0.0.0.0`) |
| Publiczny HTTPS (reverse proxy) | `https://ai-mcp-perplx.studio-colorbox.com` → proxy do `http://192.168.1.61:8765` |
| Endpoint MCP | `https://ai-mcp-perplx.studio-colorbox.com/mcp` |
| Health (monitoring) | `https://ai-mcp-perplx.studio-colorbox.com/health` → oczekiwane `ok` |

## Uwierzytelnianie

- Skonfiguruj **`MCP_AUTH_TOKEN`** w pliku **`/home/piotrszmidt/local-repo-mcp/.env`** na serwerze (nie commituj tokenu do tego repozytorium).
- Klienci (Cursor, Perplexity): nagłówek **`Authorization: Bearer <token>`** (w polu API Key często wklejasz sam token, bez słowa `Bearer`).

## Cursor — szablon `mcp.json`

Wklej nazwę i wstaw token z serwera zamiast placeholdera:

```json
{
  "mcpServers": {
    "AIGM Repo Files": {
      "url": "https://ai-mcp-perplx.studio-colorbox.com/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_MCP_AUTH_TOKEN_FROM_SERVER_ENV"
      }
    }
  }
}
```

## Systemd (na .61)

- Jednostka: **`local-repo-mcp@ai-gm-prod`** (`systemctl --user`).
- Po restarcie maszyny usługi użytkownika wymagają często **`loginctl enable-linger piotrszmidt`** (jednorazowo), inaczej MCP może nie wstać sam.
- **502** z nginx zwykle oznacza, że proces na `:8765` nie działa — sprawdź `curl http://127.0.0.1:8765/health` na serwerze i logi: `journalctl --user -u local-repo-mcp@ai-gm-prod -n 50`.

## Kod źródłowy serwera

Repozytorium / katalog instalacji MCP (poza `ai-gm`): projekt **`local-repo-mcp`** (np. klon obok workspace).

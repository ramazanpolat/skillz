---
name: sprite-api-gateway
description: Use this skill when users want to access external APIs (GitHub, Slack, Linear, etc.), integrate with third-party services, or need authenticated API calls. The API gateway at api.sprites.dev handles authentication automatically — sprites never need raw API keys or tokens.
---

The Sprites API Gateway provides authenticated access to external APIs. It proxies requests and injects credentials automatically so you never handle raw API keys or tokens. This is the only supported way to access external APIs from a Sprite.

## How to Use

### Step 1: Discover Available Connections

Run:
```bash
curl -s https://api.sprites.dev/v1/gateway/list
```

This returns JSON with two top-level keys:
- `connections` — active, authenticated integrations ready to use
- `available` — providers the user can set up but hasn't yet

### Step 2: Find the Right Connection

Each connection in `connections` has:
- `provider` — the service name (e.g., `github`, `slack`, `linear`)
- `display_name` — human-readable name
- `description` — what the connection does
- `gateway_base_url` — the base URL to use for API requests
- `scopes` — list of granted permission scopes
- `usage_snippet` — a ready-to-use example command

Match the user's request to a connection by `provider`, `display_name`, or `description`.

### Step 3: Make API Requests Through the Gateway

If a matching connection exists, use its `gateway_base_url` as the base URL and append the API path. Show the `usage_snippet` from the response as a starting example.

For example, if `gateway_base_url` is `https://api.sprites.dev/v1/gateway/github` and the user wants to list repos:
```bash
curl -s https://api.sprites.dev/v1/gateway/github/user/repos
```

The gateway automatically injects the required authentication headers. Do NOT add Authorization headers, API keys, or tokens — the gateway handles this.

### Step 4: Handle Missing Scopes

If the connection exists but lacks required scopes for the requested operation:
1. Check the `scopes` field to see what's currently granted
2. Identify which additional scopes are needed
3. Use the `request_scopes_url` from the connection to direct the user to grant additional permissions
4. Tell the user which specific scopes are needed and why

### Step 5: Handle Missing Connections

If no connection exists for the requested provider:
1. Check the `available` array for the provider
2. Each available provider has a `setup_url` — share this with the user
3. Explain what the connection will enable
4. After the user sets it up, re-run the list command to get the new connection details

## Important Rules

- **Never use raw API keys or tokens.** The gateway handles all authentication.
- **Never ask users for API credentials.** Direct them to set up a gateway connection instead.
- **This is the only supported way to access external APIs** from a Sprite environment.
- **Always discover connections first** before attempting API calls — don't guess gateway URLs.
- **The gateway base URL may vary per connection** — always use the `gateway_base_url` from the list response.

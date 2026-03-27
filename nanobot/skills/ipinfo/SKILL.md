---
name: ipinfo
description: Look up the current public IP address and basic IP geolocation info (no API key required).
homepage: https://ipinfo.io/developers
metadata: {"nanobot":{"emoji":"🌐","requires":{"bins":["curl"]}}}
---

# IP Info

Use this skill when the user wants their public IP, coarse geolocation, ISP/ASN, timezone, or a quick JSON snapshot of network identity.

## Quick commands

Public IP only:
```bash
curl -s https://api64.ipify.org?format=json
```

Public IP + location summary:
```bash
curl -s https://ipinfo.io/json
```

Alternative free geolocation response:
```bash
curl -s https://ipwho.is/
```

## Suggested workflow

1. Start with `ipinfo.io/json` for the most useful one-shot response.
2. If you only need the IP address, use `api64.ipify.org`.
3. If one service is unavailable, retry with `ipwho.is`.
4. Return a short human summary first, then include the important JSON fields if the user asked for details.

## Common fields

- `ip`: public IP address
- `city`, `region`, `country`: coarse geolocation
- `loc`: latitude/longitude pair
- `org`: ISP / ASN organization
- `timezone`: timezone name

## Notes

- These services provide approximate network geolocation, not precise device location.
- VPNs, mobile networks, carrier NAT, and proxies can change or obscure the result.
- Keep the response concise unless the user asked for raw JSON or automation-friendly output.

# ML Deadlines connector for Claude

This folder holds a remote [MCP](https://modelcontextprotocol.io) server that lets Claude answer questions about conference deadlines with the data from [ML Deadlines](https://ambress92.github.io/ml-deadlines/). It covers the same 37 conferences in machine learning, AI, NLP, computer vision, robotics, fairness, data mining and databases. Every date comes from the conference's official page, and estimated dates are marked as such.

**Connector URL:** `https://ml-deadlines.antonio-ferra577.workers.dev/mcp`

## Add it to Claude

In Claude, open **Settings > Connectors**, choose **Add custom connector**, and paste the connector URL. No account or sign-in is needed. Then ask, for example:

- "When is the CVPR 2027 deadline?"
- "Which ML or NLP submission deadlines are in the next two months?"
- "Compare the ICML and NeurIPS 2027 timelines."
- "Which robotics conferences do you know about, and where are they held?"

In Claude Code: `claude mcp add --transport http ml-deadlines <connector URL>`.

## Tools

All three tools only read data. None of them changes anything or needs a login.

| Tool | What it returns |
|---|---|
| `get_conference_deadlines` | For named conferences (acronyms or full names, optionally with a year): abstract and paper deadlines in their official time zone, rebuttal period, notification, camera-ready, conference dates and location, the official page and the date it was last checked. |
| `list_upcoming_deadlines` | Deadlines across all conferences in the next N days (60 by default), soonest first. It can be limited to areas, and can list rebuttals, notifications, camera-ready deadlines or conferences instead of submission deadlines. |
| `list_conferences` | The covered conferences by area, with full names, ICORE 2026 rank and next edition. |

## How it works

`worker.js` is a single file with no dependencies, which runs as a Cloudflare Worker. For each request it reads the site's public `data.json`, which GitHub Actions rebuilds every day from the files in `data/venues/`. A copy is kept for 10 minutes. The connector therefore needs no updates of its own when dates change.

## Deploy

1. Create a free account at [dash.cloudflare.com](https://dash.cloudflare.com).
2. Go to **Workers & Pages > Create > Start with Hello World**, name the Worker `ml-deadlines`, and deploy it.
3. Choose **Edit code**, replace the code with the contents of `worker.js`, and deploy again.
4. Under the Worker's **Settings > Observability**, make sure **Workers Logs** is off.

The connector URL is the Worker's address followed by `/mcp`.

## Privacy

See [PRIVACY.md](../PRIVACY.md). In short, the connector keeps no record of the questions it receives.

## Support

Report problems or wrong dates through the [GitHub issues](https://github.com/Ambress92/ml-deadlines/issues).

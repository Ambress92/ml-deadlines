# Privacy policy

This policy covers the ML Deadlines website (https://ambress92.github.io/ml-deadlines/) and the ML Deadlines connector for Claude. It was last updated on 2026-11-18.

## The connector for Claude

**What it receives.** When Claude uses the connector, it sends the tool's inputs: conference names, areas, a number of days, and which phase to list. The connector uses them to look up public conference dates and returns the answer to Claude. It receives no account information, no conversation text beyond these inputs, and no files.

**What it stores.** Nothing. The connector has no database, writes no logs of the requests, and sets no cookies. It needs no account or sign-in.

**Hosting.** The connector runs on Cloudflare Workers. Cloudflare processes each request in order to deliver it, including the caller's IP address, under [Cloudflare's privacy policy](https://www.cloudflare.com/privacypolicy/). The owner of the connector sees only aggregate request counts in the Cloudflare dashboard.

**Sharing.** No data is sold or shared with anyone. The only data the connector sends out are the requests for the site's public `data.json` file.

## The website

The website is hosted on GitHub Pages under [GitHub's privacy statement](https://docs.github.com/site-policy/privacy-policies/github-general-privacy-statement). Visits are counted with [GoatCounter](https://www.goatcounter.com), which uses no cookies and stores no personal data. Calendar subscriptions are plain files that calendar apps download.

## Retention

The connector keeps no data, so there is nothing to delete. GoatCounter keeps aggregate visit counts.

## Contact

Antonio Ferrara, through the [GitHub issues](https://github.com/Ambress92/ml-deadlines/issues) of this project.

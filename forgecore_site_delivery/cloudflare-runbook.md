# Cloudflare runbook for ForgeCore

I do not have direct Cloudflare access here, so these changes must be executed manually in the dashboard or through Wrangler with the correct credentials.

## Target setup

### Pages project 1
**Name:** forgecore-main  
**Domain:** forgecore.co  
**Framework:** Astro  
**Build command:** `npm run build`  
**Output directory:** `dist`

### Pages project 2
**Name:** forgecore-newsletter  
**Domain:** news.forgecore.co  
**Framework:** existing static pipeline  
**Deploy method:** existing Wrangler Pages deploy workflow

## DNS

- `forgecore.co` -> main Pages project
- `www.forgecore.co` -> redirect to apex
- `news.forgecore.co` -> newsletter Pages project

## Redirect rules

- `www.forgecore.co/*` -> `https://forgecore.co/$1` (301)

## Production checks

- verify SSL is active
- verify canonical tags point to the correct domain
- confirm Beehiiv signup still resolves from news subdomain
- verify no duplicate titles/descriptions across pages
- confirm legal pages exist before launch
- confirm analytics script is loaded once and only once

## Post-launch routine

Weekly:
- review latest publication links on home and `/news`
- add changelog entries for meaningful changes

Monthly:
- review homepage messaging
- review module states
- remove stale claims
- check broken links and redirects

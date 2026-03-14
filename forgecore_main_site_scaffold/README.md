# ForgeCore Main Site Scaffold

This is a static-first Astro scaffold for `forgecore.co`.

## Purpose

The main domain is the strategic shell for ForgeCore:
- define the system
- explain the doctrine
- map monetization modules
- show proof
- route users into the live publication on `news.forgecore.co`

The newsletter/publication remains a separate surface and should continue using the current static Jinja + Cloudflare Pages pipeline until a rewrite is economically justified.

## Pages included

- `/`
- `/system`
- `/system/how-it-works`
- `/system/architecture`
- `/system/principles`
- `/modules`
- `/modules/newsletter-intelligence`
- `/proof`
- `/proof/changelog`
- `/news`
- `/about`
- `/about/manifesto`
- `/contact`
- `/privacy`
- `/terms`

## Local development

```bash
npm install
npm run dev
```

## Cloudflare Pages

- Framework preset: Astro
- Build command: `npm run build`
- Output directory: `dist`

## Notes

- Replace placeholder legal copy before production launch.
- Replace sample latest-news entries with live data or a feed pull.
- Keep the newsletter positioned as one module inside ForgeCore, not the entire brand definition.

const CLOUDFLARE_WEB_ANALYTICS_SNIPPET = `<!-- Cloudflare Web Analytics --><script defer src='https://static.cloudflareinsights.com/beacon.min.js' data-cf-beacon='{"token": "71bb22c91bc4426384bd70e3f288ecbd"}'></script><!-- End Cloudflare Web Analytics -->`;

class CloudflareWebAnalyticsInjector {
  element(element) {
    element.append(CLOUDFLARE_WEB_ANALYTICS_SNIPPET, { html: true });
  }
}

export async function onRequest(context) {
  const response = await context.next();
  const contentType = response.headers.get("content-type") || "";

  if (!contentType.includes("text/html")) {
    return response;
  }

  return new HTMLRewriter()
    .on("head", new CloudflareWebAnalyticsInjector())
    .transform(response);
}

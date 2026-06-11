/**
 * Build Microsoft Office for the web URL to open a remote .pptx.
 * Office servers fetch `src` over HTTPS; the file URL must be reachable from the public internet
 * (localhost / intranet-only hosts will not work).
 *
 * @see https://learn.microsoft.com/en-us/microsoft-365/cloud-storage-partner-program/online/
 */
export function resolveAbsoluteFileUrl(href: string): string {
  if (href.startsWith("http://") || href.startsWith("https://")) {
    return href;
  }
  return new URL(href, window.location.origin).href;
}

export function officeOnlinePowerPointUrl(pptxAbsoluteUrl: string): string {
  const base = "https://view.officeapps.live.com/op/view.aspx";
  return `${base}?src=${encodeURIComponent(pptxAbsoluteUrl)}`;
}

function isPrivateOrLocalHost(hostname: string): boolean {
  const host = hostname.toLowerCase();
  if (host === "localhost" || host === "127.0.0.1" || host === "::1") {
    return true;
  }
  if (host.endsWith(".local")) {
    return true;
  }
  // RFC1918 + link-local + CGNAT ranges.
  return (
    /^10\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(host) ||
    /^192\.168\.\d{1,3}\.\d{1,3}$/.test(host) ||
    /^172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}$/.test(host) ||
    /^169\.254\.\d{1,3}\.\d{1,3}$/.test(host) ||
    /^100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d{1,3}\.\d{1,3}$/.test(host)
  );
}

export function canOpenInOfficeOnline(fileAbsoluteUrl: string): boolean {
  try {
    const appUrl = new URL(window.location.href);
    const fileUrl = new URL(fileAbsoluteUrl);
    // Office online fetching requires HTTPS and public addresses.
    if (appUrl.protocol !== "https:" || fileUrl.protocol !== "https:") {
      return false;
    }
    if (isPrivateOrLocalHost(appUrl.hostname) || isPrivateOrLocalHost(fileUrl.hostname)) {
      return false;
    }
    return true;
  } catch {
    return false;
  }
}

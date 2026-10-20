const PREFIX = '/downloads/antigravity';
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method !== 'GET' && request.method !== 'HEAD') {
      return new Response('Method not allowed', {status:405, headers:{Allow:'GET, HEAD'}});
    }
    if (url.pathname === PREFIX) return Response.redirect(url.origin + PREFIX + '/', 308);
    if (!url.pathname.startsWith(PREFIX + '/')) return new Response('Not found', {status:404});
    const relative = url.pathname.slice(PREFIX.length);
    const allowed = new Set(['/', '/index.html', '/downloads/antigravity-diagnostics-macos.zip',
      '/downloads/antigravity-diagnostics-windows.zip', '/downloads/SHA256SUMS.txt']);
    if (!allowed.has(relative)) return new Response('Not found', {status:404});
    url.pathname = relative === '/' ? '/index.html' : relative;
    const result = await env.ASSETS.fetch(new Request(url, {method:request.method}));
    const response = new Response(result.body,result);
    response.headers.set('X-Content-Type-Options','nosniff');
    response.headers.set('Referrer-Policy','strict-origin-when-cross-origin');
    response.headers.set('X-Frame-Options','DENY');
    response.headers.set('Cache-Control','public, max-age=300');
    if (relative.endsWith('.zip')) {
      response.headers.set('Content-Type','application/zip');
      response.headers.set('Content-Disposition','attachment; filename="'+relative.split('/').pop()+'"');
    } else if (relative==='/' || relative==='/index.html') {
      response.headers.set('Content-Security-Policy',"default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'");
    }
    return response;
  }
};

// CloudFront Function, associated with the wozi.com distribution's DEFAULT
// cache behaviour on the viewer-request event. This is NOT deployed by CI --
// it is applied by hand and lives here so the repo has a copy of it at all.
// See CLAUDE.md, "What the distribution does before S3 sees the request".
//
// Test before publishing (DEVELOPMENT stage, does not touch LIVE):
//   aws cloudfront update-function --name wozi-viewer-request \
//     --if-match "$(aws cloudfront describe-function --name wozi-viewer-request \
//                    --stage DEVELOPMENT --query ETag --output text)" \
//     --function-config Comment="www->apex redirect, directory index rewrite, /fidget slash",Runtime=cloudfront-js-2.0 \
//     --function-code fileb://infra/cloudfront-viewer-request.js
//   aws cloudfront test-function --name wozi-viewer-request --stage DEVELOPMENT \
//     --if-match "$(aws cloudfront describe-function --name wozi-viewer-request \
//                    --stage DEVELOPMENT --query ETag --output text)" \
//     --event-object fileb://<event.json>
//
// Publish to LIVE (takes effect immediately, no invalidation needed -- this
// runs on every request, cache hit or miss):
//   aws cloudfront publish-function --name wozi-viewer-request \
//     --if-match "$(aws cloudfront describe-function --name wozi-viewer-request \
//                    --stage DEVELOPMENT --query ETag --output text)"

// Directories reachable without their trailing slash. Named explicitly, not
// "any path with no extension" -- ssh_public_key is a root object published
// deliberately without one (CLAUDE.md's whitelist), and an extensionless rule
// would 301 it into /ssh_public_key/ and break it. Mirrors the deploy's own
// whitelist reasoning: a new directory does not get a redirect by being
// forgotten, and the cost of forgetting is today's 403, not a broken object.
var DIRS = ['fidget'];

function handler(event) {
    var request = event.request;
    var headers = request.headers || {};
    var host = headers.host && headers.host.value ? headers.host.value.toLowerCase() : '';
    var uri = request.uri || '/';

    /* Rebuild the query string so a redirect does not silently drop it. */
    var qs = '';
    var parts = [];
    var q = request.querystring;
    if (q) {
        for (var k in q) {
            var v = q[k];
            if (v.multiValue) {
                for (var i = 0; i < v.multiValue.length; i++) {
                    parts.push(k + '=' + v.multiValue[i].value);
                }
            } else if (v.value) {
                parts.push(k + '=' + v.value);
            } else {
                parts.push(k);
            }
        }
        if (parts.length) { qs = '?' + parts.join('&'); }
    }

    /* A directory reachable without its slash gets one, on whatever host
       asked for it -- charles.wozi.com/fidget stays on charles.wozi.com,
       it does not get forced to the apex. Done before the www check below
       so www.wozi.com/fidget takes one hop, not two: the www branch already
       redirects straight to https://wozi.com, so slashing first folds into
       that same redirect instead of following it. */
    if (DIRS.indexOf(uri.slice(1)) !== -1) {
        uri = uri + '/';
    }

    /* www -> apex. Permanent, and to https directly so the client does not
       take a second hop through the viewer-protocol redirect. */
    if (host === 'www.wozi.com') {
        return {
            statusCode: 301,
            statusDescription: 'Moved Permanently',
            headers: {
                'location': { value: 'https://wozi.com' + uri + qs },
                'cache-control': { value: 'max-age=3600' }
            }
        };
    }

    /* A slash was added above by the DIRS rule -- redirect to it explicitly
       so the browser's address bar (and any bookmark) ends up on the
       canonical form, on the SAME host it asked. */
    if (uri !== request.uri) {
        return {
            statusCode: 301,
            statusDescription: 'Moved Permanently',
            headers: {
                'location': { value: 'https://' + host + uri + qs },
                'cache-control': { value: 'max-age=3600' }
            }
        };
    }

    /* Directory index. The origin is the S3 REST endpoint behind an OAI, not the
       website endpoint, so S3's own IndexDocument rule never runs and a request
       for /fidget/ resolves to the 0-byte placeholder object instead of the page.
       CloudFront's DefaultRootObject only covers "/". Rewrite any trailing slash
       to the index document explicitly. */
    if (uri.charAt(uri.length - 1) === '/') {
        request.uri = uri + 'index.html';
    }

    return request;
}

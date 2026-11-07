"""HighLevel (LeadConnector) client-portal course API. Auth is the `catv2` cookie
on the portal domain: base64 JSON whose .token is the bearer. Never printed."""
import base64, json, urllib.parse, requests

BASE = "https://services.leadconnectorhq.com/clientportal-middleware/memberships/locations/{loc}"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"

def session(cookies_txt, product):
    rows = [l.rstrip('\n').split('\t') for l in open(cookies_txt) if l.count('\t') >= 6]
    ck = {r[5]: r[6] for r in rows}
    d = json.loads(base64.b64decode(urllib.parse.unquote(ck['catv2']) + '==='))
    loc = d['locationId']
    s = requests.Session()
    s.headers.update({
        'User-Agent': UA, 'Accept': 'application/json, text/plain, */*',
        'authorization': 'Bearer ' + d['token'], 'channel': 'APP', 'source': 'PORTAL_USER',
        'version': '2021-07-28', 'x-location-id': loc, 'x-product-id': product,
        'x-platform-details': 'web', 'Origin': 'https://' + [r[0] for r in rows if r[5] == 'catv2'][0].lstrip('.'),
    })
    return s, BASE.format(loc=loc)

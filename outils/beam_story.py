#!/usr/bin/env python3
# Beam - story "Les 3 pepites du jour". usage: python3 beam_story.py OUTDIR [YYYY-MM-DD]
# Writes OUTDIR/1_selection.png + 2..4_pepite_N.png (Instagram stories), tiktok_*.jpg (TikTok safe-zone layout) and caption.txt
import json, sys, os, re, math, io, html, datetime, urllib.request
from PIL import Image, ImageFilter, ImageStat

OUT = os.path.abspath(sys.argv[1]); os.makedirs(OUT, exist_ok=True)
TODAY = datetime.date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else (datetime.datetime.utcnow()).date()
API = 'https://api.beam.sn/item/home/public?page={}&limit=100'
UA = {'User-Agent': 'Mozilla/5.0 BeamStoryBot'}
def get(u):
    with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30) as r: return r.read()

items, page = [], 1
while page <= 25:
    d = json.loads(get(API.format(page))); items += d['items']
    if not d['meta'].get('hasNextPage'): break
    page += 1

NOT_FASHION = re.compile(r'iphone|\blivres?\b|roman|bouquin|manuel scolaire|chariot|rangement|[ée]tag[èe]re|organisateur|cuisine|vaisselle|matelas|rideau|d[ée]coration|samsung|t[ée]l[ée]phone|phone|ordinateur|laptop|\bpc\b|macbook|tablette|ipad|playstation|ps[45]|xbox|\btv\b|t[ée]l[ée]vision|console|airpods|chargeur|frigo|meuble|power\s*bank|batterie|[ée]couteur|casque|enceinte|cam[ée]ra|parfum|chauffant|douleur|r[èe]gles douloureuses|m[ée]dic|minceur', re.I)
LUXE = re.compile(r'louis\s*vuitton|\blv\b|gucci|dior|chanel|balenciaga|prada|herm[eè]s|versace|fendi|saint[\s-]*laurent|\bysl\b|givenchy|burberry|rolex|cartier|audemars|royal\s*oak|patek|hublot|off[- ]?white|moncler|celine|loewe|bottega|chrome\s*hearts?|amiri|stone\s*island', re.I)
COND = {'NEW': 2.0, 'LIKE_NEW': 1.6, 'GOOD': 1.0, 'FAIR': 0.3}
COND_FR = {'NEW': 'Neuf', 'LIKE_NEW': 'Comme neuf', 'GOOD': 'Bon état', 'FAIR': 'État correct'}
now = datetime.datetime.now(datetime.timezone.utc)
EXCLUDE = set(x.strip() for x in os.environ.get('BEAM_EXCLUDE', '').split(',') if x.strip())
# Historique : on n'affiche pas un article déjà mis en avant dans les 21 derniers jours (pepites/AAAA-MM-JJ/ids.txt)
HIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'pepites')
if os.path.isdir(HIST):
    for d in os.listdir(HIST):
        try: dd = datetime.date.fromisoformat(d)
        except ValueError: continue
        f = os.path.join(HIST, d, 'ids.txt')
        if dd != TODAY and 0 < (TODAY - dd).days <= 21 and os.path.exists(f):
            EXCLUDE |= set(x.strip() for x in open(f).read().split() if x.strip())

def score(it):
    desc = (it.get('description') or '').strip(); title = (it.get('title') or '').strip()
    s = min(len(desc), 160) / 160 * 3 + COND.get(it.get('condition'), 0)
    if nice_size(it.get('size')): s += 0.8
    s += min(it.get('favoritesCount') or 0, 6) * 0.35 + min(math.log1p(it.get('views') or 0), 5) * 0.25
    if (it.get('originalPrice') or 0) > it['price']: s += 1.2
    try:
        age = (now - datetime.datetime.fromisoformat(it['createdAt'].replace('Z', '+00:00'))).days
        s += 2.0 if age <= 14 else 1.0 if age <= 45 else 0
    except Exception: pass
    if it.get('isBoosted'): s += 1.0
    if title.isupper() and len(title) > 6: s -= 0.5
    return s

def nice_size(sz):
    sz = (sz or '').strip()
    if not sz or sz.lower() in ('standard', 'unique', '-', 'x'): return ''
    if re.search(r'tou[ts]', sz.lower()): return ''
    nums = re.findall(r'\d+', sz)
    if len(nums) >= 2 and nums[0] == nums[-1]: return nums[0]
    if len(nums) >= 2 and not re.fullmatch(r'[\d\s,./-]*\d', sz.strip()) or len(nums) >= 3: return f"{nums[0]} à {nums[-1]}"
    if len(sz) == 1 and sz.upper() not in 'SML': return ''
    sz = re.sub(r'(?i)^pointure\s*', '', sz)
    return sz.upper() if len(sz) <= 4 else sz

def ok(it):
    if it.get('id') in EXCLUDE: return False
    if it.get('status') != 'AVAILABLE' or not it.get('isPublicationPaid') or not it.get('image'): return False
    if NOT_FASHION.search(it.get('title') or ''): return False
    if re.search(r'\d[\d .-]{7,}\d', it.get('title') or ''): return False
    if LUXE.search((it.get('title') or '') + ' ' + (it.get('description') or '')): return False
    if len((it.get('description') or '').strip()) < 20 or len((it.get('title') or '').strip()) < 4: return False
    return 500 <= (it.get('price') or 0) <= 150000

def photo(it):
    u = it['image']; u = re.sub(r'width=\d+', 'width=1080', u) if 'width=' in u else u + ('&' if '?' in u else '?') + 'width=1080'
    try: im = Image.open(io.BytesIO(get(u))).convert('RGB')
    except Exception: return None
    w, h = im.size
    if min(w, h) < 500: return None
    g = im.convert('L').resize((400, int(400 * h / w)))
    if ImageStat.Stat(g.filter(ImageFilter.FIND_EDGES)).var[0] < 60: return None
    b = ImageStat.Stat(g).mean[0]
    if b < 35 or b > 235: return None
    p = os.path.join(OUT, it['id'] + '.jpg'); im.save(p, quality=92); return p

cands = [dict(it, _s=score(it)) for it in items if ok(it)]
TIERS = [('3 000 à 5 000', lambda p: 3000 <= p <= 5000), ('5 000 à 7 000', lambda p: 5000 < p <= 7000), ('7 000 à 10 000', lambda p: 7000 < p <= 10000)]
picked, sellers, doy = [], set(), TODAY.toordinal()
for label, f in TIERS:
    pool = sorted([c for c in cands if f(c['price']) and c['userUsername'] not in sellers], key=lambda c: -c['_s'])[:30]
    passing = []
    for c in pool:
        if any(c['userUsername'] == q['userUsername'] for q in passing): continue
        img = photo(c)
        if img: passing.append(dict(c, _img=img, _tier=label))
        if len(passing) >= 7: break
    if passing:
        c = passing[doy % len(passing)]  # rotate through the 7 best so an item comes back at most once a week
        picked.append(c); sellers.add(c['userUsername'])

JOURS = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
MOIS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']
date = f"{JOURS[TODAY.weekday()]} {TODAY.day} {MOIS[TODAY.month - 1]}"
fmt = lambda n: f"{n:,}".replace(',', ' ') + ' FCFA'
E = html.escape
cards = ''
for i, c in enumerate(picked):
    sz = nice_size(c.get('size')); op = c.get('originalPrice') if (c.get('originalPrice') or 0) > c['price'] else None
    title = re.sub(r'[^\w\s&|()\'’.,!/+-]', '', c['title']).strip(' |-')
    cards += f'''<div class="card c{i}" style="top:{520 + i * 355}px"><div class="ph"><img src="file://{c['_img']}"><div class="tier">{E(c['_tier'])}</div></div>
<div class="info"><div class="t">{E(title)}</div><div class="p"><b>{fmt(c['price'])}</b>{f'<s>{fmt(op)}</s>' if op else ''}</div>
<div class="chips">{f'<span>Taille {E(sz)}</span>' if sz else ''}<span>{COND_FR.get(c['condition'], '')}</span></div></div></div>'''

DIAM = '<path d="M50 2 98 50 50 98 2 50Z"/><path d="M50 14 86 50 50 86 14 50Z"/><path d="M50 26 74 50 50 74 26 50Z"/><path d="M50 38 62 50 50 62 38 50Z"/>'
LOGO = os.environ.get('BEAM_LOGO_B64', '')
page_html = f'''<!doctype html><html><head><meta charset="utf-8"><style>
*{{box-sizing:border-box;margin:0;padding:0}} html,body{{width:1080px;height:1920px;overflow:hidden}}
#s{{position:relative;width:1080px;height:1920px;overflow:hidden;font-family:Poppins,sans-serif;color:#F8F8EC;background:radial-gradient(1100px 900px at 50% 20%,#1d4266 0%,#143048 40%,#0B1B2B 85%)}}
.diam{{position:absolute;opacity:.12}}
#top{{position:absolute;left:70px;right:70px;top:220px;display:flex;justify-content:space-between;align-items:flex-start}}
.over{{font-size:26px;letter-spacing:8px;text-transform:uppercase;color:#E2BC4E;font-weight:500}}
h1{{font-family:Lora,serif;font-weight:600;font-size:76px;line-height:1.05;margin-top:14px}} h1 span{{color:#E2BC4E}}
.date{{font-size:30px;opacity:.8;margin-top:12px}}
#logo{{width:110px;height:116px;border-radius:22px}}
#word{{font-family:Lora,serif;font-weight:600;font-size:40px;letter-spacing:8px;color:#E2BC4E;border:2px solid #C9A030;border-radius:16px;padding:10px 16px}}
.card{{position:absolute;left:60px;right:60px;height:330px;border-radius:40px;background:rgba(248,248,236,.07);border:2px solid rgba(248,248,236,.16);display:flex;overflow:hidden}}
.ph{{width:330px;height:100%;flex:none;position:relative}} .ph img{{width:100%;height:100%;object-fit:cover;display:block}}
.tier{{position:absolute;left:18px;top:18px;padding:8px 18px;border-radius:999px;background:#0B1B2B;color:#E2BC4E;font-size:22px;font-weight:600}}
.info{{padding:30px 34px;display:flex;flex-direction:column;justify-content:center;min-width:0}}
.t{{font-family:Lora,serif;font-weight:600;font-size:42px;line-height:1.1;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}}
.p{{margin-top:16px;display:flex;align-items:baseline;gap:16px;flex-wrap:wrap}} .p b{{font-size:56px;color:#E2BC4E;font-weight:700;line-height:1}} .p s{{font-size:28px;opacity:.55}}
.chips{{display:flex;gap:12px;margin-top:18px;flex-wrap:wrap}} .chips span{{padding:8px 20px;border-radius:999px;border:2px solid rgba(248,248,236,.3);font-size:24px}}
#cta{{position:absolute;left:0;right:0;top:1610px;text-align:center}}
#cta .pill{{display:inline-block;padding:22px 56px;border-radius:999px;background:linear-gradient(135deg,#E9C55A,#C9A030 55%,#AC852A);color:#0B1B2B;font-weight:600;font-size:42px}}
#cta p{{margin-top:18px;font-size:28px;opacity:.75}}
</style></head><body><div id="s">
<svg class="diam" style="right:-140px;top:60px" width="520" height="520" viewBox="0 0 100 100" fill="none" stroke="#E2BC4E" stroke-width=".6">{DIAM}</svg>
<svg class="diam" style="left:-160px;bottom:40px" width="480" height="480" viewBox="0 0 100 100" fill="none" stroke="#E2BC4E" stroke-width=".6">{DIAM}</svg>
<div id="top"><div><div class="over">Beam · sélection</div><h1>Les 3 pépites<br><span>du jour</span></h1><div class="date">{date}</div></div>
{f'<img id="logo" src="data:image/jpeg;base64,{LOGO}">' if LOGO else '<div id="word">BEAM</div>'}</div>
{cards}
<div id="cta"><div class="pill">Dispo sur beam.sn</div><p>Lien en bio · Premier arrivé, premier servi</p></div></div></body></html>'''

def clean_desc(t):
    t = (t or '').replace('\\n', ' ')
    t = re.sub(r'https?://\S+|\S+@\S+', '', t)
    t = re.sub(r'(\+?\d[\d .-]{7,}\d)', '', t)
    t = re.sub(r'[^\w\s&()\'’.,!?:;/+%-]', '', t)
    t = re.sub(r'\s+', ' ', t).strip()
    if len(t) > 170: t = t[:170].rsplit(' ', 1)[0].rstrip('.,;:') + '…'
    return t

details = []
for i, c in enumerate(picked):
    sz = nice_size(c.get('size')); op = c.get('originalPrice') if (c.get('originalPrice') or 0) > c['price'] else None
    title = re.sub(r'[^\w\s&|()\'’.,!/+-]', '', c['title']).strip(' |-')
    details.append(f'''<!doctype html><html><head><meta charset="utf-8"><style>
*{{box-sizing:border-box;margin:0;padding:0}} html,body{{width:1080px;height:1920px;overflow:hidden}}
#s{{position:relative;width:1080px;height:1920px;overflow:hidden;font-family:Poppins,sans-serif;color:#F8F8EC;background:radial-gradient(1100px 900px at 50% 20%,#1d4266 0%,#143048 40%,#0B1B2B 85%)}}
.diam{{position:absolute;opacity:.12}}
#top{{position:absolute;left:70px;right:70px;top:210px;display:flex;justify-content:space-between;align-items:center}}
.over{{font-size:26px;letter-spacing:8px;text-transform:uppercase;color:#E2BC4E;font-weight:500}}
.num{{font-family:Lora,serif;font-weight:600;font-size:34px;opacity:.85}}
#ph{{position:absolute;left:70px;right:70px;top:300px;height:820px;border-radius:44px;overflow:hidden;box-shadow:0 40px 80px rgba(0,0,0,.45)}}
#ph img{{width:100%;height:100%;object-fit:cover;display:block}}
.tier{{position:absolute;left:24px;top:24px;padding:10px 22px;border-radius:999px;background:#0B1B2B;color:#E2BC4E;font-size:26px;font-weight:600}}
#price{{position:absolute;right:100px;bottom:770px;padding:22px 36px;border-radius:30px;background:linear-gradient(135deg,#E9C55A,#C9A030 55%,#AC852A);color:#0B1B2B;box-shadow:0 30px 60px rgba(0,0,0,.45);text-align:right}}
#price s{{display:block;font-size:28px;opacity:.6}} #price b{{font-size:66px;line-height:1;font-weight:700}}
#info{{position:absolute;left:70px;right:70px;top:1190px}}
h2{{font-family:Lora,serif;font-weight:600;font-size:58px;line-height:1.1;max-width:900px;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}}
.chips{{display:flex;gap:14px;margin-top:22px;flex-wrap:wrap}} .chips span{{padding:10px 24px;border-radius:999px;border:2px solid rgba(248,248,236,.3);font-size:28px}}
.desc{{margin-top:24px;font-size:30px;line-height:1.45;opacity:.85;overflow:hidden;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical}}
#cta{{position:absolute;left:70px;right:70px;top:1660px;display:flex;justify-content:space-between;align-items:center}}
#cta .pill{{padding:18px 40px;border-radius:999px;background:linear-gradient(135deg,#E9C55A,#C9A030 55%,#AC852A);color:#0B1B2B;font-weight:600;font-size:36px}}
#cta .by{{font-size:26px;opacity:.75;text-align:right}}
</style></head><body><div id="s">
<svg class="diam" style="right:-140px;top:40px" width="420" height="420" viewBox="0 0 100 100" fill="none" stroke="#E2BC4E" stroke-width=".6">{DIAM}</svg>
<div id="top"><div class="over">Pépite du jour</div><div class="num">{i + 1}/{len(picked)}</div></div>
<div id="ph"><img src="file://{c['_img']}"><div class="tier">{E(c['_tier'])} FCFA</div></div>
<div id="price">{f'<s>{fmt(op)}</s>' if op else ''}<b>{fmt(c['price'])}</b></div>
<div id="info"><h2>{E(title)}</h2>
<div class="chips">{f'<span>Taille {E(sz)}</span>' if sz else ''}<span>{COND_FR.get(c['condition'], '')}</span></div>
<div class="desc">{E(clean_desc(c.get('description')))}</div></div>
<div id="cta"><div class="pill">Dispo sur beam.sn</div><div class="by">Vendu par<br>@{E(c['userUsername'])}</div></div>
</div></body></html>''')


# TikTok : zone sûre (onglets en haut, légende en bas, boutons à droite)
TT_RECAP = """<style>
#top{top:235px!important;right:190px!important}
h1{font-size:62px!important} .over{font-size:22px!important} .date{font-size:26px!important}
#logo{width:84px!important;height:89px!important}
.card{left:56px!important;right:190px!important;height:245px!important}
.c0{top:475px!important}.c1{top:738px!important}.c2{top:1001px!important}
.ph{width:245px!important} .info{padding:20px 24px!important}
.t{font-size:34px!important} .p b{font-size:44px!important} .p s{font-size:22px!important}
.chips{margin-top:10px!important} .chips span{font-size:20px!important;padding:5px 14px!important}
.tier{font-size:18px!important;padding:6px 12px!important}
#cta{top:1268px!important;left:56px!important;right:190px!important}
#cta .pill{font-size:32px!important;padding:14px 38px!important} #cta p{display:none!important}
</style></body>"""
TT_DETAIL = """<style>
#top{top:235px!important;right:190px!important}
#ph{top:300px!important;left:56px!important;right:190px!important;height:620px!important}
#price{bottom:auto!important;top:840px!important;right:210px!important;padding:16px 26px!important}
#price b{font-size:50px!important} #price s{font-size:22px!important}
#info{top:960px!important;left:56px!important;right:190px!important}
h2{font-size:44px!important} .chips{margin-top:14px!important} .chips span{font-size:22px!important;padding:6px 16px!important}
.desc{font-size:24px!important;margin-top:14px!important;-webkit-line-clamp:3!important}
#cta{top:1270px!important;left:56px!important;right:190px!important}
#cta .pill{font-size:28px!important;padding:14px 30px!important} #cta .by{font-size:20px!important}
</style></body>"""

from playwright.sync_api import sync_playwright
with sync_playwright() as pw:
    b = pw.chromium.launch(); pg = b.new_page(viewport={'width': 1080, 'height': 1920})
    def shot(html_text, name):
        fp = os.path.join(OUT, name + '.html'); open(fp, 'w').write(html_text)
        pg.goto('file://' + fp); pg.evaluate('document.fonts.ready'); pg.wait_for_timeout(400)
        pg.screenshot(path=os.path.join(OUT, name + '.png'))
    shot(page_html, '1_selection')
    shot(page_html.replace('</body>', TT_RECAP), 'tiktok_1_selection')
    for i, h in enumerate(details):
        shot(h, f'{i + 2}_pepite_{i + 1}')
        shot(h.replace('</body>', TT_DETAIL), f'tiktok_{i + 2}_pepite_{i + 1}')
    b.close()

# TikTok refuse le PNG : versions JPEG pour TikTok (format zone sûre)
for n in ['1_selection'] + [f'{i + 2}_pepite_{i + 1}' for i in range(len(details))]:
    Image.open(os.path.join(OUT, 'tiktok_' + n + '.png')).convert('RGB').save(os.path.join(OUT, 'tiktok_' + n + '.jpg'), quality=92)
    os.remove(os.path.join(OUT, 'tiktok_' + n + '.png'))

cap = [f"Les 3 pépites du {date[0].lower() + date[1:]} ✨ Swipe pour voir le détail."] + [f"• {c['title'].strip()} : {fmt(c['price'])}" for c in picked] + ["Dispo sur beam.sn, lien en bio.", "", "#Beam #Dakar #Senegal #SecondeMain #ModeDakar #Friperie"]
open(os.path.join(OUT, 'caption.txt'), 'w').write('\n'.join(cap) + '\n')
open(os.path.join(OUT, 'ids.txt'), 'w').write('\n'.join(c['id'] for c in picked) + '\n')
print(f"{len(items)} annonces lues, {len(cands)} retenues, {len(picked)} choisies")
for c in picked: print(c['id'], '|', c['_tier'], '|', c['title'].strip(), '|', c['price'], '|', c['condition'], '|', c['userUsername'], '| score', round(c['_s'], 2))

"""Serves /state and /collage.png in front of the frame, adding the banner.

Sitting in front rather than patching the frame is deliberate: `fugleramme` is a
git checkout that updates itself, and a patched render loop would be reverted by
the next `git checkout --force`. Apache sends only these two paths here; the
admin page, static files and everything else still go straight to the frame.

The banner has to move the /state token too, or the kiosk - which only refetches
the image when the token changes - would never notice it appear or disappear.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote_plus, urljoin

from PIL import Image, ImageDraw, ImageFont

from . import labels, simulate, state
from .config import FRAME, FUGLERAMME, OVERLAY_PORT, PAPER, STYLE, USER_AGENT, has_artwork

# Kept here rather than in a template file so the service has no asset of its
# own to lose track of; it is one page and it never leaves this process.
PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bird frame - simulate a detection</title>
<style>
 :root{color-scheme:light}
 body{margin:0;background:#faf9f6;color:#3c382e;
      font:16px/1.55 Georgia,'Times New Roman',serif;
      display:flex;justify-content:center;padding:6vh 1rem}
 main{width:min(38rem,100%)}
 h1{font-size:1.6rem;font-weight:400;font-style:italic;margin:0 0 .3rem}
 p.sub{color:#8a8880;margin:0 0 2rem;font-style:italic}
 form{display:flex;gap:.6rem;margin-bottom:1.4rem}
 input{flex:1;padding:.7rem .9rem;border:1px solid #d8d4c8;border-radius:.4rem;
       background:#fff;font:inherit;color:inherit}
 input:focus{outline:2px solid #b9b2a0;outline-offset:1px}
 button{padding:.7rem 1.2rem;border:1px solid #b9b2a0;border-radius:.4rem;
        background:#efece4;font:inherit;font-style:italic;cursor:pointer;color:inherit}
 button:hover{background:#e6e2d7}
 button:disabled{opacity:.5;cursor:default}
 #msg{min-height:1.5rem;margin-bottom:1.2rem}
 .ok{color:#4a6741}.err{color:#8c4a3f}
 .card{border:1px solid #e4e0d5;border-radius:.5rem;padding:1rem 1.2rem;
       background:#fffefb;margin-bottom:1.2rem}
 .card h2{font-size:.78rem;text-transform:uppercase;letter-spacing:.09em;
          color:#8a8880;margin:0 0 .6rem;font-weight:400;font-style:normal}
 .live{font-style:italic}
 ul{list-style:none;padding:0;margin:0}
 li{display:flex;justify-content:space-between;gap:1rem;padding:.22rem 0;
    border-bottom:1px solid #f0ede4}
 li:last-child{border-bottom:0}
 .tag{font-size:.8rem;color:#8a8880;font-style:italic}
 .done{color:#4a6741}.failed{color:#8c4a3f}
 a{color:#6b6559}
 .hint{font-size:.85rem;color:#8a8880}
 .chips{display:flex;flex-wrap:wrap;gap:.4rem;margin-top:.6rem}
 .chips button{padding:.3rem .7rem;font-size:.85rem}
</style></head><body><main>
<h1>Simulate a detection</h1>
<p class="sub">Type a bird. It is written into the detector exactly as if the
microphone had heard it, and the frame takes it from there.</p>

<form id="f" autocomplete="off">
  <input id="q" name="species" placeholder="Painted Bunting, or Passerina ciris" required>
  <button id="go" type="submit">Hear it</button>
</form>
<div id="msg"></div>

<div class="card"><h2>Frame</h2><div id="live" class="live">checking...</div></div>
<div class="card"><h2>Artwork the bot has tried</h2><ul id="ledger"><li class="tag">nothing yet</li></ul></div>

<p class="hint"><a href="/">Open the frame</a> &middot; a bird with no picture
starts an image search; one that already has a picture is drawn straight away.</p>

<script>
const $=s=>document.querySelector(s);
async function refresh(){
  try{
    const r=await fetch('/birdart/status',{cache:'no-store'});
    const d=await r.json();
    const a=d.status&&d.status.active;
    const q=(d.status&&d.status.queue||[]).length;
    $('#live').textContent=a
      ? 'Image Search Underway - '+(a.common||a.scientific)+(q?'  (+'+q+' more)':'')
      : 'Idle - showing whatever has been heard recently.';
    const led=d.ledger||{};
    const keys=Object.keys(led).sort((x,y)=>(led[y].last||0)-(led[x].last||0));
    $('#ledger').innerHTML = keys.length ? keys.map(k=>{
      const v=led[k];
      return '<li><span>'+(v.common||k)+'</span><span class="tag '+v.status+'">'+v.status+'</span></li>';
    }).join('') : '<li class="tag">nothing yet</li>';
  }catch(e){ $('#live').textContent='overlay unreachable'; }
}
$('#f').addEventListener('submit',async e=>{
  e.preventDefault();
  const btn=$('#go'); btn.disabled=true;
  $('#msg').className=''; $('#msg').textContent='listening...';
  try{
    const r=await fetch('/birdart/simulate',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({species:$('#q').value})});
    const d=await r.json();
    $('#msg').className = d.ok?'ok':'err';
    $('#msg').textContent = d.message;
    if(d.suggestions&&d.suggestions.length){
      const wrap=document.createElement('div'); wrap.className='chips';
      d.suggestions.forEach(n=>{
        const b=document.createElement('button'); b.type='button'; b.textContent=n;
        b.onclick=()=>{ $('#q').value=n; $('#f').requestSubmit(); };
        wrap.appendChild(b);
      });
      $('#msg').appendChild(wrap);
    }
    if(d.ok) $('#q').value='';
  }catch(err){ $('#msg').className='err'; $('#msg').textContent='request failed'; }
  btn.disabled=false; refresh();
});
refresh(); setInterval(refresh,3000);
</script></main></body></html>
"""

INK = (60, 56, 50)
MUTED = (138, 136, 128)


# The frame's own label faces, in its preference order. They live one directory
# down, which is why a flat glob finds nothing and the banner silently falls
# back to a sans default that looks nothing like the page.
_FACES = (
    "gentiumbookplus/GentiumBookPlus-Italic.ttf",
    "ebgaramond/EBGaramond-Italic.ttf",
    "librebaskerville/LibreBaskerville-Italic.ttf",
)


def _font(size: int, italic: bool = False) -> ImageFont.FreeTypeFont:
    """Reuse the frame's own typefaces so the banner does not look bolted on."""
    d = FUGLERAMME / "assets" / "fonts"
    for rel in _FACES:
        p = d / rel
        if not p.exists():
            continue
        try:
            font = ImageFont.truetype(str(p), size)
            _pin_weight(font)
            return font
        except Exception:
            continue
    return ImageFont.load_default(size)


def _pin_weight(font: ImageFont.FreeTypeFont) -> None:
    """Pillow opens a variable font at each axis minimum, which would draw the
    banner hairline-thin. Same fix the frame's own font loader applies."""
    try:
        axes = font.get_variation_axes()
    except Exception:
        return
    if not axes:
        return
    try:
        font.set_variation_by_axes([a.get("default", a.get("minimum", 400)) for a in axes])
    except Exception:
        pass


def _fetch(path: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(
        urljoin(FRAME + "/", path.lstrip("/")), headers={"User-Agent": USER_AGENT}
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


_style_cache: tuple[float, str] = (0.0, "")


def active_style() -> str:
    """The style the frame is actually rendering, read from its own admin page.

    Not from our environment: the watcher and this service are separate units,
    and a style switched in the admin would leave an env-derived answer stale.
    Getting this wrong makes the simulate page claim a bird already has a
    picture when the style on screen has nothing for it.
    """
    global _style_cache
    age, cached = _style_cache
    if cached and (time.time() - age) < 30:
        return cached
    try:
        html = _fetch("/admin", timeout=10).decode("utf-8", "replace")
        m = re.search(r'name="style"\s+value="([^"]+)"[^>]*checked', html)
        if m:
            _style_cache = (time.time(), m.group(1))
            return m.group(1)
    except Exception:
        pass
    return cached or STYLE


def banner_text() -> tuple[str, str] | None:
    """(headline, subject) while a search is running, else None."""
    st = state.read_status()
    active = st.get("active")
    if not active:
        return None
    queued = len(st.get("queue") or [])
    subject = active.get("common") or active.get("scientific") or ""
    if queued:
        subject += f"   (+{queued} more)"
    return "Image Search Underway", subject


def _draw_banner(png: bytes, headline: str, subject: str) -> bytes:
    im = Image.open(io.BytesIO(png)).convert("RGB")
    W, H = im.size
    band = max(96, H // 9)
    d = ImageDraw.Draw(im, "RGBA")

    # A soft paper band rather than a hard bar: the frame is a picture, not a UI.
    d.rectangle([0, H - band, W, H], fill=(*PAPER, 235))
    d.line([(0, H - band), (W, H - band)], fill=(*MUTED, 140), width=max(1, H // 900))

    f1 = _font(max(22, band // 3), italic=False)
    f2 = _font(max(16, band // 4), italic=True)
    y = H - band + band * 0.20
    for text, font, fill in ((headline, f1, INK), (subject, f2, MUTED)):
        if not text:
            continue
        w = d.textlength(text, font=font)
        d.text(((W - w) / 2, y), text, font=font, fill=fill)
        y += font.size * 1.35

    out = io.BytesIO()
    im.save(out, "PNG")
    return out.getvalue()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):  # journald already timestamps; keep it quiet
        pass

    def _send(self, body: bytes, ctype: str, code: int = 200) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        try:
            if path == "/state":
                self._state()
            elif path == "/collage.png":
                self._collage()
            elif path == "/birdart/status":
                self._send(
                    json.dumps(
                        {"status": state.read_status(), "ledger": state.read_ledger()},
                        indent=1,
                    ).encode(),
                    "application/json",
                )
            elif path in ("/birdart", "/birdart/"):
                self._send(PAGE.encode(), "text/html; charset=utf-8")
            else:
                self._send(b"not found", "text/plain", 404)
        except Exception as e:
            self._send(f"overlay error: {e}".encode(), "text/plain", 502)

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path != "/birdart/simulate":
            self._send(b"not found", "text/plain", 404)
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(n).decode("utf-8", "replace") if n else "{}"
            try:
                typed = (json.loads(raw).get("species") or "").strip()
            except Exception:
                typed = unquote_plus(parse_qs(raw).get("species", [""])[0]).strip()
            self._send(json.dumps(self._simulate(typed)).encode(), "application/json")
        except Exception as e:
            self._send(
                json.dumps({"ok": False, "message": f"error: {e}"}).encode(),
                "application/json",
                500,
            )

    def _simulate(self, typed: str) -> dict:
        """Resolve the name, then write a real detection row for it."""
        if not typed:
            return {"ok": False, "message": "type a bird name first"}
        hit = labels.resolve(typed)
        if not hit:
            near = labels.suggest(typed, 6)
            if near:
                return {
                    "ok": False,
                    "message": f"“{typed}” matches several birds - pick one:",
                    "suggestions": [c for _s, c in near],
                }
            return {"ok": False, "message": f"BirdNET has no species matching “{typed}”."}
        sci, common = hit
        try:
            simulate.detect(sci)
        except Exception as e:
            return {"ok": False, "message": f"could not write the detection: {e}"}
        style = active_style()
        drawable = has_artwork(sci, style)
        tail = (
            f"The {style} style already has a picture, so the frame will draw "
            "it within seconds."
            if drawable
            else f"The {style} style has no picture for it yet - one is "
            "generated within a minute or so, then it appears."
        )
        return {
            "ok": True,
            "scientific": sci,
            "common": common,
            "had_artwork": drawable,
            "message": f"Heard {common} ({sci}). {tail}",
        }

    def _state(self) -> None:
        try:
            upstream = json.loads(_fetch("/state", timeout=15)).get("token", "")
        except Exception:
            upstream = "offline"
        b = banner_text()
        sig = f"{upstream}|{b[1] if b else ''}"
        token = hashlib.sha1(sig.encode()).hexdigest()[:16]
        self._send(json.dumps({"token": token}).encode(), "application/json")

    def _collage(self) -> None:
        png = _fetch("/collage.png", timeout=60)
        b = banner_text()
        if b:
            try:
                png = _draw_banner(png, *b)
            except Exception:
                pass  # a failed banner must never cost the user their picture
        self._send(png, "image/png")


def main() -> int:
    state.ensure_dirs()
    srv = ThreadingHTTPServer(("127.0.0.1", OVERLAY_PORT), Handler)
    print(f"birdart overlay on 127.0.0.1:{OVERLAY_PORT} in front of {FRAME}", flush=True)
    srv.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

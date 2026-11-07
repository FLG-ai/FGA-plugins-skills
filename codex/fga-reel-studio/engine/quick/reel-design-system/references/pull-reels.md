# Pull frames from a reel

The goal is two images per reel, saved in `refs/`: an overview sheet (frames across the whole reel) and a detail sheet (the hook and every kind of insert, larger). Then crop three single frames for the page.

## With a browser tool (Claude in Chrome, or Claude's built-in browser)
1. Open the reel link in a tab the person can see. A hidden or background tab won't decode the video, so bring the browser pane to the front first.
2. Wait about three seconds, then run this in the page. It draws 20 frames from the first video on the page into one sheet, with the time on each:

```js
const v=document.querySelectorAll('video')[0]; v.muted=true; const N=20,cols=5,W=216,H=384;
const c=document.createElement('canvas'); c.width=cols*W; c.height=Math.ceil(N/cols)*H; const g=c.getContext('2d');
const seek=t=>new Promise(r=>{v.onseeked=()=>r(); v.currentTime=t;}); try{await v.play()}catch(e){} v.pause();
for(let i=0;i<N;i++){const t=0.3+i*(v.duration-1)/(N-1); await seek(t); await new Promise(r=>setTimeout(r,150));
 g.drawImage(v,(i%cols)*W,Math.floor(i/cols)*H,W,H); g.fillStyle='rgba(0,0,0,.6)'; g.fillRect((i%cols)*W,Math.floor(i/cols)*H,62,24);
 g.fillStyle='#ff0'; g.font='16px sans-serif'; g.fillText(t.toFixed(1),(i%cols)*W+4,Math.floor(i/cols)*H+17);}
window.__u=c.toDataURL('image/jpeg',0.75);
const b=document.createElement('button'); b.textContent='COPY'; b.style='position:fixed;top:0;left:0;width:120px;height:60px;z-index:999999';
b.onclick=()=>{const t=document.createElement('textarea'); t.value=window.__u; document.body.appendChild(t); t.select(); window.__ok=document.execCommand('copy'); t.remove();};
document.body.appendChild(b); v.duration
```

3. Click the COPY button with a real click (the browser tool's click, not a script), then save the clipboard to a file:

```bash
pbpaste | sed 's/^data:image\/jpeg;base64,//' | base64 -D > "refs/<id> - frames.jpg"
```

4. Look at the sheet. Then make the detail sheet the same way: change the frame times to the hook (0 to 5 s) and to each moment an insert, title or effect appears, at 360x640 each.
5. Check the reel opened is the one linked. Instagram sometimes opens a feed, and the first video is usually the linked one. The caption text near the video names the account, so confirm it matches.

The snippet mutes the video, so for the Sound line on the style card, play the first 5 seconds unmuted with the tool, or ask the person, or write "not heard".

## Without a browser tool
Ask the person to send, for each reel, a screen recording of it playing or four to six screenshots: the first frame, the caption style, and each insert or title. Name the connector that would save this step: Claude in Chrome. Then make the sheets from what they send with ffmpeg.

## Crop three single frames per reel
From the detail sheet, crop the three frames that best show what to borrow, then scale each to 300x533 as `refs/<id>_0.jpg`, `_1.jpg`, `_2.jpg`. Give each a short caption, such as "Press-collage hook", "Proof card on the lap" or "Emoji tick row".

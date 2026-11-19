"""Apply the compact settings and recovery UI to the existing vanilla client."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'app/templates/chat.html';s=p.read_text(encoding='utf-8').replace('আপনার কার্টুনের গল্প লিখুন বা পেস্ট করুন...','আপনার বাংলা কার্টুনের গল্প লিখুন বা পেস্ট করুন...')
a=s.index('<dialog');s=s[:a]+'''<dialog id="settings-dialog" aria-labelledby="settings-title"><div class="drawer-title"><h2 id="settings-title">Settings</h2><button id="settings-close" class="icon-button" aria-label="Close settings">×</button></div>
<form id="settings-form"><label>Video format<select id="setting-format"><option value="shorts">Shorts · 720 × 1280</option><option value="mini">Mini cartoon · 1280 × 720</option><option value="vertical_mini">Mini cartoon · vertical</option></select></label>
<label class="check"><input id="setting-music" type="checkbox" checked> Background music</label>
<details><summary>Four saved voices</summary><p class="quiet">Selected demos are for evaluation. Commercial voice permissions remain unverified. Characters retain their category and conservative variations.</p><div id="four-voice-selectors"></div>
<audio id="voice-audition" controls preload="none" hidden aria-label="Voice audition"></audio><p id="voice-audition-status" role="status"></p>
<details><summary>Replace with licensed recordings</summary><p class="quiet">Use the upload beside each category. Enter permission details before uploading. Replacements retain character mappings and variations.</p><label>Owner, source and permission<textarea id="four-voice-permission" rows="2"></textarea></label><label class="check"><input id="four-voice-consent" type="checkbox"> I have permission to condition these voices and distribute the intended output.</label></details>
<button id="four-voice-save" type="button">Save Four Voices</button><p id="four-voice-message" role="status"></p><a href="/api/default-voices/conditioning-comparisons/archive">Download evaluation audio comparisons</a></details>
<details><summary>Optional story assistance</summary><label>Story understanding<select id="setting-understanding"><option value="rules">Local rules</option><option value="assisted">Configured AI provider</option></select></label><label class="check" id="ai-consent-label" hidden><input type="checkbox" id="setting-ai-consent"> Share this story with my configured provider; its privacy terms and possible costs apply.</label><p class="quiet">Local rules work without an external AI provider.</p></details>
<details><summary>Temporary storage</summary><p class="quiet">Remove leftover render AVI files from stopped jobs. Models, references, caches, history and finished videos are retained.</p><p id="storage-status" role="status"></p><button type="button" id="storage-cleanup">Remove disposable files</button></details>
<p id="settings-message" role="status"></p><button class="primary" type="submit">Save preferences</button></form></dialog>
<script src="/static/chat.js" defer></script><script src="/static/settings.js" defer></script></body></html>
''';p.write_text(s,encoding='utf-8')
p=ROOT/'app/static/chat.js';s=p.read_text(encoding='utf-8')
a=s.index("$('settings-toggle').onclick");b=s.index('guard(async()=>{\'$' ) if False else s.index("guard(async()=>{$('prompt').value",a)
s=s[:a]+s[b:];s=s[:s.index('\nlet fourVoiceData;')]
s=s.replace("links.append(download);card.content.append(video,info,links);", """links.append(download);if(!data.id.startsWith('legacy-'))links.append(button('Regenerate Video',async()=>{const request_id=crypto.randomUUID().replaceAll('-','');const next=await api(`/api/conversations/${data.id}/regenerate`,{prompt:data.prompt,request_id});const fresh=mount(next,true);watch(fresh);localStorage.setItem('toon-chat-selected-v5',next.id);await loadHistory();},'button-link'));card.content.append(video,info,links);""")
needle="  }\n  if(active){\n    const progress=card.content.querySelector"
assert needle in s
s=s.replace(needle,"""    if(['failed','cancelled','needs_input'].includes(data.status))card.content.append(button('Edit story',async()=>{$('prompt').value=data.prompt;localStorage.setItem('toon-chat-draft-v5',data.prompt);$('prompt').focus();controls();},'text-button'));
  }
  if(active){
    const progress=card.content.querySelector""")
s=s.replace("const recent=rows.filter(r=>!r.id.startsWith('legacy-')).slice(0,3).reverse();","const recent=rows.filter(r=>!stopped.has(r.status)||r.id===selected).reverse();")
p.write_text(s,encoding='utf-8')

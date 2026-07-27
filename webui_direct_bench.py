#!/usr/bin/env python3
import json, os, re, sys, time, urllib.request
from pathlib import Path

BASE=os.environ.get('LLAMA_BASE','http://127.0.0.1:8080/v1')
ROOT=Path(__file__).resolve().parent
OUTDIR=ROOT/'results'; OUTDIR.mkdir(exist_ok=True)
ART=OUTDIR/'webui_artifacts'; ART.mkdir(exist_ok=True)
MODELS=[
 'gemma-4-26B-A4B-it-UD-Q4_K_XL',
 'Devstral-Small-2507-UD-Q4_K_XL',
 'Mistral-Small-3.2-24B-Instruct-2506-UD-Q4_K_XL',
 'DeepSeek-Coder-V2-Lite-Instruct-Q4_K_M',
 'qwen2.5-coder-32b-instruct-q4_k_m',
 'Qwen3-Coder-30B-A3B-Instruct-1M-UD-Q4_K_XL',
 'Qwen3.6-27B-MTP-Q4_K_M',
 'Qwen3.6-27B-NEO-CODE-2T-OT-Q5_K_M',
 'Qwen3.6-35B-A3B-MTP-UD-Q2_K_XL',
 'Qwen3.6-35B-A3B-MTP-UD-Q3_K_M',
 'Qwen3.6-35B-A3B-MTP-UD-Q4_K_M',
]
TASKS=[
  {
    'name':'todo_app',
    'prompt':'''Build a polished single-file web app. Return only complete HTML, no markdown.
App: Todo manager. Requirements: responsive layout, CSS styling, add todo, delete todo, mark complete, filters All/Active/Completed, persist todos in localStorage, empty-state message, keyboard friendly form, no external dependencies.''',
    'checks':['html','style','script','localStorage','addEventListener','filter','delete','completed','@media','aria_or_label']
  },
  {
    'name':'signup_validation',
    'prompt':'''Build a polished single-file web app. Return only complete HTML, no markdown.
App: Signup form. Requirements: responsive card layout, name/email/password/confirm fields, live validation with inline error messages, disabled submit until valid, password strength indicator, accessible labels, aria-live or role=alert for errors, success message on submit, no external dependencies.''',
    'checks':['html','style','script','email','password','confirm','disabled','addEventListener','aria_or_role','strength','success','@media']
  },
  {
    'name':'kanban_board',
    'prompt':'''Build a polished single-file web app. Return only complete HTML, no markdown.
App: Mini kanban board with columns Todo/In Progress/Done. Requirements: add cards, move cards between columns with buttons or drag/drop, delete cards, persist state in localStorage, responsive columns, clear visual styling, no external dependencies.''',
    'checks':['html','style','script','localStorage','todo','progress','done','addEventListener','delete','move_or_drag','@media']
  },
]

def api(path,payload=None,timeout=700):
    req=urllib.request.Request(BASE+path) if payload is None else urllib.request.Request(BASE+path,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer llama.cpp'})
    with urllib.request.urlopen(req,timeout=timeout) as r: return json.loads(r.read())

def clean_html(s):
    s=s.strip()
    m=re.search(r'```(?:html)?\s*(.*?)```',s,re.S|re.I)
    if m:
        return m.group(1).strip()
    # Handle truncated/unterminated fenced HTML.
    s=re.sub(r'^```(?:html)?\s*', '', s, flags=re.I).strip()
    return s

def call(model,prompt):
    payload={'model':model,'messages':[{'role':'user','content':prompt}], 'max_tokens':4096, 'temperature':0, 'stream':False, 'chat_template_kwargs':{'enable_thinking':False,'preserve_thinking':True}}
    t=time.time(); j=api('/chat/completions',payload); return time.time()-t,j

def has(h, check):
    l=h.lower()
    if check=='html': return '<html' in l and '</html>' in l
    if check=='style': return '<style' in l and '</style>' in l
    if check=='script': return '<script' in l and '</script>' in l
    if check=='aria_or_label': return ('aria-' in l) or ('<label' in l)
    if check=='aria_or_role': return ('aria-live' in l) or ('role="alert"' in l) or ("role='alert'" in l)
    if check=='move_or_drag': return ('drag' in l) or ('move' in l) or ('next' in l and 'previous' in l) or ('progress' in l and 'done' in l)
    return check.lower() in l

def main():
    stamp=time.strftime('%Y%m%d-%H%M%S'); rows=[]; models=sys.argv[1:] or MODELS
    available={m['id'] for m in api('/models').get('data',[])}
    for model in models:
        if model not in available: continue
        print('\n===',model,'===',flush=True)
        api('/chat/completions',{'model':model,'messages':[{'role':'user','content':'Reply READY'}],'max_tokens':8,'chat_template_kwargs':{'enable_thinking':False,'preserve_thinking':True}})
        for task in TASKS:
            wall,j=call(model,task['prompt'])
            text=j['choices'][0]['message']['content'].strip(); html=clean_html(text)
            results={c:has(html,c) for c in task['checks']}
            score=sum(results.values()); total=len(results)
            tim=j.get('timings',{}); usage=j.get('usage',{})
            safe=model.replace('/','_').replace(':','_')+'__'+task['name']+'.html'
            (ART/safe).write_text(html)
            row={'model':model,'task':task['name'],'score':score,'total':total,'pass':score>=total-1,'wall_s':wall,'gen_tps':tim.get('predicted_per_second'),'prompt_tokens':usage.get('prompt_tokens'),'completion_tokens':usage.get('completion_tokens'),'checks':results,'artifact':str(Path('results')/'webui_artifacts'/safe)}
            rows.append(row)
            missing=[k for k,v in results.items() if not v]
            print(f"{task['name']:<18} {score:2}/{total:<2} {'PASS' if row['pass'] else 'FAIL'} wall={wall:6.1f}s gen={row['gen_tps'] or 0:6.1f} missing={missing}",flush=True)
    out=OUTDIR/f'webui_direct_{stamp}.json'; out.write_text(json.dumps(rows,indent=2))
    md=OUTDIR/f'webui_direct_{stamp}.md'
    lines=['# Web UI direct benchmark','',f'Date: {time.strftime("%Y-%m-%d %H:%M:%S")}','', '| model | total score | pass apps | avg gen tok/s |','|---|---:|---:|---:|']
    for model in models:
        sub=[r for r in rows if r['model']==model]
        if sub:
            lines.append(f"| `{model}` | {sum(r['score'] for r in sub)}/{sum(r['total'] for r in sub)} | {sum(1 for r in sub if r['pass'])}/{len(sub)} | {sum((r.get('gen_tps') or 0) for r in sub)/len(sub):.1f} |")
    md.write_text('\n'.join(lines)+'\n')
    print('\nWrote',out); print('Wrote',md); print('Artifacts in',ART)
if __name__=='__main__': main()

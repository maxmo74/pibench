#!/usr/bin/env python3
import json, os, re, subprocess, sys, time, urllib.request
from pathlib import Path

from pibench_sandbox import SandboxUnavailable, run_python_source

BASE=os.environ.get('LLAMA_BASE','http://127.0.0.1:8080/v1')
OUTDIR=Path(__file__).resolve().parent/'results'; OUTDIR.mkdir(exist_ok=True)
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

def api(path,payload=None,timeout=500):
    if payload is None: req=urllib.request.Request(BASE+path)
    else: req=urllib.request.Request(BASE+path,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer llama.cpp'})
    with urllib.request.urlopen(req,timeout=timeout) as r: return json.loads(r.read())

def clean_code(s):
    m=re.search(r'```(?:python)?\s*(.*?)```',s,re.S|re.I)
    return (m.group(1) if m else s).strip()

def call(model,prompt,max_tokens=900):
    payload={'model':model,'messages':[{'role':'user','content':prompt}], 'max_tokens':max_tokens, 'temperature':0, 'stream':False, 'chat_template_kwargs':{'enable_thinking':False,'preserve_thinking':True}}
    t=time.time(); j=api('/chat/completions',payload); return time.time()-t,j

def py_exec_check(code, tests, timeout=5):
    try:
        r=run_python_source(code+'\n\n'+tests,timeout=timeout)
        return r.returncode==0, (r.stdout+r.stderr)[-1000:]
    except SandboxUnavailable as exc:
        return False, f'sandbox unavailable: {exc}'
    except subprocess.TimeoutExpired:
        return False, f'sandboxed exec timeout after {timeout}s'

TASKS=[
  {
    'name':'interval_merge_edgecases',
    'max_tokens':700,
    'prompt':'''Return only Python code defining merge_intervals(intervals). Input is a list of (start,end) pairs, possibly unsorted, overlapping, touching, negative, or duplicated. Return a list of merged [start,end] lists sorted by start. Treat touching intervals as mergeable, e.g. (1,2),(2,3)->[[1,3]].''',
    'tests':'''\nassert merge_intervals([])==[]\nassert merge_intervals([(1,3),(2,4),(10,11),(4,5)])==[[1,5],[10,11]]\nassert merge_intervals([(5,5),(1,2),(2,2),(-3,-1),(-2,0)])==[[-3,0],[1,2],[5,5]]\nassert merge_intervals([(3,1),(2,4)])==[[1,4]]  # tolerate reversed pair\nprint('ok')\n'''
  },
  {
    'name':'toposort_cycle',
    'max_tokens':900,
    'prompt':'''Return only Python code defining topo_sort(nodes, edges). nodes is an iterable of node names. edges is iterable of (before, after). Return a valid topological ordering list containing all nodes. If there is a cycle, raise ValueError. Include nodes that have no edges.''',
    'tests':'''\ndef valid(order,nodes,edges):\n    assert set(order)==set(nodes) and len(order)==len(nodes)\n    pos={x:i for i,x in enumerate(order)}\n    assert all(pos[a] < pos[b] for a,b in edges)\nvalid(topo_sort(['a','b','c','d'], [('a','c'),('b','c')]), ['a','b','c','d'], [('a','c'),('b','c')])\nvalid(topo_sort(['x'], []), ['x'], [])\ntry:\n    topo_sort(['a','b'], [('a','b'),('b','a')])\n    raise AssertionError('cycle not detected')\nexcept ValueError:\n    pass\nprint('ok')\n'''
  },
  {
    'name':'mini_parser',
    'max_tokens':1100,
    'prompt':'''Return only Python code defining eval_expr(s). It must evaluate strings containing non-negative integers, +, *, parentheses, and whitespace. Multiplication has higher precedence than addition. Do not use eval, exec, ast, or external libraries. Examples: eval_expr('2+3*4') == 14, eval_expr('(2+3)*4') == 20.''',
    'tests':'''\nassert eval_expr('2+3*4')==14\nassert eval_expr('(2+3)*4')==20\nassert eval_expr(' 12 + 3 * (4 + 5) ')==39\nassert eval_expr('7')==7\nassert eval_expr('1+2+3*4*5+6')==69\nprint('ok')\n'''
  },
  {
    'name':'json_nested_exact',
    'max_tokens':500,
    'prompt':'''Return only valid minified JSON, no markdown. Object fields: ok true; items an array of exactly two objects: {"id":1,"tags":["a","b"]} and {"id":2,"tags":[]}; meta object with count 2 and name "pi".''',
    'json':{'ok':True,'items':[{'id':1,'tags':['a','b']},{'id':2,'tags':[]}],'meta':{'count':2,'name':'pi'}}
  },
]

def main():
    stamp=time.strftime('%Y%m%d-%H%M%S'); rows=[]; models=sys.argv[1:] or MODELS
    for model in models:
        avail={m['id'] for m in api('/models').get('data',[])}
        if model not in avail: continue
        print('\n===',model,'===',flush=True)
        call(model,'Reply READY',8)
        for task in TASKS:
            wall,j=call(model,task['prompt'],task['max_tokens'])
            text=j['choices'][0]['message']['content'].strip(); tim=j.get('timings',{}); usage=j.get('usage',{})
            if 'tests' in task:
                ok,note=py_exec_check(clean_code(text),task['tests'])
            else:
                try: ok=(json.loads(text)==task['json']); note='json parsed'
                except Exception as e: ok=False; note=f'json error {e}'
            rows.append({'model':model,'task':task['name'],'ok':ok,'note':note,'wall_s':wall,'gen_tps':tim.get('predicted_per_second'),'prompt_tps':tim.get('prompt_per_second'),'prompt_tokens':usage.get('prompt_tokens'),'completion_tokens':usage.get('completion_tokens'),'text':text})
            print(f"{task['name']:<22} {'PASS' if ok else 'FAIL':<5} wall={wall:6.2f}s gen={tim.get('predicted_per_second') or 0:7.1f} {note}",flush=True)
    out=OUTDIR/f'hard_direct_{stamp}.json'; out.write_text(json.dumps(rows,indent=2))
    md=OUTDIR/f'hard_direct_{stamp}.md'
    lines=['# Hard direct benchmark','',f'Date: {time.strftime("%Y-%m-%d %H:%M:%S")}','', '| model | pass | avg gen tok/s |','|---|---:|---:|']
    for m in models:
        sub=[r for r in rows if r['model']==m];
        if sub: lines.append(f"| `{m}` | {sum(r['ok'] for r in sub)}/{len(sub)} | {sum((r.get('gen_tps') or 0) for r in sub)/len(sub):.1f} |")
    md.write_text('\n'.join(lines)+'\n')
    print('\nWrote',out); print('Wrote',md)
if __name__=='__main__': main()

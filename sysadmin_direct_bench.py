#!/usr/bin/env python3
import json, os, re, subprocess, sys, tempfile, textwrap, time, urllib.request
from pathlib import Path

from pibench_sandbox import SandboxUnavailable, run_python_source

BASE=os.environ.get('LLAMA_BASE','http://127.0.0.1:8080/v1')
ROOT=Path(__file__).resolve().parent
OUTDIR=ROOT/'results'; OUTDIR.mkdir(exist_ok=True)
ART=OUTDIR/'sysadmin_artifacts'; ART.mkdir(exist_ok=True)
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

def api(path,payload=None,timeout=600):
    req=urllib.request.Request(BASE+path) if payload is None else urllib.request.Request(BASE+path,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer llama.cpp'})
    with urllib.request.urlopen(req,timeout=timeout) as r: return json.loads(r.read())

def clean(s, lang=None):
    s=s.strip()
    m=re.search(r'```(?:\w+)?\s*(.*?)```',s,re.S)
    if m: return m.group(1).strip()
    return re.sub(r'^```(?:\w+)?\s*','',s).strip()

def call(model,prompt,max_tokens=1400):
    payload={'model':model,'messages':[{'role':'user','content':prompt}], 'max_tokens':max_tokens, 'temperature':0, 'stream':False, 'chat_template_kwargs':{'enable_thinking':False,'preserve_thinking':True}}
    t=time.time(); j=api('/chat/completions',payload); return time.time()-t,j

def bash_check(script, required):
    with tempfile.NamedTemporaryFile('w',suffix='.sh',delete=False) as f:
        f.write(script); name=f.name
    try:
        r=subprocess.run(['bash','-n',name],capture_output=True,text=True,timeout=5)
        syntax=(r.returncode==0)
    finally:
        try: os.unlink(name)
        except OSError: pass
    l=script.lower()
    checks={'bash_syntax':syntax}
    for key, needles in required.items():
        checks[key]=any(n.lower() in l for n in needles)
    return checks

def py_func_check(code, tests):
    try:
        r=run_python_source(code+'\n\n'+tests,timeout=8)
        return {'python_exec': r.returncode==0, 'output': (r.stdout+r.stderr)[-1200:]}
    except SandboxUnavailable as exc:
        return {'python_exec': False, 'output': f'sandbox unavailable: {exc}'}
    except subprocess.TimeoutExpired:
        return {'python_exec': False, 'output': 'sandboxed exec timeout after 8s'}

def py_cli_jsonl_check(code):
    inp='{"path":"/a","latency_ms":50}\nnot-json\n{"path":"/b","latency_ms":200}\n{"path":"/c","latency_ms":"slow"}\n'
    try:
        r=run_python_source(code,args=['--min-latency','100'],input_text=inp,timeout=8)
    except SandboxUnavailable as exc:
        return {'python_cli_exec': False, 'output': f'sandbox unavailable: {exc}'}
    except subprocess.TimeoutExpired:
        return {'python_cli_exec': False, 'output': 'sandboxed exec timeout after 8s'}
    ok=False
    try:
        outs=[json.loads(x) for x in r.stdout.splitlines() if x.strip()]
        ok=(r.returncode==0 and outs==[{"path":"/b","latency_ms":200}] and ('warning' in r.stderr.lower() or 'invalid' in r.stderr.lower()))
    except Exception:
        ok=False
    return {'python_cli_exec': ok, 'output': (r.stdout+r.stderr)[-1200:]}

def static_check(text, checks):
    l=text.lower(); out={}
    for key, needles in checks.items(): out[key]=any(n.lower() in l for n in needles)
    return out

TASKS=[
    {
      'name':'bash_backup_script',
      'kind':'bash',
      'max_tokens':1400,
      'prompt':'''Return only a production-quality Bash script, no markdown. Task: backup a source directory to a destination directory using rsync. Requirements: set strict mode; usage/help; accept SOURCE DEST arguments; validate source exists; create destination; log start/end; support DRY_RUN=1; use rsync -aHAX --delete; trap errors; quote variables safely.''',
      'required':{
        'strict_mode':['set -euo pipefail'], 'usage':['usage'], 'rsync':['rsync'], 'dry_run':['DRY_RUN'], 'trap':['trap'], 'mkdir':['mkdir -p'], 'source_check':['-d "$SOURCE"','-d "${SOURCE}"','[[ -d'], 'delete':['--delete'], 'archive_flags':['-aHAX','-aHAX']
      }
    },
    {
      'name':'python_auth_log_parser',
      'kind':'python',
      'max_tokens':1300,
      'prompt':'''Return only Python code defining function top_failed_ssh_ips(lines, limit=3). It receives iterable syslog/auth.log lines and returns a list of (ip, count) sorted by count descending then ip ascending for lines containing failed ssh password attempts. Handle IPv4 addresses. Ignore invalid lines. No external dependencies.''',
      'tests':'''\nlines=[\n"Jan 1 sshd[1]: Failed password for root from 10.0.0.2 port 22 ssh2",\n"Jan 1 sshd[2]: Failed password for invalid user admin from 10.0.0.1 port 22 ssh2",\n"Jan 1 sshd[3]: Accepted password for root from 10.0.0.9 port 22 ssh2",\n"Jan 1 sshd[4]: Failed password for root from 10.0.0.2 port 22 ssh2",\n"noise",\n"Jan 1 sshd[5]: Failed password for root from 10.0.0.10 port 22 ssh2",\n]\nassert top_failed_ssh_ips(lines)==[("10.0.0.2",2),("10.0.0.1",1),("10.0.0.10",1)]\nassert top_failed_ssh_ips(lines,limit=1)==[("10.0.0.2",2)]\nassert top_failed_ssh_ips([])==[]\nprint('ok')\n'''
    },
    {
      'name':'systemd_service_timer',
      'kind':'static',
      'max_tokens':1400,
      'prompt':'''Return only two systemd unit files separated by a line containing exactly ---TIMER---. First: my-backup.service running /usr/local/bin/my-backup.sh as user backup, with safe hardening options. Second: my-backup.timer running daily at 03:30 with Persistent=true. Include install sections.''',
      'checks':{
        'service_section':['[Service]'], 'timer_separator':['---TIMER---'], 'timer_section':['[Timer]'], 'on_calendar':['OnCalendar=*-*-* 03:30','OnCalendar=daily','03:30'], 'persistent':['Persistent=true'], 'user_backup':['User=backup'], 'exec':['ExecStart=/usr/local/bin/my-backup.sh'], 'hardening':['NoNewPrivileges=true','ProtectSystem=','PrivateTmp=true'], 'install':['[Install]']
      }
    },
    {
      'name':'nginx_reverse_proxy',
      'kind':'static',
      'max_tokens':1500,
      'prompt':'''Return only an nginx server block, no markdown. Requirements: listen 443 ssl http2 for example.com; redirect HTTP to HTTPS; reverse proxy / to http://127.0.0.1:3000; set Host/X-Real-IP/X-Forwarded-For/X-Forwarded-Proto headers; websocket Upgrade support; gzip static assets; cache-control for /assets/; deny hidden files; include reasonable TLS directives.''',
      'checks':{
        'listen_443':['listen 443 ssl http2','listen 443 ssl'], 'listen_80_redirect':['listen 80','return 301 https://$host$request_uri','return 301 https://'], 'server_name':['server_name example.com'], 'proxy_pass':['proxy_pass http://127.0.0.1:3000'], 'headers':['x-real-ip','x-forwarded-for','x-forwarded-proto'], 'websocket':['upgrade','connection'], 'gzip':['gzip on'], 'assets_cache':['/assets/','cache-control','expires'], 'deny_hidden':['deny all','location ~ /\\.','location ~ /\\.'], 'tls':['ssl_protocols','ssl_ciphers']
      }
    },
    {
      'name':'cli_jsonl_filter',
      'kind':'python_cli',
      'max_tokens':1600,
      'prompt':'''Return only Python code for a complete CLI program. It reads JSON Lines from stdin and writes only records whose numeric field latency_ms is greater than a --min-latency argument. Use argparse. Invalid JSON lines must be skipped with a warning to stderr. Output JSON lines compactly. No external dependencies.''',
      'tests':''
    }
]

def main():
    stamp=time.strftime('%Y%m%d-%H%M%S'); rows=[]; models=sys.argv[1:] or MODELS
    avail={m['id'] for m in api('/models').get('data',[])}
    for model in models:
        if model not in avail: continue
        print('\n===',model,'===',flush=True)
        call(model,'Reply READY',8)
        for task in TASKS:
            wall,j=call(model,task['prompt'],task['max_tokens'])
            txt=j['choices'][0]['message']['content'].strip(); body=clean(txt)
            if task['kind']=='bash':
                res=bash_check(body,task['required']); detail=''
            elif task['kind']=='python':
                r=py_func_check(body,task['tests']); res={'python_exec':r['python_exec']}; detail=r['output']
            elif task['kind']=='python_cli':
                r=py_cli_jsonl_check(body); res={'python_cli_exec':r['python_cli_exec']}; detail=r['output']
            else:
                res=static_check(body,task['checks']); detail=''
            score=sum(1 for v in res.values() if v is True); total=len(res); ok=(score==total)
            tim=j.get('timings',{}); usage=j.get('usage',{})
            safe=model.replace('/','_').replace(':','_')+'__'+task['name']+'.txt'
            (ART/safe).write_text(body)
            rows.append({'model':model,'task':task['name'],'ok':ok,'score':score,'total':total,'checks':res,'detail':detail,'wall_s':wall,'gen_tps':tim.get('predicted_per_second'),'prompt_tokens':usage.get('prompt_tokens'),'completion_tokens':usage.get('completion_tokens'),'artifact':str(Path('results')/'sysadmin_artifacts'/safe)})
            missing=[k for k,v in res.items() if not v]
            print(f"{task['name']:<24} {score:2}/{total:<2} {'PASS' if ok else 'FAIL'} wall={wall:6.1f}s gen={tim.get('predicted_per_second') or 0:6.1f} missing={missing}",flush=True)
    out=OUTDIR/f'sysadmin_direct_{stamp}.json'; out.write_text(json.dumps(rows,indent=2))
    md=OUTDIR/f'sysadmin_direct_{stamp}.md'
    lines=['# Sysadmin/tooling direct benchmark','',f'Date: {time.strftime("%Y-%m-%d %H:%M:%S")}','', '| model | total score | pass tasks | avg gen tok/s |','|---|---:|---:|---:|']
    for model in models:
        sub=[r for r in rows if r['model']==model]
        if sub: lines.append(f"| `{model}` | {sum(r['score'] for r in sub)}/{sum(r['total'] for r in sub)} | {sum(1 for r in sub if r['ok'])}/{len(sub)} | {sum((r.get('gen_tps') or 0) for r in sub)/len(sub):.1f} |")
    md.write_text('\n'.join(lines)+'\n')
    print('\nWrote',out); print('Wrote',md); print('Artifacts in',ART)
if __name__=='__main__': main()

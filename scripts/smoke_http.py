#!/usr/bin/env python3
"""Run an actual HTTP account/friend/vote flow against a temporary Gunicorn server."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parents[1]

def run():
    with tempfile.TemporaryDirectory(prefix='gas-smoke-') as temporary:
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0))
            port=sock.getsockname()[1]
        env=dict(os.environ, GAS_DATABASE=str(Path(temporary)/'gas.sqlite3'))
        process=subprocess.Popen([sys.executable,'-m','gunicorn','--chdir',str(ROOT/'server'),'--bind',f'127.0.0.1:{port}','--preload','--workers','2','--threads','2','wsgi:application'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        def call(path, method='GET', body=None, token=''):
            request=urllib.request.Request(f'http://127.0.0.1:{port}{path}', data=json.dumps(body).encode() if body is not None else None, method=method, headers={'Content-Type':'application/json','Authorization':'Bearer '+token})
            with urllib.request.urlopen(request,timeout=5) as response:
                return json.load(response)
        try:
            for _ in range(50):
                if process.poll() is not None:
                    raise RuntimeError(process.stderr.read().decode())
                try:
                    call('/health');break
                except urllib.error.URLError:time.sleep(0.1)
            else:raise RuntimeError('Server did not become ready')
            accounts=[]
            for username in ['student_a','student_b']:
                result=call('/v1/register','POST',dict(username=username,password='smoke test password',name=username,school='테스트 학교',age=16))
                token=result['token']
                accounts.append((token,call('/v1/me',token=token)['id']))
            (a,aid),(b,bid)=accounts
            call('/v1/friends','POST',{'userId':bid},a)
            call('/v1/friends','POST',{'userId':aid},b)
            polls=call('/v1/polls',token=a)['polls']
            result=call('/v1/votes','POST',{'pollId':polls[0]['id'],'selectedUserId':bid},a)
            assert result['coinsEarned']==20
            flames=call('/v1/inbox',token=b)['flames']
            assert len(flames)==1 and 'senderId' not in flames[0]
            assert call('/v1/me',token=a)['coins']==20
            call('/v1/me','DELETE',{'password':'smoke test password'},a)
            assert call('/v1/friends',token=b)['friends']==[]
            assert call('/v1/inbox',token=b)['flames']==[]
            print('HTTP smoke PASS: Gunicorn, two accounts, friendship, vote, reward, anonymous inbox, account deletion')
        finally:
            process.terminate()
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill();process.wait()
            logs = process.stderr.read().decode()
            if process.returncode != 0:
                print(logs, file=sys.stderr)
            process.stderr.close()

if __name__=='__main__':run()

"""Run isolated QA and save machine-readable evidence without external traffic."""
import argparse
import importlib.metadata
import io
import json
import os
from pathlib import Path
import platform
import socket
import sys
import tempfile
import time
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'))
parser=argparse.ArgumentParser();parser.add_argument('--label',default='final');args=parser.parse_args()
# Set before dotenv or database imports; never use the user's configured endpoints.
for key in ['TASKFLOW_API_URL','GEMINI_API_KEY','SMTP_HOST','TASKFLOW_PUBLIC_URL','STRIPE_SECRET_KEY','STRIPE_WEBHOOK_SECRET','PAYOS_CLIENT_ID','PAYOS_API_KEY','PAYOS_CHECKSUM_KEY','GOOGLE_CLIENT_ID','GOOGLE_CLIENT_SECRET','GOOGLE_REDIRECT_URI','GOOGLE_LOGIN_CLIENT_ID','GOOGLE_LOGIN_CLIENT_SECRET','GOOGLE_LOGIN_REDIRECT_URI','FACEBOOK_APP_ID','FACEBOOK_APP_SECRET','FACEBOOK_LOGIN_REDIRECT_URI','TASKFLOW_TOKEN_ENCRYPTION_KEY']:
    os.environ[key]=''
workspace=tempfile.TemporaryDirectory(prefix='doumar-qa-run-')
os.environ['DATABASE_URL']='sqlite:///'+workspace.name+'/desktop.db'
os.environ['TASKFLOW_SERVER_DATABASE_URL']='sqlite:///'+workspace.name+'/server.db'
os.environ['TASKFLOW_TRUSTED_PROXIES']=''
blocked=[]
real_connect=socket.socket.connect

def safe_connect(sock,address):
    if sock.family in (socket.AF_INET,socket.AF_INET6) and address[0] not in ('127.0.0.1','::1','localhost'):
        blocked.append(str(address[0]));raise OSError('QA blocks external networking')
    return real_connect(sock,address)
socket.socket.connect=safe_connect

class Result(unittest.TextTestResult):
    def startTest(self,test):
        self.started=time.perf_counter();super().startTest(test)
    def record(self,test,status,detail=''):
        records.append({'id':test.id(),'group':test.__class__.__name__,'description':test.shortDescription() or test.id(),
                        'status':status,'seconds':round(time.perf_counter()-self.started,4),'detail':detail})
    def addSuccess(self,test):super().addSuccess(test);self.record(test,'PASS')
    def addFailure(self,test,err):super().addFailure(test,err);self.record(test,'FAIL',self._exc_info_to_string(err,test))
    def addError(self,test,err):super().addError(test,err);self.record(test,'ERROR',self._exc_info_to_string(err,test))
    def addSkip(self,test,reason):super().addSkip(test,reason);self.record(test,'SKIP',reason)

records=[];start=time.perf_counter()
folder=ROOT/'reports'/'qa';folder.mkdir(parents=True,exist_ok=True)
log=io.StringIO()
suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'))
result=unittest.TextTestRunner(stream=log,verbosity=2,resultclass=Result).run(suite)
report={'label':args.label,'generated_at':datetime.now(ZoneInfo('Asia/Bangkok')).isoformat(),'python':platform.python_version(),'platform':platform.platform(),'flet':importlib.metadata.version('flet'),
        'total':result.testsRun,'passed':sum(r['status']=='PASS' for r in records),'failed':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),
        'duration_seconds':round(time.perf_counter()-start,3),'external_network_blocked':blocked,'tests':records}
(folder/(args.label+'.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
(folder/(args.label+'.log')).write_text(log.getvalue(),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='tests'},ensure_ascii=False,indent=2))
for r in records:
    if r['status']!='PASS':print(r['status'],r['id'],'\n',r['detail'][-1500:])
sys.exit(0 if result.wasSuccessful() else 1)

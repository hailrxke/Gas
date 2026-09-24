import io
import json
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from app import Application

class APITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / 'test.sqlite3'
        self.app = Application(self.db)
        self.addCleanup(self.temp.cleanup)

    def call(self, path, method='GET', body=None, token='', ip='127.0.0.1'):
        raw = json.dumps(body).encode() if body is not None else b''
        route, _, query = path.partition('?')
        env = {'REQUEST_METHOD':method, 'PATH_INFO':route, 'QUERY_STRING':query,
               'CONTENT_LENGTH':str(len(raw)), 'CONTENT_TYPE':'application/json',
               'HTTP_AUTHORIZATION':'Bearer ' + token, 'REMOTE_ADDR':ip,
               'wsgi.input':io.BytesIO(raw)}
        statuses = []
        data = b''.join(self.app(env, lambda s,h: statuses.append(int(s.split()[0]))))
        return statuses[0], json.loads(data)

    def register(self, username, school='서울 학교'):
        status, response = self.call('/v1/register','POST',dict(username=username,password='correct horse battery',name=username,school=school,age=16))
        self.assertEqual(status,200,response)
        token = response['token']
        status, user = self.call('/v1/me',token=token)
        self.assertEqual(status,200)
        return token,user['id']

    def connect(self, a, aid, b, bid):
        self.assertEqual(self.call('/v1/friends','POST',{'userId':bid},a)[0],200)
        self.assertEqual(self.call('/v1/friends','POST',{'userId':aid},b)[0],200)

    def test_register_login_logout_and_hashing(self):
        token,uid = self.register('alice')
        with sqlite3.connect(self.db) as db:
            self.assertNotIn('correct horse battery',db.execute('SELECT password FROM users').fetchone()[0])
            self.assertNotEqual(token,db.execute('SELECT token FROM sessions').fetchone()[0])
        status,result = self.call('/v1/login','POST',{'username':'alice','password':'wrong password'})
        self.assertEqual(status,401)
        status,result = self.call('/v1/login','POST',{'username':'ALICE','password':'correct horse battery'})
        self.assertEqual(status,200)
        self.assertEqual(self.call('/v1/logout','POST',{},result['token'])[0],200)
        self.assertEqual(self.call('/v1/me',token=result['token'])[0],401)
        self.assertEqual(self.call('/v1/me',token=token)[0],200)

    def test_validation_and_duplicate_username(self):
        self.register('alice')
        base = dict(username='alice',password='correct horse battery',name='Alice',school='School',age=16)
        self.assertEqual(self.call('/v1/register','POST',base)[0],409)
        for changes in ({'age':13},{'age':True},{'age':20},{'username':'x'},{'username':'bad name'},{'password':'short'},{'school':''},{'name':''}):
            self.assertEqual(self.call('/v1/register','POST',dict(base,**changes))[0],400)

    def test_friend_consent_school_and_search(self):
        a,aid=self.register('alice'); b,bid=self.register('bobby'); c,cid=self.register('carol','Different school')
        self.assertEqual(self.call('/v1/people?q=bob',token=a)[1]['people'],[])
        self.assertEqual(self.call('/v1/people?q=bobby',token=a)[1]['people'][0]['id'],bid)
        self.assertEqual(self.call('/v1/people?q=carol',token=a)[1]['people'],[])
        self.assertEqual(self.call('/v1/friends','POST',{'userId':cid},a)[0],404)
        self.call('/v1/friends','POST',{'userId':bid},a)
        self.assertEqual(self.call('/v1/friends',token=a)[1]['friends'],[])
        self.assertEqual(self.call('/v1/polls',token=a)[1]['polls'],[])
        self.assertEqual(self.call('/v1/friends',token=b)[1]['requests'][0]['id'],aid)
        self.call('/v1/friends','POST',{'userId':aid},b)
        self.assertEqual(len(self.call('/v1/polls',token=a)[1]['polls']),12)
        self.assertEqual(len(self.call('/v1/friends',token=b)[1]['friends']),1)

    def test_vote_atomic_reward_anonymity_and_daily_reset(self):
        a,aid=self.register('alice'); b,bid=self.register('bobby')
        self.connect(a,aid,b,bid)
        vote={'pollId':'1','selectedUserId':bid}
        with ThreadPoolExecutor(max_workers=4) as executor:
            results=list(executor.map(lambda _:self.call('/v1/votes','POST',vote,a)[0],range(4)))
        self.assertEqual(sorted(results),[200,409,409,409])
        self.assertEqual(self.call('/v1/me',token=a)[1]['coins'],20)
        inbox=self.call('/v1/inbox',token=b)[1]['flames']
        self.assertEqual(len(inbox),1)
        self.assertEqual(set(inbox[0]),{'id','pollQuestion','day','isRead'})
        self.assertNotIn(aid,json.dumps(inbox))
        self.assertEqual(self.call('/v1/polls',token=a)[1]['answered'],1)
        with patch('app.day_key',return_value='2099-01-01'):
            self.assertEqual(self.call('/v1/votes','POST',vote,a)[0],200)
        self.assertEqual(self.call('/v1/me',token=a)[1]['coins'],40)

    def test_vote_requires_offered_friend_and_valid_poll(self):
        a,aid=self.register('alice'); b,bid=self.register('bobby'); c,cid=self.register('carol')
        self.connect(a,aid,b,bid)
        for target in (aid,cid,'missing'):
            self.assertEqual(self.call('/v1/votes','POST',{'pollId':'1','selectedUserId':target},a)[0],403)
        self.assertEqual(self.call('/v1/votes','POST',{'pollId':'999','selectedUserId':bid},a)[0],404)
        self.assertEqual(self.call('/v1/me',token=a)[1]['coins'],0)
        self.assertEqual(self.call('/v1/inbox',token=b)[1]['flames'],[])

    def test_inbox_ownership_report_and_block_privacy(self):
        a,aid=self.register('alice'); b,bid=self.register('bobby'); c,cid=self.register('carol')
        self.connect(a,aid,b,bid)
        self.call('/v1/votes','POST',{'pollId':'1','selectedUserId':bid},a)
        flame=self.call('/v1/inbox',token=b)[1]['flames'][0]
        self.assertEqual(self.call('/v1/inbox/read','POST',{'id':flame['id']},c)[0],404)
        self.assertEqual(self.call('/v1/reports','POST',{'id':flame['id'],'reason':'Unwanted'},c)[0],404)
        self.assertEqual(self.call('/v1/inbox/read','POST',{'id':flame['id']},b)[0],200)
        self.assertTrue(self.call('/v1/inbox',token=b)[1]['flames'][0]['isRead'])
        self.assertEqual(self.call('/v1/reports','POST',{'id':flame['id'],'reason':'Unwanted'},b)[0],200)
        self.assertEqual(self.call('/v1/inbox',token=b)[1]['flames'],[])
        self.assertEqual(self.call('/v1/blocks',token=b)[1]['people'],[])
        self.assertEqual(self.call('/v1/people?q=alice',token=b)[1]['people'],[])
        self.assertEqual(self.call('/v1/friends','POST',{'userId':bid},a)[0],404)
        with sqlite3.connect(self.db) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM reports').fetchone()[0],1)

    def test_manual_block_unblock_requires_new_consent(self):
        a,aid=self.register('alice'); b,bid=self.register('bobby')
        self.connect(a,aid,b,bid)
        self.call('/v1/blocks','POST',{'userId':bid},a)
        self.assertEqual(self.call('/v1/blocks',token=a)[1]['people'][0]['id'],bid)
        self.assertEqual(self.call('/v1/friends',token=b)[1]['friends'],[])
        self.assertEqual(self.call('/v1/people?q=alice',token=b)[1]['people'],[])
        self.call('/v1/blocks','DELETE',{'userId':bid},a)
        self.assertEqual(self.call('/v1/blocks',token=a)[1]['people'],[])
        self.assertEqual(self.call('/v1/friends',token=a)[1]['friends'],[])

    def test_delete_requires_password_and_cascades(self):
        a,aid=self.register('alice'); b,bid=self.register('bobby')
        self.connect(a,aid,b,bid)
        self.call('/v1/votes','POST',{'pollId':'1','selectedUserId':bid},a)
        self.assertEqual(self.call('/v1/me','DELETE',{'password':'wrong password'},a)[0],403)
        self.assertEqual(self.call('/v1/me','DELETE',{'password':'correct horse battery'},a)[0],200)
        self.assertEqual(self.call('/v1/me',token=a)[0],401)
        self.assertEqual(self.call('/v1/friends',token=b)[1]['friends'],[])
        self.assertEqual(self.call('/v1/inbox',token=b)[1]['flames'],[])
        with sqlite3.connect(self.db) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM votes').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT count(*) FROM sessions WHERE user_id=?',(aid,)).fetchone()[0],0)

    def test_restart_persistence_and_expired_sessions(self):
        a,aid=self.register('alice')
        self.app=Application(self.db)
        self.assertEqual(self.call('/v1/me',token=a)[1]['id'],aid)
        with sqlite3.connect(self.db) as db:db.execute('UPDATE sessions SET expires=0')
        self.assertEqual(self.call('/v1/me',token=a)[0],401)

    def test_auth_rate_limit_commits_failed_attempts(self):
        for _ in range(30):
            self.assertEqual(self.call('/v1/login','POST',{'username':'missing','password':'long password'})[0],401)
        self.assertEqual(self.call('/v1/login','POST',{'username':'missing','password':'long password'})[0],429)

    def test_password_whitespace_is_significant(self):
        password = '  exact password  '
        status,response = self.call('/v1/register','POST',dict(username='spaces',password=password,name='Name',school='School',age=16))
        self.assertEqual(status,200)
        self.assertEqual(self.call('/v1/login','POST',dict(username='spaces',password=password.strip()))[0],401)
        self.assertEqual(self.call('/v1/login','POST',dict(username='spaces',password=password))[0],200)

    def test_request_size_json_and_content_type(self):
        cases=[('16385',b'', 'application/json',413),('-1',b'', 'application/json',413),
               ('1',b'{','application/json',400),('2',b'{}','text/plain',415),
               ('invalid',b'', 'application/json',400)]
        for length,body,content_type,expected in cases:
            statuses=[]
            env={'REQUEST_METHOD':'POST','PATH_INFO':'/v1/register','CONTENT_LENGTH':length,
                 'CONTENT_TYPE':content_type,'wsgi.input':io.BytesIO(body)}
            response=json.loads(b''.join(self.app(env,lambda s,h:statuses.append(int(s.split()[0])))))
            self.assertEqual(statuses[0],expected,response)

    def test_non_object_json_and_unauthenticated_requests(self):
        self.assertEqual(self.call('/v1/register','POST',[])[0],400)
        for path in ['/v1/me','/v1/friends','/v1/polls','/v1/inbox']:
            self.assertEqual(self.call(path)[0],401)
        self.assertEqual(self.call('/health')[1],{'status':'ok'})

if __name__ == '__main__':
    unittest.main()

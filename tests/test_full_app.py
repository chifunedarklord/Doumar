"""Broad isolated regression matrix: no external providers, no customer data."""
import asyncio
import base64
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import date, datetime, timedelta, timezone
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import random
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

# Reuse the existing suite's isolated database before importing ORM services.
import test_personal_planning as isolated
from core.database import Storage
from core.models import User, Task, Project
from core.orm import SessionLocal, TaskModel, WorkSessionModel
from core.services import AuthService, TaskService, ProjectService, ChatService, AnalyticsService
from core.workspace import Workspace, validate_task
from core.task_focus import TaskFocus
from core.task_rules import next_occurrence
from core.snapshot import validate_snapshot
from core.sync import fingerprint
from core.sync_merge import merge_snapshots
from core.planning import propose_day
from server.app import Application, APIError, empty_workspace
from server.store import digest


def case(cls, name, description, fn):
    fn.__name__ = 'test_' + name
    fn.__doc__ = description
    setattr(cls, fn.__name__, fn)


class LocalDataTests(unittest.TestCase):
    """Công việc, dữ liệu, lịch, nhắc việc, đồng bộ cục bộ."""
    def setUp(self):
        self.uid = str(uuid.uuid4())
        self.user = User(id=self.uid, username=self.uid, email=self.uid+'@qa.invalid', password_hash='test')
        Storage.save_user(self.user)
        self.day = (date.today()+timedelta(days=3)).isoformat()

    def task(self, **kwargs):
        task = Task(id=str(uuid.uuid4()), user_id=self.uid, title='Công việc tiếng Việt', **kwargs)
        Storage.save_task(task)
        return task

    def test_unicode_and_large_valid_text(self):
        """Lưu nguyên tiếng Việt, emoji, dấu nháy và tên dài đúng giới hạn."""
        for title in ['Đồ án tiếng Việt 🐈', "O'Reilly; DROP TABLE tasks;", '<script>alert(1)</script>', 'a'*500]:
            task=self.task(); task.title=title; task.description='Nội dung\n'*100
            Storage.save_task(task)
            self.assertEqual(next(t for t in Storage.get_tasks(self.uid) if t.id==task.id).title,title)

    def test_optimistic_revision_prevents_overwrite(self):
        """Hai bản sửa cũ/mới: từ chối bản cũ, giữ bản đã lưu."""
        task=self.task(); old=deepcopy(task)
        task.title='Bản mới'; Storage.save_task(task,expected_revision=old.updated_at)
        old.title='Bản cũ'
        with self.assertRaises(ValueError): Storage.save_task(old,expected_revision=old.updated_at)
        self.assertEqual(TaskFocus.task(self.uid,task.id).title,'Bản mới')

    def test_foreign_upsert_rejected(self):
        """Không ghi đè công việc của tài khoản khác bằng cùng ID."""
        task=self.task(); task.user_id='other'
        with self.assertRaises(ValueError): Storage.save_task(task)
        self.assertEqual(len(Storage.get_tasks(self.uid)),1)

    def test_trash_restore_preserves_children_and_removes_calendar(self):
        """Xóa rồi khôi phục giữ nội dung/việc nhỏ; lịch bị gỡ khi xóa."""
        task=self.task(subtasks=[{'title':'Bước 1'}])
        Workspace.save_blocks(self.uid,[{'task_id':task.id,'title':task.title,'start_at':self.day+'T09:00','end_at':self.day+'T10:00'}])
        Workspace.trash_task(self.uid,task.id)
        self.assertEqual(Storage.get_tasks(self.uid),[]);self.assertEqual(Workspace.blocks(self.uid),[])
        self.assertEqual(len(Workspace.trash(self.uid)),1)
        Workspace.restore_task(self.uid,task.id)
        self.assertEqual(Storage.get_tasks(self.uid)[0].subtasks,[{'title':'Bước 1'}])
        with self.assertRaises(ValueError): Workspace.restore_task(self.uid,task.id)

    def test_foreign_trash_and_restore_rejected(self):
        """Không xóa hoặc phục hồi công việc của tài khoản khác."""
        task=self.task()
        with self.assertRaises(ValueError):Workspace.trash_task('other',task.id)
        Workspace.trash_task(self.uid,task.id)
        with self.assertRaises(ValueError):Workspace.restore_task('other',task.id)

    def test_backup_restore_roundtrip_and_repeat(self):
        """Sao lưu/khôi phục giữ việc nhỏ, lịch và không nhân đôi khi nhập lại."""
        task=self.task(subtasks=[{'id':'child-1','title':'Bước 1','status':'done'},{'id':'child-2','title':'Bước 2'}])
        Workspace.save_blocks(self.uid,[{'task_id':task.id,'title':task.title,'start_at':self.day+'T09:00','end_at':self.day+'T10:00'}])
        backup=Workspace.backup(self.uid)
        target=str(uuid.uuid4());Storage.save_user(replace(self.user,id=target,username=target,email=target+'@qa.invalid'))
        Workspace.restore(target,backup);Workspace.restore(target,backup)
        restored=Storage.get_tasks(target)
        self.assertEqual(len(restored),1);self.assertEqual(restored[0].subtasks,task.subtasks)
        self.assertEqual(Workspace.blocks(target)[0]['task_id'],restored[0].id)
        self.assertEqual(len(Storage.get_tasks(self.uid)),1)

    def test_restore_rolls_back_on_bad_block(self):
        """Tệp sao lưu có lịch lỗi không được nhập dở dang."""
        self.task();backup=Workspace.backup(self.uid)
        target=str(uuid.uuid4());Storage.save_user(replace(self.user,id=target,username=target,email=target+'@qa.invalid'))
        backup['blocks']=[{'id':'bad','title':'bad','start_at':self.day+'T12:00','end_at':self.day+'T11:00','task_id':None}]
        with self.assertRaises(ValueError):Workspace.restore(target,backup)
        self.assertEqual(Storage.get_tasks(target),[])

    def test_backup_does_not_restore_privileges(self):
        """Tệp nhập không được tự cấp quyền nội bộ hoặc quyền gói."""
        backup=Workspace.backup(self.uid)
        backup['memories']=[{'memory_type':'system','key':'admin','value':'true','confidence':1}]
        Workspace.restore(self.uid,backup)
        self.assertEqual(Storage.get_memory(self.uid,'system'),[])

    def test_csv_formula_sanitized_and_utf8_bom(self):
        """Xuất CSV tiếng Việt có BOM, vô hiệu hóa ô công thức."""
        for title in ['=HYPERLINK("https://example.invalid")','+1','-2','@SUM(A1)','  =1+1']:
            task=self.task();task.title=title;Storage.save_task(task)
        raw=Workspace.export_csv(self.uid)
        self.assertTrue(raw.startswith(b'\xef\xbb\xbf'))
        import csv
        rows=list(csv.reader(io.StringIO(raw.decode('utf-8-sig'))))[1:]
        self.assertTrue(all(row[0].startswith("'") for row in rows))

    def test_calendar_overlap_rejected_adjacency_allowed(self):
        """Lịch trùng bị chặn; hai lịch liền kề được phép."""
        block={'title':'A','start_at':self.day+'T09:00','end_at':self.day+'T10:00'}
        Workspace.save_blocks(self.uid,[block])
        with self.assertRaises(ValueError):Workspace.save_blocks(self.uid,[dict(block,start_at=self.day+'T09:30')])
        Workspace.save_blocks(self.uid,[dict(block,start_at=self.day+'T10:00',end_at=self.day+'T11:00')])
        self.assertEqual(len(Workspace.blocks(self.uid)),2)

    def test_calendar_scoped_delete(self):
        """Xóa lịch tài khoản khác không làm mất lịch đó."""
        Workspace.save_blocks(self.uid,[{'title':'A','start_at':self.day+'T09:00','end_at':self.day+'T10:00'}])
        block=Workspace.blocks(self.uid)[0];Workspace.delete_block('other',block['id'])
        self.assertEqual(len(Workspace.blocks(self.uid)),1)
        Workspace.delete_block(self.uid,block['id']);self.assertEqual(Workspace.blocks(self.uid),[])

    def test_reminder_due_deduplicated_and_completed_ignored(self):
        """Nhắc đúng cửa sổ thời gian, gửi một lần và bỏ qua việc đã xong."""
        task=self.task(due_date=self.day,due_time='09:00',reminder_minutes=15)
        now=datetime.fromisoformat(self.day+'T08:45:00')
        pending=Workspace.pending_reminders(self.uid,now)
        self.assertEqual(len(pending),1)
        Workspace.mark_reminded(self.uid,pending[0]['key'])
        self.assertEqual(Workspace.pending_reminders(self.uid,now),[])
        other=self.task(due_date=self.day,due_time='09:00',reminder_minutes=15,status='done')
        self.assertEqual(Workspace.pending_reminders(self.uid,now),[])

    def test_reminder_future_and_outside_window_not_sent(self):
        """Không nhắc trước giờ hoặc nhắc quá xa cửa sổ bắt kịp."""
        self.task(due_date=self.day,due_time='09:00',reminder_minutes=15)
        for stamp in ['08:44:59','09:00:00']:
            self.assertEqual(Workspace.pending_reminders(self.uid,datetime.fromisoformat(self.day+'T'+stamp)),[])

    def test_sync_snapshot_roundtrip_and_stale_hash(self):
        """Đồng bộ giữ ID; phát hiện dữ liệu máy thay đổi trước khi thay thế."""
        task=self.task();before=Workspace.sync_snapshot(self.uid)
        updated=deepcopy(before);updated['tasks'][0]['title']='Từ máy chủ'
        Workspace.apply_sync_snapshot(self.uid,updated,fingerprint(before))
        self.assertEqual(TaskFocus.task(self.uid,task.id).title,'Từ máy chủ')
        with self.assertRaises(ValueError):Workspace.apply_sync_snapshot(self.uid,before,fingerprint(before))

    def test_sync_foreign_id_conflict_rolls_back(self):
        """Từ chối ID trùng dữ liệu tài khoản khác và giữ nguyên dữ liệu máy."""
        other=str(uuid.uuid4());Storage.save_user(replace(self.user,id=other,username=other,email=other+'@qa.invalid'))
        foreign=Task(id=str(uuid.uuid4()),user_id=other,title='Riêng tư');Storage.save_task(foreign)
        self.task();snapshot=Workspace.sync_snapshot(self.uid);incoming=deepcopy(snapshot)
        incoming['tasks']=[asdict(foreign)]
        with self.assertRaises(ValueError):Workspace.apply_sync_snapshot(self.uid,incoming,fingerprint(snapshot))
        self.assertEqual(Workspace.sync_snapshot(self.uid),snapshot)

    def test_project_create_rename_delete_keeps_tasks(self):
        """Thêm/sửa/xóa dự án; xóa dự án không xóa công việc."""
        project=Project(id=str(uuid.uuid4()),user_id=self.uid,name='Dự án thử')
        with patch('core.access.require_feature'):
            ProjectService.save_project(project);project.name='Đổi tên';ProjectService.save_project(project)
        task=self.task(project_id=project.id)
        self.assertEqual(ProjectService.get_projects(self.uid)[0].name,'Đổi tên')
        ProjectService.delete_project(project.id,self.uid)
        self.assertIsNone(TaskFocus.task(self.uid,task.id).project_id)
        self.assertEqual(ProjectService.get_projects(self.uid),[])

    def test_concurrent_focus_only_one_wins(self):
        """Hai lần bắt đầu đồng thời chỉ tạo một phiên tập trung đang chạy."""
        task=self.task(subtasks=[{'id':'a','title':'A'},{'id':'b','title':'B'}])
        def start(child):
            try:return TaskFocus.start(self.uid,task.id,child)['session_id']
            except ValueError:return None
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(start,['a','b']))
        self.assertEqual(sum(r is not None for r in results),1)
        with SessionLocal() as db:self.assertEqual(db.query(WorkSessionModel).filter_by(user_id=self.uid,ended_at=None).count(),1)

    def test_concurrent_ai_confirmation_idempotent(self):
        """Hai lần xác nhận AI đồng thời không tạo công việc/lịch trùng."""
        from core.plan_commit import save_suggestion
        item={'title':'AI task','start_at':self.day+'T09:00','end_at':self.day+'T10:00'}
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:save_suggestion(self.uid,item,'same'),[1,2]))
        self.assertEqual(sorted(results),[False,True]);self.assertEqual(len(Workspace.blocks(self.uid)),1)


INVALID_TASKS=[
 ('empty_title',{'title':''}),('blank_title',{'title':'   '}),('long_title',{'title':'x'*501}),
 ('unknown_status',{'status':'unknown'}),('unknown_priority',{'priority':'urgent'}),
 ('bad_date',{'due_date':'2026-02-30'}),('bad_time',{'due_time':'25:00'}),
 ('zero_minutes',{'estimated_minutes':0}),('negative_minutes',{'estimated_minutes':-1}),
 ('huge_minutes',{'estimated_minutes':10081}),('bool_minutes',{'estimated_minutes':True}),
 ('string_minutes',{'estimated_minutes':'30'}),('negative_reminder',{'reminder_minutes':-1}),
 ('bad_tags',{'tags':'text'}),('too_many_tags',{'tags':['x']*101}),('bad_tag_type',{'tags':[1]}),
 ('bad_children',{'subtasks':'text'}),('too_many_children',{'subtasks':[{'title':'a'}]*201}),
 ('empty_child',{'subtasks':[{'title':''}]}),('missing_child_title',{'subtasks':[{}]}),
 ('invalid_child_state',{'subtasks':[{'title':'a','status':'bad'}]}),
 ('invalid_child_duration',{'subtasks':[{'title':'a','estimated_minutes':-3}]}),
 ('child_after_parent',{'due_date':'2027-01-01','subtasks':[{'title':'a','due_date':'2027-01-02'}]}),
 ('child_hour_after_parent',{'due_date':'2027-01-01','due_time':'10:00','subtasks':[{'title':'a','due_time':'11:00'}]}),
 ('child_time_without_date',{'subtasks':[{'title':'a','due_time':'10:00'}]}),
 ('invalid_recurrence',{'is_recurring':True,'recur_pattern':'yearly'}),
 ('time_without_date',{'due_time':'10:00'}),('noncanonical_date',{'due_date':'20270101'}),
]
for name,values in INVALID_TASKS:
    def invalid(self,values=values):
        task=Task(id=str(uuid.uuid4()),user_id=self.uid,title='Valid');task.__dict__.update(deepcopy(values))
        with self.assertRaises((ValueError,TypeError)):Storage.save_task(task)
        self.assertEqual(Storage.get_tasks(self.uid),[])
    case(LocalDataTests,'invalid_'+name,'Từ chối dữ liệu lỗi: '+name+'; không ghi dữ liệu dở dang.',invalid)


class SchedulingTests(unittest.TestCase):
    """Lịch, phụ thuộc, giới hạn thời gian và tính bất biến."""
    def test_dependency_cycle_is_unscheduled(self):
        """Phụ thuộc vòng không làm treo bộ xếp lịch."""
        tasks=[Task(id='a',user_id='u',title='A',dependencies=['b']),Task(id='b',user_id='u',title='B',dependencies=['a'])]
        result=propose_day(tasks,[],'2027-01-02',now=datetime(2027,1,1))
        self.assertEqual(result['blocks'],[]);self.assertEqual(set(result['unscheduled']),{'A','B'})

    def test_dependency_order_and_hard_deadline(self):
        """Bước phụ thuộc chạy sau; hạn cứng không bị vượt."""
        tasks=[Task(id='a',user_id='u',title='A',estimated_minutes=60),Task(id='b',user_id='u',title='B',dependencies=['a'],estimated_minutes=60)]
        result=propose_day(tasks,[],'2027-01-02',now=datetime(2027,1,1))
        self.assertEqual([b['task_id'] for b in result['blocks']],['a','b'])
        tasks[0].due_date='2027-01-02';tasks[0].due_time='08:30';tasks[0].deadline_type='hard'
        result=propose_day(tasks,[],'2027-01-02',now=datetime(2027,1,1))
        self.assertEqual(result['blocks'],[])

    def test_past_day_and_reversed_work_hours_rejected(self):
        """Từ chối ngày quá khứ và giờ làm việc đảo ngược."""
        for day,start,end in [('2026-01-01','08:00','18:00'),('2027-01-02','18:00','08:00')]:
            with self.assertRaises(ValueError):propose_day([],[],day,start,end,now=datetime(2027,1,1))

    def test_long_task_without_capacity_not_partially_scheduled(self):
        """Không ghi một phần lịch nếu cả công việc không đủ chỗ."""
        task=Task(id='a',user_id='u',title='A',estimated_minutes=500)
        result=propose_day([task],[],'2027-01-02','08:00','10:00',now=datetime(2027,1,1))
        self.assertEqual(result['blocks'],[]);self.assertEqual(result['unscheduled'],['A'])

    def test_today_never_schedules_in_the_past(self):
        """Lịch hôm nay bắt đầu sau thời điểm hiện tại, làm tròn phút."""
        now=datetime(2027,1,2,11,15,30)
        result=propose_day([Task(id='a',user_id='u',title='A')],[],'2027-01-02',now=now)
        self.assertGreaterEqual(datetime.fromisoformat(result['blocks'][0]['start_at']),now)

for seed in range(20):
    def schedule(self,seed=seed):
        rng=random.Random(seed)
        tasks=[Task(id=str(i),user_id='u',title=str(i),estimated_minutes=rng.randint(1,240),priority=rng.choice(['high','medium','low'])) for i in range(12)]
        fixed=[{'start_at':'2027-01-02T10:00','end_at':'2027-01-02T11:00'},{'start_at':'2027-01-02T13:00','end_at':'2027-01-02T14:00'}]
        before=deepcopy(fixed);result=propose_day(tasks,fixed,'2027-01-02',now=datetime(2027,1,1))
        blocks=result['blocks'];self.assertEqual(fixed,before)
        for i,b in enumerate(blocks):
            self.assertLess(b['start_at'],b['end_at']);self.assertGreaterEqual(b['start_at'],'2027-01-02T08:00');self.assertLessEqual(b['end_at'],'2027-01-02T18:00')
            self.assertLessEqual((datetime.fromisoformat(b['end_at'])-datetime.fromisoformat(b['start_at'])).total_seconds(),90*60)
            for event in fixed:self.assertFalse(b['start_at']<event['end_at'] and event['start_at']<b['end_at'])
            if i:self.assertLessEqual(blocks[i-1]['end_at'],b['start_at'])
        for t in tasks:
            minutes=sum((datetime.fromisoformat(b['end_at'])-datetime.fromisoformat(b['start_at'])).total_seconds()/60 for b in blocks if b['task_id']==t.id)
            self.assertIn(minutes,[0,t.estimated_minutes])
    case(SchedulingTests,f'random_schedule_{seed:02}',f'Xếp lịch ngẫu nhiên seed {seed}: 12 việc; không trùng lịch, không mất thời lượng, không sửa lịch cố định.',schedule)

for pattern,base,today,expected in [('daily','2027-01-01','2027-01-10','2027-01-11'),('weekly','2027-01-01','2027-01-10','2027-01-15'),('monthly','2027-01-31','2027-01-31','2027-02-28'),('monthly','2028-01-31','2028-01-31','2028-02-29'),('monthly','2027-12-31','2027-12-31','2028-01-31')]:
    def recurring(self,pattern=pattern,base=base,today=today,expected=expected):
        original=Task(id='r',user_id='u',title='Lặp',status='done',due_date=base,is_recurring=True,recur_pattern=pattern,subtasks=[{'title':'Bước','status':'done'}])
        result=next_occurrence(original,date.fromisoformat(today))
        self.assertEqual(result.due_date,expected);self.assertEqual(result.status,'todo');self.assertEqual(result.subtasks[0]['status'],'todo');self.assertEqual(original.subtasks[0]['status'],'done')
    case(SchedulingTests,'recurrence_'+pattern+'_'+base.replace('-',''),'Lặp '+pattern+' từ '+base+' → '+expected+'; xử lý cuối tháng/năm nhuận.',recurring)


class SnapshotTests(unittest.TestCase):
    def valid(self):
        snap=empty_workspace();snap['tasks']=[asdict(Task(id='t',user_id='u',title='A'))];return snap

    def test_independent_merge_and_overlapping_edit(self):
        """Gộp hai thay đổi độc lập; báo xung đột khi cùng sửa một việc."""
        base=self.valid();left=deepcopy(base);right=deepcopy(base)
        left['tasks'][0]['title']='B';right['tasks'].append(asdict(Task(id='b',user_id='u',title='C')))
        self.assertEqual(len(merge_snapshots(base,left,right)['tasks']),2)
        right['tasks'][0]['title']='D';self.assertIsNone(merge_snapshots(base,left,right))

    def test_delete_versus_edit_conflicts(self):
        """Một máy xóa và máy kia sửa cùng việc phải báo xung đột."""
        base=self.valid();left=deepcopy(base);left['tasks']=[];right=deepcopy(base);right['tasks'][0]['title']='B'
        self.assertIsNone(merge_snapshots(base,left,right))

    def test_fingerprint_order_independent(self):
        """Đổi thứ tự danh sách không làm sai nhận diện phiên bản đồng bộ."""
        base=self.valid();base['tasks'].append(asdict(Task(id='b',user_id='u',title='B')))
        reverse=deepcopy(base);reverse['tasks'].reverse();self.assertEqual(fingerprint(base),fingerprint(reverse))

BAD_SNAPSHOTS=[('wrong_version',lambda s:s.update(version=2)),('duplicate_task',lambda s:s['tasks'].append(deepcopy(s['tasks'][0]))),('unknown_memory',lambda s:s['memories'].append({'memory_type':'system'})),('orphan_calendar',lambda s:s['blocks'].append({'id':'b','task_id':'missing','title':'X','source':'manual','start_at':'2027-01-01T09:00','end_at':'2027-01-01T10:00'})),('orphan_message',lambda s:s['messages'].append({'session_id':'missing','role':'user','text':'x','timestamp':datetime.now().isoformat()})),('invalid_timezone',lambda s:s.update(profile={'full_name':'X','timezone':'Invalid/Zone','work_start':'08:00','work_end':'18:00'})),('invalid_child_duration',lambda s:s['tasks'][0].update(subtasks=[{'title':'A','estimated_minutes':-1}])),('child_after_parent',lambda s:s['tasks'][0].update(due_date='2027-01-01',subtasks=[{'title':'A','due_date':'2027-01-02'}]))]
for name,change in BAD_SNAPSHOTS:
    def invalid(self,change=change):
        snapshot=self.valid();change(snapshot)
        with self.assertRaises((ValueError,TypeError,KeyError)):validate_snapshot(snapshot)
    case(SnapshotTests,'reject_'+name,'Đồng bộ từ chối: '+name+'.',invalid)


class ServerTests(unittest.TestCase):
    """WSGI API thật + DB tạm; AI/email/cổng thanh toán được thay bằng test doubles."""
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.mail=[]
        cls.api=Application(path=Path(cls.tmp.name)/'server.db',mailer=lambda email,token:cls.mail.append((email,token)),
                            ai=lambda payload:'Phản hồi AI giả lập',payment=lambda order:{'provider':'test-'+order['id'],'checkout_url':'https://checkout.invalid/'+order['id']})
        import bcrypt
        cls.hashed=bcrypt.hashpw(b'Validpassword123',bcrypt.gensalt()).decode()

    def setUp(self):
        self.uid=str(uuid.uuid4());self.username='qa_'+self.uid.replace('-','')[:16];self.email=self.username+'@qa.invalid';self.token=uuid.uuid4().hex
        with self.api.store.connect() as db:
            db.execute('INSERT INTO accounts VALUES (?,?,?,?,?,?)',(self.uid,self.username,self.email,self.hashed,'QA',time.time()))
            db.execute('INSERT INTO tokens VALUES (?,?,?)',(digest(self.token),self.uid,time.time()+3600))
        self.auth='Bearer '+self.token

    def call(self,method,path,data=None,auth=True,raw=None,**overrides):
        body=raw if raw is not None else json.dumps(data or {}).encode()
        env={'REQUEST_METHOD':method,'PATH_INFO':path,'CONTENT_LENGTH':str(len(body)),'wsgi.input':io.BytesIO(body),'REMOTE_ADDR':self.uid,'HTTP_AUTHORIZATION':self.auth if auth else ''}
        env.update(overrides);capture={}
        def response(status,headers):capture.update(status=int(status.split()[0]),headers=dict(headers))
        payload=json.loads(b''.join(self.api(env,response)))
        return capture['status'],payload,capture['headers']

    def grant(self,plan='plus'):
        with self.api.store.connect() as db:db.upsert('entitlements',('account',),{'account':self.uid,'plan':plan,'expires':time.time()+3600})

    def checkout(self,**overrides):
        data={'plan':'plus','cycle':'monthly','payment_method':'visa','request_id':uuid.uuid4().hex};data.update(overrides)
        return self.call('POST','/v1/billing/checkouts',data),data

    def test_health_headers_and_account_privacy(self):
        """Health hoạt động; phản hồi không cache; không lộ hash mật khẩu/token."""
        status,data,headers=self.call('GET','/health',auth=False)
        self.assertEqual(status,200);self.assertEqual(data['status'],'ok');self.assertEqual(headers['Cache-Control'],'no-store')
        status,data,_=self.call('GET','/v1/account');self.assertEqual(status,200);self.assertNotIn('password',data['account']);self.assertNotIn(self.hashed,json.dumps(data))

    def test_login_valid_wrong_and_logout(self):
        """Đăng nhập đúng/sai và hủy hiệu lực token sau đăng xuất."""
        status,data,_=self.call('POST','/v1/auth/login',{'username':self.username.upper(),'password':'Validpassword123'},auth=False)
        self.assertEqual(status,200);self.assertEqual(data['account']['id'],self.uid)
        self.assertEqual(self.call('POST','/v1/auth/login',{'username':self.username,'password':'wrong'},auth=False)[0],401)
        self.assertEqual(self.call('POST','/v1/auth/logout')[0],200);self.assertEqual(self.call('GET','/v1/account')[0],401)

    def test_register_valid_and_duplicate(self):
        """Đăng ký mới thành công, trùng tên/email trả 409."""
        data={'username':'new_'+self.username,'email':'new_'+self.email,'password':'Validpassword123'}
        self.assertEqual(self.call('POST','/v1/auth/register',data,auth=False)[0],200)
        self.assertEqual(self.call('POST','/v1/auth/register',data,auth=False)[0],409)

    def test_password_reset_single_use_and_revoke_tokens(self):
        """Mã khôi phục dùng một lần; mật khẩu mới hoạt động, token cũ bị hủy."""
        self.assertEqual(self.call('POST','/v1/auth/forgot-password',{'email':self.email},auth=False)[0],200)
        token=self.mail[-1][1]
        data={'token':token,'password':'Newpassword123'}
        self.assertEqual(self.call('POST','/v1/auth/reset-password',data,auth=False)[0],200)
        self.assertEqual(self.call('POST','/v1/auth/reset-password',data,auth=False)[0],400)
        self.assertEqual(self.call('GET','/v1/account')[0],401)
        self.assertEqual(self.call('POST','/v1/auth/login',{'username':self.username,'password':'Newpassword123'},auth=False)[0],200)

    def test_reset_unknown_email_does_not_reveal_account(self):
        """Email có/không tồn tại nhận thông báo như nhau; mail chỉ được giả lập."""
        a=self.call('POST','/v1/auth/forgot-password',{'email':self.email},auth=False)
        b=self.call('POST','/v1/auth/forgot-password',{'email':self.username+'-missing@qa.invalid'},auth=False)
        self.assertEqual(a[:2],b[:2])

    def test_change_password_revoke_other_sessions(self):
        """Đổi mật khẩu giữ phiên hiện tại và hủy phiên thiết bị khác."""
        old_token=uuid.uuid4().hex
        with self.api.store.connect() as db:db.execute('INSERT INTO tokens VALUES (?,?,?)',(digest(old_token),self.uid,time.time()+3600))
        self.assertEqual(self.call('POST','/v1/auth/change-password',{'old_password':'wrong','password':'Newpassword123'})[0],400)
        self.assertEqual(self.call('POST','/v1/auth/change-password',{'old_password':'Validpassword123','password':'Newpassword123'})[0],200)
        self.assertEqual(self.call('GET','/v1/account')[0],200)
        self.assertEqual(self.call('GET','/v1/account',HTTP_AUTHORIZATION='Bearer '+old_token)[0],401)

    def test_expired_token_rejected(self):
        """Token hết hạn không thể truy cập tài khoản."""
        with self.api.store.connect() as db:db.execute('UPDATE tokens SET expires=? WHERE hash=?',(time.time()-1,digest(self.token)))
        self.assertEqual(self.call('GET','/v1/account')[0],401)

    def test_sync_revision_and_account_isolation(self):
        """Đồng bộ qua WSGI có kiểm tra revision và giữ dữ liệu riêng từng tài khoản."""
        status,result,_=self.call('GET','/v1/sync');self.assertEqual(status,200);self.assertEqual(result['revision'],0)
        workspace=empty_workspace();workspace['tasks']=[asdict(Task(id='server-task-'+self.uid,user_id=self.uid,title='X'))]
        self.assertEqual(self.call('PUT','/v1/sync',{'revision':0,'workspace':workspace})[1]['revision'],1)
        self.assertEqual(self.call('PUT','/v1/sync',{'revision':0,'workspace':workspace})[0],409)
        self.assertEqual(self.call('GET','/v1/sync')[1]['workspace'],workspace)
        other=uuid.uuid4().hex
        with self.api.store.connect() as db:
            uid=uuid.uuid4().hex;db.execute('INSERT INTO accounts VALUES (?,?,?,?,?,?)',(uid,uid,uid+'@qa.invalid',self.hashed,'QA',time.time()))
            db.execute('INSERT INTO tokens VALUES (?,?,?)',(digest(other),uid,time.time()+3600))
        self.assertEqual(self.call('GET','/v1/sync',HTTP_AUTHORIZATION='Bearer '+other)[1]['workspace']['tasks'],[])

    def test_ai_free_blocked_plus_allowed_and_counted(self):
        """Free bị chặn; Plus gọi AI giả lập được và tính đúng một lượt."""
        self.assertEqual(self.call('POST','/v1/ai/generate',{'message':'Xin chào'})[0],403)
        self.grant()
        status,result,_=self.call('POST','/v1/ai/generate',{'message':'Xin chào'})
        self.assertEqual(status,200);self.assertEqual(result['usage']['used'],1);self.assertEqual(result['text'],'Phản hồi AI giả lập')

    def test_ai_failure_refunds_quota(self):
        """Nhà cung cấp AI lỗi: trả 503 và hoàn lượt hạn mức."""
        self.grant()
        with patch.object(self.api,'ai',side_effect=TimeoutError('test timeout')):
            self.assertEqual(self.call('POST','/v1/ai/generate',{'message':'Hello'})[0],503)
        self.assertEqual(self.call('GET','/v1/ai/usage')[1]['used'],0)

    def test_ai_quota_exhausted(self):
        """Hết hạn mức tháng không gọi AI và trả 429."""
        self.grant()
        with self.api.store.connect() as db:db.upsert('usage',('account','period'),{'account':self.uid,'period':datetime.now(timezone.utc).strftime('%Y-%m'),'count':100000})
        with patch.object(self.api,'ai') as ai:
            self.assertEqual(self.call('POST','/v1/ai/generate',{'message':'Hello'})[0],429);ai.assert_not_called()

    def test_ai_pro_image_valid_and_invalid_base64(self):
        """Pro nhận ảnh hợp lệ theo giao thức, dữ liệu base64 lỗi bị từ chối."""
        self.grant('pro')
        from PIL import Image
        image=io.BytesIO();Image.new('RGB',(1,1)).save(image,format='PNG')
        data={'message':'Ảnh','feature':'ai_images','image':base64.b64encode(image.getvalue()).decode(),'mime':'image/png'}
        self.assertEqual(self.call('POST','/v1/ai/generate',data)[0],200)
        data['image']='%%%';self.assertEqual(self.call('POST','/v1/ai/generate',data)[0],400)

    def test_checkout_idempotent_and_no_activation_before_payment(self):
        """Tạo đơn lặp không nhân đôi; chưa xác nhận thanh toán không được cấp gói."""
        (status,order,_),data=self.checkout()
        self.assertEqual(status,200);self.assertEqual(order['amount'],67000)
        repeat=self.call('POST','/v1/billing/checkouts',data)
        self.assertEqual(repeat[1]['order_id'],order['order_id'])
        self.assertEqual(self.call('GET','/v1/billing/entitlement')[1]['plan'],'free')
        self.assertEqual(len(self.call('GET','/v1/billing/orders')[1]['orders']),1)

    def test_payment_wrong_amount_and_repeat_webhook(self):
        """Sai số tiền không cấp gói; webhook đúng gọi lại không gia hạn hai lần."""
        (_,order,_),_=self.checkout()
        oid=order['order_id'];provider='test-'+oid
        with self.assertRaises(APIError):self.api.settle(oid,provider,1,'VND')
        self.assertEqual(self.api.entitlement(self.uid)['plan'],'free')
        self.api.settle(oid,provider,order['amount'],'VND');first=self.api.entitlement(self.uid)
        self.api.settle(oid,provider,order['amount'],'VND');self.assertEqual(first,self.api.entitlement(self.uid));self.assertEqual(first['plan'],'plus')

    def test_pending_order_blocks_second_purchase(self):
        """Có đơn chờ thì chặn đơn mới để tránh hai lần ưu đãi đầu tiên."""
        self.assertEqual(self.checkout()[0][0],200)
        self.assertEqual(self.checkout()[0][0],409)

    def test_request_id_reuse_different_plan_rejected(self):
        """Không dùng một request_id để đổi sang gói khác."""
        (_,_,_),data=self.checkout();data['plan']='pro'
        self.assertEqual(self.call('POST','/v1/billing/checkouts',data)[0],409)

    def test_payment_provider_failure_no_fake_success(self):
        """Cổng thanh toán lỗi không tự báo thành công hoặc cấp gói."""
        with patch.object(self.api,'payment',side_effect=TimeoutError()):
            self.assertEqual(self.checkout()[0][0],503)
        self.assertEqual(self.api.entitlement(self.uid)['plan'],'free')

    def test_expired_plan_reverts_to_free(self):
        """Gói hết hạn trở về Free và mất quyền gọi AI."""
        self.grant('pro')
        with self.api.store.connect() as db:db.execute('UPDATE entitlements SET expires=? WHERE account=?',(time.time()-1,self.uid))
        self.assertEqual(self.api.entitlement(self.uid)['plan'],'free')
        self.assertEqual(self.call('POST','/v1/ai/generate',{'message':'Hello'})[0],403)

    def test_no_provider_config_no_checkout(self):
        """Chưa cấu hình merchant không tạo đơn hoặc thu tiền."""
        with patch.object(self.api,'payment_override',False),patch('server.payments.configured',return_value=False):
            self.assertEqual(self.checkout()[0][0],503)
        self.assertEqual(self.call('GET','/v1/billing/orders')[1]['orders'],[])

    def test_missing_oauth_config_fails_clearly(self):
        """Chưa cấu hình Google/Facebook/Calendar trả lỗi rõ, không đăng nhập giả."""
        with patch('server.social_auth.ready',return_value=False),patch('server.google_calendar.configured',return_value=False):
            for provider in ['google','facebook']:
                self.assertEqual(self.call('POST','/v1/auth/social/start',{'provider':provider},auth=False)[0],400)
            self.assertIn(self.call('POST','/v1/google/connect')[0],[400,503])

    def test_ai_non_image_bytes_must_not_masquerade_as_png(self):
        """Ảnh giả đuôi PNG cần được từ chối trước khi gọi nhà cung cấp AI."""
        self.grant('pro')
        with patch.object(self.api,'ai',return_value='mock') as ai:
            result=self.call('POST','/v1/ai/generate',{'message':'X','feature':'ai_images','image':base64.b64encode(b'not a PNG').decode(),'mime':'image/png'})
            self.assertEqual(result[0],400);ai.assert_not_called()

for name,change in [('invalid_username',{'username':'!bad'}),('invalid_email',{'email':'no-email'}),('short_password',{'password':'short'}),('oversize_password',{'password':'x'*73}),('nonstring_password',{'password':123})]:
    def invalid_register(self,change=change):
        data={'username':'new_'+self.username,'email':'new_'+self.email,'password':'Validpassword123'};data.update(change)
        self.assertEqual(self.call('POST','/v1/auth/register',data,auth=False)[0],400)
    case(ServerTests,'registration_'+name,'Đăng ký API từ chối '+name+'.',invalid_register)

for path in ['/v1/account','/v1/sync','/v1/billing/entitlement','/v1/billing/orders','/v1/ai/usage','/v1/google/status']:
    def unauth(self,path=path):self.assertEqual(self.call('GET',path,auth=False)[0],401)
    case(ServerTests,'unauth_'+path.replace('/','_'),'Không có token không được đọc '+path+'.',unauth)

for name,raw,overrides,status in [('bad_json',b'{oops',{},400),('array_json',b'[]',{},400),('truncated',b'{}',{'CONTENT_LENGTH':'99'},400),('oversized',b'',{'CONTENT_LENGTH':str(8*1024*1024+1)},413),('negative_length',b'',{'CONTENT_LENGTH':'-1'},413)]:
    def wsgi(self,raw=raw,overrides=overrides,status=status):self.assertEqual(self.call('POST','/v1/auth/login',raw=raw,auth=False,**overrides)[0],status)
    case(ServerTests,'wsgi_'+name,'HTTP/JSON không hợp lệ: '+name+'.',wsgi)

for feature in ['ai_voice','ai_documents','ai_images','made_up']:
    def feature_case(self,feature=feature):
        self.grant('plus');self.assertEqual(self.call('POST','/v1/ai/generate',{'message':'Hello','feature':feature})[0],403)
    case(ServerTests,'plus_blocks_'+feature,'Plus không được dùng '+feature+'.',feature_case)

for name,change in [('empty_message',{'message':''}),('long_message',{'message':'x'*60001}),('bad_instruction',{'instruction':123})]:
    def ai_invalid(self,change=change):
        self.grant();data={'message':'Hello'};data.update(change)
        self.assertEqual(self.call('POST','/v1/ai/generate',data)[0],400)
        self.assertEqual(self.call('GET','/v1/ai/usage')[1]['used'],0)
    case(ServerTests,'ai_validation_'+name,'AI từ chối '+name+' và không trừ lượt.',ai_invalid)


class AIAndProviderTests(unittest.TestCase):
    def test_ai_json_and_markdown_fence(self):
        """Phân tích JSON kế hoạch có/không có khung markdown."""
        from core.ai_planner_service import _parse_response
        payload={'type':'plan_result','title':'Test','ready_to_save':True,'suggested_tasks':[{'title':'A'}]}
        for raw in [json.dumps(payload),'```json\n'+json.dumps(payload)+'\n```']:
            result=_parse_response(raw,'lên lịch');self.assertEqual(result['type'],'plan_result');self.assertEqual(result['suggested_tasks'][0]['title'],'A')

    def test_ai_offline_fallback_not_saveable(self):
        """AI offline/JSON hỏng không tạo kế hoạch có thể lưu giả."""
        from core.ai_planner_service import _parse_response
        for raw in ['', 'not JSON', '[]', '{broken']:
            result=_parse_response(raw,'lên kế hoạch du lịch')
            self.assertFalse(result.get('ready_to_save',False))

    def test_ai_malformed_task_payload_does_not_crash_ui(self):
        """Kế hoạch AI chứa task sai kiểu không làm sập phần hiển thị."""
        from core.ai_planner_service import _parse_response
        from components.ai_plan import build_plan
        for values in [[None],[5],['text']]:
            result=_parse_response(json.dumps({'type':'plan_result','suggested_tasks':values}),'lên lịch')
            if result['type']=='plan_result':build_plan(result,SimpleNamespace(update=lambda:None),'u',lambda:None,lambda _:None)

    def test_stripe_signature_valid_forged_expired(self):
        """Webhook Stripe: nhận chữ ký đúng, chặn giả mạo/hết hạn."""
        from server.payments import verified_stripe_event
        raw=b'{"type":"test"}';stamp=str(int(time.time()))
        expected=hmac.new(b'qa-secret',stamp.encode()+b'.'+raw,hashlib.sha256).hexdigest()
        with patch.dict(os.environ,{'STRIPE_WEBHOOK_SECRET':'qa-secret'}):
            self.assertEqual(verified_stripe_event(raw,'t='+stamp+',v1='+expected)['type'],'test')
            for signature in ['t='+stamp+',v1=invalid','t=1,v1='+expected]:
                with self.assertRaises(ValueError):verified_stripe_event(raw,signature)

    def test_payos_signature_valid_and_tampered(self):
        """Webhook payOS: dữ liệu bị sửa không vượt qua kiểm tra chữ ký."""
        from server.payments import payos_signature, verified_payos_event
        with patch.dict(os.environ,{'PAYOS_CHECKSUM_KEY':'qa-secret'}):
            data={'amount':67000,'orderCode':123};signature=payos_signature(data)
            raw=json.dumps({'data':data,'signature':signature}).encode();self.assertEqual(verified_payos_event(raw),data)
            data['amount']=1
            with self.assertRaises(ValueError):verified_payos_event(json.dumps({'data':data,'signature':signature}).encode())

    def test_entitlement_cannot_belong_to_other_account(self):
        """Client từ chối quyền gói thuộc tài khoản khác hoặc dữ liệu demo."""
        from core.billing import BillingClient,BillingError
        for result in [{'account_id':'other','plan':'pro'},{'account_id':'me','plan':'pro','demo':True},{'account_id':'me','plan':'unknown'}]:
            with patch.object(BillingClient,'_request',return_value=result):
                with self.assertRaises(BillingError):BillingClient().entitlement('me')

    def test_paid_entitlement_must_have_future_aware_expiry(self):
        """Quyền trả phí cần thời hạn có múi giờ, còn hiệu lực."""
        from core.billing import BillingClient,BillingError
        for expiry in ['2000-01-01T00:00:00+00:00','2999-01-01T00:00:00','bad']:
            with patch.object(BillingClient,'_request',return_value={'account_id':'me','plan':'pro','valid_until':expiry}):
                with self.assertRaises(BillingError):BillingClient().entitlement('me')

    def test_prices_all_cycles_and_intro(self):
        """Giá Plus/Pro, gói năm và ưu đãi tháng đầu đúng cấu hình sản phẩm."""
        from core.plans import quote
        for plan,monthly,intro,annual in [('plus',149000,67000,1430400),('pro',499000,399000,4790400)]:
            self.assertEqual(quote(plan,'monthly')['amount'],monthly)
            self.assertEqual(quote(plan,'monthly',True)['amount'],intro)
            self.assertEqual(quote(plan,'annual',True)['amount'],annual)
        with self.assertRaises(ValueError):quote('free','monthly')

    def test_feature_matrix(self):
        """Free/Plus/Pro chỉ có đúng quyền trong ma trận tính năng."""
        from core.access import Access,FEATURES,LEVELS
        for plan in LEVELS:
            for feature,(required,_) in FEATURES.items():self.assertEqual(Access(plan).allows(feature),LEVELS[plan]>=LEVELS[required])

    def test_insecure_urls_rejected(self):
        """Chặn URL HTTP bên ngoài, URL có mật khẩu, query hoặc fragment."""
        from core.cloud import validate_api_url,CloudError
        for value in ['http://example.com','https://user:pass@example.com','https://example.com?token=x','https://example.com/#fragment','javascript:alert(1)','']:
            with self.assertRaises(CloudError):validate_api_url(value)
        validate_api_url('https://example.invalid')


class LocalAuthTests(unittest.TestCase):
    def setUp(self):
        self.name='local_'+uuid.uuid4().hex[:12]
        self.email=self.name+'@qa.invalid'

    def test_register_login_wrong_password_and_duplicates(self):
        """Tài khoản cục bộ: đăng ký, đăng nhập, sai mật khẩu, trùng tên/email."""
        with patch('core.cloud.CloudClient.configured',new_callable=unittest.mock.PropertyMock,return_value=False):
            self.assertTrue(AuthService.register(self.name,self.email,'password123')[0])
            self.assertFalse(AuthService.register(self.name,self.email,'password123')[0])
            self.assertFalse(AuthService.login(self.name,'wrong')[0])
            self.assertTrue(AuthService.login(self.name,'password123')[0])

    def test_password_change_validation(self):
        """Đổi mật khẩu cục bộ kiểm tra mật khẩu cũ, xác nhận và độ dài."""
        AuthService.register(self.name,self.email,'password123')
        user=Storage.find_user(username=self.name)
        for old,new,confirm in [('wrong','newpassword','newpassword'),('password123','newpassword','different'),('password123','tiny','tiny')]:
            self.assertFalse(AuthService.change_password(user,old,new,confirm)[0])
        self.assertTrue(AuthService.change_password(user,'password123','newpassword','newpassword')[0])
        self.assertTrue(AuthService.login(self.name,'newpassword')[0])

for name,username,email,password in [('blank_username','  ','valid@qa.invalid','password123'),('bad_email','valid','bad','password123'),('too_long_bcrypt','valid','valid@qa.invalid','x'*73)]:
    def local_invalid(self,username=username,email=email,password=password):
        if username=='valid':username=self.name
        if email=='valid@qa.invalid':email=self.email
        result=AuthService.register(username,email,password)
        self.assertFalse(result[0]);self.assertIsNone(Storage.find_user(email=email))
    case(LocalAuthTests,'invalid_'+name,'Tài khoản cục bộ từ chối '+name+' bằng thông báo, không crash.',local_invalid)


def chat_roundtrip(self):
    sid=ChatService.create_session(self.uid)
    ChatService.add_message(self.uid,sid,'user','Xin chào Doumar')
    self.assertEqual(ChatService.get_session(self.uid,sid)['messages'][0]['text'],'Xin chào Doumar')
    self.assertIsNone(ChatService.get_session('other',sid))
    ChatService.delete_session('other',sid);self.assertIsNotNone(ChatService.get_session(self.uid,sid))
    ChatService.delete_session(self.uid,sid);self.assertIsNone(ChatService.get_session(self.uid,sid))
case(LocalDataTests,'chat_history_roundtrip','Chat: tạo/lưu/đọc/xóa hội thoại và ngăn tài khoản khác đọc/xóa.',chat_roundtrip)


def chat_foreign_write(self):
    sid=ChatService.create_session(self.uid)
    with self.assertRaises(ValueError):ChatService.add_message('other',sid,'user','Không được ghi vào hội thoại này')
    self.assertEqual(ChatService.get_session(self.uid,sid)['messages'],[])
case(LocalDataTests,'chat_foreign_write_rejected','Chat: tài khoản khác không được chèn tin nhắn vào hội thoại của chủ sở hữu.',chat_foreign_write)


def analytics_empty(self):
    report=AnalyticsService.get_full_report(self.uid)
    self.assertEqual(report['total_tasks'],0)
case(LocalDataTests,'analytics_empty','Báo cáo dữ liệu trống không chia cho 0 hoặc phát sinh lỗi.',analytics_empty)


def reminders_failed(self):
    from core.reminders import deliver
    task=self.task(due_date=self.day,due_time='09:00',reminder_minutes=15)
    now=datetime.fromisoformat(self.day+'T08:45:00');Storage.set_session(self.uid)
    with patch('core.reminders.send_notification',return_value=False):self.assertEqual(deliver(self.uid,now),0)
    self.assertEqual(len(Workspace.pending_reminders(self.uid,now)),1)
case(LocalDataTests,'reminders_retry_after_os_failure','Nhắc việc: thông báo OS thất bại không đánh dấu đã gửi, có thể thử lại.',reminders_failed)


def autostart_temporary(self):
    from core.reminders import set_autostart,autostart_enabled
    import sys
    if not sys.platform.startswith('linux'):self.skipTest('Linux only')
    with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'XDG_CONFIG_HOME':folder}):
        set_autostart(True);self.assertTrue(autostart_enabled())
        self.assertIn('[Desktop Entry]',Path(folder,'autostart','taskflow-reminders.desktop').read_text())
        set_autostart(False);self.assertFalse(autostart_enabled())
case(LocalDataTests,'autostart_in_temporary_config','Nhắc nền Linux: bật/tắt file tự khởi động trong thư mục cấu hình tạm, không đổi thiết lập thật.',autostart_temporary)


def onboarding_skip(self):
    from screens.onboarding_screen import survey_to_ai_memory
    survey_to_ai_memory(self.uid,{})
    self.assertEqual(Storage.get_memory_value(self.uid,'preference','planning_profile'),{})
    self.assertTrue(Storage.get_memory_value(self.uid,'system','onboarding_done'))
case(LocalDataTests,'onboarding_skip_all','Bỏ qua toàn bộ bảng hỏi không bịa câu trả lời và vẫn vào ứng dụng được.',onboarding_skip)


def large_account(self):
    with SessionLocal.begin() as db:
        db.add_all([TaskModel(**asdict(Task(id=str(uuid.uuid4()),user_id=self.uid,title=f'Công việc {i}',priority=['high','medium','low'][i%3]))) for i in range(500)])
    self.assertEqual(len(TaskService.get_tasks(self.uid)),500)
    import core.compat
    from screens.desktop_screen import build_tasks
    view=build_tasks(SimpleNamespace(update=lambda:None,on_keyboard_event=None),self.user,lambda *a,**k:None)
    self.assertIsNotNone(view)
case(LocalDataTests,'account_with_500_tasks','Tài khoản có 500 công việc: đọc dữ liệu và dựng trang danh sách không lỗi.',large_account)


class SyncFlowTests(unittest.TestCase):
    setUp=LocalDataTests.setUp
    task=LocalDataTests.task

    def remote(self,workspace=None,revision=0):
        fixture={'account_id':self.uid,'revision':revision,'workspace':workspace or empty_workspace()}
        class Client:
            url='https://qa.invalid'
            def __init__(inner,*args):pass
            def request(inner,method,path,data=None):
                if method=='PUT':fixture.update(revision=fixture['revision']+1,workspace=deepcopy(data['workspace']))
                return deepcopy(fixture)
        return fixture,Client

    def test_upload_then_unchanged_sync(self):
        """Luồng đồng bộ: tải lên lần đầu, lần sau nhận biết không thay đổi."""
        from core.sync import synchronize
        self.task();fixture,client=self.remote()
        with patch('core.sync.CloudClient',client):
            self.assertEqual(synchronize(self.uid)['state'],'uploaded')
            self.assertEqual(synchronize(self.uid)['state'],'synced')
        self.assertEqual(len(fixture['workspace']['tasks']),1)

    def test_remote_download_deferred_during_edit(self):
        """Đang sửa dữ liệu thì hoãn tải xuống, không ghi đè bản nháp."""
        from core.sync import synchronize
        remote=empty_workspace();remote['tasks']=[asdict(Task(id='remote-'+self.uid,user_id=self.uid,title='Máy chủ'))]
        fixture,client=self.remote(remote,1)
        with patch('core.sync.CloudClient',client):
            self.assertEqual(synchronize(self.uid,can_download=lambda:False)['state'],'deferred')
        self.assertEqual(Storage.get_tasks(self.uid),[])

    def test_remote_download_with_recovery_copy(self):
        """Tải bản máy chủ và tạo bản phục hồi cục bộ trong thư mục thử."""
        from core.sync import synchronize
        remote=empty_workspace();remote['tasks']=[asdict(Task(id='remote-'+self.uid,user_id=self.uid,title='Máy chủ'))]
        _,client=self.remote(remote,1)
        with patch('core.sync.CloudClient',client):self.assertEqual(synchronize(self.uid)['state'],'downloaded')
        self.assertEqual(Storage.get_tasks(self.uid)[0].title,'Máy chủ')

    def test_wrong_remote_account_rejected(self):
        """Máy chủ trả sai tài khoản bị chặn trước khi tải dữ liệu."""
        from core.sync import synchronize
        from core.cloud import CloudError
        fixture,client=self.remote();fixture['account_id']='wrong'
        with patch('core.sync.CloudClient',client):
            with self.assertRaises(CloudError):synchronize(self.uid)

    def test_offline_never_loses_local_data(self):
        """Mất mạng khi đồng bộ không xóa dữ liệu cục bộ."""
        from core.sync import synchronize
        from core.cloud import CloudError
        self.task();before=Workspace.sync_snapshot(self.uid)
        with patch('core.sync.CloudClient') as client:
            client.return_value.request.side_effect=CloudError('Offline')
            with self.assertRaises(CloudError):synchronize(self.uid)
        self.assertEqual(Workspace.sync_snapshot(self.uid),before)



def oauth_handoff(self):
    from urllib.parse import urlsplit,parse_qs
    settings={'client':'qa-client','secret':'qa-secret','redirect':'https://qa.invalid/callback'}
    identity={'subject':'qa-'+self.uid,'email':'google-'+self.email,'name':'Google QA'}
    with patch('server.social_auth.ready',return_value=True),patch('server.social_auth.config',return_value=settings),patch('server.social_auth.profile',return_value=identity):
        request=self.api.social.start('google');ticket=request['ticket'];state=parse_qs(urlsplit(request['authorization_url']).query)['state'][0]
        self.assertEqual(self.api.social.poll(ticket)['status'],'pending')
        self.api.social.callback('google',state,'test-code')
        self.assertEqual(self.api.social.poll(ticket)['status'],'ready')
        complete=self.api.social.poll(ticket,finish=True);self.assertIn('access_token',complete)
        from server.social_auth import SocialError
        with self.assertRaises(SocialError):self.api.social.poll(ticket,finish=True)
case(ServerTests,'oauth_mocked_handoff_single_use','OAuth giả lập: start → callback → ready → finish; ticket dùng một lần.',oauth_handoff)


def throttle(self):
    key='qa-rate:'+self.uid
    self.api.throttle(key,2,60);self.api.throttle(key,2,60)
    with self.assertRaises(APIError) as error:self.api.throttle(key,2,60)
    self.assertEqual(error.exception.status,429)
case(ServerTests,'rate_limit','API: quá số lần cho phép trả 429.',throttle)


class GoogleTransformTests(unittest.TestCase):
    def payload(self):
        result=empty_workspace();result['profile']={'full_name':'QA','work_start':'08:00','work_end':'18:00','timezone':'Asia/Ho_Chi_Minh'};return result

    def test_timed_event_timezone_and_idempotency(self):
        """Nhập Google giả lập: đổi UTC sang múi giờ tài khoản và không nhân đôi."""
        from server.google_calendar import import_event
        payload=self.payload();event={'id':'google-event','summary':'Họp','start':{'dateTime':'2027-01-02T09:00:00Z'},'end':{'dateTime':'2027-01-02T10:00:00Z'}}
        import_event(payload,'u',event);import_event(payload,'u',event)
        self.assertEqual(len(payload['tasks']),1);self.assertEqual(len(payload['blocks']),1)
        self.assertEqual(payload['tasks'][0]['due_time'],'16:00');validate_snapshot(payload)

    def test_all_day_event_and_google_deletion(self):
        """Sự kiện cả ngày không có giờ; xóa phía Google đưa công việc vào Thùng rác."""
        from server.google_calendar import import_event
        payload=self.payload();event={'id':'day','summary':'Ngày nghỉ','start':{'date':'2027-01-02'},'end':{'date':'2027-01-03'}}
        local_id=import_event(payload,'u',event)
        self.assertIsNone(payload['tasks'][0]['due_time']);self.assertEqual(payload['blocks'],[])
        import_event(payload,'u',{'id':'day','status':'cancelled'},local_id)
        self.assertEqual(payload['tasks'],[]);self.assertEqual(len(payload['trash']),1)

    def test_google_preserves_subtask_slot_title(self):
        """Xuất lịch việc nhỏ giữ tên từng bước, không đổi thành tên cha."""
        from server.google_calendar import desired_events
        payload=self.payload();payload['tasks']=[asdict(Task(id='t',user_id='u',title='Báo cáo'))]
        payload['blocks']=[{'id':'b','task_id':'t','title':'Báo cáo · Viết kết luận','start_at':'2027-01-02T09:00','end_at':'2027-01-02T10:00','source':'manual'}]
        self.assertEqual(desired_events(payload)['block:b']['summary'],'Báo cáo · Viết kết luận')


def pro_locked_label(self):
    from screens.upgrade_screen import build_locked
    import flet as ft
    view=build_locked(SimpleNamespace(),SimpleNamespace(),lambda *args,**kwargs:None,'ai_images')
    labels=[c.value for c in view.controls if isinstance(c,ft.Text)]
    self.assertIn('Tính năng này có trong gói Pro.',labels)
    self.assertFalse(any('Pro và Pro' in label for label in labels))
case(AIAndProviderTests,'pro_locked_label','Thông báo khóa tính năng Pro không lặp sai tên gói thành Pro và Pro.',pro_locked_label)


def walk_controls(node):
    yield node
    for child in getattr(node,'controls',[]) or []:
        yield from walk_controls(child)
    content=getattr(node,'content',None)
    import flet as ft
    if isinstance(content,ft.Control):yield from walk_controls(content)

for label,route in [('Thêm thư mục','task_edit'),('Lịch','calendar'),('Dự án','projects'),('Thùng rác','trash')]:
    def nav_button(self,label=label,route=route):
        import core.compat
        from screens.desktop_screen import build_tasks
        visited=[];page=SimpleNamespace(update=lambda:None,on_keyboard_event=None)
        view=build_tasks(page,self.user,lambda r,**kwargs:visited.append(r))
        button=next(c for c in walk_controls(view) if getattr(c,'content',None)==label and getattr(c,'on_click',None))
        button.on_click(None);self.assertEqual(visited[-1],route)
    case(LocalDataTests,'visible_navigation_'+route,'Thanh công cụ: nút '+label+' hiển thị trực tiếp và mở đúng '+route+'.',nav_button)


def task_search_and_filters(self):
    import core.compat
    import flet as ft
    from screens.desktop_screen import build_tasks
    self.task(subtasks=[{'title':'Tìm nội dung bước nhỏ'}],priority='high')
    done=self.task(status='done');done.title='Việc đã xong';Storage.save_task(done)
    page=SimpleNamespace(update=lambda:None,on_keyboard_event=None)
    view=build_tasks(page,self.user,lambda *args,**kwargs:None)
    def labels():return [c.value for c in walk_controls(view) if isinstance(c,ft.Text)]
    self.assertIn('1 thư mục',labels())
    filter=next(c for c in walk_controls(view) if isinstance(c,ft.Dropdown) and c.value=='active')
    filter.on_select(SimpleNamespace(control=SimpleNamespace(value='all')));self.assertIn('2 thư mục',labels())
    search=next(c for c in walk_controls(view) if isinstance(c,ft.TextField) and c.hint_text=='Tìm công việc…')
    search.on_change(SimpleNamespace(control=SimpleNamespace(value='BƯỚC NHỎ')));self.assertIn('1 thư mục',labels())
    search.on_change(SimpleNamespace(control=SimpleNamespace(value='không tồn tại')));self.assertIn('0 thư mục',labels())
case(LocalDataTests,'task_search_filters','Danh sách: bộ lọc hoàn thành, tìm tên việc nhỏ không phân biệt hoa/thường và kết quả trống.',task_search_and_filters)


def refresh_button(self):
    from screens.desktop_screen import build_tasks
    page=SimpleNamespace(update=lambda:None,on_keyboard_event=None)
    view=build_tasks(page,self.user,lambda *args,**kwargs:None)
    button=next(c for c in walk_controls(view) if getattr(c,'content',None)=='Làm mới')
    button.on_click(None)
case(LocalDataTests,'refresh_button','Thanh công cụ: Làm mới đọc lại danh sách và không lỗi khi dữ liệu trống.',refresh_button)

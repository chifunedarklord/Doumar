"""Regression tests use an isolated temporary database, never the user's data."""
import os
import tempfile
import unittest
from copy import deepcopy
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

_tmp = tempfile.TemporaryDirectory()
os.environ['DATABASE_URL'] = 'sqlite:///' + _tmp.name + '/test.db'
from core.models import User, Task
from core.database import Storage
from core.orm import SessionLocal, TaskModel, ScheduleBlockModel
from core.plan_commit import save_suggestion
from core.task_rules import reconcile_subtasks
from core.workspace import Workspace


class PlanningTests(unittest.TestCase):
    def setUp(self):
        import uuid
        self.uid = str(uuid.uuid4())
        Storage.save_user(User(id=self.uid, username=self.uid, email=self.uid+'@test.invalid', password_hash='test'))
        self.day = (datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')) + timedelta(days=2)).date().isoformat()

    def item(self, scheduled=True):
        item = {'title': 'Chuẩn bị chuyến đi', 'subtasks': [{'title': 'Đặt vé'}, {'title': 'Hành lý'}]}
        if scheduled:
            item.update(start_at=self.day+'T09:00', end_at=self.day+'T10:00', estimated_minutes=60)
        return item

    def test_completion_and_reopen_after_deadline(self):
        task = Task(id='one', user_id=self.uid, title='Cha', due_date='2000-01-01',
                    subtasks=[{'title':'A','status':'done'}, {'title':'B','done':True}])
        Storage.save_task(task)
        loaded = Storage.get_tasks(self.uid)[0]
        self.assertEqual(loaded.status, 'done')
        self.assertEqual(loaded.due_date_display, 'Đã hoàn thành')
        self.assertFalse(loaded.is_overdue)
        finished = loaded.completed_at
        Storage.save_task(loaded)
        self.assertEqual(loaded.completed_at, finished)
        loaded.subtasks[0]['status'] = 'todo'
        Storage.save_task(loaded)
        self.assertEqual(loaded.status, 'in_progress')
        self.assertIsNone(loaded.completed_at)
        self.assertTrue(loaded.is_overdue)

    def test_no_deadline_not_overdue_and_legacy_status_authoritative(self):
        task = Task(id='none', user_id=self.uid, title='Cha', subtasks=[{'title':'A','status':'todo','done':True}])
        reconcile_subtasks(task)
        self.assertEqual(task.subtask_progress, (0,1))
        self.assertFalse(task.is_overdue)

    def test_schedule_and_task_linked_and_idempotent(self):
        self.assertTrue(save_suggestion(self.uid, self.item(), 'plan:0'))
        self.assertFalse(save_suggestion(self.uid, self.item(), 'plan:0'))
        tasks = Storage.get_tasks(self.uid)
        blocks = Workspace.blocks(self.uid)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]['task_id'], tasks[0].id)
        self.assertIsNone(tasks[0].due_date)  # execution time is not a deadline
        self.assertEqual(len(tasks[0].subtasks), 2)

    def test_deadline_alone_does_not_create_calendar(self):
        item = self.item(False)
        item.update(due_date=self.day, due_time='12:00')
        save_suggestion(self.uid, item, 'unscheduled')
        self.assertEqual(len(Storage.get_tasks(self.uid)), 1)
        self.assertEqual(Workspace.blocks(self.uid), [])

    def test_conflict_rolls_back_and_preserves_existing(self):
        save_suggestion(self.uid, self.item(), 'first')
        before = deepcopy(Workspace.blocks(self.uid))
        with self.assertRaisesRegex(ValueError, 'trùng lịch'):
            save_suggestion(self.uid, self.item(), 'second')
        self.assertEqual(len(Storage.get_tasks(self.uid)), 1)
        self.assertEqual(Workspace.blocks(self.uid), before)

    def test_account_isolation(self):
        save_suggestion(self.uid, self.item(), 'same')
        other = self.uid + '-other'
        Storage.save_user(User(id=other, username=other, email=other+'@test.invalid', password_hash='test'))
        save_suggestion(other, self.item(), 'same')
        self.assertNotEqual(Workspace.blocks(other)[0]['task_id'], Workspace.blocks(self.uid)[0]['task_id'])

    def test_subtasks_can_have_separate_slots_without_parent_double_booking(self):
        item = self.item(False)
        item['subtasks'][0].update(start_at=self.day+'T09:00', end_at=self.day+'T09:30')
        item['subtasks'][1].update(start_at=self.day+'T10:00', end_at=self.day+'T10:30')
        save_suggestion(self.uid, item, 'children')
        self.assertEqual(len(Storage.get_tasks(self.uid)), 1)
        self.assertEqual(len(Workspace.blocks(self.uid)), 2)
        from core.snapshot import validate_snapshot
        validate_snapshot(Workspace.sync_snapshot(self.uid))

    def test_overlapping_children_and_parent_double_booking_rejected(self):
        item = self.item()
        item['subtasks'][0].update(start_at=self.day+'T09:00', end_at=self.day+'T09:30')
        with self.assertRaisesRegex(ValueError, 'cha hoặc'):
            save_suggestion(self.uid, item, 'both')
        item.pop('start_at'); item.pop('end_at')
        item['subtasks'][1].update(start_at=self.day+'T09:15', end_at=self.day+'T10:00')
        with self.assertRaisesRegex(ValueError, 'trùng giờ'):
            save_suggestion(self.uid, item, 'overlap')
        self.assertEqual(Storage.get_tasks(self.uid), [])

    def test_survey_profile_is_in_sync_snapshot(self):
        from screens.onboarding_screen import survey_to_ai_memory
        from core.snapshot import validate_snapshot
        survey_to_ai_memory(self.uid, {'role':'student', 'availability':'Rảnh chiều thứ ba'})
        snapshot = Workspace.sync_snapshot(self.uid)
        validate_snapshot(snapshot)
        profile = next(m for m in snapshot['memories'] if m['key'] == 'planning_profile')
        import json
        self.assertEqual(json.loads(profile['value'])['availability'], 'Rảnh chiều thứ ba')

    def test_invalid_subtask_or_past_slot_no_partial_task(self):
        item = self.item(False)
        item['subtasks'][0]['estimated_minutes'] = 'wrong'
        with self.assertRaises(ValueError):
            save_suggestion(self.uid, item, 'invalid')
        item = self.item()
        item.update(start_at='2000-01-01T09:00', end_at='2000-01-01T10:00')
        with self.assertRaisesRegex(ValueError, 'đã qua'):
            save_suggestion(self.uid, item, 'past')
        self.assertEqual(Storage.get_tasks(self.uid), [])

    def test_partial_survey_does_not_manufacture_answers(self):
        from screens.onboarding_screen import survey_to_ai_memory
        survey_to_ai_memory(self.uid, {'role':'student'})
        user = next(u for u in Storage.get_users() if u.id == self.uid)
        self.assertEqual(user.settings['planning_profile'], {'role':'student'})
        from core.services import AIMemoryService
        self.assertIsNone(AIMemoryService.recall_value(self.uid, 'preference', 'peak_hours'))
        self.assertTrue(AIMemoryService.recall_value(self.uid, 'system', 'onboarding_done'))

    def test_prompt_shared_and_context_no_default_profile(self):
        from utils.ai_helper import _get_system_prompt, _build_context
        from core.ai_planner_service import _get_planner_prompt, _make_fallback_plan
        from core.ai_policy import DOUMAR_POLICY
        self.assertIn(DOUMAR_POLICY, _get_system_prompt('context'))
        self.assertIn(DOUMAR_POLICY, _get_planner_prompt('context'))
        context = _build_context(self.uid)
        self.assertIn('[ACCOUNT TIME]', context)
        self.assertIn('[SAVED CALENDAR', context)
        self.assertNotIn('Giờ làm việc: 08:00', context)
        self.assertFalse(_make_fallback_plan('mai đi du lịch')['ready_to_save'])

    def test_draft_cannot_save_and_ready_plan_confirmation(self):
        import flet as ft
        from components.ai_plan import build_plan
        page = SimpleNamespace(update=lambda: None)
        draft = {'suggested_tasks':[self.item(False)], 'ready_to_save':False}
        card = build_plan(draft, page, self.uid, lambda: None, lambda _: None)
        def controls(node):
            yield node
            for child in getattr(node, 'controls', []) or []:
                yield from controls(child)
            content = getattr(node, 'content', None)
            if isinstance(content, ft.Control):
                yield from controls(content)
        buttons = [c for c in controls(card) if isinstance(c, ft.TextButton) and c.content == 'Xác nhận lưu']
        self.assertTrue(buttons[0].disabled)
        buttons[0].on_click(None)
        self.assertEqual(Storage.get_tasks(self.uid), [])
        draft['ready_to_save'] = True
        card = build_plan(draft, page, self.uid, lambda: None, lambda _: None)
        button = next(c for c in controls(card) if isinstance(c, ft.TextButton) and c.content == 'Xác nhận lưu')
        button.on_click(None)
        self.assertEqual(len(Storage.get_tasks(self.uid)), 1)
        button.on_click(None)
        self.assertEqual(len(Storage.get_tasks(self.uid)), 1)


class FolderFocusTests(unittest.TestCase):
    def setUp(self):
        import uuid
        from core.task_focus import TaskFocus
        self.focus = TaskFocus
        self.uid = str(uuid.uuid4())
        self.task_id = str(uuid.uuid4())
        Storage.save_user(User(id=self.uid, username=self.uid, email=self.uid+'@test.invalid', password_hash='test'))
        Storage.save_task(Task(id=self.task_id, user_id=self.uid, title='Thư mục dự án', due_date='2000-01-01',
                              subtasks=[{'title':'Việc đầu'}, {'title':'Việc sau'}]))
        self.task = self.focus.ensure_ids(self.uid, self.task_id)
        self.first, self.second = [s['id'] for s in self.task.subtasks]

    def test_legacy_children_receive_stable_ids(self):
        self.assertNotEqual(self.first, self.second)
        self.assertEqual(self.focus.ensure_ids(self.uid,self.task_id).subtasks, self.task.subtasks)

    def test_target_survives_reorder_and_same_target_is_idempotent(self):
        target = self.focus.start(self.uid,self.task_id,self.first)
        task = self.focus.task(self.uid,self.task_id)
        task.subtasks.reverse()
        Storage.save_task(task)
        current = self.focus.current(self.uid)
        self.assertEqual(current['subtask_id'], self.first)
        self.assertEqual(self.focus.start(self.uid,self.task_id,self.first)['session_id'],target['session_id'])
        with self.assertRaisesRegex(ValueError,'kết thúc phiên'):
            self.focus.start(self.uid,self.task_id,self.second)
        from core.orm import WorkSessionModel
        with SessionLocal() as db:
            self.assertEqual(db.query(WorkSessionModel).filter_by(user_id=self.uid,ended_at=None).count(),1)

    def test_completing_target_stops_timer_and_finishing_all_completes_parent(self):
        self.focus.start(self.uid,self.task_id,self.first)
        self.focus.set_done(self.uid,self.task_id,self.first,True)
        self.assertIsNone(self.focus.current(self.uid))
        task = self.focus.set_done(self.uid,self.task_id,self.second,True)
        self.assertEqual(task.status,'done')
        self.assertFalse(task.is_overdue)
        self.assertEqual(task.subtask_progress,(2,2))
        self.assertTrue(task.subtasks[0]['completed_at'])
        self.focus.set_done(self.uid,self.task_id,self.first,False)
        self.assertTrue(self.focus.task(self.uid,self.task_id).is_overdue)

    def test_stopping_focus_records_time_once_without_completing(self):
        target=self.focus.start(self.uid,self.task_id,self.first)
        from core.orm import WorkSessionModel
        with SessionLocal.begin() as db:
            row=db.get(WorkSessionModel,target['session_id'])
            row.started_at=(datetime.now()-timedelta(minutes=7)).isoformat()
        self.assertEqual(self.focus.stop(self.uid,target['session_id']),7)
        self.assertEqual(self.focus.stop(self.uid,target['session_id']),7)
        task=self.focus.task(self.uid,self.task_id)
        self.assertEqual(task.actual_minutes,7)
        self.assertEqual(task.subtasks[0]['actual_minutes'],7)
        self.assertEqual(task.subtask_progress,(0,2))

    def test_foreign_account_cannot_read_target_start_or_complete(self):
        other=self.uid+'-other'
        Storage.save_user(User(id=other,username=other,email=other+'@test.invalid',password_hash='test'))
        target=self.focus.start(self.uid,self.task_id,self.first)
        self.assertIsNone(self.focus.current(other))
        for action in [lambda:self.focus.start(other,self.task_id,self.first),
                       lambda:self.focus.set_done(other,self.task_id,self.first,True),
                       lambda:self.focus.stop(other,target['session_id'])]:
            with self.assertRaises(ValueError):
                action()
        self.assertEqual(self.focus.current(self.uid)['session_id'],target['session_id'])

    def test_completed_child_not_focusable_and_add_reopens_folder(self):
        self.focus.set_done(self.uid,self.task_id,self.first,True)
        with self.assertRaises(ValueError):
            self.focus.start(self.uid,self.task_id,self.first)
        self.focus.set_done(self.uid,self.task_id,self.second,True)
        task=self.focus.add_child(self.uid,self.task_id,'Bước bổ sung')
        self.assertEqual(task.status,'in_progress')
        self.assertEqual(task.subtask_progress,(2,3))

    def test_standalone_task_can_focus_complete_and_reopen(self):
        plain = Task(id=self.task_id+'-plain',user_id=self.uid,title='Một việc độc lập')
        Storage.save_task(plain)
        self.focus.start(self.uid,plain.id)
        result = self.focus.set_task_done(self.uid,plain.id,True)
        self.assertEqual(result.status,'done')
        self.assertIsNone(self.focus.current(self.uid))
        self.assertEqual(self.focus.set_task_done(self.uid,plain.id,False).status,'todo')
        with self.assertRaisesRegex(ValueError,'từng việc nhỏ'):
            self.focus.set_task_done(self.uid,self.task_id,True)

    def test_completing_another_child_keeps_current_target_running(self):
        target=self.focus.start(self.uid,self.task_id,self.first)
        self.focus.set_done(self.uid,self.task_id,self.second,True)
        self.assertEqual(self.focus.current(self.uid)['session_id'],target['session_id'])

    def test_folder_navigation_and_inline_completion_controls(self):
        import core.compat
        import flet as ft
        from screens.desktop_screen import build_tasks
        from screens.task_folder_screen import build_task_folder
        page=SimpleNamespace(update=lambda:None,overlay=[],on_keyboard_event=None)
        visited=[]
        nav=lambda route,**kwargs:visited.append((route,kwargs))
        user=next(u for u in Storage.get_users() if u.id==self.uid)
        def controls(node):
            yield node
            for child in getattr(node,'controls',[]) or []:
                yield from controls(child)
            content=getattr(node,'content',None)
            if isinstance(content,ft.Control):
                yield from controls(content)
        root=build_tasks(page,user,nav)
        folder=next(c for c in controls(root) if isinstance(c,ft.IconButton) and c.tooltip=='Mở thư mục công việc')
        folder.on_click(None)
        self.assertEqual(visited[-1],('task_folder',{'task_id':self.task_id}))
        view=build_task_folder(page,user,nav,self.task_id)
        check=next(c for c in controls(view) if isinstance(c,ft.Checkbox))
        check.on_change(SimpleNamespace(control=SimpleNamespace(value=True)))
        self.assertEqual(self.focus.task(self.uid,self.task_id).subtask_progress,(1,2))
        quick = next(c for c in controls(root) if isinstance(c,ft.TextField) and c.hint_text == 'Thêm thư mục công việc rồi nhấn Enter')
        quick.value = 'Thư mục chưa có hạn'
        quick.on_submit(None)
        created = next(t for t in Storage.get_tasks(self.uid) if t.title == quick.value or t.title == 'Thư mục chưa có hạn')
        self.assertIsNone(created.due_date)


if __name__ == '__main__':
    unittest.main()

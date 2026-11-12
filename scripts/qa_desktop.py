"""Render actual Flet screen builders with an isolated QA account and fake access."""
import os
import sys
import tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
TMP=tempfile.TemporaryDirectory(prefix='doumar-ui-qa-')
os.environ['DATABASE_URL']='sqlite:///'+TMP.name+'/desktop.db'
for key in ['TASKFLOW_API_URL','GEMINI_API_KEY','SMTP_HOST','TASKFLOW_PUBLIC_URL','GOOGLE_CLIENT_ID','GOOGLE_CLIENT_SECRET','STRIPE_SECRET_KEY','PAYOS_API_KEY']:
    os.environ[key]=''
import asyncio
import json
import time
from datetime import date
from unittest.mock import patch
import flet as ft
import core.compat
from core.models import User, Task, Project
from core.database import Storage
from core.access import Access
from core.task_focus import TaskFocus
from core.services import ProjectService
from screens.desktop_screen import build_tasks, build_editor, build_report
from screens.task_folder_screen import build_task_folder
from screens.workspace_screen import build_schedule, build_projects, build_data, build_trash, build_account_settings
from screens.auth_screen import build_auth_screen
from screens.onboarding_screen import build_onboarding_screen
from screens.ai_screen import build_ai_screen
from screens.upgrade_screen import build_upgrade, build_locked

OUT=ROOT/'reports'/'qa'/'screens';OUT.mkdir(parents=True,exist_ok=True)
user=User(id='qa-desktop',username='qa_desktop',email='qa-desktop@example.invalid',password_hash='test',full_name='Tài khoản kiểm thử')
Storage.save_user(user)
task=Task(id='qa-folder',user_id=user.id,title='Hoàn thiện báo cáo dự án',description='Nội dung minh họa để kiểm tra bố cục, không phải dữ liệu khách hàng.',subtasks=[{'id':'qa-a','title':'Tổng hợp số liệu','status':'done'},{'id':'qa-b','title':'Viết nội dung báo cáo','estimated_minutes':45},{'id':'qa-c','title':'Kiểm tra và gửi báo cáo'}])
Storage.save_task(task)
Storage.save_task(Task(id='qa-long',user_id=user.id,title='Một tên công việc rất dài để kiểm tra cách xuống dòng và thao tác khi không gian hiển thị bị giới hạn trên cửa sổ nhỏ',due_date=date.today().isoformat()))
nav=lambda *args,**kwargs:None
results=[]

async def main(page):
    page.theme_mode=ft.ThemeMode.LIGHT;page.bgcolor='#FFFFFF';page.padding=0;page.enable_screenshots=True
    paid=Access('pro','qa-only')
    with patch('core.access.access_for',return_value=paid),patch('core.access.require_feature'),patch('screens.upgrade_screen.access_for',return_value=paid):
        ProjectService.save_project(Project(id='qa-project',user_id=user.id,name='Dự án kiểm thử'))
        builders=[('tasks',lambda:build_tasks(page,user,nav)),('folder',lambda:build_task_folder(page,user,nav,task.id)),
                  ('editor',lambda:build_editor(page,user,nav,task=task)),('schedule',lambda:build_schedule(page,user,nav)),
                  ('projects',lambda:build_projects(page,user,nav)),('report',lambda:build_report(page,user,nav)),
                  ('data',lambda:build_data(page,user,nav)),('trash',lambda:build_trash(page,user,nav)),
                  ('settings',lambda:build_account_settings(page,user,nav,lambda:None)),
                  ('plans',lambda:build_upgrade(page,user,nav)),('onboarding',lambda:build_onboarding_screen(page,user,lambda:None)),
                  ('auth',lambda:build_auth_screen(page,lambda u:None)),('ai',lambda:build_ai_screen(page,user,nav,standalone=True)),
                  ('locked',lambda:build_locked(page,user,nav,'ai_images'))]
        for width,height in [(1280,820),(1040,600)]:
            page.window.width=width;page.window.height=height
            for name,builder in builders:
                start=time.perf_counter()
                try:
                    page.controls.clear();page.overlay.clear();control=builder()
                    if name == 'ai':
                        def texts(node):
                            if isinstance(node, ft.Text):
                                yield node.value
                            for child in getattr(node, 'controls', []) or []:
                                yield from texts(child)
                            content = getattr(node, 'content', None)
                            if isinstance(content, ft.Control):
                                yield from texts(content)
                        from core.i18n import t
                        assert t('ai_unconfigured') in list(texts(control)), 'AI header must reflect missing configuration'
                    side=ft.Container(ft.Column([ft.Text('Doumar · QA',size=18,weight=ft.FontWeight.W_600),ft.Text('Dữ liệu thử',size=13),ft.Text(name,size=14)],spacing=14),width=190,padding=20,bgcolor='#FAFAFA')
                    shot=ft.Screenshot(ft.Container(ft.Row([side,ft.Container(control,expand=True,padding=24,bgcolor='#FFFFFF')],expand=True,vertical_alignment=ft.CrossAxisAlignment.STRETCH),expand=True,bgcolor='#FFFFFF'),expand=True)
                    page.add(shot);await asyncio.sleep(.7)
                    raw=await shot.capture(pixel_ratio=1.0)
                    filename=f'{name}-{width}x{height}.png';(OUT/filename).write_bytes(raw)
                    results.append(dict(screen=name,width=width,height=height,status='PASS',file='screens/'+filename,seconds=round(time.perf_counter()-start,3)))
                    print('SCREEN PASS',name,width,height,flush=True)
                except Exception as exc:
                    import traceback
                    detail=traceback.format_exc();print('SCREEN ERROR',name,detail,flush=True)
                    results.append(dict(screen=name,width=width,height=height,status='ERROR',detail=detail))
        # Real native timer: verify it renders and advances, then complete its child.
        try:
            target=TaskFocus.start(user.id,task.id,'qa-b')
            control=build_task_folder(page,user,nav,task.id);page.controls.clear()
            shot=ft.Screenshot(ft.Container(control,expand=True,padding=24,bgcolor='#FFFFFF'),expand=True);page.add(shot)
            await asyncio.sleep(2)
            (OUT/'focus-running.png').write_bytes(await shot.capture(pixel_ratio=1.0))
            TaskFocus.set_done(user.id,task.id,'qa-b',True)
            assert TaskFocus.current(user.id) is None
            results.append(dict(screen='focus-native',status='PASS',file='screens/focus-running.png'))
        except Exception:
            import traceback
            results.append(dict(screen='focus-native',status='ERROR',detail=traceback.format_exc()))
    (OUT.parent/'desktop.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    print('SCREEN SUMMARY',len(results),sum(r['status']=='PASS' for r in results),flush=True)
    page.controls.clear();page.update();await asyncio.sleep(.1)
    await page.window.destroy()

if __name__=='__main__':ft.run(main, assets_dir=str(ROOT/'assets'))

"""
TaskFlow - Core package
Public API re-exports để backward-compat.
"""
from core.models import User, Task, WorkSession, BehaviorEvent, AIMemory, Project

# Importing pure models from the API server must not open a desktop database.
_SERVICES = {'AuthService', 'TaskService', 'ChatService', 'BehaviorService',
             'WorkSessionService', 'AnalyticsService', 'AIMemoryService'}
__all__ = ['User', 'Task', 'WorkSession', 'BehaviorEvent', 'AIMemory', 'Project', 'Storage',
           *_SERVICES, 'login', 'register', 'logout', 'get_current_user', 'hash_password']


def __getattr__(name):
    if name == 'Storage':
        from core.database import Storage
        value = Storage
    elif name in _SERVICES:
        from core import services
        value = getattr(services, name)
    else:
        raise AttributeError(name)
    globals()[name] = value
    return value


def _auth():
    from core.services import AuthService
    return AuthService

# Backward-compat aliases (dùng trong auth_screen cũ)
def login(username, password):
    return _auth().login(username, password)

def register(username, email, password, full_name=""):
    return _auth().register(username, email, password, full_name)

def logout():
    _auth().logout()

def get_current_user():
    return _auth().get_current_user()

def hash_password(password):
    return _auth().hash_password(password)

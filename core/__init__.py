"""
TaskFlow - Core package
Public API re-exports để backward-compat.
"""
from core.models import User, Task
from core.database import Storage
from core.services import AuthService, TaskService

# Backward-compat aliases (dùng trong auth_screen cũ)
def login(username, password):
    return AuthService.login(username, password)

def register(username, email, password, full_name=""):
    return AuthService.register(username, email, password, full_name)

def logout():
    AuthService.logout()

def get_current_user():
    return AuthService.get_current_user()

def hash_password(password):
    return AuthService.hash_password(password)

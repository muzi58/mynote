import os
import json
import hashlib
import time
import uuid
import shutil
from django.conf import settings

# 用户数据文件路径
USER_FILE = os.path.join(settings.USER_DATA_DIR, 'users.json')

def get_users():
    """获取所有用户信息"""
    if not os.path.exists(USER_FILE):
        return {}
    
    try:
        with open(USER_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def save_users(users):
    """保存用户信息"""
    with open(USER_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=4)

def hash_password(password):
    """密码加密"""
    return hashlib.sha256(password.encode()).hexdigest()

def create_user(username, password):
    """创建用户"""
    users = get_users()
    
    # 检查用户数量限制
    if len(users) >= 6:
        return False, "已达到最大用户数量限制（6名）"
    
    # 检查用户名是否已存在
    if username in users:
        return False, "用户名已存在"
    
    # 创建用户
    user_dir = os.path.join(settings.USER_DATA_DIR, username)
    os.makedirs(user_dir, exist_ok=True)
    
    # 创建用户笔记数据文件
    notes_file = os.path.join(user_dir, 'notes.json')
    with open(notes_file, 'w', encoding='utf-8') as f:
        json.dump({}, f)
    
    # 创建用户文件存储目录
    files_dir = os.path.join(user_dir, 'files')
    os.makedirs(files_dir, exist_ok=True)
    
    # 保存用户信息
    users[username] = {
        'password': hash_password(password),
        'created_at': time.time()
    }
    save_users(users)
    
    return True, "注册成功"

def authenticate(username, password):
    """验证用户"""
    users = get_users()
    if username not in users:
        return False
    
    if users[username]['password'] != hash_password(password):
        return False
    
    return True

def get_user_notes(username):
    """获取用户的所有笔记"""
    notes_file = os.path.join(settings.USER_DATA_DIR, username, 'notes.json')
    if not os.path.exists(notes_file):
        return {}
    
    try:
        with open(notes_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def save_user_notes(username, notes):
    """保存用户笔记"""
    notes_file = os.path.join(settings.USER_DATA_DIR, username, 'notes.json')
    with open(notes_file, 'w', encoding='utf-8') as f:
        json.dump(notes, f, ensure_ascii=False, indent=4)

def add_note_for_user(username, content, timestamp, file=None):
    """为用户添加笔记"""
    notes = get_user_notes(username)
    note_id = str(uuid.uuid4())
    
    note_data = {
        'id': note_id,
        'content': content,
        'timestamp': timestamp,
        'created_at': time.time(),
        'has_file': False,
        'file_name': ''
    }
    
    # 如果有文件，保存文件
    if file:
        file_dir = os.path.join(settings.USER_DATA_DIR, username, 'files')
        # 确保文件目录存在
        os.makedirs(file_dir, exist_ok=True)
        
        # 检查用户存储空间
        user_size = get_user_storage_size(username)
        if user_size + file.size > 50 * 1024 * 1024:  # 50MB
            return False, "存储空间不足，每个用户最多50MB"
        
        # 保存文件
        file_name = file.name
        file_path = os.path.join(file_dir, f"{note_id}_{file_name}")
        
        with open(file_path, 'wb+') as destination:
            for chunk in file.chunks():
                destination.write(chunk)
        
        note_data['has_file'] = True
        note_data['file_name'] = file_name
    
    notes[note_id] = note_data
    save_user_notes(username, notes)
    
    return True, note_id

def get_note(username, note_id):
    """获取用户的特定笔记"""
    notes = get_user_notes(username)
    return notes.get(note_id)

def update_note_for_user(username, note_id, content):
    """更新用户笔记"""
    notes = get_user_notes(username)
    if note_id not in notes:
        return False
    
    notes[note_id]['content'] = content
    save_user_notes(username, notes)
    return True

def delete_note_for_user(username, note_id):
    """删除用户笔记"""
    notes = get_user_notes(username)
    if note_id not in notes:
        return False
    
    # 如果有文件，删除文件
    if notes[note_id]['has_file']:
        file_dir = os.path.join(settings.USER_DATA_DIR, username, 'files')
        file_pattern = f"{note_id}_"
        
        for file_name in os.listdir(file_dir):
            if file_name.startswith(file_pattern):
                os.remove(os.path.join(file_dir, file_name))
    
    # 删除笔记
    del notes[note_id]
    save_user_notes(username, notes)
    return True

def get_user_storage_size(username):
    """获取用户存储空间使用量"""
    user_dir = os.path.join(settings.USER_DATA_DIR, username)
    total_size = 0
    
    for dirpath, dirnames, filenames in os.walk(user_dir):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            total_size += os.path.getsize(fp)
    
    return total_size
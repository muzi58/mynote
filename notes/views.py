import os
import json
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required as django_login_required
from django.contrib.auth.models import User
from django.conf import settings
from . import utils
import asyncio
import time

def login_required(view_func):
    """登录验证装饰器"""
    def wrapper(request, *args, **kwargs):
        if 'username' not in request.session:
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return wrapper

def home(request):
    """主页视图"""
    # 检查Django认证系统的登录状态
    if request.user.is_authenticated:
        username = request.user.username
        request.session['username'] = username  # 同时设置session
        
        # 如果是admin用户，重定向到管理员面板
        if username == 'admin':
            return redirect('admin_panel')
    elif 'username' not in request.session:
        return redirect('login')
    else:
        username = request.session['username']
        # 如果是admin用户，重定向到管理员面板
        if username == 'admin':
            return redirect('admin_panel')
    
    notes = utils.get_user_notes(username)
    
    # 按时间戳排序
    sorted_notes = sorted(
        [note for note in notes.values()],
        key=lambda x: x['timestamp'],
        reverse=True
    )
    
    # 计算用户已使用的空间
    user_data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'user_data', username)
    used_space = 0
    if os.path.exists(user_data_dir):
        for dirpath, dirnames, filenames in os.walk(user_data_dir):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                used_space += os.path.getsize(fp)
    
    # 转换为可读格式
    if used_space < 1024:
        used_space_str = f"{used_space} B"
    elif used_space < 1024 * 1024:
        used_space_str = f"{used_space / 1024:.2f} KB"
    else:
        used_space_str = f"{used_space / (1024 * 1024):.2f} MB"
    
    # 计算剩余空间
    total_space = 50 * 1024 * 1024  # 50MB
    remaining_space = total_space - used_space
    
    if remaining_space < 1024:
        remaining_space_str = f"{remaining_space} B"
    elif remaining_space < 1024 * 1024:
        remaining_space_str = f"{remaining_space / 1024:.2f} KB"
    else:
        remaining_space_str = f"{remaining_space / (1024 * 1024):.2f} MB"
    
    return render(request, 'notes/home.html', {
        'notes': sorted_notes,
        'username': username,
        'used_space': used_space_str,
        'remaining_space': remaining_space_str
    })

def login_view(request):
    """登录视图"""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        # 首先尝试从文件中验证
        users_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'users.json')
        user_authenticated = False
        
        if os.path.exists(users_file):
            with open(users_file, 'r') as f:
                users_data = json.load(f)
            
            for user_id, user_info in users_data.items():
                if user_info['username'] == username and user_info['password'] == password:
                    # 设置session
                    request.session['username'] = username
                    # 设置session过期时间为7天
                    request.session.set_expiry(7 * 24 * 60 * 60)  # 7天，单位为秒
                    user_authenticated = True
                    
                    # 同时尝试使用Django认证系统
                    try:
                        # 检查用户是否存在于Django系统中
                        user = User.objects.get(username=username)
                    except User.DoesNotExist:
                        # 如果不存在，创建用户
                        user = User.objects.create_user(username=username, password=password)
                    
                    # 登录Django系统
                    user = authenticate(username=username, password=password)
                    if user is not None:
                        login(request, user)
                    
                    # 如果是admin用户，重定向到管理员页面
                    if username == 'admin':
                        return redirect('admin_panel')
                    
                    return redirect('home')
        
        # 如果文件验证失败，尝试Django认证系统
        if not user_authenticated:
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                request.session['username'] = username
                # 设置session过期时间为7天
                request.session.set_expiry(7 * 24 * 60 * 60)  # 7天，单位为秒
                
                # 如果是admin用户，重定向到管理员页面
                if username == 'admin':
                    return redirect('admin_panel')
                
                return redirect('home')
            else:
                # 登录失败
                return render(request, 'notes/login.html', {'error': '用户名或密码不正确'})
    
    return render(request, 'notes/login.html')

def register(request):
    """用户注册视图"""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        
        # 验证密码是否匹配
        if password != confirm_password:
            return render(request, 'notes/register.html', {'error': '两次输入的密码不一致'})
        
        # 验证用户名是否已存在
        users_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'users.json')
        
        users_data = {}
        if os.path.exists(users_file):
            with open(users_file, 'r') as f:
                users_data = json.load(f)
            
            # 检查用户名是否已存在
            for user_id, user_info in users_data.items():
                if user_info['username'] == username:
                    return render(request, 'notes/register.html', {'error': '用户名已存在'})
        
        # 创建新用户
        new_user_id = str(len(users_data) + 1)
        users_data[new_user_id] = {
            'username': username,
            'password': password
        }
        
        # 保存用户数据
        with open(users_file, 'w') as f:
            json.dump(users_data, f, indent=4)
        
        # 创建用户笔记目录
        user_notes_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'user_notes', username)
        os.makedirs(user_notes_dir, exist_ok=True)
        
        # 登录用户
        user = authenticate(request, username=username, password=password)
        if user is None:
            # 如果用户不存在于Django认证系统，创建一个
            from django.contrib.auth.models import User
            user = User.objects.create_user(username=username, password=password)
        
        login(request, user)
        return redirect('home')
    
    return render(request, 'notes/register.html')

def logout_view(request):
    """注销视图"""
    # 清除Django认证
    logout(request)
    # 清除session
    if 'username' in request.session:
        del request.session['username']
    return redirect('login')

@login_required
def add_note(request):
    """添加笔记视图"""
    if request.method == 'POST':
        content = request.POST.get('content', '')
        timestamp = request.POST.get('timestamp', '')
        file = request.FILES.get('file')
        
        # 确保内容或文件至少有一项
        if not content.strip() and not file:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': '内容和附件至少填写一项'})
            messages.error(request, '内容和附件至少填写一项')
            return render(request, 'notes/add_note.html')
        
        username = request.session['username']
        success, result = utils.add_note_for_user(username, content, timestamp, file)
        
        if success:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'note_id': result})
            return redirect('home')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': result})
            messages.error(request, result)
    
    return render(request, 'notes/add_note.html')

@login_required
def note_detail(request, note_id):
    """笔记详情视图"""
    username = request.session['username']
    note = utils.get_note(username, note_id)
    
    if not note:
        messages.error(request, '笔记不存在')
        return redirect('home')
    
    return render(request, 'notes/note_detail.html', {'note': note})

@csrf_exempt
@login_required
def delete_note(request, note_id):
    """删除笔记视图"""
    if request.method == 'POST':
        username = request.session['username']
        success = utils.delete_note_for_user(username, note_id)
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': success})
        
        if success:
            messages.success(request, '笔记已删除')
        else:
            messages.error(request, '删除笔记失败')
        
        return redirect('home')
    
    return JsonResponse({'success': False, 'error': '方法不允许'})

@csrf_exempt
@login_required
def update_note(request, note_id):
    """更新笔记视图"""
    if request.method == 'POST':
        content = request.POST.get('content', '')
        username = request.session['username']
        
        success = utils.update_note_for_user(username, note_id, content)
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': success})
        
        if success:
            messages.success(request, '笔记已更新')
        else:
            messages.error(request, '更新笔记失败')
        
        return redirect('note_detail', note_id=note_id)
    
    return JsonResponse({'success': False, 'error': '方法不允许'})

@csrf_exempt
@login_required
def copy_note(request, note_id):
    """复制笔记内容"""
    if request.method == 'POST':
        username = request.session['username']
        note = utils.get_note(username, note_id)
        
        if note:
            return JsonResponse({'success': True, 'content': note['content']})
        
        return JsonResponse({'success': False, 'error': '笔记不存在'})
    
    return JsonResponse({'success': False, 'error': '方法不允许'})

@login_required
def download_file(request, note_id):
    """下载笔记附件"""
    username = request.session['username']
    note = utils.get_note(username, note_id)
    
    if not note or not note.get('file_name'):
        messages.error(request, '文件不存在')
        return redirect('note_detail', note_id=note_id)
    
    # 直接构建正确的文件路径
    base_dir = os.path.dirname(os.path.dirname(__file__))
    file_name = note.get('file_name')
    file_path = os.path.join(base_dir, 'user_data', username, 'files', file_name)
    
    # 如果文件名包含UUID前缀，尝试查找匹配的文件
    if not os.path.exists(file_path):
        files_dir = os.path.join(base_dir, 'user_data', username, 'files')
        if os.path.exists(files_dir):
            for filename in os.listdir(files_dir):
                if filename.endswith(file_name):
                    file_path = os.path.join(files_dir, filename)
                    break
    
    # 检查文件是否存在
    if not os.path.exists(file_path):
        messages.error(request, f'文件不存在: {file_path}')
        return redirect('note_detail', note_id=note_id)
    
    # 读取文件内容
    try:
        with open(file_path, 'rb') as f:
            file_content = f.read()
        
        # 创建响应
        response = HttpResponse(file_content, content_type='application/octet-stream')
        response['Content-Disposition'] = f'attachment; filename="{file_name}"'
        
        return response
    except Exception as e:
        messages.error(request, f'下载文件失败: {str(e)}')
        return redirect('note_detail', note_id=note_id)

@login_required
def admin_panel(request):
    """管理员控制面板"""
    # 检查是否是管理员
    username = request.session.get('username')
    if username != 'admin' and request.user.username != 'admin':
        messages.error(request, '无权访问管理员面板')
        return redirect('home')
    
    # 获取所有用户信息
    users = []
    users_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'users.json')
    
    if os.path.exists(users_file):
        with open(users_file, 'r') as f:
            users_data = json.load(f)
            
            for user_id, user_info in users_data.items():
                # 计算用户占用空间 - 修正计算逻辑
                total_size = 0
                username = user_info['username']
                
                # 检查user_notes目录
                user_notes_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'user_notes', username)
                if os.path.exists(user_notes_dir):
                    for dirpath, dirnames, filenames in os.walk(user_notes_dir):
                        for f in filenames:
                            fp = os.path.join(dirpath, f)
                            total_size += os.path.getsize(fp)
                
                # 检查user_data目录
                user_data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'user_data', username)
                if os.path.exists(user_data_dir):
                    for dirpath, dirnames, filenames in os.walk(user_data_dir):
                        for f in filenames:
                            fp = os.path.join(dirpath, f)
                            total_size += os.path.getsize(fp)
                
                # 转换为可读格式
                if total_size < 1024:
                    space_used = f"{total_size} B"
                elif total_size < 1024 * 1024:
                    space_used = f"{total_size / 1024:.2f} KB"
                else:
                    space_used = f"{total_size / (1024 * 1024):.2f} MB"
                
                users.append({
                    'id': user_id,
                    'username': user_info['username'],
                    'password': user_info['password'],
                    'space_used': space_used
                })
    
    return render(request, 'notes/admin_panel.html', {'users': users})

@login_required
def update_user_password(request):
    """更新用户密码"""
    if request.method != 'POST' or request.user.username != 'admin':
        return JsonResponse({'success': False, 'error': '无权限'})
    
    user_id = request.POST.get('user_id')
    new_password = request.POST.get('new_password')
    
    if not user_id or not new_password:
        return JsonResponse({'success': False, 'error': '参数不完整'})
    
    users_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'users.json')
    
    if os.path.exists(users_file):
        with open(users_file, 'r') as f:
            users_data = json.load(f)
        
        if user_id in users_data:
            users_data[user_id]['password'] = new_password
            
            with open(users_file, 'w') as f:
                json.dump(users_data, f, indent=4)
            
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False, 'error': '用户不存在'})
    
    return JsonResponse({'success': False, 'error': '用户数据文件不存在'})

@login_required
def delete_user(request):
    """删除用户"""
    if request.method != 'POST' or request.user.username != 'admin':
        return JsonResponse({'success': False, 'error': '无权限'})
    
    user_id = request.POST.get('user_id')
    
    if not user_id:
        return JsonResponse({'success': False, 'error': '参数不完整'})
    
    users_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'users.json')
    
    if os.path.exists(users_file):
        with open(users_file, 'r') as f:
            users_data = json.load(f)
        
        if user_id in users_data:
            username = users_data[user_id]['username']
            
            # 删除用户数据
            user_notes_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'user_notes', username)
            if os.path.exists(user_notes_dir):
                import shutil
                shutil.rmtree(user_notes_dir)
            
            # 从用户文件中删除
            del users_data[user_id]
            
            with open(users_file, 'w') as f:
                json.dump(users_data, f, indent=4)
            
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False, 'error': '用户不存在'})
    
    return JsonResponse({'success': False, 'error': '用户数据文件不存在'})

def init_admin_user():
    """初始化管理员用户"""
    users_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'users.json')
    
    # 确保users.json文件存在
    if not os.path.exists(users_file):
        with open(users_file, 'w') as f:
            json.dump({}, f)
    
    # 读取用户数据
    with open(users_file, 'r') as f:
        users_data = json.load(f)
    
    # 检查admin用户是否已存在
    admin_exists = False
    for user_id, user_info in users_data.items():
        if user_info['username'] == 'admin':
            admin_exists = True
            # 更新admin密码
            user_info['password'] = '888888'
            break
    
    # 如果admin不存在，创建它
    if not admin_exists:
        new_user_id = str(len(users_data) + 1) if users_data else "1"
        users_data[new_user_id] = {
            'username': 'admin',
            'password': '888888'
        }
    
    # 保存用户数据
    with open(users_file, 'w') as f:
        json.dump(users_data, f, indent=4)
    
    # 创建admin用户目录
    admin_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'user_notes', 'admin')
    os.makedirs(admin_dir, exist_ok=True)
    
    # 确保user_data目录存在
    user_data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'user_data', 'admin', 'files')
    os.makedirs(user_data_dir, exist_ok=True)
    
    # 同时在Django认证系统中创建admin用户
    try:
        from django.contrib.auth.models import User
        try:
            admin_user = User.objects.get(username='admin')
            admin_user.set_password('888888')
            admin_user.is_staff = True
            admin_user.is_superuser = True
            admin_user.save()
        except User.DoesNotExist:
            User.objects.create_superuser(username='admin', email='admin@example.com', password='888888')
    except Exception as e:
        print(f"创建Django管理员用户时出错: {e}")

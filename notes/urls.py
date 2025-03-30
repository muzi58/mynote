from django.urls import path
from . import views

urlpatterns = [
    # 现有的URL路径
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register, name='register'),
    path('add/', views.add_note, name='add_note'),
    path('note/<str:note_id>/', views.note_detail, name='note_detail'),
    path('update/<str:note_id>/', views.update_note, name='update_note'),
    path('delete/<str:note_id>/', views.delete_note, name='delete_note'),
    # 添加下载文件的URL路径
    path('download/<str:note_id>/', views.download_file, name='download_file'),
    
    # 管理员相关的URL路径
    path('admin-panel/', views.admin_panel, name='admin_panel'),
    path('update-user-password/', views.update_user_password, name='update_user_password'),
    path('delete-user/', views.delete_user, name='delete_user'),
]
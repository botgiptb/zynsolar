from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('settings/', views.SettingsView.as_view(), name='settings'),
    path('profile/', views.UserProfileView.as_view(), name='profile'),
    path('team/', views.TeamListView.as_view(), name='team_list'),
    path('team/create/', views.TeamMemberCreateView.as_view(), name='team_create'),
    path('team/<int:pk>/', views.TeamMemberDetailView.as_view(), name='team_detail'),
    path('team/<int:pk>/edit/', views.TeamMemberUpdateView.as_view(), name='team_update'),
    path('team/<int:pk>/delete/', views.TeamMemberDeleteView.as_view(), name='team_delete'),
    path('team/<int:pk>/toggle-active/', views.TeamMemberToggleActiveView.as_view(), name='team_toggle_active'),
    path('team/sync-users/', views.TeamSyncUsersView.as_view(), name='team_sync_users'),
    path('users/', views.UserListView.as_view(), name='user_list'),
    path('users/create/', views.UserCreateView.as_view(), name='user_create'),
    path('users/<int:pk>/toggle-active/', views.UserToggleActiveView.as_view(), name='user_toggle_active'),
    path('teams/create/', views.TeamCreateOperationalView.as_view(), name='team_create_operational'),
    path('teams/<int:pk>/', views.TeamOperationalDetailView.as_view(), name='team_operational_detail'),
    path('teams/<int:pk>/edit/', views.TeamUpdateOperationalView.as_view(), name='team_update_operational'),
    path('teams/<int:pk>/delete/', views.TeamDeleteOperationalView.as_view(), name='team_delete_operational'),
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('user-approvals/', views.UserApprovalListView.as_view(), name='user_approvals'),
    path('user-approvals/<int:pk>/approve/', views.UserApproveActionView.as_view(), name='user_approve'),
    path('user-approvals/<int:pk>/reject/', views.UserRejectActionView.as_view(), name='user_reject'),
    path('user-approvals/<int:pk>/delete/', views.UserDeleteActionView.as_view(), name='user_delete'),
    # Master Catalog Management APIs
    path('api/catalog/', views.CatalogItemAjaxView.as_view(), name='catalog_ajax'),
    path('api/catalog/<int:pk>/delete/', views.CatalogItemDeleteAjaxView.as_view(), name='catalog_delete_ajax'),
]

from django.urls import path
from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("about/", views.about, name="about"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("storage/", views.storage, name="storage"),
    path("water/", views.water, name="water"),
    path("adminpanel/", views.adminpanel, name="adminpanel"),
    path("login/", views.login_view, name="login"),
    path("login/faceid-verify/", views.faceid_verify, name="faceid_verify"),
    path("logout/", views.logout_view, name="logout"),
    path("user/", views.user, name="user"),
    path("faceid/setup/", views.faceid_setup, name="faceid_setup"),
    path("faceid/test/", views.faceid_test, name="faceid_test"),
    # API (интерактивные задачи/локации)
    path("api/admin/metrics/", views.api_admin_metrics, name="api_admin_metrics"),
    path("api/locations/", views.api_locations, name="api_locations"),
    path("api/users/", views.api_users, name="api_users"),
    path("api/tasks/", views.api_tasks, name="api_tasks"),
    path("api/tasks/<int:task_id>/", views.api_task_detail, name="api_task_detail"),
    path("api/storage/", views.api_storage, name="api_storage"),
    path("api/storage/<int:item_id>/", views.api_storage_detail, name="api_storage_detail"),
]
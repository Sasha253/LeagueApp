from django.urls import path

from . import views

urlpatterns = [
    path("register/", views.RegisterView.as_view(), name="register"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("refresh/", views.RefreshView.as_view(), name="refresh"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("me/", views.MeView.as_view(), name="me"),
    path("test-users/", views.TesterListView.as_view(), name="test-users"),
    path("test-users/<int:pk>/login/", views.TesterLoginView.as_view(), name="test-user-login"),
]

"""Notifications. `urlpatterns` go under /api/v1/."""

from django.urls import path

from . import views

urlpatterns = [
    path("inbox/", views.InboxView.as_view(), name="inbox"),
    path("inbox/summary/", views.InboxSummaryView.as_view(), name="inbox-summary"),
    path(
        "inbox/<int:notification_id>/", views.NotificationDetailView.as_view(), name="notification"
    ),
    path(
        "inbox/<int:notification_id>/read/", views.MarkReadView.as_view(), name="notification-read"
    ),
    path(
        "inbox/<int:notification_id>/answer/",
        views.AnswerView.as_view(),
        name="notification-answer",
    ),
    path("devices/", views.DeviceListView.as_view(), name="devices"),
    path("devices/<int:device_id>/", views.DeviceDetailView.as_view(), name="device"),
]

"""Bookings. `urlpatterns` go under /api/v1/; `club_urlpatterns` under /api/v1/clubs/{club_id}/."""

from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("me/bookings", views.MyBookingViewSet, basename="my-bookings")

urlpatterns = [
    path("bookings/clubs/", views.BookingClubListView.as_view(), name="booking-clubs"),
    path("bookings/policy/", views.PolicyView.as_view(), name="booking-policy"),
    path("bookings/availability/", views.AvailabilityView.as_view(), name="booking-availability"),
    *router.urls,
]

club_router = SimpleRouter()
club_router.register("bookings", views.ClubBookingViewSet, basename="club-bookings")

club_urlpatterns = [*club_router.urls]

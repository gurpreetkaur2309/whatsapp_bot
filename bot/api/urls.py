from django.urls import include, path
from rest_framework.routers import DefaultRouter

from bot.api import views

router = DefaultRouter()
router.register("stops", views.StopViewSet, basename="stop")
router.register("routes", views.RouteViewSet, basename="route")
router.register("bookings", views.BookingViewSet, basename="booking")

urlpatterns = [
    path("fare/", views.fare_quote, name="api-fare"),
    path("trips/", views.trip_search, name="api-trips"),
    path("bookings/create/", views.create_booking, name="api-booking-create"),
    path("", include(router.urls)),
]

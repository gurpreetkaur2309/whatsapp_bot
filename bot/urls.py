from django.urls import path
from . import views
from django.contrib.auth.views import LogoutView

urlpatterns = [
    path("whatsapp-bot/", views.whatsapp_bot, name="whatsapp_bot"),
    path('register/', views.register, name='register'),

    # User Login
    path('login/', views.login_view, name='login'),

    # Booking page (source and destination)
    path('booking/', views.booking_view, name='booking'),
    path('', views.index, name='index'),
    # Payment page and ticket generation
    path('logout/', LogoutView.as_view(next_page='index'), name='logout'), 
   
    path('payment/<int:booking_id>/', views.payment_view, name='payment_view'),  # Updated to accept booking_id

]

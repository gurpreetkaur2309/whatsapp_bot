from django.contrib.auth import views as auth_views
from django.urls import path

from bot import views
from bot.webhooks.twilio import whatsapp_webhook

urlpatterns = [
    path("", views.home, name="home"),
    path("search/", views.search, name="search"),
    path("checkout/", views.checkout, name="checkout"),
    path("routes/", views.routes, name="routes"),

    path("ticket/<str:pnr>/", views.ticket, name="ticket"),
    path("ticket/<str:pnr>/qr.png", views.ticket_qr, name="ticket_qr"),
    path("ticket/<str:pnr>/cancel/", views.cancel_ticket, name="cancel_ticket"),
    path("pnr/", views.pnr_lookup, name="pnr_lookup"),
    path("my-tickets/", views.my_tickets, name="my_tickets"),

    path("register/", views.register, name="register"),
    path("login/", auth_views.LoginView.as_view(template_name="bot/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),

    # Twilio posts here. CSRF-exempt, but signature-validated.
    path("webhook/whatsapp/", whatsapp_webhook, name="whatsapp_webhook"),
]

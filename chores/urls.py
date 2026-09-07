from django.urls import path

from . import views

urlpatterns = [
    path("", views.health, name="health"),
    path("identity/", views.choose_identity, name="choose_identity"),
    path("switch/", views.switch_identity, name="switch_identity"),
]

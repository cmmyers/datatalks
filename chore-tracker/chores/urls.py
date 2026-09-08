from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("health/", views.health, name="health"),
    path("identity/", views.choose_identity, name="choose_identity"),
    path("switch/", views.switch_identity, name="switch_identity"),
    path("chores/", views.chore_pool, name="chore_pool"),
    path("chores/<int:chore_id>/claim/", views.claim_chore, name="claim_chore"),
    path("chores/<int:chore_id>/release/", views.release_chore, name="release_chore"),
    path("chores/<int:chore_id>/complete/", views.complete_chore, name="complete_chore"),
    path("points/", views.points_board, name="points_board"),
]

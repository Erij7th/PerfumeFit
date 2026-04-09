from django.urls import path

from .views import fragrance_discovery, home, recommend

app_name = "recommender"

urlpatterns = [
    path("", home, name="home"),
    path("fragrance-discovery/", fragrance_discovery, name="fragrance_discovery"),
    path("api/recommend/", recommend, name="recommend"),
]

from django.urls import path

from . import views

app_name = "tutores"

urlpatterns = [
    path("", views.TutorListView.as_view(), name="tutor_list"),
    path("novo/", views.TutorCreateView.as_view(), name="tutor_create"),
    path("<int:pk>/", views.TutorDetailView.as_view(), name="tutor_detail"),
    path("<int:pk>/editar/", views.TutorUpdateView.as_view(), name="tutor_update"),
    path("pets/novo/", views.PetCreateView.as_view(), name="pet_create"),
    path("pets/<int:pk>/editar/", views.PetUpdateView.as_view(), name="pet_update"),
]

from django.urls import path

from . import views

app_name = "agenda"

urlpatterns = [
    path("", views.AgendaDiaView.as_view(), name="dia"),
    path("novo/", views.AgendamentoCreateView.as_view(), name="create"),
    path("<int:pk>/editar/", views.AgendamentoUpdateView.as_view(), name="update"),
    path("<int:pk>/situacao/", views.AgendamentoStatusView.as_view(), name="status"),
]

from django.urls import path

from . import views

app_name = "prontuario"

urlpatterns = [
    path("pet/<int:pk>/", views.PetProntuarioView.as_view(), name="pet_prontuario"),
    path("atendimentos/novo/", views.AtendimentoCreateView.as_view(), name="atendimento_create"),
    path("atendimentos/<int:pk>/", views.AtendimentoDetailView.as_view(), name="atendimento_detail"),
    path("atendimentos/<int:pk>/editar/", views.AtendimentoUpdateView.as_view(), name="atendimento_update"),
    path("atendimentos/<int:pk>/assinar/", views.AtendimentoAssinarView.as_view(), name="atendimento_assinar"),
    path("exames/novo/", views.ExameCreateView.as_view(), name="exame_create"),
    path("exames/<int:pk>/", views.ExameDetailView.as_view(), name="exame_detail"),
    path("anexos/novo/", views.AnexoCreateView.as_view(), name="anexo_create"),
    path("anexos/<int:pk>/baixar/", views.AnexoDownloadView.as_view(), name="anexo_download"),
    path("vacinas/nova/", views.VacinaCreateView.as_view(), name="vacina_create"),
    path("vacinas/alertas/", views.VacinasAlertasView.as_view(), name="vacinas_alertas"),
]

from django.contrib import admin

from clinicas.admin import TenantAdminMixin

from .models import Agendamento


@admin.register(Agendamento)
class AgendamentoAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ("inicio", "pet", "veterinario", "status", "unidade")
    list_filter = ("status", "unidade", "veterinario")
    search_fields = ("pet__nome", "pet__tutor__nome", "motivo")
    date_hierarchy = "inicio"

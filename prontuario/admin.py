from django.contrib import admin

from clinicas.admin import TenantAdminMixin

from .models import Vacina
from .permissoes import pode_acessar_clinico


@admin.register(Vacina)
class VacinaAdmin(TenantAdminMixin, admin.ModelAdmin):
    # Atendimentos ficam só nas telas do prontuario, que respeitam a regra de assinatura.
    list_display = ("nome", "pet", "data_aplicacao", "proxima_dose")
    list_filter = ("nome",)
    search_fields = ("nome", "pet__nome")

    def _clinico(self, request):
        return request.user.is_superuser or pode_acessar_clinico(request.user)

    def has_module_permission(self, request):
        return self._clinico(request)

    def has_view_permission(self, request, obj=None):
        return self._clinico(request)

    def has_add_permission(self, request):
        return self._clinico(request)

    def has_change_permission(self, request, obj=None):
        return self._clinico(request)

    def has_delete_permission(self, request, obj=None):
        return False

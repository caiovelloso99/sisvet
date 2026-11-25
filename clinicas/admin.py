from django.contrib import admin

from .models import Clinica, Unidade, Vinculo


def clinica_do_usuario(user):
    """Retorna a clínica do usuário logado, ou None se ele não tiver vínculo."""
    vinculo = getattr(user, "vinculo", None) if user.is_authenticated else None
    return vinculo.clinica if vinculo else None


class TenantAdminMixin:
    """
    Isola os dados por clínica no Django admin.

    - Superusuário enxerga tudo.
    - Demais usuários veem e editam só os registros da própria clínica.
    - Ao criar um registro, a clínica é preenchida automaticamente.
    """

    exclude_for_tenant = ("clinica",)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        clinica = clinica_do_usuario(request.user)
        return qs.filter(clinica=clinica) if clinica else qs.none()

    def get_exclude(self, request, obj=None):
        exclude = list(super().get_exclude(request, obj) or [])
        if not request.user.is_superuser:
            exclude.extend(self.exclude_for_tenant)
        return exclude

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser and not change:
            obj.clinica = clinica_do_usuario(request.user)
        super().save_model(request, obj, form, change)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Limita as opções de chave estrangeira à clínica do usuário
        if not request.user.is_superuser and db_field.name != "clinica":
            clinica = clinica_do_usuario(request.user)
            related_model = db_field.remote_field.model
            if hasattr(related_model, "clinica"):
                kwargs["queryset"] = related_model.objects.filter(clinica=clinica)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Clinica)
class ClinicaAdmin(admin.ModelAdmin):
    list_display = ("nome", "cnpj", "ativa", "criado_em")
    search_fields = ("nome", "cnpj")
    list_filter = ("ativa",)

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(Unidade)
class UnidadeAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ("nome", "cidade", "uf", "ativa")
    search_fields = ("nome", "cidade")
    list_filter = ("ativa", "uf")


@admin.register(Vinculo)
class VinculoAdmin(admin.ModelAdmin):
    list_display = ("usuario", "clinica", "papel")
    list_filter = ("papel", "clinica")
    search_fields = ("usuario__username", "clinica__nome")

    def has_module_permission(self, request):
        return request.user.is_superuser

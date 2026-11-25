from django.contrib import admin

from clinicas.admin import TenantAdminMixin

from .models import Pet, Tutor


class PetInline(TenantAdminMixin, admin.TabularInline):
    model = Pet
    extra = 0
    fields = ("nome", "especie", "raca", "sexo", "data_nascimento", "peso_kg", "castrado", "ativo")


@admin.register(Tutor)
class TutorAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ("nome", "telefone", "email", "criado_em")
    search_fields = ("nome", "cpf", "telefone", "email")
    inlines = [PetInline]

    def save_formset(self, request, form, formset, change):
        # Pets criados pelo inline herdam a clínica do tutor (o campo fica oculto).
        if formset.model is Pet:
            instances = formset.save(commit=False)
            for obj in instances:
                obj.clinica = form.instance.clinica
                obj.save()
            for obj in formset.deleted_objects:
                obj.delete()
            formset.save_m2m()
        else:
            super().save_formset(request, form, formset, change)


@admin.register(Pet)
class PetAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ("nome", "especie", "tutor", "sexo", "ativo")
    list_filter = ("especie", "sexo", "ativo")
    search_fields = ("nome", "raca", "tutor__nome")

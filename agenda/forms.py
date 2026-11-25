from django import forms
from django.contrib.auth import get_user_model

from clinicas.models import Unidade, Vinculo
from tutores.models import Pet

from .models import Agendamento

User = get_user_model()


class AgendamentoForm(forms.ModelForm):
    class Meta:
        model = Agendamento
        fields = ["unidade", "veterinario", "pet", "inicio", "duracao_min", "motivo", "observacoes"]
        widgets = {
            "inicio": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "observacoes": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {"duracao_min": "Duração (minutos)"}

    def __init__(self, *args, clinica, **kwargs):
        super().__init__(*args, **kwargs)
        self.clinica = clinica
        # Garante a clínica antes da validação, para a checagem de conflito funcionar
        self.instance.clinica = clinica
        self.fields["inicio"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["unidade"].queryset = Unidade.objects.filter(clinica=clinica, ativa=True)
        self.fields["unidade"].required = False
        self.fields["pet"].queryset = Pet.objects.filter(clinica=clinica, ativo=True).select_related("tutor")
        self.fields["veterinario"].queryset = User.objects.filter(
            vinculo__clinica=clinica,
            vinculo__papel=Vinculo.Papel.VETERINARIO,
            is_active=True,
        ).order_by("username")
        self.fields["veterinario"].label = "Veterinário(a)"
        self.fields["veterinario"].label_from_instance = lambda u: u.get_full_name() or u.get_username()

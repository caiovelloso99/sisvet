from django import forms
from django.db.models import Q

from agenda.models import Agendamento
from tutores.models import Pet

from .arquivos import validar_arquivo
from .models import Anexo, Atendimento, Exame, Vacina


class AtendimentoForm(forms.ModelForm):
    class Meta:
        model = Atendimento
        fields = [
            "pet",
            "agendamento",
            "data_hora",
            "queixa_principal",
            "anamnese",
            "exame_fisico",
            "peso_kg",
            "temperatura_c",
            "frequencia_cardiaca",
            "diagnostico",
            "conduta",
        ]
        widgets = {
            "data_hora": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "queixa_principal": forms.Textarea(attrs={"rows": 2}),
            "anamnese": forms.Textarea(attrs={"rows": 3}),
            "exame_fisico": forms.Textarea(attrs={"rows": 3}),
            "diagnostico": forms.Textarea(attrs={"rows": 2}),
            "conduta": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, clinica, **kwargs):
        super().__init__(*args, **kwargs)
        self.clinica = clinica
        self.instance.clinica = clinica
        self.fields["data_hora"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["pet"].queryset = Pet.objects.filter(clinica=clinica, ativo=True).select_related("tutor")
        # Só agendamentos ainda sem atendimento (ou o já vinculado a este registro)
        disponiveis = Q(atendimento__isnull=True)
        if self.instance.pk and self.instance.agendamento_id:
            disponiveis |= Q(pk=self.instance.agendamento_id)
        self.fields["agendamento"].queryset = (
            Agendamento.objects.filter(clinica=clinica).filter(disponiveis).select_related("pet")
        )
        self.fields["agendamento"].required = False
        self.fields["agendamento"].label = "Agendamento de origem"

    def clean(self):
        cleaned = super().clean()
        pet = cleaned.get("pet")
        agendamento = cleaned.get("agendamento")
        if agendamento and pet and agendamento.pet_id != pet.pk:
            self.add_error("agendamento", "O agendamento escolhido é de outro pet.")
        return cleaned


class VacinaForm(forms.ModelForm):
    class Meta:
        model = Vacina
        fields = ["pet", "nome", "data_aplicacao", "lote", "proxima_dose", "observacoes"]
        widgets = {
            "data_aplicacao": forms.DateInput(attrs={"type": "date"}),
            "proxima_dose": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, clinica, **kwargs):
        super().__init__(*args, **kwargs)
        self.clinica = clinica
        self.instance.clinica = clinica
        self.fields["pet"].queryset = Pet.objects.filter(clinica=clinica, ativo=True).select_related("tutor")


class ExameForm(forms.ModelForm):
    class Meta:
        model = Exame
        fields = ["pet", "atendimento", "tipo", "nome", "data_coleta", "laboratorio", "resultado"]
        widgets = {
            "data_coleta": forms.DateInput(attrs={"type": "date"}),
            "resultado": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, clinica, **kwargs):
        super().__init__(*args, **kwargs)
        self.clinica = clinica
        self.instance.clinica = clinica
        self.fields["pet"].queryset = Pet.objects.filter(clinica=clinica, ativo=True).select_related("tutor")
        self.fields["atendimento"].queryset = Atendimento.objects.filter(clinica=clinica)
        self.fields["atendimento"].required = False
        self.fields["atendimento"].label = "Atendimento relacionado"

    def clean(self):
        cleaned = super().clean()
        pet = cleaned.get("pet")
        atendimento = cleaned.get("atendimento")
        if atendimento and pet and atendimento.pet_id != pet.pk:
            self.add_error("atendimento", "O atendimento escolhido é de outro pet.")
        return cleaned


class AnexoForm(forms.ModelForm):
    class Meta:
        model = Anexo
        fields = ["arquivo"]
        widgets = {
            "arquivo": forms.ClearableFileInput(attrs={"accept": ".pdf,.jpg,.jpeg,.png,.webp"}),
        }
        labels = {"arquivo": "Arquivo (PDF ou imagem, até 10 MB)"}

    def __init__(self, *args, clinica=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.clinica = clinica

    def clean_arquivo(self):
        arquivo = self.cleaned_data["arquivo"]
        self.mime_type, self.extensao = validar_arquivo(arquivo)
        return arquivo

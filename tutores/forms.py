from django import forms

from .models import Pet, Tutor


class TutorForm(forms.ModelForm):
    class Meta:
        model = Tutor
        fields = ["nome", "cpf", "telefone", "email", "endereco", "observacoes"]
        widgets = {
            "observacoes": forms.Textarea(attrs={"rows": 3}),
        }


class PetForm(forms.ModelForm):
    class Meta:
        model = Pet
        fields = [
            "tutor",
            "nome",
            "especie",
            "raca",
            "sexo",
            "data_nascimento",
            "peso_kg",
            "castrado",
            "observacoes",
            "ativo",
        ]
        widgets = {
            "data_nascimento": forms.DateInput(attrs={"type": "date"}),
            "observacoes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, clinica=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Só permite escolher tutores da própria clínica
        if clinica is not None:
            self.fields["tutor"].queryset = Tutor.objects.filter(clinica=clinica)

from django.db import models

from clinicas.models import ClinicaModel


class Tutor(ClinicaModel):
    """Dono do animal (tutor)."""

    nome = models.CharField("nome", max_length=150)
    cpf = models.CharField("CPF", max_length=14, blank=True)
    telefone = models.CharField("telefone/WhatsApp", max_length=20, blank=True)
    email = models.EmailField("e-mail", blank=True)
    endereco = models.CharField("endereço", max_length=255, blank=True)
    observacoes = models.TextField("observações", blank=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        verbose_name = "tutor"
        verbose_name_plural = "tutores"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Pet(ClinicaModel):
    """Animal atendido pela clínica."""

    class Especie(models.TextChoices):
        CAO = "cao", "Cão"
        GATO = "gato", "Gato"
        AVE = "ave", "Ave"
        ROEDOR = "roedor", "Roedor"
        REPTIL = "reptil", "Réptil"
        OUTRO = "outro", "Outro"

    class Sexo(models.TextChoices):
        MACHO = "M", "Macho"
        FEMEA = "F", "Fêmea"
        INDEFINIDO = "I", "Indefinido"

    tutor = models.ForeignKey(Tutor, on_delete=models.PROTECT, related_name="pets", verbose_name="tutor")
    nome = models.CharField("nome", max_length=100)
    especie = models.CharField("espécie", max_length=20, choices=Especie.choices)
    raca = models.CharField("raça", max_length=100, blank=True)
    sexo = models.CharField("sexo", max_length=1, choices=Sexo.choices, default=Sexo.INDEFINIDO)
    data_nascimento = models.DateField("data de nascimento", null=True, blank=True)
    peso_kg = models.DecimalField("peso (kg)", max_digits=6, decimal_places=2, null=True, blank=True)
    castrado = models.BooleanField("castrado", default=False)
    observacoes = models.TextField("observações", blank=True)
    ativo = models.BooleanField("ativo", default=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        verbose_name = "pet"
        verbose_name_plural = "pets"
        ordering = ["nome"]

    def __str__(self):
        return f"{self.nome} ({self.get_especie_display()})"

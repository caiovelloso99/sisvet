from django.conf import settings
from django.db import models


class Clinica(models.Model):
    """Cliente do SisVet. Todo dado de negócio pertence a uma clínica (multi-tenant)."""

    nome = models.CharField("nome", max_length=150)
    cnpj = models.CharField("CNPJ", max_length=18, blank=True)
    ativa = models.BooleanField("ativa", default=True)
    criado_em = models.DateTimeField("criada em", auto_now_add=True)

    class Meta:
        verbose_name = "clínica"
        verbose_name_plural = "clínicas"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Unidade(models.Model):
    """Unidade física de uma clínica (uma clínica pode ter várias)."""

    clinica = models.ForeignKey(Clinica, on_delete=models.CASCADE, related_name="unidades")
    nome = models.CharField("nome", max_length=150)
    endereco = models.CharField("endereço", max_length=255, blank=True)
    cidade = models.CharField("cidade", max_length=100, blank=True)
    uf = models.CharField("UF", max_length=2, blank=True)
    ativa = models.BooleanField("ativa", default=True)

    class Meta:
        verbose_name = "unidade"
        verbose_name_plural = "unidades"
        ordering = ["nome"]

    def __str__(self):
        return f"{self.nome} ({self.clinica})"


class Vinculo(models.Model):
    """Liga um usuário do sistema a uma clínica, com um papel definido."""

    class Papel(models.TextChoices):
        DONO = "dono", "Dono(a)"
        GERENTE = "gerente", "Gerente"
        VETERINARIO = "veterinario", "Veterinário(a)"
        RECEPCAO = "recepcao", "Recepção"
        FINANCEIRO = "financeiro", "Financeiro"

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="vinculo",
        verbose_name="usuário",
    )
    clinica = models.ForeignKey(Clinica, on_delete=models.CASCADE, related_name="vinculos")
    papel = models.CharField("papel", max_length=20, choices=Papel.choices)

    class Meta:
        verbose_name = "vínculo"
        verbose_name_plural = "vínculos"

    def __str__(self):
        return f"{self.usuario} · {self.get_papel_display()} · {self.clinica}"


class ClinicaModel(models.Model):
    """Base abstrata para qualquer modelo de negócio. Garante o isolamento por clínica."""

    clinica = models.ForeignKey(Clinica, on_delete=models.CASCADE, related_name="+")

    class Meta:
        abstract = True

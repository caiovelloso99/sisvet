from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from clinicas.models import ClinicaModel, Unidade
from tutores.models import Pet

# Duração máxima de um atendimento; limita a janela de busca de conflitos.
DURACAO_MAXIMA_MIN = 720


class Agendamento(ClinicaModel):
    """Horário marcado para um pet com um veterinário."""

    class Status(models.TextChoices):
        AGENDADO = "agendado", "Agendado"
        CONFIRMADO = "confirmado", "Confirmado"
        EM_ATENDIMENTO = "em_atendimento", "Em atendimento"
        CONCLUIDO = "concluido", "Concluído"
        FALTOU = "faltou", "Faltou"
        CANCELADO = "cancelado", "Cancelado"

    # Situações que liberam o horário do veterinário
    STATUS_LIBERADOS = (Status.CANCELADO, Status.FALTOU)

    unidade = models.ForeignKey(
        Unidade,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="agendamentos",
        verbose_name="unidade",
    )
    veterinario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="agendamentos_veterinario",
        verbose_name="veterinário(a)",
    )
    pet = models.ForeignKey(Pet, on_delete=models.PROTECT, related_name="agendamentos", verbose_name="pet")
    inicio = models.DateTimeField("início")
    duracao_min = models.PositiveSmallIntegerField(
        "duração (minutos)",
        default=30,
        validators=[MinValueValidator(5), MaxValueValidator(DURACAO_MAXIMA_MIN)],
    )
    motivo = models.CharField("motivo", max_length=200, blank=True)
    status = models.CharField("situação", max_length=20, choices=Status.choices, default=Status.AGENDADO)
    observacoes = models.TextField("observações", blank=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        verbose_name = "agendamento"
        verbose_name_plural = "agendamentos"
        ordering = ["inicio"]
        indexes = [models.Index(fields=["clinica", "inicio"])]

    def __str__(self):
        return f"{self.pet} · {timezone.localtime(self.inicio):%d/%m %H:%M}"

    @property
    def fim(self):
        return self.inicio + timedelta(minutes=self.duracao_min)

    def conflitos(self):
        """Agendamentos ativos do mesmo veterinário que se sobrepõem a este horário."""
        if not (self.inicio and self.veterinario_id and self.clinica_id):
            return []
        qs = Agendamento.objects.filter(
            clinica_id=self.clinica_id,
            veterinario_id=self.veterinario_id,
            inicio__gte=self.inicio - timedelta(minutes=DURACAO_MAXIMA_MIN),
            inicio__lt=self.fim,
        ).exclude(status__in=self.STATUS_LIBERADOS).select_related("pet")
        if self.pk:
            qs = qs.exclude(pk=self.pk)
        return [a for a in qs if a.inicio < self.fim and a.fim > self.inicio]

    def clean(self):
        super().clean()
        if self.status in self.STATUS_LIBERADOS:
            return
        conflitos = self.conflitos()
        if conflitos:
            c = conflitos[0]
            raise ValidationError(
                f"Este veterinário já tem atendimento das "
                f"{timezone.localtime(c.inicio):%H:%M} às "
                f"{timezone.localtime(c.fim):%H:%M} (pet: {c.pet.nome})."
            )

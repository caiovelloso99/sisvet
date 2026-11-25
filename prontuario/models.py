import os

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from agenda.models import Agendamento
from clinicas.models import ClinicaModel
from tutores.models import Pet

from .arquivos import caminho_anexo


class AtendimentoBloqueado(Exception):
    """Levantada ao tentar alterar um atendimento já assinado."""


class Atendimento(ClinicaModel):
    """
    Registro clínico de uma consulta.

    Regras (ver CLAUDE.md, item 3):
    - Não é apagado fisicamente: a view de exclusão não existe e o método delete() é bloqueado.
    - Depois de assinado, não pode mais ser alterado. Correções exigem um novo atendimento.
    """

    pet = models.ForeignKey(Pet, on_delete=models.PROTECT, related_name="atendimentos", verbose_name="pet")
    veterinario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="atendimentos_realizados",
        verbose_name="veterinário(a)",
    )
    agendamento = models.OneToOneField(
        Agendamento,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="atendimento",
        verbose_name="agendamento",
    )
    data_hora = models.DateTimeField("data e hora", default=timezone.now)
    queixa_principal = models.TextField("queixa principal", blank=True)
    anamnese = models.TextField("anamnese (histórico)", blank=True)
    exame_fisico = models.TextField("exame físico", blank=True)
    peso_kg = models.DecimalField(
        "peso (kg)", max_digits=6, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0)],
    )
    temperatura_c = models.DecimalField(
        "temperatura (°C)", max_digits=4, decimal_places=1, null=True, blank=True,
        validators=[MinValueValidator(25), MaxValueValidator(45)],
    )
    frequencia_cardiaca = models.PositiveSmallIntegerField("frequência cardíaca (bpm)", null=True, blank=True)
    diagnostico = models.TextField("diagnóstico", blank=True)
    conduta = models.TextField("conduta e prescrição", blank=True)
    assinado_em = models.DateTimeField("assinado em", null=True, blank=True)
    assinado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="atendimentos_assinados",
        verbose_name="assinado por",
    )
    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)

    CAMPOS_CLINICOS = (
        "queixa_principal", "anamnese", "exame_fisico", "peso_kg", "temperatura_c",
        "frequencia_cardiaca", "diagnostico", "conduta", "data_hora", "pet", "veterinario",
    )

    class Meta:
        verbose_name = "atendimento"
        verbose_name_plural = "atendimentos"
        ordering = ["-data_hora"]
        indexes = [models.Index(fields=["clinica", "pet", "-data_hora"])]

    def __str__(self):
        return f"{self.pet} · {timezone.localtime(self.data_hora):%d/%m/%Y %H:%M}"

    @property
    def assinado(self):
        return self.assinado_em is not None

    def assinar(self, usuario):
        if self.assinado:
            raise AtendimentoBloqueado("Atendimento já assinado.")
        if not (self.diagnostico or self.conduta or self.queixa_principal):
            raise ValidationError("Preencha ao menos a queixa, o diagnóstico ou a conduta antes de assinar.")
        self.assinado_em = timezone.now()
        self.assinado_por = usuario
        self.save(update_fields=["assinado_em", "assinado_por", "atualizado_em"])

    def save(self, *args, **kwargs):
        if self.pk and self.assinado:
            # Confere no banco o estado anterior, para impedir alteração de registro assinado
            original = Atendimento.objects.filter(pk=self.pk).values("assinado_em").first()
            if original and original["assinado_em"] is not None:
                raise AtendimentoBloqueado("Registro assinado não pode ser alterado.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise AtendimentoBloqueado("Atendimentos não são apagados. Use um novo registro para correção.")


class Exame(ClinicaModel):
    """Resultado de exame (laboratório, imagem, outro). Append-only: não é editado nem apagado."""

    class Tipo(models.TextChoices):
        LABORATORIO = "laboratorio", "Laboratório"
        IMAGEM = "imagem", "Imagem (raio-X, ultrassom)"
        OUTRO = "outro", "Outro"

    pet = models.ForeignKey(Pet, on_delete=models.PROTECT, related_name="exames", verbose_name="pet")
    atendimento = models.ForeignKey(
        Atendimento,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="exames",
        verbose_name="atendimento",
    )
    tipo = models.CharField("tipo", max_length=20, choices=Tipo.choices, default=Tipo.LABORATORIO)
    nome = models.CharField("exame", max_length=150)
    data_coleta = models.DateField("data da coleta/realização", default=timezone.localdate)
    resultado = models.TextField("resultado / laudo resumido", blank=True)
    laboratorio = models.CharField("laboratório / clínica externa", max_length=150, blank=True)
    veterinario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="exames_registrados",
        verbose_name="registrado por",
    )
    criado_em = models.DateTimeField("registrado em", auto_now_add=True)

    class Meta:
        verbose_name = "exame"
        verbose_name_plural = "exames"
        ordering = ["-data_coleta", "-criado_em"]

    def __str__(self):
        return f"{self.nome} · {self.pet}"

    def save(self, *args, **kwargs):
        if self.pk:
            raise AtendimentoBloqueado("Exames registrados não são alterados. Crie um novo registro para correção.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise AtendimentoBloqueado("Exames não são apagados.")


def caminho_upload_anexo(instance, filename):
    """Nome aleatório em disco; o nome original fica só no banco."""
    extensao = os.path.splitext(filename)[1].lower()
    return caminho_anexo(instance.clinica_id, extensao)


class Anexo(ClinicaModel):
    """Arquivo enviado ao prontuário (PDF ou imagem), ligado a um exame, a um atendimento ou ao pet."""

    pet = models.ForeignKey(Pet, on_delete=models.PROTECT, related_name="anexos", verbose_name="pet")
    exame = models.ForeignKey(
        Exame, on_delete=models.PROTECT, null=True, blank=True, related_name="anexos", verbose_name="exame"
    )
    atendimento = models.ForeignKey(
        Atendimento, on_delete=models.PROTECT, null=True, blank=True, related_name="anexos", verbose_name="atendimento"
    )
    arquivo = models.FileField("arquivo", upload_to=caminho_upload_anexo, max_length=255)
    nome_original = models.CharField("nome original", max_length=200)
    tipo_mime = models.CharField("tipo", max_length=60)
    tamanho_bytes = models.PositiveIntegerField("tamanho (bytes)")
    enviado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="anexos_enviados",
        verbose_name="enviado por",
    )
    criado_em = models.DateTimeField("enviado em", auto_now_add=True)

    class Meta:
        verbose_name = "anexo"
        verbose_name_plural = "anexos"
        ordering = ["-criado_em"]

    def __str__(self):
        return self.nome_original

    @property
    def tamanho_legivel(self):
        if self.tamanho_bytes >= 1024 * 1024:
            return f"{self.tamanho_bytes / (1024 * 1024):.1f} MB"
        return f"{max(self.tamanho_bytes // 1024, 1)} KB"

    def save(self, *args, **kwargs):
        if self.pk:
            raise AtendimentoBloqueado("Anexos não são alterados. Envie um novo arquivo para correção.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise AtendimentoBloqueado("Anexos não são apagados.")


class Vacina(ClinicaModel):
    """Aplicação de vacina registrada no prontuário do pet."""

    pet = models.ForeignKey(Pet, on_delete=models.PROTECT, related_name="vacinas", verbose_name="pet")
    nome = models.CharField("vacina", max_length=100)
    data_aplicacao = models.DateField("data da aplicação")
    lote = models.CharField("lote", max_length=50, blank=True)
    proxima_dose = models.DateField("próxima dose", null=True, blank=True)
    veterinario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="vacinas_aplicadas",
        verbose_name="veterinário(a)",
    )
    observacoes = models.CharField("observações", max_length=200, blank=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        verbose_name = "vacina"
        verbose_name_plural = "vacinas"
        ordering = ["-data_aplicacao", "nome"]

    def __str__(self):
        return f"{self.nome} · {self.pet}"

    def delete(self, *args, **kwargs):
        raise ValidationError("Registros de vacina não são apagados.")

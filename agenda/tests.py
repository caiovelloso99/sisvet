from datetime import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from clinicas.models import Clinica, Vinculo
from tutores.models import Pet, Tutor

from .forms import AgendamentoForm
from .models import Agendamento

User = get_user_model()


def dt(hora, minuto=0, dia=10):
    return timezone.make_aware(datetime(2030, 1, dia, hora, minuto))


class AgendaBaseTest(TestCase):
    def setUp(self):
        self.clinica = Clinica.objects.create(nome="Clinica Agenda")
        self.outra = Clinica.objects.create(nome="Outra Clinica")

        self.recepcao = User.objects.create_user("recepcao", password="senha-forte-123")
        Vinculo.objects.create(usuario=self.recepcao, clinica=self.clinica, papel=Vinculo.Papel.RECEPCAO)

        self.vet1 = User.objects.create_user("vet1", password="senha-forte-123", first_name="Ana")
        Vinculo.objects.create(usuario=self.vet1, clinica=self.clinica, papel=Vinculo.Papel.VETERINARIO)
        self.vet2 = User.objects.create_user("vet2", password="senha-forte-123")
        Vinculo.objects.create(usuario=self.vet2, clinica=self.clinica, papel=Vinculo.Papel.VETERINARIO)
        self.vet_outra = User.objects.create_user("vet_outra", password="senha-forte-123")
        Vinculo.objects.create(usuario=self.vet_outra, clinica=self.outra, papel=Vinculo.Papel.VETERINARIO)

        self.tutor = Tutor.objects.create(clinica=self.clinica, nome="Maria")
        self.pet = Pet.objects.create(clinica=self.clinica, tutor=self.tutor, nome="Thor", especie=Pet.Especie.CAO)
        self.pet_outra = Pet.objects.create(
            clinica=self.outra,
            tutor=Tutor.objects.create(clinica=self.outra, nome="Outro"),
            nome="Bolinha",
            especie=Pet.Especie.GATO,
        )

    def agendar(self, hora, minuto=0, duracao=30, vet=None, pet=None, status=Agendamento.Status.AGENDADO):
        return Agendamento.objects.create(
            clinica=self.clinica,
            veterinario=vet or self.vet1,
            pet=pet or self.pet,
            inicio=dt(hora, minuto),
            duracao_min=duracao,
            status=status,
        )

    def form_data(self, hora, minuto=0, duracao=30, vet=None, pet=None):
        return {
            "veterinario": (vet or self.vet1).pk,
            "pet": (pet or self.pet).pk,
            "inicio": f"2030-01-10T{hora:02d}:{minuto:02d}",
            "duracao_min": duracao,
            "motivo": "Consulta",
        }


class ConflitoDeHorarioTest(AgendaBaseTest):
    def test_sobreposicao_do_mesmo_veterinario_e_bloqueada(self):
        self.agendar(10, 0, 30)
        form = AgendamentoForm(data=self.form_data(10, 15), clinica=self.clinica)
        self.assertFalse(form.is_valid())
        self.assertIn("já tem atendimento", str(form.non_field_errors()))

    def test_horarios_encostados_sao_permitidos(self):
        self.agendar(10, 0, 30)
        form = AgendamentoForm(data=self.form_data(10, 30), clinica=self.clinica)
        self.assertTrue(form.is_valid(), form.errors)

    def test_outro_veterinario_no_mesmo_horario_e_permitido(self):
        self.agendar(10, 0, 30, vet=self.vet1)
        form = AgendamentoForm(data=self.form_data(10, 0, vet=self.vet2), clinica=self.clinica)
        self.assertTrue(form.is_valid(), form.errors)

    def test_horario_cancelado_nao_bloqueia(self):
        self.agendar(10, 0, 30, status=Agendamento.Status.CANCELADO)
        form = AgendamentoForm(data=self.form_data(10, 0), clinica=self.clinica)
        self.assertTrue(form.is_valid(), form.errors)

    def test_reativar_cancelado_em_conflito_e_bloqueado_na_situacao(self):
        cancelado = self.agendar(10, 0, 30, status=Agendamento.Status.CANCELADO)
        self.agendar(10, 10, 30)
        self.client.force_login(self.recepcao)
        resp = self.client.post(
            reverse("agenda:status", args=[cancelado.pk]), {"status": Agendamento.Status.AGENDADO}, follow=True
        )
        cancelado.refresh_from_db()
        self.assertEqual(cancelado.status, Agendamento.Status.CANCELADO)
        self.assertContains(resp, "já tem atendimento")

    def test_edicao_nao_conflita_consigo_mesmo(self):
        ag = self.agendar(10, 0, 30)
        form = AgendamentoForm(data=self.form_data(10, 0), instance=ag, clinica=self.clinica)
        self.assertTrue(form.is_valid(), form.errors)


class FormRestricoesTest(AgendaBaseTest):
    def test_pets_e_veterinarios_limitados_a_clinica(self):
        form = AgendamentoForm(clinica=self.clinica)
        self.assertEqual(list(form.fields["pet"].queryset), [self.pet])
        vets = set(form.fields["veterinario"].queryset)
        self.assertIn(self.vet1, vets)
        self.assertIn(self.vet2, vets)
        self.assertNotIn(self.vet_outra, vets)
        self.assertNotIn(self.recepcao, vets)

    def test_pet_de_outra_clinica_e_rejeitado(self):
        form = AgendamentoForm(data=self.form_data(10, 0, pet=self.pet_outra), clinica=self.clinica)
        self.assertFalse(form.is_valid())
        self.assertIn("pet", form.errors)


class AgendaViewsTest(AgendaBaseTest):
    def test_agenda_exige_login(self):
        resp = self.client.get(reverse("agenda:dia"))
        self.assertEqual(resp.status_code, 302)

    def test_dia_mostra_apenas_agendamentos_da_clinica(self):
        self.agendar(9, 0)
        Agendamento.objects.create(
            clinica=self.outra,
            veterinario=self.vet_outra,
            pet=self.pet_outra,
            inicio=dt(9, 0),
            duracao_min=30,
        )
        self.client.force_login(self.recepcao)
        resp = self.client.get(reverse("agenda:dia"), {"data": "2030-01-10"})
        self.assertEqual(len(resp.context["agendamentos"]), 1)
        self.assertContains(resp, "Thor")
        self.assertNotContains(resp, "Bolinha")

    def test_criar_agendamento_pela_view(self):
        self.client.force_login(self.recepcao)
        resp = self.client.post(reverse("agenda:create"), self.form_data(14, 0))
        self.assertEqual(resp.status_code, 302)
        ag = Agendamento.objects.get(pet=self.pet)
        self.assertEqual(ag.clinica, self.clinica)
        self.assertEqual(timezone.localtime(ag.inicio).hour, 14)

    def test_mudar_situacao_para_concluido(self):
        ag = self.agendar(11, 0)
        self.client.force_login(self.recepcao)
        self.client.post(reverse("agenda:status", args=[ag.pk]), {"status": Agendamento.Status.CONCLUIDO})
        ag.refresh_from_db()
        self.assertEqual(ag.status, Agendamento.Status.CONCLUIDO)

    def test_situacao_de_outra_clinica_retorna_404(self):
        ag = Agendamento.objects.create(
            clinica=self.outra, veterinario=self.vet_outra, pet=self.pet_outra, inicio=dt(9, 0)
        )
        self.client.force_login(self.recepcao)
        resp = self.client.post(reverse("agenda:status", args=[ag.pk]), {"status": "cancelado"})
        self.assertEqual(resp.status_code, 404)

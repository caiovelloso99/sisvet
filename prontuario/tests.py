import os
import shutil
import tempfile
from datetime import date, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from agenda.models import Agendamento
from clinicas.models import Clinica, Vinculo
from tutores.models import Pet, Tutor

from .arquivos import nome_original_seguro, validar_arquivo
from .forms import AtendimentoForm, ExameForm
from .models import Anexo, Atendimento, AtendimentoBloqueado, Exame, Vacina

User = get_user_model()


class ProntuarioBaseTest(TestCase):
    def setUp(self):
        self.clinica = Clinica.objects.create(nome="Clinica Prontuario")
        self.outra = Clinica.objects.create(nome="Outra Clinica Prontuario")

        self.vet = self._usuario("vet", self.clinica, Vinculo.Papel.VETERINARIO)
        self.vet2 = self._usuario("vet2", self.clinica, Vinculo.Papel.VETERINARIO)
        self.dono = self._usuario("dono", self.clinica, Vinculo.Papel.DONO)
        self.recepcao = self._usuario("recepcao", self.clinica, Vinculo.Papel.RECEPCAO)
        self.vet_outra = self._usuario("vet_outra", self.outra, Vinculo.Papel.VETERINARIO)

        self.tutor = Tutor.objects.create(clinica=self.clinica, nome="Tutor A")
        self.pet = Pet.objects.create(clinica=self.clinica, tutor=self.tutor, nome="Thor", especie=Pet.Especie.CAO)
        self.pet_outra = Pet.objects.create(
            clinica=self.outra,
            tutor=Tutor.objects.create(clinica=self.outra, nome="Tutor B"),
            nome="Bolinha",
            especie=Pet.Especie.GATO,
        )

    def _usuario(self, username, clinica, papel):
        user = User.objects.create_user(username, password="senha-forte-123")
        Vinculo.objects.create(usuario=user, clinica=clinica, papel=papel)
        return user

    def atendimento(self, **kwargs):
        dados = dict(
            clinica=self.clinica,
            pet=self.pet,
            veterinario=self.vet,
            queixa_principal="Vômito",
            diagnostico="Gastroenterite",
        )
        dados.update(kwargs)
        return Atendimento.objects.create(**dados)


class AcessoClinicoTest(ProntuarioBaseTest):
    def test_recepcao_nao_acessa_prontuario(self):
        self.client.force_login(self.recepcao)
        resp = self.client.get(reverse("prontuario:pet_prontuario", args=[self.pet.pk]))
        self.assertEqual(resp.status_code, 403)

    def test_veterinario_acessa_prontuario(self):
        self.client.force_login(self.vet)
        resp = self.client.get(reverse("prontuario:pet_prontuario", args=[self.pet.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_dono_acessa_prontuario(self):
        self.client.force_login(self.dono)
        resp = self.client.get(reverse("prontuario:pet_prontuario", args=[self.pet.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_prontuario_de_pet_de_outra_clinica_retorna_404(self):
        self.client.force_login(self.vet_outra)
        resp = self.client.get(reverse("prontuario:pet_prontuario", args=[self.pet.pk]))
        self.assertEqual(resp.status_code, 404)

    def test_atendimento_de_outra_clinica_retorna_404(self):
        atend = self.atendimento()
        self.client.force_login(self.vet_outra)
        resp = self.client.get(reverse("prontuario:atendimento_detail", args=[atend.pk]))
        self.assertEqual(resp.status_code, 404)

    def test_anonimo_vai_para_login(self):
        resp = self.client.get(reverse("prontuario:pet_prontuario", args=[self.pet.pk]))
        self.assertEqual(resp.status_code, 302)


class ImutabilidadeTest(ProntuarioBaseTest):
    def test_assinar_torna_registro_somente_leitura(self):
        atend = self.atendimento()
        atend.assinar(self.vet)
        atend.refresh_from_db()
        self.assertTrue(atend.assinado)
        atend.diagnostico = "Alterado depois"
        with self.assertRaises(AtendimentoBloqueado):
            atend.save()
        atend.refresh_from_db()
        self.assertEqual(atend.diagnostico, "Gastroenterite")

    def test_post_de_edicao_em_registro_assinado_e_bloqueado(self):
        atend = self.atendimento()
        atend.assinar(self.vet)
        self.client.force_login(self.vet)
        self.client.post(
            reverse("prontuario:atendimento_update", args=[atend.pk]),
            {
                "pet": self.pet.pk,
                "data_hora": "2030-01-10T10:00",
                "queixa_principal": "Outra",
                "diagnostico": "Trocado",
                "conduta": "",
            },
        )
        atend.refresh_from_db()
        self.assertEqual(atend.diagnostico, "Gastroenterite")

    def test_atendimento_nao_pode_ser_apagado(self):
        atend = self.atendimento()
        with self.assertRaises(AtendimentoBloqueado):
            atend.delete()
        self.assertTrue(Atendimento.objects.filter(pk=atend.pk).exists())

    def test_assinar_sem_conteudo_e_recusado(self):
        atend = self.atendimento(queixa_principal="", diagnostico="", conduta="")
        with self.assertRaises(ValidationError):
            atend.assinar(self.vet)
        atend.refresh_from_db()
        self.assertFalse(atend.assinado)

    def test_vacina_nao_pode_ser_apagada(self):
        vacina = Vacina.objects.create(
            clinica=self.clinica, pet=self.pet, nome="V10", data_aplicacao=date(2030, 1, 1), veterinario=self.vet
        )
        with self.assertRaises(ValidationError):
            vacina.delete()
        self.assertTrue(Vacina.objects.filter(pk=vacina.pk).exists())


class CriacaoTest(ProntuarioBaseTest):
    def test_criar_atendimento_grava_clinica_e_veterinario_logado(self):
        self.client.force_login(self.vet)
        self.client.post(
            reverse("prontuario:atendimento_create"),
            {
                "pet": self.pet.pk,
                "data_hora": "2030-01-10T10:00",
                "queixa_principal": "Tosse",
                "diagnostico": "Traqueíte",
            },
        )
        atend = Atendimento.objects.get(queixa_principal="Tosse")
        self.assertEqual(atend.clinica, self.clinica)
        self.assertEqual(atend.veterinario, self.vet)

    def test_veterinario_nao_pode_ser_definido_pelo_formulario(self):
        self.client.force_login(self.vet)
        self.client.post(
            reverse("prontuario:atendimento_create"),
            {
                "pet": self.pet.pk,
                "data_hora": "2030-01-10T10:00",
                "queixa_principal": "Tosse",
                "veterinario": self.vet2.pk,
            },
        )
        atend = Atendimento.objects.get(queixa_principal="Tosse")
        self.assertEqual(atend.veterinario, self.vet)

    def test_formulario_nao_aceita_agendamento_de_outro_pet(self):
        outro_pet = Pet.objects.create(clinica=self.clinica, tutor=self.tutor, nome="Mel", especie=Pet.Especie.GATO)
        ag = Agendamento.objects.create(
            clinica=self.clinica, veterinario=self.vet, pet=outro_pet, inicio=timezone.now()
        )
        form = AtendimentoForm(
            data={"pet": self.pet.pk, "agendamento": ag.pk, "data_hora": "2030-01-10T10:00", "queixa_principal": "x"},
            clinica=self.clinica,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("agendamento", form.errors)

    def test_agendamento_ja_atendido_nao_e_oferecido(self):
        ag = Agendamento.objects.create(clinica=self.clinica, veterinario=self.vet, pet=self.pet, inicio=timezone.now())
        self.atendimento(agendamento=ag)
        form = AtendimentoForm(clinica=self.clinica)
        self.assertNotIn(ag, form.fields["agendamento"].queryset)

    def test_formulario_limita_pets_a_clinica(self):
        form = AtendimentoForm(clinica=self.clinica)
        self.assertEqual(list(form.fields["pet"].queryset), [self.pet])


class AlertasVacinaTest(ProntuarioBaseTest):
    def test_alertas_mostram_atrasadas_e_proximas_da_propria_clinica(self):
        hoje = timezone.localdate()
        Vacina.objects.create(
            clinica=self.clinica, pet=self.pet, nome="V10", data_aplicacao=hoje - timedelta(days=400),
            proxima_dose=hoje - timedelta(days=5), veterinario=self.vet,
        )
        Vacina.objects.create(
            clinica=self.clinica, pet=self.pet, nome="Raiva", data_aplicacao=hoje - timedelta(days=350),
            proxima_dose=hoje + timedelta(days=10), veterinario=self.vet,
        )
        Vacina.objects.create(
            clinica=self.outra, pet=self.pet_outra, nome="Outra", data_aplicacao=hoje,
            proxima_dose=hoje - timedelta(days=1), veterinario=self.vet_outra,
        )
        self.client.force_login(self.vet)
        resp = self.client.get(reverse("prontuario:vacinas_alertas"))
        self.assertEqual([v.nome for v in resp.context["atrasadas"]], ["V10"])
        self.assertEqual([v.nome for v in resp.context["proximas"]], ["Raiva"])
        self.assertNotContains(resp, "Bolinha")


# ---------------------------------------------------------------------------
# Exames e anexos
# ---------------------------------------------------------------------------

PDF_VALIDO = b"%PDF-1.4\n% conteudo de teste\n%%EOF\n"
PNG_VALIDO = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
WEBP_VALIDO = b"RIFF" + b"\x24\x00\x00\x00" + b"WEBP" + b"VP8 " + b"\x00" * 16


def _arquivo(nome, conteudo):
    return SimpleUploadedFile(nome, conteudo, content_type="application/octet-stream")


class ValidacaoArquivoTest(TestCase):
    def test_pdf_valido_e_aceito(self):
        mime, ext = validar_arquivo(_arquivo("laudo.pdf", PDF_VALIDO))
        self.assertEqual((mime, ext), ("application/pdf", ".pdf"))

    def test_png_e_webp_validos_sao_aceitos(self):
        self.assertEqual(validar_arquivo(_arquivo("foto.png", PNG_VALIDO))[1], ".png")
        self.assertEqual(validar_arquivo(_arquivo("foto.webp", WEBP_VALIDO))[1], ".webp")

    def test_executavel_renomeado_para_pdf_e_recusado(self):
        with self.assertRaises(ValidationError):
            validar_arquivo(_arquivo("laudo.pdf", b"MZ\x90\x00 programa"))

    def test_extensao_nao_permitida_e_recusada(self):
        with self.assertRaises(ValidationError):
            validar_arquivo(_arquivo("script.exe", PDF_VALIDO))

    def test_webp_sem_marca_webp_e_recusado(self):
        with self.assertRaises(ValidationError):
            validar_arquivo(_arquivo("foto.webp", b"RIFF" + b"\x00" * 20))

    def test_arquivo_vazio_e_recusado(self):
        with self.assertRaises(ValidationError):
            validar_arquivo(_arquivo("laudo.pdf", b""))

    @override_settings(ANEXO_TAMANHO_MAX_MB=0)
    def test_arquivo_acima_do_limite_e_recusado(self):
        with self.assertRaises(ValidationError):
            validar_arquivo(_arquivo("laudo.pdf", PDF_VALIDO))

    def test_nome_original_nao_carrega_caminho(self):
        self.assertEqual(nome_original_seguro("../../etc/Laudo final.pdf"), "Laudo final.pdf")
        self.assertEqual(nome_original_seguro("<script>.pdf"), "script.pdf")


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="sisvet_teste_"))
class ExameAnexoTest(ProntuarioBaseTest):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        super().setUp()
        self.exame = Exame.objects.create(
            clinica=self.clinica,
            pet=self.pet,
            nome="Hemograma",
            data_coleta=date(2030, 1, 5),
            veterinario=self.vet,
        )

    def upload(self, user, arquivo, exame=None):
        url = reverse("prontuario:anexo_create") + (f"?exame={exame.pk}" if exame else f"?pet={self.pet.pk}")
        self.client.force_login(user)
        return self.client.post(url, {"arquivo": arquivo})

    def test_veterinario_envia_pdf_ligado_ao_exame(self):
        resp = self.upload(self.vet, _arquivo("Laudo final.pdf", PDF_VALIDO), exame=self.exame)
        self.assertEqual(resp.status_code, 302)
        anexo = Anexo.objects.get()
        self.assertEqual(anexo.exame, self.exame)
        self.assertEqual(anexo.clinica, self.clinica)
        self.assertEqual(anexo.enviado_por, self.vet)
        self.assertEqual(anexo.nome_original, "Laudo final.pdf")
        self.assertEqual(anexo.tipo_mime, "application/pdf")
        self.assertTrue(os.path.exists(os.path.join(settings.MEDIA_ROOT, anexo.arquivo.name)))

    def test_nome_em_disco_nao_revela_nome_original(self):
        self.upload(self.vet, _arquivo("paciente-secreto.pdf", PDF_VALIDO), exame=self.exame)
        anexo = Anexo.objects.get()
        self.assertNotIn("paciente-secreto", anexo.arquivo.name)
        self.assertTrue(anexo.arquivo.name.endswith(".pdf"))

    def test_anexo_direto_ao_pet_sem_exame(self):
        self.upload(self.vet, _arquivo("foto.png", PNG_VALIDO))
        anexo = Anexo.objects.get()
        self.assertIsNone(anexo.exame)
        self.assertEqual(anexo.pet, self.pet)

    def test_arquivo_invalido_nao_e_salvo(self):
        resp = self.upload(self.vet, _arquivo("laudo.pdf", b"MZ\x90 falso"), exame=self.exame)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Anexo.objects.exists())

    def test_download_pelo_veterinario_entrega_como_anexo_com_cabecalhos_seguros(self):
        self.upload(self.vet, _arquivo("laudo.pdf", PDF_VALIDO), exame=self.exame)
        anexo = Anexo.objects.get()
        self.client.force_login(self.vet)
        resp = self.client.get(reverse("prontuario:anexo_download", args=[anexo.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(b"".join(resp.streaming_content), PDF_VALIDO)
        self.assertIn("attachment", resp["Content-Disposition"])
        self.assertEqual(resp["X-Content-Type-Options"], "nosniff")
        self.assertIn("no-store", resp["Cache-Control"])

    def test_download_com_abrir_usa_inline(self):
        self.upload(self.vet, _arquivo("laudo.pdf", PDF_VALIDO), exame=self.exame)
        anexo = Anexo.objects.get()
        self.client.force_login(self.vet)
        resp = self.client.get(reverse("prontuario:anexo_download", args=[anexo.pk]) + "?abrir=1")
        self.assertIn("inline", resp["Content-Disposition"])

    def test_download_de_outra_clinica_retorna_404(self):
        self.upload(self.vet, _arquivo("laudo.pdf", PDF_VALIDO), exame=self.exame)
        anexo = Anexo.objects.get()
        self.client.force_login(self.vet_outra)
        resp = self.client.get(reverse("prontuario:anexo_download", args=[anexo.pk]))
        self.assertEqual(resp.status_code, 404)

    def test_download_por_recepcao_e_negado(self):
        self.upload(self.vet, _arquivo("laudo.pdf", PDF_VALIDO), exame=self.exame)
        anexo = Anexo.objects.get()
        self.client.force_login(self.recepcao)
        resp = self.client.get(reverse("prontuario:anexo_download", args=[anexo.pk]))
        self.assertEqual(resp.status_code, 403)

    def test_download_anonimo_vai_para_login(self):
        self.upload(self.vet, _arquivo("laudo.pdf", PDF_VALIDO), exame=self.exame)
        anexo = Anexo.objects.get()
        self.client.logout()
        resp = self.client.get(reverse("prontuario:anexo_download", args=[anexo.pk]))
        self.assertEqual(resp.status_code, 302)

    def test_recepcao_nao_registra_exame(self):
        self.client.force_login(self.recepcao)
        resp = self.client.get(reverse("prontuario:exame_create") + f"?pet={self.pet.pk}")
        self.assertEqual(resp.status_code, 403)

    def test_exame_nao_pode_ser_alterado_nem_apagado(self):
        with self.assertRaises(AtendimentoBloqueado):
            self.exame.save()
        with self.assertRaises(AtendimentoBloqueado):
            self.exame.delete()
        self.assertTrue(Exame.objects.filter(pk=self.exame.pk).exists())

    def test_anexo_nao_pode_ser_alterado_nem_apagado(self):
        self.upload(self.vet, _arquivo("laudo.pdf", PDF_VALIDO), exame=self.exame)
        anexo = Anexo.objects.get()
        with self.assertRaises(AtendimentoBloqueado):
            anexo.save()
        with self.assertRaises(AtendimentoBloqueado):
            anexo.delete()
        self.assertTrue(Anexo.objects.filter(pk=anexo.pk).exists())

    def test_exame_de_outra_clinica_nao_recebe_anexo(self):
        self.client.force_login(self.vet_outra)
        resp = self.client.post(
            reverse("prontuario:anexo_create") + f"?exame={self.exame.pk}",
            {"arquivo": _arquivo("laudo.pdf", PDF_VALIDO)},
        )
        self.assertEqual(resp.status_code, 404)
        self.assertFalse(Anexo.objects.exists())

    def test_exame_com_atendimento_de_outro_pet_e_recusado(self):
        outro_pet = Pet.objects.create(clinica=self.clinica, tutor=self.tutor, nome="Mel", especie=Pet.Especie.GATO)
        atend = self.atendimento(pet=outro_pet)
        form = ExameForm(
            data={"pet": self.pet.pk, "atendimento": atend.pk, "tipo": "laboratorio", "nome": "X",
                  "data_coleta": "2030-01-05"},
            clinica=self.clinica,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("atendimento", form.errors)


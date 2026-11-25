from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from clinicas.models import Clinica, Vinculo

from .forms import PetForm
from .models import Pet, Tutor

User = get_user_model()


class TutoresViewsTest(TestCase):
    def setUp(self):
        self.clinica_a = Clinica.objects.create(nome="Clínica A")
        self.clinica_b = Clinica.objects.create(nome="Clínica B")

        self.user_a = User.objects.create_user("ana", password="senha-forte-123")
        Vinculo.objects.create(usuario=self.user_a, clinica=self.clinica_a, papel=Vinculo.Papel.RECEPCAO)
        self.user_b = User.objects.create_user("bruno", password="senha-forte-123")
        Vinculo.objects.create(usuario=self.user_b, clinica=self.clinica_b, papel=Vinculo.Papel.RECEPCAO)
        self.user_sem_vinculo = User.objects.create_user("carla", password="senha-forte-123")

        self.tutor_a = Tutor.objects.create(clinica=self.clinica_a, nome="Maria Silva")
        self.tutor_b = Tutor.objects.create(clinica=self.clinica_b, nome="João Souza")
        self.pet_a = Pet.objects.create(
            clinica=self.clinica_a, tutor=self.tutor_a, nome="Rex", especie=Pet.Especie.CAO
        )

    def test_lista_exige_login(self):
        resp = self.client.get(reverse("tutores:tutor_list"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login/", resp["Location"])

    def test_lista_mostra_apenas_tutores_da_propria_clinica(self):
        self.client.force_login(self.user_a)
        resp = self.client.get(reverse("tutores:tutor_list"))
        self.assertContains(resp, "Maria Silva")
        self.assertNotContains(resp, "João Souza")

    def test_busca_respeita_isolamento(self):
        self.client.force_login(self.user_a)
        resp = self.client.get(reverse("tutores:tutor_list"), {"q": "João"})
        self.assertNotContains(resp, "João Souza")

    def test_detalhe_de_tutor_de_outra_clinica_retorna_404(self):
        self.client.force_login(self.user_a)
        resp = self.client.get(reverse("tutores:tutor_detail", args=[self.tutor_b.pk]))
        self.assertEqual(resp.status_code, 404)

    def test_usuario_sem_vinculo_recebe_403(self):
        self.client.force_login(self.user_sem_vinculo)
        resp = self.client.get(reverse("tutores:tutor_list"))
        self.assertEqual(resp.status_code, 403)

    def test_criar_tutor_grava_na_clinica_do_usuario(self):
        self.client.force_login(self.user_a)
        resp = self.client.post(reverse("tutores:tutor_create"), {"nome": "Pedro Lima", "telefone": "71999990000"})
        self.assertEqual(resp.status_code, 302)
        tutor = Tutor.objects.get(nome="Pedro Lima")
        self.assertEqual(tutor.clinica, self.clinica_a)

    def test_editar_tutor_de_outra_clinica_retorna_404(self):
        self.client.force_login(self.user_a)
        resp = self.client.post(
            reverse("tutores:tutor_update", args=[self.tutor_b.pk]),
            {"nome": "Invasão"},
        )
        self.assertEqual(resp.status_code, 404)
        self.tutor_b.refresh_from_db()
        self.assertEqual(self.tutor_b.nome, "João Souza")

    def test_criar_pet_com_tutor_de_outra_clinica_e_rejeitado(self):
        self.client.force_login(self.user_a)
        resp = self.client.post(
            reverse("tutores:pet_create"),
            {
                "tutor": self.tutor_b.pk,
                "nome": "Mel",
                "especie": Pet.Especie.GATO,
                "sexo": "I",
                "castrado": "",
                "ativo": "on",
            },
        )
        self.assertEqual(resp.status_code, 200)  # formulário inválido, permanece na tela
        self.assertFalse(Pet.objects.filter(nome="Mel").exists())

    def test_criar_pet_com_tutor_da_clinica_funciona(self):
        self.client.force_login(self.user_a)
        resp = self.client.post(
            reverse("tutores:pet_create"),
            {
                "tutor": self.tutor_a.pk,
                "nome": "Mel",
                "especie": Pet.Especie.GATO,
                "sexo": "I",
                "ativo": "on",
            },
        )
        self.assertEqual(resp.status_code, 302)
        pet = Pet.objects.get(nome="Mel")
        self.assertEqual(pet.clinica, self.clinica_a)
        self.assertEqual(pet.tutor, self.tutor_a)

    def test_pet_form_limita_tutores_a_clinica(self):
        form = PetForm(clinica=self.clinica_a)
        self.assertEqual(list(form.fields["tutor"].queryset), [self.tutor_a])

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase

from tutores.admin import TutorAdmin
from tutores.models import Tutor

from .admin import clinica_do_usuario
from .models import Clinica, Vinculo

User = get_user_model()


class IsolamentoPorClinicaTest(TestCase):
    """Garante que um usuário nunca enxerga dados de outra clínica."""

    def setUp(self):
        self.clinica_a = Clinica.objects.create(nome="Clínica A")
        self.clinica_b = Clinica.objects.create(nome="Clínica B")

        self.user_a = User.objects.create_user("ana", password="senha-forte-123")
        Vinculo.objects.create(usuario=self.user_a, clinica=self.clinica_a, papel=Vinculo.Papel.RECEPCAO)
        self.user_b = User.objects.create_user("bruno", password="senha-forte-123")
        Vinculo.objects.create(usuario=self.user_b, clinica=self.clinica_b, papel=Vinculo.Papel.RECEPCAO)
        self.superuser = User.objects.create_superuser("root", "root@example.com", "senha-forte-123")

        self.tutor_a = Tutor.objects.create(clinica=self.clinica_a, nome="Tutor da A")
        self.tutor_b = Tutor.objects.create(clinica=self.clinica_b, nome="Tutor da B")

        self.admin = TutorAdmin(Tutor, admin_site=None)
        self.factory = RequestFactory()

    def _request(self, user):
        request = self.factory.get("/admin/tutores/tutor/")
        request.user = user
        return request

    def test_usuario_ve_somente_tutores_da_propria_clinica(self):
        qs = self.admin.get_queryset(self._request(self.user_a))
        self.assertEqual(list(qs), [self.tutor_a])

    def test_outro_usuario_nao_ve_tutor_de_outra_clinica(self):
        qs = self.admin.get_queryset(self._request(self.user_b))
        self.assertEqual(list(qs), [self.tutor_b])

    def test_superusuario_ve_tudo(self):
        qs = self.admin.get_queryset(self._request(self.superuser))
        self.assertCountEqual(list(qs), [self.tutor_a, self.tutor_b])

    def test_usuario_sem_vinculo_nao_ve_nada(self):
        sem_vinculo = User.objects.create_user("carla", password="senha-forte-123")
        qs = self.admin.get_queryset(self._request(sem_vinculo))
        self.assertEqual(list(qs), [])

    def test_anonimo_nao_tem_clinica(self):
        self.assertIsNone(clinica_do_usuario(AnonymousUser()))

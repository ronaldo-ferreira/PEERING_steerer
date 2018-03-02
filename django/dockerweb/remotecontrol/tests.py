from django.test import TestCase


class HomeTest(TestCase):
    def setUp(self):
        self.response = self.client.get('/')

    def test_get(self):
        """GET / must return status code 200"""
        self.assertEqual(200, self.response.status_code)

    def test_template(self):
        """Must use index.html"""
        self.assertTemplateUsed(self.response, 'index.html')

    def test_select_form(self):
        """Validate form options"""
        self.assertContains(self.response, '<form')
        self.assertContains(self.response, '<input', 2)
        self.assertContains(self.response, 'type="submit"')

class DockerConnectedTest(TestCase):
    def setUp(self):
        data = dict(remoteserver='xbrivas0')
        self.response = self.client.post('/', data)

    def test_template(self):
        self.assertTemplateUsed(self.response, 'connected.html')


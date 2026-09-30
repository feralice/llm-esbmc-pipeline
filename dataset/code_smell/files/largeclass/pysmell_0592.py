# smell: LargeClass
# validated by: PySmell manual inspection (Chen et al.)
# origin: https://github.com/django/django/blob/1.8.2/tests/test_client/tests.py#L37-L47
# smelly line(s) in the original file: 37
# smelly line(s) in this file: 8
# ids: pysmell_0592
# note: Python 2 era source, kept as found
def test_get_view(self):
    "GET a view"
    # The data is ignored, but let's check it doesn't crash the system
    # anyway.
    data = {'var': '\xf2'}
    response = self.client.get('/get_view/', data)

    # Check some response details
    self.assertContains(response, 'This is a test')
    self.assertEqual(response.context['var'], '\xf2')
    self.assertEqual(response.templates[0].name, 'GET Template')

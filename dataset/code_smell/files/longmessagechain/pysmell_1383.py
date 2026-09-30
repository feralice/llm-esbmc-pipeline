# smell: LongMessageChain
# validated by: PySmell manual inspection (Chen et al.)
# origin: https://github.com/django/django/blob/1.8.2/tests/migrations/test_operations.py#L617-L641
# smelly line(s) in the original file: 641
# smelly line(s) in this file: 32
# ids: pysmell_1383
# note: Python 2 era source, kept as found
def test_rename_m2m_target_model(self):
    app_label = "test_rename_m2m_target_model"
    project_state = self.apply_operations(app_label, ProjectState(), operations=[
        migrations.CreateModel("Rider", fields=[]),
        migrations.CreateModel("Pony", fields=[
            ("riders", models.ManyToManyField("Rider")),
        ]),
    ])
    Pony = project_state.apps.get_model(app_label, "Pony")
    Rider = project_state.apps.get_model(app_label, "Rider")
    pony = Pony.objects.create()
    rider = Rider.objects.create()
    pony.riders.add(rider)

    project_state = self.apply_operations(app_label, project_state, operations=[
        migrations.RenameModel("Rider", "Rider2"),
    ])
    Pony = project_state.apps.get_model(app_label, "Pony")
    Rider = project_state.apps.get_model(app_label, "Rider2")
    pony = Pony.objects.create()
    rider = Rider.objects.create()
    pony.riders.add(rider)
    self.assertEqual(Pony.objects.count(), 2)
    self.assertEqual(Rider.objects.count(), 2)
    self.assertEqual(Pony._meta.get_field('riders').rel.through.objects.count(), 2)

# Unit groups and their model permissions. Row-level rules (only the owning
# unit edits a hold) live in registry/services.py and registry/admin.py.
from django.db import migrations

PERMS = {
    "student_affairs": [
        "view_student", "add_student", "change_student",
        "view_studentdocument", "add_studentdocument", "change_studentdocument",
        "view_hold",
        "view_request", "add_request", "change_request",
        "view_requeststep",
    ],
    "finance": [
        "view_student", "view_studentdocument",
        "view_hold", "add_hold", "change_hold",
        "view_request", "view_requeststep",
    ],
    "legal": [
        "view_student", "view_studentdocument",
        "view_hold", "add_hold", "change_hold",
        "view_request", "view_requeststep",
    ],
}


def create_groups(apps, schema_editor):
    from django.contrib.auth.management import create_permissions

    for app_config in apps.get_app_configs():
        app_config.models_module = True
        create_permissions(app_config, verbosity=0)
        app_config.models_module = None

    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    for name, codenames in PERMS.items():
        group, _ = Group.objects.get_or_create(name=name)
        perms = Permission.objects.filter(content_type__app_label="registry",
                                          codename__in=codenames)
        group.permissions.set(perms)


def remove_groups(apps, schema_editor):
    apps.get_model("auth", "Group").objects.filter(name__in=PERMS).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("registry", "0001_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.RunPython(create_groups, remove_groups),
    ]

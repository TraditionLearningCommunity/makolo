from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("tickets", "0001_initial"),
    ]

    operations = [
        migrations.RenameIndex(
            model_name="ticket",
            old_name="tickets_tic_event_i_d6dbab_idx",
            new_name="tickets_tic_event_i_d07e31_idx",
        ),
        migrations.RenameIndex(
            model_name="ticket",
            old_name="tickets_tic_owner_i_b7d868_idx",
            new_name="tickets_tic_owner_i_70fd59_idx",
        ),
        migrations.RenameIndex(
            model_name="ticketorder",
            old_name="tickets_tic_event_i_90a056_idx",
            new_name="tickets_tic_event_i_974187_idx",
        ),
        migrations.RenameIndex(
            model_name="ticketorder",
            old_name="tickets_tic_buyer_i_a16f5d_idx",
            new_name="tickets_tic_buyer_i_8dee1a_idx",
        ),
    ]

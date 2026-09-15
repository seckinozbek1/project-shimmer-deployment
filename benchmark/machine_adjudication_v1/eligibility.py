"""Machine-only namespace; authored disputes and ambiguity are quarantined."""


def held_out(row):
    return row['domain'] in ('astronomy','ecology')


def candidate(row,label,primary_valid,material_dispute):
    return (row['split'] in ('train','dev') and not held_out(row) and all(primary_valid.values())
            and len(primary_valid)==3 and label.get('valid') is True
            and label.get('unresolved') is False and label['review']['ambiguity'] is False
            and not material_dispute)


def machine_label(row,label):
    return dict(example_id=row['example_id'],split=row['split'],
                provenance='machine_adjudicated_training_candidate',human_reviewed=False,
                input_sha256=label['review']['input_sha256'],machine_target=label['review']['semantic_target'])

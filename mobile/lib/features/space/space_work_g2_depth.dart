import 'package:flutter/material.dart';

import '../../design/action_controls.dart';

import 'package:go_router/go_router.dart';

import '../../presentation/contracts/space_presentation.dart';

/// Presentation of authorized owner relations. No local Journey/Session
/// aggregation and no permission inferred from an empty or cached list.
class SpaceWorkG2Depth extends StatelessWidget {
  const SpaceWorkG2Depth({
    super.key,
    required this.slug,
    required this.archetype,
    required this.occurrences,
    required this.work,
    required this.onOccurrencesPageChange,
    required this.onWorkPageChange,
    this.workSection,
    this.fromWorkCollection = false,
  });

  final String slug;
  final String archetype;
  final Map<String, dynamic> occurrences;
  final Map<String, dynamic> work;
  final ValueChanged<int> onOccurrencesPageChange;
  final ValueChanged<int> onWorkPageChange;
  final String? workSection;
  final bool fromWorkCollection;

  bool get isEducation => archetype == 'education';

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _collection(
          context,
          title: isEducation
              ? 'Sessions de ce programme'
              : 'Réalisations liées',
          empty: isEducation
              ? 'Aucune session programmée.'
              : 'Aucune réalisation programmée.',
          data: occurrences,
          onPageChange: onOccurrencesPageChange,
          isOccurrence: true,
        ),
        const SizedBox(height: 24),
        _collection(
          context,
          title: isEducation ? 'Inscriptions' : 'Dossiers de cette prestation',
          empty: isEducation
              ? 'Aucune inscription accessible.'
              : 'Aucun dossier accessible.',
          data: work,
          onPageChange: onWorkPageChange,
          isOccurrence: false,
        ),
      ],
    );
  }

  Widget _collection(
    BuildContext context, {
    required String title,
    required String empty,
    required Map<String, dynamic> data,
    required ValueChanged<int> onPageChange,
    required bool isOccurrence,
  }) {
    final items = data['items'] is List ? data['items'] as List : const [];
    final offset = data['offset'] is int ? data['offset'] as int : 0;
    final limit = data['limit'] is int ? data['limit'] as int : 12;
    final hasMore = data['has_more'] == true;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title, style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 8),
        if (items.isEmpty) Text(offset == 0 ? empty : 'Fin des résultats.'),
        for (final raw in items)
          if (spaceMap(raw) case final Map<String, dynamic> item)
            _row(context, item, isOccurrence),
        if (offset > 0 || hasMore)
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              if (offset > 0)
                MakoloActionButton(
                  appearance: MakoloActionAppearance.secondary,
                  onPressed: () =>
                      onPageChange(offset > limit ? offset - limit : 0),
                  label: 'Précédentes',
                ),
              if (hasMore)
                MakoloActionButton(
                  appearance: MakoloActionAppearance.secondary,
                  onPressed: () => onPageChange(offset + limit),
                  label: 'Voir les suivantes',
                ),
            ],
          ),
      ],
    );
  }

  Widget _row(
    BuildContext context,
    Map<String, dynamic> row,
    bool isOccurrence,
  ) {
    final source = spaceMap(row['source']);
    final timing = spaceMap(row['timing']);
    final route = (!isOccurrence || row['openable'] == true)
        ? spaceWorkOwnerRoute(
            slug: slug,
            kind: spaceText(source?['kind']),
            id: spaceText(source?['id']),
            section: workSection,
            fromCollection: fromWorkCollection,
          )
        : null;
    final title =
        spaceText(row['title']) ?? (isOccurrence ? 'Réalisation' : 'Démarche');
    final date = spaceText(timing?['start_date']);
    final state = spaceText(row['state']);
    return ListTile(
      contentPadding: EdgeInsets.zero,
      title: Text(title),
      subtitle: Text(
        [
          ?date,
          if (state != null) spaceStateLabel(state),
          if (isOccurrence && route == null) 'Date non ouvrable dans cet état',
        ].join(' · '),
      ),
      trailing: route != null ? const Icon(Icons.chevron_right) : null,
      onTap: route == null ? null : () => context.push(route),
    );
  }
}

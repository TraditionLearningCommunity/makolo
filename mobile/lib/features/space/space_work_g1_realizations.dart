import 'package:flutter/material.dart';

import '../../design/action_controls.dart';

import 'package:go_router/go_router.dart';

import '../../presentation/contracts/space_presentation.dart';

/// Native N2 relation supplied by the authorized Work owner selection.
/// It neither owns Occurrences nor claims that an elapsed date is ongoing.
class SpaceWorkG1Realizations extends StatelessWidget {
  const SpaceWorkG1Realizations({
    super.key,
    required this.payload,
    required this.slug,
    required this.onPageChange,
    this.isCommunity = false,
    this.workSection,
    this.fromWorkCollection = false,
  });

  final Map<String, dynamic> payload;
  final String slug;
  final ValueChanged<int> onPageChange;
  final bool isCommunity;
  final String? workSection;
  final bool fromWorkCollection;

  @override
  Widget build(BuildContext context) {
    final rows = payload['items'] is List ? payload['items'] as List : const [];
    final offset = payload['offset'] is int ? payload['offset'] as int : 0;
    final limit = payload['limit'] is int ? payload['limit'] as int : 12;
    final hasMore = payload['has_more'] == true;

    return Padding(
      padding: const EdgeInsets.only(top: 20, bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            isCommunity ? 'Actions et réalisations' : 'Dates et réalisations',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 8),
          if (rows.isEmpty && offset == 0)
            Text(
              isCommunity
                  ? 'Aucune action datée pour le moment. '
                        'L’initiative reste disponible.'
                  : 'Aucune réalisation datée pour le moment. '
                        'L’activité reste disponible.',
            ),
          for (final raw in rows)
            if (spaceMap(raw) case final Map<String, dynamic> row)
              _RealizationRow(
                row: row,
                slug: slug,
                workSection: workSection,
                fromWorkCollection: fromWorkCollection,
              ),
          if (offset > 0 || hasMore)
            Padding(
              padding: const EdgeInsets.only(top: 12),
              child: Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  if (offset > 0)
                    MakoloActionButton(
                      label: 'Précédentes',
                      onPressed: () =>
                          onPageChange(offset > limit ? offset - limit : 0),
                      appearance: MakoloActionAppearance.secondary,
                    ),
                  if (hasMore)
                    MakoloActionButton(
                      label: 'Voir les suivantes',
                      onPressed: () => onPageChange(offset + limit),
                      appearance: MakoloActionAppearance.secondary,
                    ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

class _RealizationRow extends StatelessWidget {
  const _RealizationRow({
    required this.row,
    required this.slug,
    this.workSection,
    this.fromWorkCollection = false,
  });

  final Map<String, dynamic> row;
  final String slug;
  final String? workSection;
  final bool fromWorkCollection;

  @override
  Widget build(BuildContext context) {
    final source = spaceMap(row['source']);
    final title = spaceText(row['title']) ?? 'Réalisation';
    final state = spaceText(row['state']);
    final timing = spaceMap(row['timing']);
    final date = spaceText(timing?['start_date']);
    final clock = spaceText(timing?['start_time']);
    final route = row['openable'] == true
        ? spaceWorkOwnerRoute(
            slug: slug,
            kind: spaceText(source?['kind']),
            id: spaceText(source?['id']),
            section: workSection,
            fromCollection: fromWorkCollection,
          )
        : null;
    return ListTile(
      contentPadding: EdgeInsets.zero,
      title: Text(title),
      subtitle: Text(
        [
          ?date,
          ?clock,
          if (state != null) spaceStateLabel(state),
          if (route == null) 'Date non ouvrable ici',
        ].join(' · '),
      ),
      trailing: route != null ? const Icon(Icons.chevron_right) : null,
      onTap: route == null ? null : () => context.push(route),
    );
  }
}

import 'package:flutter/material.dart';

import '../../design/action_controls.dart';

import 'package:go_router/go_router.dart';

import '../../presentation/contracts/space_presentation.dart';

/// MT6: Creative/Media N2, never a second owner for Works or Productions.
/// Published recognition imagery is supplied only after the server owner
/// selection and the public delivery policy have both been satisfied.
class SpaceWorkG4Depth extends StatelessWidget {
  const SpaceWorkG4Depth({
    super.key,
    required this.slug,
    required this.sourceKind,
    required this.sourceId,
    required this.archetype,
    required this.isActivity,
    required this.detail,
    required this.related,
    required this.mediaBindings,
    required this.onPageChange,
    this.nextOccurrence,
    this.mediaBaseUri,
    this.workSection,
    this.fromWorkCollection = false,
  });

  final String slug;
  final String sourceKind;
  final String sourceId;
  final String archetype;
  final bool isActivity;
  final Map<String, dynamic> detail;
  final Map<String, dynamic>? related;
  final List<dynamic> mediaBindings;
  final Map<String, dynamic>? nextOccurrence;
  final Uri? mediaBaseUri;
  final String? workSection;
  final bool fromWorkCollection;
  final ValueChanged<int> onPageChange;

  bool get _creative => archetype == 'creative';

  Uri? _publishedImageUri() {
    if (mediaBaseUri == null) return null;
    for (final raw in mediaBindings) {
      final binding = spaceMap(raw);
      final owner = spaceMap(binding?['owner']);
      final path = spaceText(binding?['url']);
      if (binding?['authorized'] == true &&
          binding?['purpose'] == 'recognize' &&
          binding?['kind'] == 'image' &&
          (binding?['mime_type'] == 'image/jpeg' ||
              binding?['mime_type'] == 'image/png') &&
          owner?['kind'] == sourceKind &&
          owner?['id'] == sourceId &&
          path != null &&
          path.startsWith('/presentation/media/uses/') &&
          path.endsWith('/file/')) {
        return mediaBaseUri!.resolve(path);
      }
    }
    return null;
  }

  @override
  Widget build(BuildContext context) {
    final rows = related?['items'] is List
        ? related!['items'] as List
        : const [];
    final offset = related?['offset'] is int ? related!['offset'] as int : 0;
    final limit = related?['limit'] is int ? related!['limit'] as int : 12;
    final hasMore = related?['has_more'] == true;
    final mediaUri = _publishedImageUri();
    final title = _creative
        ? 'Présentations et réalisations'
        : 'Éditions et réalisations';
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (mediaUri != null)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 16),
            child: Semantics(
              label:
                  spaceText(spaceMap(mediaBindings.first)?['label']) ??
                  'Visuel publié de reconnaissance',
              child: ClipRRect(
                borderRadius: BorderRadius.circular(12),
                child: Image.network(
                  mediaUri.toString(),
                  width: 260,
                  height: 200,
                  fit: BoxFit.contain,
                  errorBuilder: (_, _, _) =>
                      const Text('Visuel publié indisponible.'),
                ),
              ),
            ),
          ),
        if (isActivity)
          if (spaceText(detail['description']) case final String description)
            Padding(
              padding: const EdgeInsets.only(bottom: 20),
              child: Text(description),
            ),
        if (isActivity && nextOccurrence != null)
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: const Icon(Icons.event_outlined),
            title: Text(
              _creative ? 'Prochaine présentation' : 'Prochaine édition',
            ),
            subtitle: Text(
              [
                if (spaceText(nextOccurrence?['label']) case final String label)
                  label,
                if (spaceText(nextOccurrence?['start_date'])
                    case final String date)
                  date,
              ].join(' · '),
            ),
          ),
        if (isActivity) ...[
          Text(title, style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          if (rows.isEmpty && offset == 0)
            Text(
              _creative
                  ? 'Aucune présentation prévue.'
                  : 'Aucune édition prévue.',
            ),
          if (rows.isEmpty && offset > 0) const Text('Fin des résultats.'),
          for (final raw in rows)
            if (spaceMap(raw) case final Map<String, dynamic> row)
              _G4OccurrenceRow(
                slug: slug,
                row: row,
                workSection: workSection,
                fromWorkCollection: fromWorkCollection,
              ),
          if (offset > 0 || hasMore)
            Padding(
              padding: const EdgeInsets.only(top: 12),
              child: Wrap(
                spacing: 8,
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
            ),
        ],
      ],
    );
  }
}

class _G4OccurrenceRow extends StatelessWidget {
  const _G4OccurrenceRow({
    required this.slug,
    required this.row,
    this.workSection,
    this.fromWorkCollection = false,
  });

  final String slug;
  final Map<String, dynamic> row;
  final String? workSection;
  final bool fromWorkCollection;

  @override
  Widget build(BuildContext context) {
    final source = spaceMap(row['source']);
    final timing = spaceMap(row['timing']);
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
      title: Text(spaceText(row['title']) ?? 'Réalisation'),
      subtitle: Text(
        [
          if (spaceText(timing?['start_date']) case final String date) date,
          if (spaceText(row['state']) case final String state)
            spaceStateLabel(state),
          if (route == null) 'Date non ouvrable dans cet état',
        ].join(' · '),
      ),
      trailing: route == null ? null : const Icon(Icons.chevron_right),
      onTap: route == null ? null : () => context.push(route),
    );
  }
}

import 'package:flutter/material.dart';

import '../../design/makolo_theme.dart';
import '../../features/discovery/discovery_selector.dart';
import 'discovery_n2_model.dart';

/// N2 shows only facts from the current admitted owner projection. N1 remains
/// intentionally compact; read-only owner depths still re-check permissions.
class DiscoveryN2DepthSection extends StatelessWidget {
  const DiscoveryN2DepthSection({
    super.key,
    required this.item,
    this.onOpenOccurrence,
  });

  final DiscoveryItemPresentation item;
  final ValueChanged<String>? onOpenOccurrence;

  @override
  Widget build(BuildContext context) {
    final depth = DiscoveryN2Depth(item);
    if (depth.assessments.isEmpty &&
        depth.variants.isEmpty &&
        depth.relations.isEmpty &&
        depth.freshness == null) {
      return const SizedBox.shrink();
    }
    final theme = Theme.of(context);
    final comparison = depth.comparisonRows;

    return Padding(
      key: const Key('discover-n2-depth'),
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (depth.assessments.isNotEmpty) ...[
            Text('Ce qui est établi', style: theme.textTheme.titleMedium),
            const SizedBox(height: MakoloSpacing.sm),
            for (final group in const [
              ('favorable', 'Points favorables', Icons.check_circle_outline),
              ('limiting', 'Points à considérer', Icons.info_outline),
              ('unknown', 'Informations non établies', Icons.help_outline),
            ])
              if (depth.assessments.any((a) => a.state == group.$1))
                Padding(
                  key: ValueKey('discover-n2-assessment-${group.$1}'),
                  padding: const EdgeInsets.only(bottom: MakoloSpacing.sm),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(group.$2, style: theme.textTheme.titleSmall),
                      const SizedBox(height: MakoloSpacing.xs),
                      for (final fact in depth.assessments.where(
                        (a) => a.state == group.$1,
                      ))
                        Padding(
                          padding: const EdgeInsets.symmetric(
                            vertical: MakoloSpacing.micro,
                          ),
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Icon(
                                group.$3,
                                size: 18,
                                color: theme.colorScheme.onSurfaceVariant,
                              ),
                              const SizedBox(width: MakoloSpacing.sm),
                              Expanded(child: Text(fact.label)),
                            ],
                          ),
                        ),
                    ],
                  ),
                ),
          ],
          if (depth.variants.isNotEmpty) ...[
            const SizedBox(height: MakoloSpacing.sm),
            Text(
              item.routeLabel == null
                  ? 'Sessions et réalisations proposées'
                  : 'Départs et réalisations proposés',
              style: theme.textTheme.titleMedium,
            ),
            const SizedBox(height: MakoloSpacing.xs),
            for (var index = 0; index < depth.variants.length; index++)
              Card(
                key: ValueKey(
                  'discover-n2-variant-${depth.variants[index].id}',
                ),
                child: Padding(
                  padding: const EdgeInsets.all(MakoloSpacing.md),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Variante ${index + 1}',
                        style: theme.textTheme.titleSmall,
                      ),
                      if (depth.variants[index].start != null)
                        Text('Début : ${depth.variants[index].start}'),
                      if (depth.variants[index].end != null)
                        Text('Fin : ${depth.variants[index].end}'),
                      for (final place in depth.variants[index].places)
                        Text('Lieu : $place'),
                      if (depth.variants[index].start == null &&
                          depth.variants[index].end == null &&
                          depth.variants[index].places.isEmpty)
                        Text(
                          'Date et lieu non renseignés dans cette variante.',
                          style: theme.textTheme.bodySmall,
                        ),
                      if (onOpenOccurrence != null) ...[
                        const SizedBox(height: MakoloSpacing.xs),
                        TextButton.icon(
                          key: ValueKey(
                            'discover-n2-owner-occurrence-${depth.variants[index].id}',
                          ),
                          onPressed: () =>
                              onOpenOccurrence!(depth.variants[index].id),
                          icon: const Icon(Icons.open_in_new_rounded),
                          label: const Text('Consulter cette réalisation'),
                        ),
                      ],
                    ],
                  ),
                ),
              ),
          ],
          if (comparison.isNotEmpty) ...[
            const SizedBox(height: MakoloSpacing.md),
            Text(
              'Comparer les variantes connues',
              style: theme.textTheme.titleMedium,
            ),
            const SizedBox(height: MakoloSpacing.xs),
            Text(
              'Seules les dimensions renseignées pour toutes les variantes '
              'sont affichées. Aucune option n’est classée.',
              style: theme.textTheme.bodySmall,
            ),
            SingleChildScrollView(
              key: const Key('discover-n2-conditional-comparison'),
              scrollDirection: Axis.horizontal,
              child: DataTable(
                columns: [
                  const DataColumn(label: Text('Fait')),
                  for (var i = 0; i < depth.variants.length; i++)
                    DataColumn(label: Text('Variante ${i + 1}')),
                ],
                rows: [
                  for (final row in comparison)
                    DataRow(
                      cells: [
                        DataCell(Text(row.label)),
                        for (final value in row.values) DataCell(Text(value)),
                      ],
                    ),
                ],
              ),
            ),
          ],
          if (depth.relations.isNotEmpty) ...[
            const SizedBox(height: MakoloSpacing.md),
            Text('Relations indiquées', style: theme.textTheme.titleMedium),
            for (final relation in depth.relations)
              Padding(
                padding: const EdgeInsets.only(top: MakoloSpacing.xs),
                child: Text(relation),
              ),
            Text(
              'Une relation ne signifie pas nécessairement une alternative.',
              style: theme.textTheme.bodySmall,
            ),
          ],
          if (depth.freshness != null) ...[
            const SizedBox(height: MakoloSpacing.md),
            Text(
              'Vérification : ${depth.freshness}',
              style: theme.textTheme.bodySmall,
            ),
          ],
        ],
      ),
    );
  }
}

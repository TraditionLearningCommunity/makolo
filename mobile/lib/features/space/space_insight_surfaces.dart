import 'package:flutter/material.dart';

import '../../design/behavior_states.dart';
import '../../design/makolo_components.dart';
import '../../design/makolo_patterns.dart';
import '../../design/makolo_theme.dart';
import '../../presentation/contracts/space_presentation.dart';

class SpacePilotSurface extends StatelessWidget {
  const SpacePilotSurface({super.key, required this.payload});
  final Map<String, dynamic> payload;

  @override
  Widget build(BuildContext context) {
    final analytics = spaceMap(spaceMap(payload['sections'])?['analytics']);
    if (analytics == null) {
      return const MakoloEmptyState(
        title: 'Pilotage non autorisé ou indisponible.',
        icon: Icons.lock_outline,
      );
    }
    final signals = analytics['signals'] is List
        ? analytics['signals'] as List
        : const [];
    final metrics = analytics['metrics'] is List
        ? analytics['metrics'] as List
        : const [];
    final coverage = spaceMap(analytics['coverage']);
    final generated = spaceText(analytics['generated_at']);
    final period = spaceText(analytics['period']);
    final money =
        spaceMap(payload['capabilities'])?['view_financials'] == true &&
            analytics['money'] is List
        ? analytics['money'] as List
        : const [];
    return ListView(
      key: const PageStorageKey('space-pilot-secondary'),
      padding: const EdgeInsets.all(MakoloSpacing.lg),
      children: [
        const MakoloDetailHeader(
          title: 'Piloter',
          subtitle: 'Que faut-il examiner ?',
        ),
        Text(
          'Source : Analytics',
          style: Theme.of(context).textTheme.labelLarge,
        ),
        if (coverage?['kind'] == 'latest_visible_events' &&
            coverage?['limit'] is num)
          Text(
            'Couverture : les ${coverage!['limit']} derniers événements visibles au maximum.',
          ),
        if (generated != null) Text('Observation : $generated'),
        Text(
          period == null
              ? 'Période de comparaison non établie.'
              : 'Période : $period',
        ),
        const SizedBox(height: MakoloSpacing.md),
        if (analytics['state'] == 'insufficient_data')
          const MakoloEmptyState(
            title: 'Données insuffisantes',
            body: 'Les observations disponibles ne permettent pas encore d’interpréter le fonctionnement.',
          ),
        if (signals.isEmpty && analytics['state'] != 'insufficient_data')
          const Text(
            'Aucun signal interprétable dans les observations disponibles.',
          ),
        for (final value in signals)
          if (spaceMap(value) case final Map<String, dynamic> signal)
            Padding(
              padding: const EdgeInsets.only(bottom: MakoloSpacing.md),
              child: MakoloCard(
                child: ExpansionTile(
                  title: Text(spaceText(signal['title']) ?? 'Observation'),
                  subtitle: spaceText(signal['summary']) == null
                      ? null
                      : Text(spaceText(signal['summary'])!),
                  childrenPadding: const EdgeInsets.all(MakoloSpacing.md),
                  expandedCrossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (spaceText(signal['why']) case final String why)
                      Text(why),
                    const SizedBox(height: MakoloSpacing.sm),
                    if (spaceMap(signal['evidence'])
                        case final Map<String, dynamic> evidence)
                      Text(
                        '${spaceMetricLabels[evidence['metric_key']] ?? 'Mesure observée'} : ${evidence['value'] ?? 'Inconnu'}',
                      ),
                    if (spaceText(signal['owner']) case final String owner)
                      Text('Source : $owner'),
                    if (spaceText(signal['uncertainty'])
                        case final String uncertainty)
                      Padding(
                        padding: const EdgeInsets.only(top: MakoloSpacing.sm),
                        child: MakoloAttentionBlock(
                          title: 'Limites de cette observation',
                          body: uncertainty,
                          icon: Icons.info_outline,
                        ),
                      ),
                  ],
                ),
              ),
            ),
        ExpansionTile(
          title: const Text('Mesures de soutien'),
          children: [
            for (final value in metrics)
              if (spaceMap(value) case final Map<String, dynamic> metric)
                ListTile(
                  title: Text(spaceMetricLabels[metric['key']] ?? 'Mesure'),
                  subtitle: Text(spaceMetricValue(metric)),
                ),
          ],
        ),
        if (money.isNotEmpty)
          ExpansionTile(
            title: const Text('Montants par devise'),
            children: [
              for (final value in money)
                if (spaceMap(value) case final Map<String, dynamic> row)
                  ListTile(
                    title: Text(
                      spaceText(row['currency']) ?? 'Devise non précisée',
                    ),
                    subtitle: Text(
                      'Brut : ${row['gross'] ?? 'Inconnu'} · Remboursements : ${row['refunds'] ?? 'Inconnu'} · Net : ${row['net'] ?? 'Inconnu'}',
                    ),
                  ),
            ],
          ),
      ],
    );
  }
}

class SpaceRelationshipCard extends StatelessWidget {
  const SpaceRelationshipCard({super.key, required this.row, this.onOpen});
  final Map<String, dynamic> row;
  final VoidCallback? onOpen;

  @override
  Widget build(BuildContext context) {
    final profile = spaceMap(row['profile']);
    final title =
        spaceText(row['identity']) ??
        spaceText(profile?['name']) ??
        spaceText(row['name']) ??
        spaceText(row['label']) ??
        'Relation';
    final relation = spaceText(row['relation_type']) ?? 'Relation';
    final owner = spaceText(row['owner_identity']);
    final state = spaceText(row['status']);
    final icon = switch (row['kind']) {
      'team_member' => Icons.badge_outlined,
      'group' || 'audience' => Icons.groups_outlined,
      'partner' => Icons.handshake_outlined,
      _ => Icons.person_outline,
    };
    return Padding(
      padding: const EdgeInsets.only(bottom: MakoloSpacing.sm),
      child: MakoloCard(
        onTap: onOpen,
        semanticLabel: '$title · $relation',
        child: Padding(
          padding: const EdgeInsets.all(MakoloSpacing.md),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(icon),
              const SizedBox(width: MakoloSpacing.md),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title, style: Theme.of(context).textTheme.titleMedium),
                    Text(relation),
                    if (owner != null && owner != title) Text(owner),
                    if (state != null)
                      MakoloStatus(label: spaceStateLabel(state)),
                  ],
                ),
              ),
              if (onOpen != null) const Icon(Icons.chevron_right),
            ],
          ),
        ),
      ),
    );
  }
}

const spaceRelationshipSectionLabels = {
  'team': 'Équipe',
  'groups': 'Groupes',
  'crm_contacts': 'Contacts',
  'audiences': 'Audiences',
  'partners': 'Partenaires',
};

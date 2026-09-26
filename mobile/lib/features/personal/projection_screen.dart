import 'package:flutter/material.dart';

import '../../data/local/profile_store.dart';
import '../../design/behavior_states.dart';
import '../../design/makolo_theme.dart';

class ProjectionScreen extends StatelessWidget {
  const ProjectionScreen({
    super.key,
    required this.title,
    required this.stream,
    required this.emptyMessage,
  });

  final String title;
  final Stream<StoredProjection?> stream;
  final String emptyMessage;

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<StoredProjection?>(
      stream: stream,
      builder: (context, snapshot) {
        if (!snapshot.hasData &&
            snapshot.connectionState == ConnectionState.waiting) {
          return const MakoloLoadingState();
        }
        final projection = snapshot.data;
        if (projection == null) {
          return MakoloEmptyState(
            title: 'Pas encore disponible sur cet appareil',
            body: 'Makolo affichera ici les données déjà synchronisées. Une connexion est nécessaire pour les obtenir la première fois.',
            icon: Icons.cloud_off_outlined,
          );
        }

        final items = projection.payload['items'];
        if (items is List && items.isEmpty) {
          return MakoloEmptyState(title: emptyMessage);
        }

        return ListView(
          padding: const EdgeInsets.all(MakoloSpacing.lg),
          children: [
            Text(title, style: Theme.of(context).textTheme.headlineSmall),
            const SizedBox(height: MakoloSpacing.sm),
            Text(
              'Projection locale synchronisée · ${projection.receivedAt.toLocal()}',
              style: Theme.of(context).textTheme.bodySmall,
            ),
            const SizedBox(height: MakoloSpacing.lg),
            if (items is List)
              ...items.map(
                (item) => Card(
                  child: Padding(
                    padding: const EdgeInsets.all(MakoloSpacing.md),
                    child: Text(_humanLabel(item)),
                  ),
                ),
              )
            else
              const InlineMessage(
                message: 'Cette projection est disponible localement. Son expérience détaillée arrive dans A2.',
              ),
          ],
        );
      },
    );
  }

  String _humanLabel(Object? item) {
    if (item is Map) {
      for (final key in const ['title', 'label', 'name', 'headline']) {
        final value = item[key];
        if (value is String && value.trim().isNotEmpty) return value;
      }
    }
    return 'Élément Makolo';
  }
}

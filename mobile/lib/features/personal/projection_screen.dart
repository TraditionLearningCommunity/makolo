import 'package:flutter/material.dart';

import '../../data/local/profile_store.dart';
import '../../design/behavior_primitives.dart';
import '../../design/behavior_states.dart';
import '../../design/makolo_theme.dart';

class ProjectionScreen extends StatelessWidget {
  const ProjectionScreen({
    super.key,
    required this.title,
    required this.stream,
    required this.emptyMessage,
    this.headerAction,
    this.showTitle = true,
  });

  final String title;
  final Stream<StoredProjection?> stream;
  final String emptyMessage;
  final Widget? headerAction;
  final bool showTitle;

  @override
  Widget build(BuildContext context) {
    final body = StreamBuilder<StoredProjection?>(
      stream: stream,
      builder: (context, snapshot) => _buildBody(
        context,
        snapshot,
        includeTitle: showTitle && headerAction == null,
      ),
    );

    if (headerAction == null) return body;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(
            MakoloSpacing.lg,
            MakoloSpacing.md,
            MakoloSpacing.sm,
            0,
          ),
          child: Row(
            children: [
              Expanded(
                child: Text(
                  title,
                  style: Theme.of(context).textTheme.headlineSmall,
                ),
              ),
              headerAction!,
            ],
          ),
        ),
        Expanded(child: body),
      ],
    );
  }

  Widget _buildBody(
    BuildContext context,
    AsyncSnapshot<StoredProjection?> snapshot, {
    required bool includeTitle,
  }) {
    if (!snapshot.hasData &&
        snapshot.connectionState == ConnectionState.waiting) {
      return const MakoloSkeleton(lines: 5);
    }
    final projection = snapshot.data;
    if (projection == null) {
      return const MakoloEmptyState(
        title: 'Pas encore disponible sur cet appareil',
        body: 'Une première connexion est nécessaire pour rendre ce contenu disponible ici.',
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
        if (includeTitle) ...[
          Text(title, style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: MakoloSpacing.sm),
        ],
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
          MakoloEmptyState(title: emptyMessage),
      ],
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

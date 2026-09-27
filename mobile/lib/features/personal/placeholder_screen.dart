import 'package:flutter/material.dart';

import '../../design/behavior_states.dart';
import '../../design/makolo_theme.dart';

class PlaceholderScreen extends StatelessWidget {
  const PlaceholderScreen({
    super.key,
    required this.title,
    required this.message,
    this.showTitle = true,
  });

  final String title;
  final String message;
  final bool showTitle;

  @override
  Widget build(BuildContext context) => ListView(
    padding: const EdgeInsets.all(MakoloSpacing.lg),
    children: [
      if (showTitle) ...[
        Text(title, style: Theme.of(context).textTheme.headlineSmall),
        const SizedBox(height: MakoloSpacing.lg),
      ],
      MakoloEmptyState(title: message),
    ],
  );
}

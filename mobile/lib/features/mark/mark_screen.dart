import 'package:flutter/material.dart';

import '../../app/providers.dart';
import '../../design/makolo_mark.dart';
import '../../design/makolo_theme.dart';
import '../../navigation/avatar_sheet.dart';
import '../../navigation/shell_header.dart';

class MarkScreen extends StatelessWidget {
  const MarkScreen({super.key, required this.runtime});

  final AppRuntime runtime;

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: MakoloPrimaryHeader(
      kind: MakoloHeaderKind.mark,
      onAvatar: () => showMakoloAvatarSheet(context, runtime: runtime),
    ),
    body: SafeArea(
      top: false,
      child: ListView(
        padding: const EdgeInsets.all(MakoloSpacing.lg),
        children: [
          const Center(child: MakoloMark(size: 64)),
          const SizedBox(height: MakoloSpacing.lg),
          Text(
            'Qu’est-ce que vous avez en tête ?',
            style: Theme.of(context).textTheme.headlineSmall,
          ),
          const SizedBox(height: MakoloSpacing.md),
          const Text(
            'Cette entrée sera disponible ici lorsqu’elle pourra vous aider à avancer.',
          ),
        ],
      ),
    ),
  );
}

import 'package:flutter/material.dart';

import '../../design/makolo_mark.dart';
import '../../design/makolo_theme.dart';

class MarkScreen extends StatelessWidget {
  const MarkScreen({super.key});

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Makolo')),
        body: ListView(
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
              'A1 prépare cette porte d’entrée. L’intake complet et son orchestration appartiennent à A2.',
            ),
          ],
        ),
      );
}
